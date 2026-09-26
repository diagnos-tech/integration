"""🇺🇸 Free functions `Diagnos` leans on: settings resolution, the default enrollment prompt, and building a resource.

None of these need `self` beyond what is passed in — `_resolve_settings`
only reads its own arguments and the process environment,
`_print_enrollment_prompt_fallback` only defers an import, and
`_build_patients`/`_build_exams` only wire a fresh `VersionedDocuments` into
the resource-specific face — so they live apart from `client.py`'s own
constructor and lazy properties, which are otherwise all instance wiring.

🇧🇷 Funções livres em que `Diagnos` se apoia: resolução de settings, o prompt de enrollment padrão, e montar um recurso.

Nenhuma precisa de mais `self` do que o que recebe — `_resolve_settings` só
lê os próprios argumentos e o ambiente do processo,
`_print_enrollment_prompt_fallback` só adia um import, e
`_build_patients`/`_build_exams` só conectam um `VersionedDocuments` novo à
face específica do recurso — então vivem à parte do próprio construtor e
das propriedades preguiçosas de `client.py`, que são, fora isso, toda
conexão de instância.
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
    """🇺🇸 `settings` wins outright; `token` overrides only `DIAGNOS_API_TOKEN` on top of the real environment.

    Routing an explicit `token` through `Settings.from_env` (instead of
    hand-building a `Settings`) means `vault_url`/`time_precision`/OpenBao config
    still come from the environment exactly as they would without `token` —
    a caller passing a token is choosing *which credential* to use, not
    opting out of every other env var.

    🇧🇷 `settings` vence direto; `token` sobrescreve só `DIAGNOS_API_TOKEN` em cima do ambiente de verdade.

    Rotear um `token` explícito por `Settings.from_env` (em vez de montar um
    `Settings` à mão) faz `vault_url`/`time_precision`/config do OpenBao continuarem
    vindo do ambiente exatamente como viriam sem `token` — quem chama
    passando um token está escolhendo *qual credencial* usar, não saindo de
    toda outra variável de ambiente.
    """
    if settings is not None:
        return settings
    if token is not None:
        return Settings.from_env({**os.environ, "DIAGNOS_API_TOKEN": token})
    return Settings.from_env()


def _print_enrollment_prompt_fallback() -> PromptCallback:
    """🇺🇸 A deferred-import wrapper around `SessionManager`'s own `default_prompt`.

    Returning the bound reference this way (instead of importing
    `diagnos.session.manager.default_prompt` at module scope) keeps this
    module's only hard dependency on `session/manager.py` the one class it
    actually orchestrates, `SessionManager` itself — its default keyword
    argument already covers "no `on_prompt` given".

    🇧🇷 O próprio `default_prompt` do `SessionManager` já é um padrão
    sensato; isto só existe para `Diagnos` nunca precisar importá-lo só para
    ler o nome.

    Devolver a referência assim (em vez de importar
    `diagnos.session.manager.default_prompt` no nível do módulo) mantém a
    única dependência forte deste módulo em `session/manager.py` a classe que
    ele de fato orquestra, o próprio `SessionManager` — o argumento nomeado
    padrão dele já cobre "nenhum `on_prompt` foi dado".
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
    """🇺🇸 A fresh `VersionedDocuments` for `patients`, wrapped in its resource-specific face.

    🇧🇷 Um `VersionedDocuments` novo para `patients`, envolto na face específica do recurso.
    """
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
    """🇺🇸 A fresh `VersionedDocuments` for `exams`, wrapped in its resource-specific face.

    🇧🇷 Um `VersionedDocuments` novo para `exams`, envolto na face específica do recurso.
    """
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
