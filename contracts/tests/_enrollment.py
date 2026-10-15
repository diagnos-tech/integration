"""🇺🇸 The enrollment vocabulary both session suites share: the registry and poll paths, registration, polling.

`test_session.py` covers the enrollment and lock under the service account
credential; `test_credential_auth.py` covers the credential failures and the
deprecated `apikey-` token. Both declare the same registration, so it lives
here once.

🇧🇷 O vocabulário de enrollment que as duas suítes de sessão dividem: os paths de registro e poll, registro, poll.

`test_session.py` cobre o enrollment e o lock sob a credencial de conta de
serviço; `test_credential_auth.py` cobre as falhas de credencial e o token
`apikey-` obsoleto. As duas declaram o mesmo registro, então ele mora aqui
uma vez.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pact import Pact, match

from diagnos.session import runtime as runtime_module

from _crypto import b64url, sdk_keypair
from _identity import identity_headers
from _wire import EXTERNAL_PREFIX, WORKSPACE_ID, bearer_header, declare_clock, ok, path, workspace_state

ENROLLMENT_ID = "enr-contract"
EXPIRES_AT = 1_780_000_600
REGISTRY = f"{EXTERNAL_PREFIX}/workspaces/{WORKSPACE_ID}/session/registry"
REGISTRY_PATTERN = rf"^{EXTERNAL_PREFIX}/workspaces/[^/]+/session/registry$"
REGISTRY_EXPRESSION = f"{EXTERNAL_PREFIX}/workspaces/${{workspace_id}}/session/registry"
POLL = f"{REGISTRY}/{ENROLLMENT_ID}"
POLL_PATTERN = rf"^{EXTERNAL_PREFIX}/workspaces/[^/]+/session/registry/[^/]+$"
POLL_EXPRESSION = f"{EXTERNAL_PREFIX}/workspaces/${{workspace_id}}/session/registry/${{enrollment_id}}"


def pin_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 Pins the machine-dependent optional `runtime` fields, so the request body is the same on every machine.

    🇧🇷 Fixa os campos opcionais de `runtime` que dependem da máquina, para o corpo ser igual em toda máquina.
    """
    monkeypatch.setattr(runtime_module, "_detect_hostname", lambda: "contract-host")
    monkeypatch.setattr(runtime_module, "_detect_user", lambda: "contract")
    monkeypatch.setattr(runtime_module, "_detect_container", lambda: False)
    monkeypatch.setattr(runtime_module, "_detect_cloud", lambda: None)


LEGACY = "on a legacy apikey- token "


def register(pact: Pact, *, legacy: bool = False) -> None:
    """🇺🇸 `POST .../session/registry` — identical in every test, so pact_ffi merges it into one interaction.

    🇧🇷 `POST .../session/registry` — idêntico em todo teste, então o pact_ffi o mescla numa interação só.
    """
    keypair = sdk_keypair()
    if not legacy:
        declare_clock(pact)
    state, params = workspace_state(
        "a legacy apikey- token can enroll an SDK session" if legacy else "a service account can enroll an SDK session"
    )
    (
        pact.upon_receiving(
            f"an SDK process {LEGACY if legacy else ''}registers its hybrid public keys to request a session"
        )
        .given(state, params)
        .with_request("POST", path(REGISTRY, pattern=REGISTRY_PATTERN, expression=REGISTRY_EXPRESSION))
        .with_headers(bearer_header() if legacy else identity_headers(body=True))
        .with_body(
            {
                "public_keys": {
                    "x25519": match.regex(b64url(keypair.x25519_public), regex=r"^[A-Za-z0-9_-]{43}$"),
                    "mlkem768": match.regex(b64url(keypair.mlkem768_public), regex=r"^[A-Za-z0-9_-]{1579}$"),
                },
                "runtime": {
                    "sdk_name": "diagnos-python",
                    "sdk_version": match.str("0.2.0"),
                    "language": match.regex("python 3.12", regex=r"^python 3\.[0-9]+$"),
                    "os": match.str("linux"),
                    "arch": match.str("x86_64"),
                    "hostname": match.str("contract-host"),
                    "user": match.str("contract"),
                    "container": match.bool(False),
                },
            },
            content_type="application/json",
        )
        .will_respond_with(201)
        .with_body(
            ok(
                {
                    "enrollment_id": match.str(ENROLLMENT_ID),
                    "approval_url": match.regex(
                        f"https://app.diagnos.health/sdk/approve/{ENROLLMENT_ID}", regex=r"^https?://.+$"
                    ),
                    "code": match.regex("482915", regex=r"^[0-9]{6}$"),
                    "expires_at": match.int(EXPIRES_AT),
                    "poll_interval_seconds": match.number(2),
                }
            ),
            content_type="application/json",
        )
    )


def poll(
    pact: Pact, *, state: str, description: str, status: int, body: dict[str, object], legacy: bool = False
) -> None:
    """🇺🇸 `GET .../session/registry/{enrollment_id}` answering `body` under `state`.

    🇧🇷 `GET .../session/registry/{enrollment_id}` respondendo `body` sob `state`.
    """
    name, params = workspace_state(state, enrollment_id=ENROLLMENT_ID)
    (
        pact.upon_receiving(description)
        .given(name, params)
        .with_request("GET", path(POLL, pattern=POLL_PATTERN, expression=POLL_EXPRESSION))
        .with_headers(bearer_header() if legacy else identity_headers())
        .will_respond_with(status)
        .with_body(body, content_type="application/json")
    )


def clock(*readings: float) -> Callable[[], float]:
    """🇺🇸 A fake `now()` that returns `readings` in order, then keeps returning the last one.

    🇧🇷 Um `now()` falso que devolve `readings` em ordem e depois repete o último.
    """
    values = list(readings)

    def _now() -> float:
        return values.pop(0) if len(values) > 1 else values[0]

    return _now
