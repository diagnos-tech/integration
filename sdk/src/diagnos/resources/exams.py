"""🇺🇸 `Exams`: the exam-shaped face of `VersionedDocuments` (`docs/PROTOCOL.md §8`).

🇧🇷 `Exams`: a face de exame de `VersionedDocuments` (`docs/PROTOCOL.md §8`).
"""

from __future__ import annotations

import builtins
from collections.abc import Iterator, Mapping
from typing import Any

from diagnos.models import DocumentIndex, Exam, ExamRecord, Page

from ._documents import VersionedDocuments, coerce_record

# 🇺🇸 `builtins.list[...]`, not the bare generic: `Exams` defines a method
# literally named `list`, and mypy (with `from __future__ import annotations`)
# resolves a later bare `list` to that method instead of the builtin type.
# 🇧🇷 `builtins.list[...]`, não o genérico cru: `Exams` define um método
# chamado exatamente `list`, e o mypy (com `from __future__ import annotations`)
# resolve um `list` cru mais adiante para esse método, não para o tipo embutido.


class Exams:
    """🇺🇸 `vault.exams` — list, read, create, update, archive/unarchive/delete.

    🇧🇷 `vault.exams` — listar, ler, criar, atualizar, arquivar/desarquivar/apagar.
    """

    def __init__(self, documents: VersionedDocuments[ExamRecord]) -> None:
        """🇺🇸 Wraps an already-configured `VersionedDocuments` for the `exams` resource.

        🇧🇷 Envolve um `VersionedDocuments` já configurado para o recurso `exams`.
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
        """🇺🇸 One page of exam indexes. 🇧🇷 Uma página de índices de exame."""
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
        """🇺🇸 Every exam index, across all pages. 🇧🇷 Todo índice de exame, por todas as páginas."""
        return self._documents.iter_all(security_group=security_group, include_deleted=include_deleted, limit=limit)

    def get(self, exam_id: str, *, version_id: str | None = None) -> Exam:
        """🇺🇸 Fetches and decrypts one exam, latest version unless `version_id` is given.

        🇧🇷 Busca e decifra um exame, na versão mais recente salvo se `version_id` for dado.
        """
        index, record = self._documents.read(exam_id, version_id=version_id)
        return Exam(index=index, record=record)

    def create(
        self,
        record: ExamRecord | Mapping[str, Any],
        *,
        patient_id: str,
        security_group: str | builtins.list[str],
        modality: str | None = None,
    ) -> Exam:
        """🇺🇸 Encrypts `record`, links it to `patient_id` in clear `meta`, and creates the exam.

        `patient_id` is required and clear on purpose — it is the axis the
        vault itself uses to route and authorize an exam without ever
        opening its encrypted content (`docs/PROTOCOL.md §8`).

        🇧🇷 Cifra `record`, liga ao `patient_id` no `meta` em claro, e cria o exame.

        `patient_id` é obrigatório e em claro de propósito — é o eixo que o
        próprio cofre usa para rotear e autorizar um exame sem nunca abrir o
        conteúdo cifrado (`docs/PROTOCOL.md §8`).
        """
        exam_record = coerce_record(ExamRecord, record)
        security_groups = [security_group] if isinstance(security_group, str) else list(security_group)
        meta: dict[str, Any] = {"patient_id": patient_id}
        if modality is not None:
            meta["modality"] = modality
        index = self._documents.create(exam_record, security_groups=security_groups, meta=meta)
        return Exam(index=index, record=exam_record)

    def update(
        self,
        exam_id: str,
        record: ExamRecord | Mapping[str, Any],
        *,
        modality: str | None = None,
    ) -> Exam:
        """🇺🇸 Encrypts a brand new version of `record` for `exam_id`, reusing its existing DEK.

        🇧🇷 Cifra uma versão nova de `record` para `exam_id`, reusando a DEK existente.
        """
        exam_record = coerce_record(ExamRecord, record)
        meta = {"modality": modality} if modality is not None else None
        index = self._documents.update(exam_id, exam_record, meta=meta)
        return Exam(index=index, record=exam_record)

    def archive(self, exam_id: str) -> DocumentIndex:
        """🇺🇸 Marks the exam archived, in a new version. 🇧🇷 Marca o exame arquivado, numa versão nova."""
        return self._documents.archive(exam_id)

    def unarchive(self, exam_id: str) -> DocumentIndex:
        """🇺🇸 Clears the archived flag, in a new version. 🇧🇷 Tira a flag de arquivado, numa versão nova."""
        return self._documents.unarchive(exam_id)

    def delete(self, exam_id: str) -> DocumentIndex:
        """🇺🇸 Marks the exam deleted, in a new version — never a hard delete.

        🇧🇷 Marca o exame apagado, numa versão nova — nunca um apagar de verdade.
        """
        return self._documents.delete(exam_id)
