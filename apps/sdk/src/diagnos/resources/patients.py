"""🇺🇸 `Patients`: the patient-shaped face of `VersionedDocuments` (`docs/PROTOCOL.md §8`).

🇧🇷 `Patients`: a face de paciente de `VersionedDocuments` (`docs/PROTOCOL.md §8`).
"""

from __future__ import annotations

import builtins
from collections.abc import Iterator, Mapping
from typing import Any

from diagnos.models import DocumentIndex, Page, Patient, PatientRecord

from ._documents import VersionedDocuments, coerce_record

# 🇺🇸 `builtins.list[...]`, not the bare generic: `Patients` defines a method
# literally named `list`, and mypy (with `from __future__ import annotations`)
# resolves a later bare `list` to that method instead of the builtin type.
# 🇧🇷 `builtins.list[...]`, não o genérico cru: `Patients` define um método
# chamado exatamente `list`, e o mypy (com `from __future__ import annotations`)
# resolve um `list` cru mais adiante para esse método, não para o tipo embutido.


class Patients:
    """🇺🇸 `vault.patients` — list, read, create, update, archive/unarchive/delete.

    🇧🇷 `vault.patients` — listar, ler, criar, atualizar, arquivar/desarquivar/apagar.
    """

    def __init__(self, documents: VersionedDocuments[PatientRecord]) -> None:
        """🇺🇸 Wraps an already-configured `VersionedDocuments` for the `patients` resource.

        🇧🇷 Envolve um `VersionedDocuments` já configurado para o recurso `patients`.
        """
        self._documents = documents

    def list(
        self,
        *,
        security_group: str | None = None,
        include_deleted: bool = False,
        limit: int = 50,
        cursor: str | None = None,
    ) -> Page[DocumentIndex]:
        """🇺🇸 One page of patient indexes. 🇧🇷 Uma página de índices de paciente."""
        return self._documents.list(
            security_group=security_group, include_deleted=include_deleted, limit=limit, cursor=cursor
        )

    def iter_all(
        self,
        *,
        security_group: str | None = None,
        include_deleted: bool = False,
        limit: int = 50,
    ) -> Iterator[DocumentIndex]:
        """🇺🇸 Every patient index, across all pages. 🇧🇷 Todo índice de paciente, por todas as páginas."""
        return self._documents.iter_all(security_group=security_group, include_deleted=include_deleted, limit=limit)

    def get(self, patient_id: str, *, version_id: str | None = None) -> Patient:
        """🇺🇸 Fetches and decrypts one patient, latest version unless `version_id` is given.

        🇧🇷 Busca e decifra um paciente, na versão mais recente salvo se `version_id` for dado.
        """
        index, record = self._documents.read(patient_id, version_id=version_id)
        return Patient(index=index, record=record)

    def create(
        self,
        record: PatientRecord | Mapping[str, Any],
        *,
        security_group: str | builtins.list[str],
        specialist_ids: builtins.list[str] | None = None,
    ) -> Patient:
        """🇺🇸 Encrypts `record` under `security_group`(s) and creates the patient.

        A single group id is the common case; a list covers a patient shared
        by more than one group from the moment it is created.

        🇧🇷 Cifra `record` sob o(s) `security_group`(s) e cria o paciente.

        Um único id de grupo é o caso comum; uma lista cobre um paciente
        compartilhado por mais de um grupo já na criação.
        """
        patient_record = coerce_record(PatientRecord, record)
        security_groups = [security_group] if isinstance(security_group, str) else list(security_group)
        meta = {"specialist_ids": specialist_ids} if specialist_ids else None
        index = self._documents.create(patient_record, security_groups=security_groups, meta=meta)
        return Patient(index=index, record=patient_record)

    def update(
        self,
        patient_id: str,
        record: PatientRecord | Mapping[str, Any],
        *,
        specialist_ids: builtins.list[str] | None = None,
    ) -> Patient:
        """🇺🇸 Encrypts a brand new version of `record` for `patient_id`, reusing its existing DEK.

        🇧🇷 Cifra uma versão nova de `record` para `patient_id`, reusando a DEK existente.
        """
        patient_record = coerce_record(PatientRecord, record)
        meta = {"specialist_ids": specialist_ids} if specialist_ids else None
        index = self._documents.update(patient_id, patient_record, meta=meta)
        return Patient(index=index, record=patient_record)

    def archive(self, patient_id: str) -> DocumentIndex:
        """🇺🇸 Marks the patient archived, in a new version. 🇧🇷 Marca o paciente arquivado, numa versão nova."""
        return self._documents.archive(patient_id)

    def unarchive(self, patient_id: str) -> DocumentIndex:
        """🇺🇸 Clears the archived flag, in a new version. 🇧🇷 Tira a flag de arquivado, numa versão nova."""
        return self._documents.unarchive(patient_id)

    def delete(self, patient_id: str) -> DocumentIndex:
        """🇺🇸 Marks the patient deleted, in a new version — never a hard delete.

        🇧🇷 Marca o paciente apagado, numa versão nova — nunca um apagar de verdade.
        """
        return self._documents.delete(patient_id)
