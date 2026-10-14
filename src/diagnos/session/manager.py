"""`SessionManager`: the one object that turns "I have a token" into "I have a live, usable session".

Everything else in `session/` is a building block: `enroll()` does one
round trip of the enrollment dance and `OpenBaoStore` does one KV path. This
module is where they compose into the lifecycle a caller actually wants:
try to resume silently, fall back to a human approval, remember the result
if asked to, and tear it all down cleanly on `lock()`.
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from diagnos.crypto.hybrid import HybridKeyPair
from diagnos.crypto.secure import harden_process, warn_if_unlocked
from diagnos.errors import SessionExpiredError
from diagnos.session.enrollment import EnrollmentPrompt, PromptCallback, enroll
from diagnos.session.keyring import Keyring, SessionKeys
from diagnos.session.unseal import OpenBaoStore, UnsealedState

# Same reasoning as `enrollment.py` and `unseal.py`: `diagnos.transport`
# eagerly imports `diagnos.session.keyring`, so importing any of its
# submodules at module scope here would close an import cycle. `Settings`,
# `VaultTransport` and `ServiceAccountToken` are only ever used as type
# hints; every real use below is a duck-typed call or attribute the manager
# receives already constructed.
if TYPE_CHECKING:
    from diagnos.transport.config import Settings
    from diagnos.transport.http import VaultTransport
    from diagnos.transport.token import ServiceAccountToken

logger = logging.getLogger("diagnos")

# `docs/PROTOCOL.md §5`: ends a session; signed because a session must
# already exist to lock, unlike the two enrollment routes.
_LOCK_PATH = "/api/external/v1/session/lock"


def default_prompt(prompt: EnrollmentPrompt) -> None:
    """Print the approval link and code to `stderr`.

    No color, no animation: this has to render correctly in a plain CI log
    or a piped process just as well as an interactive terminal, and the
    person approving needs to be able to read the code back accurately.
    Spacing the digits out is the only concession to legibility.

    Args:
        prompt: The enrollment prompt to show.
    """
    spaced_code = " ".join(prompt.code)
    lines = [
        "",
        "diagnos SDK — enrollment approval needed",
        "",
        "Open this link to approve:",
        f"  {prompt.approval_url}",
        "",
        "Code to type:",
        f"  {spaced_code}",
        "",
        f"Expires at (unix seconds): {prompt.expires_at}",
        "",
    ]
    print("\n".join(lines), file=sys.stderr)


class SessionManager:
    """Orchestrates unlock (restore or enroll), the live `Keyring`, and `lock()`."""

    def __init__(
        self,
        settings: Settings,
        token: ServiceAccountToken,
        transport: VaultTransport,
        *,
        on_prompt: PromptCallback = default_prompt,
        store: OpenBaoStore | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.time,
    ) -> None:
        """Create a manager that has not unlocked anything yet.

        Args:
            settings: The SDK configuration.
            token: The parsed service-account token.
            transport: The HTTP transport used for enrollment and `lock()`.
            on_prompt: Called with the approval link and code when a person must approve an enrollment.
            store: Optional OpenBao store (`docs/PROTOCOL.md §11`). Without one, every `unlock()` enrolls fresh.
            sleep: The sleep function used between enrollment polls; replaced in tests.
            now: The clock, in Unix seconds; replaced in tests.
        """
        self._settings = settings
        self._token = token
        self._transport = transport
        self._on_prompt = on_prompt
        self._store = store
        self._sleep = sleep
        self._now = now
        # Public because nothing about *which* identity is in use is
        # secret; the bytes inside it are (`HybridKeyPair.zeroize()` covers
        # those). `keyring` is a validated property instead (see below).
        self.keypair: HybridKeyPair | None = None
        self._keyring: Keyring | None = None
        self._hardened = False

    @property
    def keyring(self) -> Keyring:
        """The live `Keyring`.

        Checking `is_valid` here, not just "is it set", is what stops a
        caller from silently signing requests with a session that is about
        to be rejected by the vault anyway. It is better to fail on the SDK
        side with a clear exception than to let `VaultTransport` turn it into
        a 401 two layers down.

        Raises:
            SessionExpiredError: If there is no session or it has lapsed.
        """
        if self._keyring is None or not self._keyring.session.is_valid(now=int(self._now())):
            raise SessionExpiredError(
                "no live session; call unlock() (which enrolls, or restores from OpenBao) first."
            )
        return self._keyring

    def session_keys(self) -> SessionKeys | None:
        """Return the session keys, as the provider `VaultTransport(session_keys=...)` expects.

        This is deliberately the mirror image of the `keyring` property. A
        transport asks for keys on every signed request and has its own
        recovery path for "none available" (`SessionExpiredError`, raised by
        `VaultTransport._send_once`), so this method hands back a plain `None`
        instead of raising a second exception on top of that one.

        Returns:
            The live session keys, or `None` when there is no usable session. It never raises.
        """
        if self._keyring is None:
            return None
        session = self._keyring.session
        if not session.is_valid(now=int(self._now())):
            return None
        return session

    def _harden_once(self) -> None:
        """Harden the process, right before the first secret exists, once per manager.

        This is done here and not at import time: importing a library must
        never change process-wide state, but *unlocking* is the explicit
        moment the caller decides this process will hold clinical keys. The
        report (what took effect on this platform) goes to the debug log.
        """
        if self._hardened or not self._settings.harden_process:
            return
        self._hardened = True
        logger.debug("process hardening: %s", harden_process())

    def unlock(self) -> Keyring:
        """Restore from `store` if it holds a still-valid session; otherwise enroll and, if there is a store, save.

        Returns:
            The live keyring.

        Raises:
            EnrollmentDeniedError: If a person denied the enrollment.
            EnrollmentExpiredError: If nobody approved the enrollment in time.
        """
        self._harden_once()
        if self._store is not None:
            restored = self._store.restore(now=int(self._now()))
            if restored is not None and restored.keyring.session.is_valid(now=int(self._now())):
                self.keypair = restored.keypair
                self._keyring = restored.keyring
                warn_if_unlocked()
                return self.keyring

        keypair = HybridKeyPair.generate()
        keyring = enroll(
            self._transport,
            self._token,
            keypair,
            on_prompt=self._on_prompt,
            sleep=self._sleep,
            now=self._now,
        )
        self.keypair = keypair
        self._keyring = keyring
        if self._store is not None:
            self._store.save(UnsealedState(keypair=keypair, keyring=keyring))
        warn_if_unlocked()
        return self.keyring

    def lock(self) -> None:
        """End the session best-effort on the server, then tear it down locally without condition.

        The `session/lock` call is best-effort on purpose: a network error
        or an already-expired session (401) still means that the caller's
        intent, "I am done with this session", has to succeed locally.
        Zeroizing happens regardless of whether the server call did.
        """
        try:
            self._transport.post(_LOCK_PATH, signed=True)
        except Exception:
            logger.debug("session/lock failed; ending the session locally anyway", exc_info=True)

        if self._store is not None:
            self._store.clear()
        if self._keyring is not None:
            self._keyring.zeroize()
        if self.keypair is not None:
            self.keypair.zeroize()
        self._keyring = None
        self.keypair = None
