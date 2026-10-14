"""Optional auto-unseal through OpenBao: restart without a human by restoring the unlocked state.

`docs/PROTOCOL.md §11`: enrollment is a human clicking "approve" on a web
page, which is exactly the step a long-running or auto-restarting process
(a worker, a cron job) cannot repeat on every boot. Saving the unlocked
state to OpenBao trades that human step for a different, deliberate one:
the group DEKs, normally alive only in this process's locked memory, now
also sit in OpenBao's encrypted KV storage, so whoever can read
`OPENBAO_ADDR`'s `<prefix>/<workspace_id>/<account_id>` path can read the
workspace exactly as this SDK process can. Scoping the OpenBao token to
that one path is what keeps this an intentional trade rather than a silent
widening of who can decrypt.

This is also the one place secrets leave the enclave as clear text: to be
written into a JSON body, each `SecretBox` is `reveal()`ed into a
`bytearray` that is zeroed as soon as the request is built. The base64 text
inside that JSON, and the `bytes` that `base64` produces on restore, are
immutable Python objects that live until the collector frees them. That
exposure window, measured in milliseconds, is accepted knowingly and is the
reason this path is opt-in.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.hybrid import HybridKeyPair
from diagnos.crypto.secure import SecretBox, secret_from_b64url, zero
from diagnos.errors import ConfigError
from diagnos.session.keyring import Keyring, SessionKeys

# Same reasoning as `enrollment.py`: `diagnos.transport` eagerly imports
# `diagnos.session.keyring`, so a module-level import of any of its
# submodules here would close an import cycle. `Settings` is only ever used
# as a type hint — its fields are read through plain attribute access.
if TYPE_CHECKING:
    from diagnos.transport.config import Settings

# `docs/PROTOCOL.md §11`'s `"v": 1`, bumped only if the saved shape ever
# changes incompatibly. A mismatch means "not this SDK version's format" and
# is treated the same as "nothing saved" rather than a crash.
_STATE_VERSION = 1

# Mirrors `SessionKeys.is_valid`'s own margin (`session/keyring.py`): a
# restore that leaves less than a minute before `session_expires_at` is not
# worth handing back, because the caller would immediately have to re-enroll
# anyway, so `restore` reports "nothing usable" up front.
_MIN_REMAINING_VALIDITY_SECONDS = 60


@dataclass(frozen=True)
class UnsealedState:
    """Everything needed to resume: the key pair and the keyring.

    Attributes:
        keypair: The SDK identity that opened the enrollment.
        keyring: The session keys and group DEKs the enrollment granted.
    """

    keypair: HybridKeyPair
    keyring: Keyring


class _Exporter:
    """Reveal boxes for one `save()` and zero every revealed buffer afterwards, success or not."""

    def __init__(self) -> None:
        """Start with nothing revealed."""
        self._revealed: list[bytearray] = []

    def b64url(self, box: SecretBox) -> str:
        """`reveal()` the box and encode it; the buffer is remembered for `close()`."""
        buffer = box.reveal()
        self._revealed.append(buffer)
        return b64url_encode(buffer)

    def close(self) -> None:
        """Zero every revealed buffer."""
        for buffer in self._revealed:
            zero(buffer)
        self._revealed.clear()


class OpenBaoStore:
    """A KV v2 store at `<prefix>/<workspace_id>/<account_id>` that persists the unlocked state (PROTOCOL §11)."""

    def __init__(self, settings: Settings, *, workspace_id: str, account_id: str, client: Any | None = None) -> None:
        """Create the store, importing the optional `hvac` client lazily.

        `hvac` is optional (`pip install "diagnos[openbao]"`), so it is
        imported here and not at module scope. Importing lazily means the
        SDK's core import path never requires `hvac` to be installed. Only a
        process that actually configures `OPENBAO_ADDR` and `OPENBAO_TOKEN`
        and constructs this class pays that cost, and it pays with a clear
        message instead of a bare `ModuleNotFoundError` several frames deep.

        Args:
            settings: The SDK configuration holding the OpenBao address, token, namespace, mount and path prefix.
            workspace_id: The workspace the state belongs to.
            account_id: The service account the state belongs to.
            client: A prebuilt `hvac` client, for tests.

        Raises:
            ConfigError: If the `hvac` package is not installed.
        """
        try:
            import hvac  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ConfigError(
                "OpenBao auto-unseal needs the optional 'hvac' dependency; install it with "
                'pip install "diagnos[openbao]".'
            ) from exc

        # Kept as an instance attribute (not re-imported per call) so
        # `restore()` can catch "no secret at this path" without needing its
        # own module-level `import hvac`. The whole point of the try/except
        # above is that this is the *one* place that import happens.
        self._invalid_path_exc: type[BaseException] = hvac.exceptions.InvalidPath
        self._client: Any = None
        if client is not None:
            self._client = client
        else:
            self._client = hvac.Client(
                url=settings.openbao_addr,
                token=settings.openbao_token,
                namespace=settings.openbao_namespace,
            )
        self._mount_point = settings.openbao_mount
        self._path = f"{settings.openbao_path_prefix}/{workspace_id}/{account_id}"

    def restore(self, *, now: int | None = None) -> UnsealedState | None:
        """Return the saved state if it is still valid, else `None`.

        Every "not usable" outcome (nothing saved, a version this SDK does
        not recognize, a session too close to `session_expires_at`) returns
        `None` rather than raising, because the caller's response to all of
        them is identical: enroll again.

        Args:
            now: The current time in Unix seconds; defaults to the system clock.

        Returns:
            The restored key pair and keyring, or `None` when nothing usable is saved.
        """
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                path=self._path,
                mount_point=self._mount_point,
                raise_on_deleted_version=True,
            )
        except self._invalid_path_exc:
            return None

        data = response["data"]["data"]
        if data.get("v") != _STATE_VERSION:
            return None

        current = now if now is not None else int(time.time())
        session_expires_at = int(data["session_expires_at"])
        if session_expires_at - current <= _MIN_REMAINING_VALIDITY_SECONDS:
            return None

        keypair = HybridKeyPair.from_secrets(
            secret_from_b64url(data["x25519_secret"]),
            secret_from_b64url(data["mlkem768_secret"]),
        )
        session = SessionKeys(
            session_id=data["session_id"],
            sign_key=secret_from_b64url(data["sign_key"]),
            enc_key=secret_from_b64url(data["enc_key"]),
            expires_at=session_expires_at,
        )
        group_keys = {
            security_group_id: secret_from_b64url(wrapped)
            for security_group_id, wrapped in data.get("group_keys", {}).items()
        }
        keyring = Keyring(enrollment_id=data["enrollment_id"], session=session, group_keys=group_keys)
        return UnsealedState(keypair=keypair, keyring=keyring)

    def save(self, state: UnsealedState) -> None:
        """Persist the unlocked state in the exact JSON shape of `docs/PROTOCOL.md §11`.

        Args:
            state: The key pair and keyring to save.
        """
        keypair = state.keypair
        session = state.keyring.session
        exporter = _Exporter()
        try:
            secret = {
                "v": _STATE_VERSION,
                "enrollment_id": state.keyring.enrollment_id,
                "x25519_secret": exporter.b64url(keypair.x25519_secret()),
                "mlkem768_secret": exporter.b64url(keypair.mlkem768_secret()),
                "session_id": session.session_id,
                "sign_key": exporter.b64url(session.sign_key),
                "enc_key": exporter.b64url(session.enc_key),
                "session_expires_at": session.expires_at,
                "group_keys": {
                    security_group_id: exporter.b64url(dek)
                    for security_group_id, dek in state.keyring.group_keys.items()
                },
                "saved_at": int(time.time()),
            }
            self._client.secrets.kv.v2.create_or_update_secret(
                path=self._path,
                secret=secret,
                mount_point=self._mount_point,
            )
        finally:
            exporter.close()

    def clear(self) -> None:
        """Delete the saved state and all its versions, as part of a session lock."""
        self._client.secrets.kv.v2.delete_metadata_and_all_versions(
            path=self._path,
            mount_point=self._mount_point,
        )
