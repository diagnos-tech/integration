"""`Diagnos`: the one object an application constructs; everything else hangs off it.

`vault = Diagnos(); vault.patients.list()` is the whole point of this
module: every other file in this package exists to make that call correct
and safe, and this is where they compose. Nothing below does cryptography or
speaks HTTP directly. It wires together a `VaultTransport`, a
`SessionManager` (or a caller-supplied stand-in, for tests) and one lazily
built resource per kind (`patients`, `exams`, `drives`), all sharing the same
`EntropyMixer` so that the server's response seed (`docs/PROTOCOL.md §4`)
reaches every DEK and node key this process ever generates.
"""

from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING, Any

from diagnos import _client_wiring
from diagnos._client_wiring import _print_enrollment_prompt_fallback, _resolve_settings
from diagnos.crypto import EntropyMixer
from diagnos.errors import SessionExpiredError
from diagnos.resources.drives import Drives
from diagnos.resources.exams import Exams
from diagnos.resources.patients import Patients
from diagnos.session.enrollment import PromptCallback
from diagnos.session.manager import SessionManager
from diagnos.session.unseal import OpenBaoStore
from diagnos.transport.config import Settings
from diagnos.transport.http import VaultTransport
from diagnos.transport.token import ServiceAccountToken, redact_api_token

if TYPE_CHECKING:
    from diagnos.session.keyring import Keyring, SessionKeys


