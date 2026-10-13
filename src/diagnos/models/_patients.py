"""🇺🇸 The patient domain: identity documents, address, the sealed record, and its clear-index summary.

🇧🇷 O domínio de paciente: documentos de identidade, endereço, o registro selado, e o resumo do índice em claro.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from ._shared import _from_vault, _Record
from ._temporal import IsoInstant

BiologicalSex = Literal["MALE", "FEMALE", "INTERSEX", "UNDEFINED"]
GenderIdentity = Literal[
    "CIS_MALE",
    "CIS_FEMALE",
    "TRANS_MALE",
    "TRANS_FEMALE",
    "NON_BINARY",
    "AGENDER",
    "FLUID",
    "OTHER",
    "PREFER_NOT_TO_SAY",
]
RaceIdentity = Literal["WHITE", "BLACK", "BROWN", "YELLOW", "INDIGENOUS", "NOT_DECLARED"]

# 🇺🇸 `secret:v1:<salt>:<iv>:<payload>` — a value the vault sealed through its sensitive-data route.
# 🇧🇷 `secret:v1:<salt>:<iv>:<payload>` — um valor que o cofre selou pela rota de dado sensível.
_SEALED_SECRET = re.compile(r"^secret:v1:[^:]+:[^:]+:[^:]+$")


class PersonalIdentifier(_Record):
    """🇺🇸 An identity document (CPF, RG, passport…) whose `value` is sealed by the vault, not by this SDK.

    Opening one is audited server-side, which is why the value is
    `secret:v1:…` sealed material rather than plain text. The external API
    has no route to seal a new one yet: records read from the vault carry
    them through untouched, and a caller-built record must already hold
    sealed values. For a plain id from another system, use
    `PatientRecord.external_id`.

    🇧🇷 Um documento de identidade (CPF, RG, passaporte…) cujo `value` é selado pelo cofre, não por este SDK.

    Abrir um é auditado no servidor, por isso o valor é material selado
    `secret:v1:…` e não texto claro. A API externa ainda não tem rota para
    selar um novo: registros lidos do cofre os carregam intactos, e um
    registro montado por quem chama já precisa trazer valores selados. Para
    um id simples de outro sistema, use `PatientRecord.external_id`.
    """

    name: str = Field(min_length=1)
    value: str

    @field_validator("value")
    @classmethod
    def _value_is_sealed(cls, value: str, info: ValidationInfo) -> str:
        """🇺🇸 Refuses a plain-text identifier. 🇧🇷 Recusa um identificador em texto claro."""
        if _from_vault(info) or _SEALED_SECRET.match(value):
            return value
        raise ValueError(
            "identifiers[].value must be vault-sealed material ('secret:v1:…'); plain-text identity documents "
            "are never stored — use external_id for a plain id · identifiers[].value precisa ser material selado "
            "pelo cofre ('secret:v1:…'); documento de identidade em texto claro nunca é gravado — use external_id"
        )


class PatientAddress(_Record):
    """🇺🇸 A patient's address; every field optional (an emergency registration may have none).

    🇧🇷 O endereço de um paciente; todo campo opcional (um cadastro de emergência pode não ter nenhum).
    """

    postal_code: str | None = None
    street: str | None = None
    number: str | None = None
    complement: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None


class PatientRecord(_Record):
    """🇺🇸 The `data` stream of a patient (`PatientData` in the web app) — everything here is sealed before upload.

    `birth_date` accepts a `date` or an aware `datetime` and is stored the
    way the web app stores it, as a UTC ISO 8601 instant. Set
    `Settings.time_precision` to truncate it to the workspace's
    anonymization precision before sealing, like the web app does.

    🇧🇷 O fluxo `data` de um paciente (`PatientData` no app web) — tudo aqui é selado antes do upload.

    `birth_date` aceita `date` ou `datetime` com fuso e é gravado do jeito
    que o app web grava, como um instante ISO 8601 em UTC. Defina
    `Settings.time_precision` para truncá-lo à precisão de anonimização do
    workspace antes de selar, como o app web faz.
    """

    _MISPLACED: ClassVar[dict[str, str]] = {
        "tags": "not a record field — pass tags=[...] to create/update · não é campo do registro — passe tags=[...]",
        "specialist_ids": "clear metadata — pass specialist_ids=[...] to create/update · metadado em claro — passe "
        "specialist_ids=[...]",
    }

    legal_name: str
    display_name: str
    identifiers: list[PersonalIdentifier] | None = None
    external_id: str | None = None
    birth_date: IsoInstant = None
    biological_sex: BiologicalSex | None = None
    gender_identity: GenderIdentity | None = None
    race_identity: RaceIdentity | None = None
    email: str | None = None
    phone: str | None = None
    address: PatientAddress | None = None
    internal_notes: list[str] | None = None
    custom_attributes: dict[str, Any] | None = None


class PatientSummary(BaseModel):
    """🇺🇸 The plaintext of a patient's `encrypted_index`: what a list shows without opening any version.

    The SDK derives it from the record on every write (plus `tags`, which
    are not a record field); it never carries identity documents, because
    opening the summary is not audited.

    🇧🇷 O texto claro do `encrypted_index` de um paciente: o que uma lista mostra sem abrir nenhuma versão.

    O SDK o deriva do registro a cada gravação (mais `tags`, que não são
    campo do registro); ele nunca carrega documento de identidade, porque
    abrir o resumo não é auditado.
    """

    model_config = ConfigDict(frozen=True, extra="allow", hide_input_in_errors=True)

    display_name: str | None = None
    legal_name: str | None = None
    external_id: str | None = None
    birth_date: str | None = None
    tags: list[str] = Field(default_factory=list)

    @classmethod
    def of(cls, record: PatientRecord, tags: Sequence[str]) -> PatientSummary:
        """🇺🇸 The summary the web app would write for `record`. 🇧🇷 O resumo que o app web gravaria para `record`."""
        return cls(
            display_name=record.display_name,
            legal_name=record.legal_name,
            external_id=record.external_id,
            birth_date=record.birth_date,
            tags=list(tags),
        )
