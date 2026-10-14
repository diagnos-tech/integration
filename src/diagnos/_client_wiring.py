"""Free functions `Diagnos` leans on: settings resolution, the default enrollment prompt, and building a resource.

None of these need `self` beyond what is passed in. `_resolve_settings`
only reads its own arguments and the process environment,
`_print_enrollment_prompt_fallback` only defers an import, and
`_build_patients` and `_build_exams` only wire a fresh `VersionedDocuments`
into the resource-specific face. They live apart from `client.py`'s own
constructor and lazy properties, which are otherwise all instance wiring.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from diagnos.crypto import EntropyMixer
from diagnos.dates import TimePrecision
from diagnos.models import ExamRecord, ExamSummary, PatientRecord, PatientSummary
from diagnos.resources._documents import VersionedDocuments
from diagnos.resources.exams import Exams
from diagnos.resources.patients import Patients
from diagnos.session.enrollment import PromptCallback
from diagnos.transport.config import Settings

if TYPE_CHECKING:
    from diagnos.session.keyring import Keyring
    from diagnos.transport.http import VaultTransport


def _resolve_settings(settings: Settings | None, token: str | None) -> Settings:
    """Resolve the client's settings: `settings` wins outright, `token` overrides only `DIAGNOS_API_TOKEN`.

    Routing an explicit `token` through `Settings.from_env` (instead of
    hand-building a `Settings`) means the `vault_url`, `time_precision` and
    OpenBao configuration still come from the environment exactly as they
    would without `token`. A caller passing a token is choosing *which
    credential* to use, not opting out of every other env var.
    """
    if settings is not None:
        return settings
    if token is not None:
        return Settings.from_env({**os.environ, "DIAGNOS_API_TOKEN": token})
    return Settings.from_env()


def _print_enrollment_prompt_fallback() -> PromptCallback:
    """Return `SessionManager`'s own `default_prompt`, imported lazily.

    Returning the reference this way (instead of importing
    `diagnos.session.manager.default_prompt` at module scope) keeps this
    module's only hard dependency on `session/manager.py` the one class it
    actually orchestrates, `SessionManager` itself. Its default keyword
    argument already covers "no `on_prompt` given".
    """
    from diagnos.session.manager import default_prompt

    return default_prompt


def _build_patients(
    transport: VaultTransport,
    keyring_provider: Callable[[], Keyring],
    entropy: EntropyMixer,
    *,
    workspace_id: str,
    time_precision: TimePrecision | None,
) -> Patients:
    """Build a fresh `VersionedDocuments` for `patients`, wrapped in its resource-specific face."""
    documents = VersionedDocuments(
        transport,
        keyring_provider,
        entropy,
        workspace_id=workspace_id,
        resource="patients",
        record_model=PatientRecord,
        summary_model=PatientSummary,
    )
    return Patients(documents, time_precision=time_precision)


def _build_exams(
    transport: VaultTransport,
    keyring_provider: Callable[[], Keyring],
    entropy: EntropyMixer,
    *,
    workspace_id: str,
    time_precision: TimePrecision | None,
) -> Exams:
    """Build a fresh `VersionedDocuments` for `exams`, wrapped in its resource-specific face."""
    documents = VersionedDocuments(
        transport,
        keyring_provider,
        entropy,
        workspace_id=workspace_id,
        resource="exams",
        record_model=ExamRecord,
        summary_model=ExamSummary,
    )
    return Exams(documents, time_precision=time_precision)
