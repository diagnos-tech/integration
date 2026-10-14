"""Re-exports the fixtures and fakes of `fakes.py` so that pytest's conftest auto-discovery finds them.

`fake_vault`, `api_settings` and `client` stay fixtures once imported here: pytest scans this module's own attributes
for the `@pytest.fixture` marker regardless of which file first defined the function, so importing them (rather than
redefining them) keeps every route test's fixture request working. `FakeDiagnos`, `build_app` and `TRUSTED_IDENTITY`
are re-exported the same way because several test modules do `from conftest import FakeDiagnos` directly.
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
