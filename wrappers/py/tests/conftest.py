"""🇺🇸 Shared fixtures for the base's tests: fake package metadata and a recorder in place of `subprocess.run`.

The base decides everything from two sources — the installed metadata of
`diagnos` (`importlib.metadata`) and the programs it runs (`subprocess`) —
so faking exactly those two lets every branch run here, on any machine,
without installing or launching anything.

🇧🇷 Fixtures compartilhadas dos testes da base: metadados de pacote falsos e um gravador no lugar do `subprocess.run`.

A base decide tudo a partir de duas fontes — os metadados instalados do
`diagnos` (`importlib.metadata`) e os programas que ela roda (`subprocess`)
— então falsificar exatamente essas duas deixa todo ramo rodar aqui, em
qualquer máquina, sem instalar nem lançar nada.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError
from typing import Any

import pytest

from diagnos import _extras

REQUIRES = [
    'httpx>=0.28; extra == "sdk"',
    'pydantic>=2.9; extra == "sdk"',
    'diagnos[sdk]; extra == "openbao"',
    'hvac>=2.3; extra == "openbao"',
    'diagnos[sdk]; extra == "cli"',
    'typer>=0.15; extra == "cli"',
    'rich>=13.9; extra == "cli"',
    'diagnos[sdk,openbao]; extra == "api"',
    'fastapi>=0.115; extra == "api"',
    'diagnos[api]; extra == "dev-certs"',
    'cryptography>=43; extra == "dev-certs"',
]
EXTRAS = ["api", "cli", "dev-certs", "openbao", "sdk"]


@dataclass(frozen=True)
class FakeMetadata:
    """🇺🇸 The slice of `PackageMetadata` the base reads. 🇧🇷 A fatia de `PackageMetadata` que a base lê."""

    extras: list[str]

    def get_all(self, name: str) -> list[str] | None:
        """🇺🇸 `Provides-Extra` values. 🇧🇷 Os valores de `Provides-Extra`."""
        return self.extras if name == "Provides-Extra" else None


@dataclass
class FakeDistribution:
    """🇺🇸 A distribution as `importlib.metadata.distribution` returns it.

    🇧🇷 Uma distribuição como a função a devolve.
    """

    requires: list[str] | None = None
    extras: list[str] = field(default_factory=list)
    direct_url: str | None = None

    @property
    def metadata(self) -> FakeMetadata:
        """🇺🇸 Its metadata. 🇧🇷 Os metadados dela."""
        return FakeMetadata(self.extras)

    def read_text(self, filename: str) -> str | None:
        """🇺🇸 Only `direct_url.json` is ever read. 🇧🇷 Só o `direct_url.json` é lido."""
        return self.direct_url if filename == "direct_url.json" else None


@dataclass
class Packages:
    """🇺🇸 What is "installed": `diagnos` itself and the names of every other distribution present.

    🇧🇷 O que está "instalado": o próprio `diagnos` e os nomes de toda outra distribuição presente.
    """

    diagnos: FakeDistribution | None = field(default_factory=lambda: FakeDistribution(list(REQUIRES), list(EXTRAS)))
    present: set[str] = field(default_factory=set)

    def distribution(self, name: str) -> FakeDistribution:
        """🇺🇸 Stand-in for `importlib.metadata.distribution`. 🇧🇷 Substituto de `importlib.metadata.distribution`."""
        if name == "diagnos" and self.diagnos is not None:
            return self.diagnos
        if name in self.present:
            return FakeDistribution()
        raise PackageNotFoundError(name)


@pytest.fixture
def packages(monkeypatch: pytest.MonkeyPatch) -> Iterator[Packages]:
    """🇺🇸 Fake metadata for `diagnos._extras` and `setup.environment`, starting with no extra installed.

    🇧🇷 Metadados falsos para `diagnos._extras` e `setup.environment`, começando sem nenhum extra instalado.
    """
    fake = Packages()
    monkeypatch.setattr(_extras, "distribution", fake.distribution)
    monkeypatch.setattr("diagnos._wrapper.setup.environment.distribution", fake.distribution)
    _extras._declared.cache_clear()
    yield fake
    _extras._declared.cache_clear()


@dataclass
class Programs:
    """🇺🇸 A recorder for `subprocess.run`: every argv, and a scripted result per program and subcommand.

    🇧🇷 Um gravador do `subprocess.run`: todo argv, e um resultado roteirizado por programa e subcomando.
    """

    calls: list[list[str]] = field(default_factory=list)
    results: dict[tuple[str, ...], Callable[[], subprocess.CompletedProcess[str]]] = field(default_factory=dict)

    def answer(self, *prefix: str, returncode: int = 0, stdout: str = "") -> None:
        """🇺🇸 Scripts the result of argv starting with `prefix` (program by its file name).

        🇧🇷 Roteiriza o resultado do argv que começa com `prefix` (programa pelo nome do arquivo).
        """
        self.results[prefix] = lambda: subprocess.CompletedProcess(list(prefix), returncode, stdout, "")

    def fail(self, *prefix: str, error: BaseException) -> None:
        """🇺🇸 Makes argv starting with `prefix` raise `error`. 🇧🇷 Faz o argv que começa com `prefix` lançar `error`."""

        def raising() -> subprocess.CompletedProcess[str]:
            raise error

        self.results[prefix] = raising

    def run(self, argv: Sequence[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        """🇺🇸 Stand-in for `subprocess.run`; unscripted programs succeed silently.

        🇧🇷 Substituto do `subprocess.run`; programas sem roteiro dão certo em silêncio.
        """
        words = [str(argv[0]).rsplit("/", 1)[-1], *map(str, argv[1:])]
        self.calls.append(list(map(str, argv)))
        for length in range(len(words), 0, -1):
            if (scripted := self.results.get(tuple(words[:length]))) is not None:
                return scripted()
        return subprocess.CompletedProcess(list(argv), 0, "", "")

    def ran(self, *words: str) -> bool:
        """🇺🇸 Whether some call's argv (program by file name) starts with `words`.

        🇧🇷 Se o argv de alguma chamada (programa pelo nome do arquivo) começa com `words`.
        """
        return any([call[0].rsplit("/", 1)[-1], *call[1:]][: len(words)] == list(words) for call in self.calls)


@pytest.fixture
def programs(monkeypatch: pytest.MonkeyPatch) -> Programs:
    """🇺🇸 `subprocess.run` replaced everywhere by a recorder.

    🇧🇷 O `subprocess.run` trocado em todo lugar por um gravador.
    """
    fake = Programs()
    monkeypatch.setattr(subprocess, "run", fake.run)
    return fake
