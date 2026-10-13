"""🇺🇸 `diagnos setup api`: pull, pin the digest, verify exactly that digest, run by digest — or say NOT verified.

🇧🇷 `diagnos setup api`: baixar, fixar o digest, verificar exatamente esse, rodar por ele — ou dizer NÃO verificada.
"""

from __future__ import annotations

import json

import pytest

from diagnos._wrapper.exit_codes import EXIT_FAILED, EXIT_OK, EXIT_UNAVAILABLE
from diagnos._wrapper.output import Output
from diagnos._wrapper.setup import api, image
from diagnos._wrapper.setup.environment import Environment
from diagnos._wrapper.setup.run import Plan

from conftest import Programs

DIGEST = "sha256:" + "a" * 64
PINNED = f"{image.IMAGE}@{DIGEST}"
TOOLS = {"docker": "/usr/bin/docker", "cosign": "/usr/bin/cosign"}


@pytest.fixture
def tools(monkeypatch: pytest.MonkeyPatch, programs: Programs) -> dict[str, str]:
    """🇺🇸 Docker running, cosign 3.1.3, version 1.2.3; remove a key to take a tool away.

    🇧🇷 Docker rodando, cosign 3.1.3, versão 1.2.3; remova uma chave para tirar uma ferramenta.
    """
    found = dict(TOOLS)
    release = Environment("/venv/bin/python", "1.2.3", False, False, False, True)
    monkeypatch.setattr(Environment, "current", classmethod(lambda _cls: release))
    monkeypatch.setattr(api, "find", found.get)
    programs.answer("docker", "info", stdout="29.0.0")
    programs.answer("docker", "image", "inspect", stdout=json.dumps([PINNED, "mirror.example/x@" + DIGEST]))
    programs.answer("cosign", "version", stdout=json.dumps({"gitVersion": "v3.1.3"}))
    return found


def _run(plan: Plan | int) -> int:
    """🇺🇸 Runs every step of `plan` as `--yes` would. 🇧🇷 Roda todo passo do `plan` como o `--yes` faria."""
    assert isinstance(plan, Plan)
    for step in plan.steps:
        if (code := step.action(Output())) != EXIT_OK:
            return code
    return EXIT_OK


def test_identity_is_the_release_workflow_at_this_tag() -> None:
    """🇺🇸 One signer, one tag, GitHub's issuer. 🇧🇷 Um assinante, uma tag, o emissor do GitHub."""
    argv = image.verify_argv("cosign", PINNED, "1.2.3")
    assert argv[argv.index("--certificate-identity") + 1].endswith("/.github/workflows/release.yml@refs/tags/v1.2.3")
    assert argv[argv.index("--certificate-oidc-issuer") + 1] == image.ISSUER and argv[-1] == PINNED


def test_a_verified_image_is_run_by_its_digest(
    tools: dict[str, str], programs: Programs, capsys: pytest.CaptureFixture[str]
) -> None:
    """🇺🇸 pull → inspect → cosign verify of that digest → `docker run …@sha256`.

    🇧🇷 pull → inspect → verify do digest → run.
    """
    assert _run(api.api(Output())) == EXIT_OK
    assert programs.ran("docker", "pull", f"{image.IMAGE}:1.2.3")
    assert programs.ran("cosign", "verify") and programs.calls[-1][-1] == PINNED
    text = capsys.readouterr().out
    assert "Verified" in text and f'-v "$PWD/certs:/certs:ro" {PINNED}' in text and "--read-only" in text


def test_a_bad_signature_removes_the_image(
    tools: dict[str, str], programs: Programs, capsys: pytest.CaptureFixture[str]
) -> None:
    """🇺🇸 Nothing unverified is left to start. 🇧🇷 Nada não verificado fica para subir."""
    programs.answer("cosign", "verify", returncode=1)
    assert _run(api.api(Output())) == EXIT_FAILED
    assert programs.ran("docker", "image", "rm", f"{image.IMAGE}:1.2.3")
    assert "image removed" in capsys.readouterr().err


@pytest.mark.parametrize("cosign", [None, "v3.0.6", "garbage", ""])
def test_without_a_trustworthy_cosign_the_image_is_not_verified(
    tools: dict[str, str], programs: Programs, capsys: pytest.CaptureFixture[str], cosign: str | None
) -> None:
    """🇺🇸 Missing or older than 3.1.3: pulled, announced NOT verified, with the command to verify it.

    🇧🇷 Ausente ou anterior ao 3.1.3: baixada, anunciada NÃO verificada, com o comando que a verifica.
    """
    if cosign is None:
        del tools["cosign"]
    else:
        programs.answer("cosign", "version", stdout=json.dumps({"gitVersion": cosign}) if cosign else "not json")
    assert _run(api.api(Output())) == EXIT_OK
    captured = capsys.readouterr()
    assert "NOT verified" in captured.err and "cosign verify --certificate-identity" in captured.err
    assert not programs.ran("cosign", "verify")


@pytest.mark.parametrize(
    "recorded",
    [
        json.dumps([]),
        json.dumps([PINNED, f"{image.IMAGE}@sha256:{'b' * 64}"]),
        json.dumps([f"{image.IMAGE}@sha256:short"]),
        "not json",
    ],
)
def test_no_single_well_formed_digest_stops_the_setup(tools: dict[str, str], programs: Programs, recorded: str) -> None:
    """🇺🇸 Zero, two, malformed or unreadable: nothing is verified or printed.

    🇧🇷 Zero, dois, malformado ou ilegível: nada segue.
    """
    programs.answer("docker", "image", "inspect", stdout=recorded)
    assert _run(api.api(Output())) == EXIT_FAILED


def test_docker_missing_offers_the_pip_way(tools: dict[str, str], capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 The install page, or `diagnos[api]` without a container.

    🇧🇷 A página de instalação, ou `diagnos[api]` sem container.
    """
    del tools["docker"]
    assert api.api(Output()) == EXIT_UNAVAILABLE
    assert 'uv tool install "diagnos[api]"' in capsys.readouterr().err


def test_docker_stopped_is_unavailable(
    tools: dict[str, str], programs: Programs, capsys: pytest.CaptureFixture[str]
) -> None:
    """🇺🇸 Installed but not running. 🇧🇷 Instalado, mas parado."""
    programs.answer("docker", "info", returncode=1)
    assert api.api(Output()) == EXIT_UNAVAILABLE
    assert "not running" in capsys.readouterr().err


def test_a_development_version_has_no_image(tools: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `0.0.0+unknown` was never published. 🇧🇷 `0.0.0+unknown` nunca foi publicada."""
    dev = Environment("/venv/bin/python", "0.0.0+unknown", True, False, False, True)
    monkeypatch.setattr(Environment, "current", classmethod(lambda _cls: dev))
    assert api.api(Output()) == EXIT_FAILED


def test_cosign_version_tolerates_a_failing_cosign(programs: Programs) -> None:
    """🇺🇸 Exit status non-zero, or JSON that is not an object. 🇧🇷 Saída diferente de zero, ou JSON que não é objeto."""
    programs.answer("cosign", "version", returncode=1)
    assert image.cosign_version("/usr/bin/cosign") is None
    programs.answer("cosign", "version", stdout="[1]")
    assert image.cosign_version("/usr/bin/cosign") is None
    programs.answer("cosign", "version", stdout='{"gitVersion": 3}')
    assert image.cosign_version("/usr/bin/cosign") is None
