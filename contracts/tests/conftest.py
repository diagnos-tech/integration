"""🇺🇸 Consumer-side Pact harness: the real SDK against the Pact mock server (Rust `pact_ffi`).

Each test builds its own `Pact`, declares the interactions it needs, points
the SDK's real `VaultTransport` at the mock server and exercises SDK code —
never hand-written HTTP. When the `with pact.serve()` block closes, the Rust
mock server fails the test on any request the SDK sent that no interaction
describes, and on any interaction the SDK never exercised.

Passing tests append their interactions to `contracts/.pact-raw/`. When the
whole suite passes, the raw file is normalized (sorted, tool versions
dropped) and written to `contracts/diagnos-sdk-diagnos-vault.json` — the file
the vault verifies. A partial run (`-k`, a single file, a failure) never
touches it, so the committed contract is always the full, passing one.
`--contract-check` compares instead of writing: CI uses it to fail when a
change to the SDK's HTTP behaviour was not committed along with its contract.

🇧🇷 Harness Pact do lado do consumidor: o SDK de verdade contra o mock server do Pact (`pact_ffi`, em Rust).

Cada teste monta o próprio `Pact`, declara as interações de que precisa,
aponta o `VaultTransport` real do SDK para o mock server e exercita código do
SDK — nunca HTTP escrito à mão. Quando o bloco `with pact.serve()` fecha, o
mock server em Rust reprova o teste por qualquer requisição que o SDK mandou
e nenhuma interação descreve, e por qualquer interação que o SDK nunca
exercitou.

Testes que passam acrescentam suas interações em `contracts/.pact-raw/`.
Quando a suíte inteira passa, o arquivo cru é normalizado (ordenado, versões
de ferramenta removidas) e gravado em `contracts/diagnos-sdk-diagnos-vault.json`
— o arquivo que o cofre verifica. Uma rodada parcial (`-k`, um arquivo só,
uma falha) nunca toca nele, então o contrato commitado é sempre o completo e
aprovado. `--contract-check` compara em vez de gravar: a CI usa isso para
falhar quando uma mudança no comportamento HTTP do SDK não foi commitada
junto com o contrato.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from diagnos.crypto.secure import SecretBox
from diagnos.session.keyring import SessionKeys
from diagnos.transport.config import Settings
from diagnos.transport.http import VaultTransport
from pact import Pact

from _wire import API_TOKEN, CONSUMER, PROVIDER, TOKEN, session_keys

CONTRACTS_DIR = Path(__file__).resolve().parents[1]
CONTRACT_FILE = CONTRACTS_DIR / f"{CONSUMER}-{PROVIDER}.json"
RAW_DIR = CONTRACTS_DIR / ".pact-raw"

_passed_all = pytest.StashKey[bool]()
_reports = pytest.StashKey[dict[str, pytest.TestReport]]()


def pytest_addoption(parser: pytest.Parser) -> None:
    """🇺🇸 `--contract-check`: compare against the committed contract instead of rewriting it.

    🇧🇷 `--contract-check`: compara com o contrato commitado em vez de reescrevê-lo.
    """
    parser.addoption(
        "--contract-check",
        action="store_true",
        help="fail if the generated contract differs from the committed one (CI) · "
        "falha se o contrato gerado diferir do commitado (CI)",
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    """🇺🇸 Starts every run from an empty raw directory — pact_ffi merges into, never replaces, an existing file.

    🇧🇷 Começa toda rodada de um diretório cru vazio — o pact_ffi mescla num arquivo existente, nunca o substitui.
    """
    shutil.rmtree(RAW_DIR, ignore_errors=True)
    session.stash[_passed_all] = True


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Generator[None, Any, Any]:
    """🇺🇸 Remembers each phase's outcome on the item, so the `pact` fixture only persists passing interactions.

    🇧🇷 Guarda o resultado de cada fase no item, para a fixture `pact` só persistir interações aprovadas.
    """
    report = yield
    item.stash.setdefault(_reports, {})[report.when] = report
    if report.failed:
        item.session.stash[_passed_all] = False
    return report


@pytest.fixture
def pact(request: pytest.FixtureRequest) -> Iterator[Pact]:
    """🇺🇸 A fresh V4 `Pact` for one test; its interactions are kept only if the test passed.

    🇧🇷 Um `Pact` V4 novo para um teste; suas interações só são mantidas se o teste passou.
    """
    contract = Pact(CONSUMER, PROVIDER).with_specification("V4")
    yield contract
    call = request.node.stash.get(_reports, {}).get("call")
    if call is not None and call.passed:
        contract.write_file(RAW_DIR, overwrite=False)


def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """🇺🇸 Makes the contract a pure function of the interactions: stable order, no tool versions.

    `metadata.pactRust` records which pact_ffi build wrote the file; it says
    nothing about the SDK and would turn every dependency bump into a
    contract diff. Interactions are sorted so test order never matters.

    🇧🇷 Torna o contrato uma função pura das interações: ordem estável, sem versões de ferramenta.

    `metadata.pactRust` registra qual build do pact_ffi gravou o arquivo; não
    diz nada sobre o SDK e transformaria toda atualização de dependência num
    diff de contrato. As interações são ordenadas para a ordem dos testes
    nunca importar.
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
    """🇺🇸 The exact bytes committed: sorted keys, two-space indent, trailing newline.

    🇧🇷 Os bytes exatos commitados: chaves ordenadas, indentação de dois espaços, quebra de linha final.
    """
    return json.dumps(contract, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _is_partial_run(session: pytest.Session) -> bool:
    """🇺🇸 True when only some contract tests ran, so the result must not replace the committed contract.

    🇧🇷 Verdadeiro quando só parte dos testes de contrato rodou, então o resultado não pode substituir o commitado.
    """
    option = session.config.option
    narrowed_by_path = any("::" in arg or not Path(arg).is_dir() for arg in session.config.args)
    return bool(option.keyword or option.markexpr or option.lf or narrowed_by_path)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """🇺🇸 Writes (or, with `--contract-check`, compares) the normalized contract after a full, green run.

    🇧🇷 Grava (ou, com `--contract-check`, compara) o contrato normalizado depois de uma rodada completa e verde.
    """
    if exitstatus != 0 or not session.stash.get(_passed_all, False) or session.testscollected == 0:
        return
    raw_file = RAW_DIR / f"{CONSUMER}-{PROVIDER}.json"
    if not raw_file.exists():
        return
    if _is_partial_run(session):
        print(f"\npartial run · rodada parcial: {CONTRACT_FILE.name} left untouched · não foi alterado")
        return
    rendered = render(normalize(json.loads(raw_file.read_text(encoding="utf-8"))))
    if session.config.getoption("--contract-check"):
        committed = CONTRACT_FILE.read_text(encoding="utf-8") if CONTRACT_FILE.exists() else ""
        if committed != rendered:
            print(
                f"\n✖ {CONTRACT_FILE.relative_to(CONTRACTS_DIR.parent)} is out of date · está desatualizado.\n"
                "  The SDK's HTTP behaviour changed without its contract · "
                "o comportamento HTTP do SDK mudou sem o contrato.\n"
                "  Fix · Correção: make contract && git add contracts/"
            )
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        return
    CONTRACT_FILE.write_text(rendered, encoding="utf-8")


def _no_storage(request: httpx.Request) -> httpx.Response:
    """🇺🇸 Default R2 stand-in: any object-storage call is a test bug.

    🇧🇷 Substituto padrão do R2: qualquer chamada ao armazenamento é bug do teste.
    """
    raise AssertionError(f"unexpected storage call · chamada inesperada ao storage: {request.method} {request.url}")


def make_transport(
    url: str,
    *,
    signed: bool = True,
    on_seed: Callable[[SecretBox], None] | None = None,
    storage: Callable[[httpx.Request], httpx.Response] = _no_storage,
) -> VaultTransport:
    """🇺🇸 The SDK's real `VaultTransport`, pointed at the mock server, with the contract's session (if `signed`).

    Only the R2 side is stubbed: presigned object-storage URLs are not the
    vault's API, so they are not part of this contract.

    🇧🇷 O `VaultTransport` real do SDK, apontado para o mock server, com a sessão do contrato (se `signed`).

    Só o lado do R2 é substituído: URLs pré-assinadas de armazenamento de
    objetos não são a API do cofre, então não fazem parte deste contrato.
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
