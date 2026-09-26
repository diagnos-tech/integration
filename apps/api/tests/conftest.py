"""🇺🇸 Re-exports `fakes.py`'s fixtures and fakes so pytest's conftest auto-discovery finds them.

`fake_vault`, `api_settings` and `client` stay fixtures once imported here — pytest scans this
module's own attributes for the `@pytest.fixture` marker regardless of which file first defined the
function, so importing them (rather than redefining them) keeps every route test's fixture request
working exactly as before. `FakeDiagnos`, `build_app` and `TRUSTED_IDENTITY` are re-exported the same
way because several test modules do `from conftest import FakeDiagnos` directly.

🇧🇷 Reexporta as fixtures e os fakes de `fakes.py` para a descoberta automática de conftest do pytest os achar.

`fake_vault`, `api_settings` e `client` continuam fixtures depois de importadas aqui — o pytest varre
os próprios atributos deste módulo atrás do marcador `@pytest.fixture`, não importa em qual arquivo a
função foi definida primeiro, então importá-las (em vez de redefini-las) mantém a solicitação de
fixture de todo teste de rota funcionando exatamente como antes. `FakeDiagnos`, `build_app` e
`TRUSTED_IDENTITY` são reexportados do mesmo jeito porque vários módulos de teste fazem
`from conftest import FakeDiagnos` direto.
"""

from __future__ import annotations

from fakes import (
    TRUSTED_IDENTITY,
    WORKSPACE_ID,
    FakeDiagnos,
    FakeDrive,
    FakeDrives,
    FakeExams,
    FakePatients,
    api_settings,
    build_app,
    client,
    fake_vault,
)

__all__ = [
    "TRUSTED_IDENTITY",
    "WORKSPACE_ID",
    "FakeDiagnos",
    "FakeDrive",
    "FakeDrives",
    "FakeExams",
    "FakePatients",
    "api_settings",
    "build_app",
    "client",
    "fake_vault",
]
