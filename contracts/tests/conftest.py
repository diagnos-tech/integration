"""Consumer-side Pact harness: the real SDK against the Pact mock server (Rust `pact_ffi`).

Each test builds its own `Pact`, declares the interactions it needs, points the SDK's real `VaultTransport` at the mock
server and exercises SDK code, never hand-written HTTP. When the `with pact.serve()` block closes, the Rust mock server
fails the test on any request the SDK sent that no interaction describes, and on any interaction the SDK never
exercised.

Passing tests append their interactions to `contracts/.pact-raw/`. When the whole suite passes, the raw file is
normalized (sorted, tool versions dropped) and written to `contracts/diagnos-sdk-diagnos-vault.json`, the file the
vault verifies. A partial run (`-k`, a single file, a failure) never touches it, so the committed contract is always the
full, passing one. `--contract-check` compares instead of writing: CI uses it to fail when a change to the SDK's HTTP
behaviour was not committed along with its contract.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from pact import Pact

from diagnos.crypto.secure import SecretBox
from diagnos.session.keyring import SessionKeys
from diagnos.transport.config import Settings
from diagnos.transport.http import VaultTransport

from _wire import API_TOKEN, CONSUMER, PROVIDER, TOKEN, session_keys

CONTRACTS_DIR = Path(__file__).resolve().parents[1]
CONTRACT_FILE = CONTRACTS_DIR / f"{CONSUMER}-{PROVIDER}.json"
RAW_DIR = CONTRACTS_DIR / ".pact-raw"

_passed_all = pytest.StashKey[bool]()
_reports = pytest.StashKey[dict[str, pytest.TestReport]]()


def pytest_addoption(parser: pytest.Parser) -> None:
    """`--contract-check`: compare against the committed contract instead of rewriting it."""
    parser.addoption(
        "--contract-check",
        action="store_true",
        help="fail if the generated contract differs from the committed one (CI)",
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    """Starts every run from an empty raw directory — pact_ffi merges into, never replaces, an existing file."""
    shutil.rmtree(RAW_DIR, ignore_errors=True)
    session.stash[_passed_all] = True


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Generator[None, Any, Any]:
    """Remembers each phase's outcome on the item, so the `pact` fixture only persists passing interactions."""
    report = yield
    item.stash.setdefault(_reports, {})[report.when] = report
    if report.failed:
        item.session.stash[_passed_all] = False
    return report


@pytest.fixture
def pact(request: pytest.FixtureRequest) -> Iterator[Pact]:
    """A fresh V4 `Pact` for one test; its interactions are kept only if the test passed."""
    contract = Pact(CONSUMER, PROVIDER).with_specification("V4")
    yield contract
    call = request.node.stash.get(_reports, {}).get("call")
    if call is not None and call.passed:
        contract.write_file(RAW_DIR, overwrite=False)


def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Makes the contract a pure function of the interactions: stable order, no tool versions.

    `metadata.pactRust` records which pact_ffi build wrote the file. It says nothing about the SDK and would turn every
    dependency bump into a contract diff. Interactions are sorted so that test order never matters.
    """
    interactions = sorted(
        raw["interactions"],
        key=lambda interaction: (interaction["description"], json.dumps(interaction.get("providerStates", []))),
    )
    return {
        "consumer": raw["consumer"],
        "provider": raw["provider"],
        "interactions": interactions,
        "metadata": {"pactSpecification": raw["metadata"]["pactSpecification"]},
    }


def render(contract: dict[str, Any]) -> str:
    """The exact bytes committed: sorted keys, two-space indent, trailing newline."""
    return json.dumps(contract, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _is_partial_run(session: pytest.Session) -> bool:
    """True when only some contract tests ran, so the result must not replace the committed contract."""
    option = session.config.option
    narrowed_by_path = any("::" in arg or not Path(arg).is_dir() for arg in session.config.args)
    return bool(option.keyword or option.markexpr or getattr(option, "lf", False) or narrowed_by_path)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Writes (or, with `--contract-check`, compares) the normalized contract after a full, green run."""
    if exitstatus != 0 or not session.stash.get(_passed_all, False) or session.testscollected == 0:
        return
    raw_file = RAW_DIR / f"{CONSUMER}-{PROVIDER}.json"
    if not raw_file.exists():
        return
    if _is_partial_run(session):
        print(f"\npartial run: {CONTRACT_FILE.name} left untouched")
        return
    rendered = render(normalize(json.loads(raw_file.read_text(encoding="utf-8"))))
    if session.config.getoption("--contract-check"):
        committed = CONTRACT_FILE.read_text(encoding="utf-8") if CONTRACT_FILE.exists() else ""
        if committed != rendered:
            print(
                f"\n✖ {CONTRACT_FILE.relative_to(CONTRACTS_DIR.parent)} is out of date.\n"
                "  The SDK's HTTP behaviour changed without its contract.\n"
                "  Fix: make contract && git add contracts/"
            )
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        return
    CONTRACT_FILE.write_text(rendered, encoding="utf-8")


def _no_storage(request: httpx.Request) -> httpx.Response:
    """Default R2 stand-in: any object-storage call is a test bug."""
    raise AssertionError(f"unexpected storage call: {request.method} {request.url}")


def make_transport(
    url: str,
    *,
    signed: bool = True,
    on_seed: Callable[[SecretBox], None] | None = None,
    storage: Callable[[httpx.Request], httpx.Response] = _no_storage,
) -> VaultTransport:
    """The SDK's real `VaultTransport`, pointed at the mock server, with the contract's session (if `signed`).

    Only the R2 side is stubbed: presigned object-storage URLs are not the vault's API, so they are not part of this
    contract.
    """
    keys: SessionKeys | None = session_keys() if signed else None
    settings = Settings(api_token=API_TOKEN, vault_url=url)
    return VaultTransport(
        settings,
        TOKEN,
        session_keys=lambda: keys,
        on_seed=on_seed,
        client=httpx.Client(base_url=url, timeout=10.0),
        storage_client=httpx.Client(transport=httpx.MockTransport(storage)),
        sleep=lambda seconds: None,
    )