class Diagnos:
    """The SDK's entry point: one service account's live connection to one workspace.

    Construct it once, read documents and files through `patients`, `exams` and `drives`, and let it unlock the
    session on first use:

        with Diagnos() as vault:
            page = vault.patients.list()

    Exiting the `with` block closes the HTTP clients but does not end the session; call `lock()` for that.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        token: str | None = None,
        on_prompt: PromptCallback | None = None,
        auto_unseal: bool | None = None,
        transport: VaultTransport | None = None,
        session: SessionManager | None = None,
    ) -> None:
        """Build (or accept) every layer below `patients`, `exams` and `drives`.

        `transport` and `session` are escape hatches for tests, not something
        a real application ever passes. See `apps/sdk/tests/test_client.py`
        for the pattern (a fake `session` that never touches the network).

        Args:
            settings: The configuration, used as is. If omitted, it is read from the environment
                (`DIAGNOS_API_TOKEN` and friends); see `Settings.from_env`.
            token: A `DIAGNOS_API_TOKEN` value that replaces the one in the environment. Ignored when `settings`
                is given.
            on_prompt: Called with the enrollment prompt (approval link and code) when the session needs a person's
                approval. If omitted, the prompt is printed to the terminal.
            auto_unseal: Whether to persist and restore the unlocked session through OpenBao. If omitted, it is
                enabled exactly when `settings.openbao_addr` is set.
            transport: A prebuilt transport, for tests.
            session: A prebuilt session manager, for tests.

        Raises:
            ConfigError: If the token is missing or malformed.
        """
        self._settings = _resolve_settings(settings, token)
        self._token = ServiceAccountToken.parse(self._settings.api_token)
        self._entropy = EntropyMixer()
        self._transport = (
            transport
            if transport is not None
            else VaultTransport(
                self._settings,
                self._token,
                session_keys=self._current_session_keys,
                on_seed=self._entropy.mix,
            )
        )

        if session is not None:
            self._session = session
        else:
            auto_unseal_enabled = auto_unseal if auto_unseal is not None else self._settings.openbao_addr is not None
            store = (
                OpenBaoStore(self._settings, workspace_id=self._token.workspace_id, account_id=self._token.account_id)
                if auto_unseal_enabled
                else None
            )
            resolved_prompt = on_prompt if on_prompt is not None else _print_enrollment_prompt_fallback()
            session_kwargs: dict[str, Any] = {"store": store, "on_prompt": resolved_prompt}
            self._session = SessionManager(self._settings, self._token, self._transport, **session_kwargs)

        self._patients: Patients | None = None
        self._exams: Exams | None = None
        self._drives: Drives | None = None

    def _current_session_keys(self) -> SessionKeys | None:
        """Return the session keys, the callback `VaultTransport` polls before signing every request."""
        return self._session.session_keys()

    def _keyring_provider(self) -> Keyring:
        """Return the live `Keyring`, auto-unlocking on first use so `vault.patients.list()` just works.

        This is the one place laziness is deliberate: `unlock()` is
        documented as idempotent (`session/manager.py`), so paying for it on
        first resource access, instead of forcing every caller to remember
        an explicit `unlock()`, is what makes the "30 seconds to your first
        `list()`" README example true without a `with` block.
        """
        try:
            keyring = self._session.keyring
        except SessionExpiredError:
            keyring = None
        return keyring if keyring is not None else self._session.unlock()

    @property
    def workspace_id(self) -> str:
        """This service account's workspace, read from its token."""
        return self._token.workspace_id

    @property
    def account_id(self) -> str:
        """This service account's owning account, read from its token."""
        return self._token.account_id

    @property
    def name(self) -> str:
        """The service account's human-readable name (`slug@<workspace_id>.diagnos.health`)."""
        return self._token.name

    @property
    def key_id(self) -> str:
        """The id of the token's key pair, which is what an admin rotates or revokes."""
        return self._token.key_id

    @property
    def security_groups(self) -> list[str]:
        """The ids of every security group this session holds a DEK for; `[]` before `unlock()`."""
        try:
            keyring = self._session.keyring
        except SessionExpiredError:
            keyring = None
        return keyring.security_group_ids if keyring is not None else []

    @property
    def patients(self) -> Patients:
        """The patient records resource, built once on first access."""
        if self._patients is None:
            self._patients = _client_wiring._build_patients(
                self._transport,
                self._keyring_provider,
                self._entropy,
                workspace_id=self.workspace_id,
                time_precision=self._settings.time_precision,
            )
        return self._patients

    @property
    def exams(self) -> Exams:
        """The exam records resource, built once on first access."""
        if self._exams is None:
            self._exams = _client_wiring._build_exams(
                self._transport,
                self._keyring_provider,
                self._entropy,
                workspace_id=self.workspace_id,
                time_precision=self._settings.time_precision,
            )
        return self._exams

    @property
    def drives(self) -> Drives:
        """The drive (files and folders) resource, built once on first access."""
        if self._drives is None:
            self._drives = Drives(
                self._transport,
                self._keyring_provider,
                self._entropy,
                workspace_id=self.workspace_id,
            )
        return self._drives

    def unlock(self) -> Keyring:
        """Enroll (or restore from OpenBao) and return the live `Keyring`; idempotent.

        Returns:
            The keyring holding a DEK for every security group the session may use.

        Raises:
            EnrollmentDeniedError: If a person denied the enrollment in the web app.
            EnrollmentExpiredError: If nobody approved the enrollment within the window.
            VaultError: If the vault rejects the enrollment.
        """
        return self._session.unlock()

    def lock(self) -> None:
        """End the session, best-effort server-side, and always wipe local key material.

        Unlike `close()`, this is never called automatically; see the
        `__exit__` docstring for why.
        """
        self._session.lock()

    def close(self) -> None:
        """Close the underlying HTTP clients. This does not `lock()`; see `__exit__`."""
        self._transport.close()

    def __enter__(self) -> Diagnos:
        """Unlock the session on entry to a `with Diagnos(...) as vault:` block.

        Returns:
            This client.
        """
        self.unlock()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the HTTP clients but deliberately do not `lock()` the session.

        Exiting a `with` block means "this process is done talking to the
        vault right now", not "revoke this session forever". An
        auto-unsealing worker that restarts a minute later should restore
        the very session this process was using, not be forced to enroll
        again because closing merely freed a socket. Call `lock()` yourself
        when the intent really is to end the session.
        """
        self.close()

    def __repr__(self) -> str:
        """Render the client without the token, showing only what identifies the workspace and account."""
        return (
            f"Diagnos(workspace_id={self.workspace_id!r}, account_id={self.account_id!r}, "
            f"name={self._token.name!r}, api_token={redact_api_token(self._token.raw)!r})"
        )
