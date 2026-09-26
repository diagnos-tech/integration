"""🇺🇸 `Exams`: the exam-shaped face of `VersionedDocuments` (`docs/PROTOCOL.md §8`).

🇧🇷 `Exams`: a face de exame de `VersionedDocuments` (`docs/PROTOCOL.md §8`).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from diagnos.dates import TimePrecision, truncate_timestamp
from diagnos.models import DocumentIndex, Exam, ExamListItem, ExamRecord, ExamSummary, Page

from ._documents import DEFAULT_PAGE_SIZE, OpenedDocument, VersionedDocuments, coerce_record
from .patients import require_single_group


class Exams:
    """🇺🇸 `vault.exams` — list, read, create, update, archive/unarchive, delete/restore.

    🇧🇷 `vault.exams` — listar, ler, criar, atualizar, arquivar/desarquivar, apagar/restaurar.
    """

    def __init__(
        self,
        documents: VersionedDocuments[ExamRecord, ExamSummary],
        *,
        time_precision: TimePrecision | None = None,
    ) -> None:
        """🇺🇸 Wraps a `VersionedDocuments` for `exams`; `time_precision` truncates dates before sealing.

        🇧🇷 Envolve um `VersionedDocuments` de `exams`; `time_precision` trunca datas antes de selar.
        """
        self._documents = documents
        self._time_precision = time_precision

    def list(
        self,
        *,
        security_group: str | None = None,
        include_deleted: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> Page[ExamListItem]:
        """🇺🇸 One page of exams, each with its decrypted summary (title, modality, date).

        🇧🇷 Uma página de exames, cada um com o resumo decifrado (título, modalidade, data).
        """
        return self._documents.list(
            security_group=security_group, include_deleted=include_deleted, limit=limit, cursor=cursor
        )

    def iter_all(
        self,
        *,
        security_group: str | None = None,
        include_deleted: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[ExamListItem]:
        """🇺🇸 Every exam, across all pages. 🇧🇷 Todo exame, por todas as páginas."""
        return self._documents.iter_all(security_group=security_group, include_deleted=include_deleted, limit=limit)

    def get(self, exam_id: str, *, version_id: str | None = None, include_draft: bool = True) -> Exam:
        """🇺🇸 Fetches and decrypts one exam: the newest content (draft included), or `version_id`.

        🇧🇷 Busca e decifra um exame: o conteúdo mais novo (rascunho incluído), ou `version_id`.
        """
        return _exam(self._documents.read(exam_id, version_id=version_id, include_draft=include_draft))

    def index(self, exam_id: str) -> DocumentIndex:
        """🇺🇸 The exam's metadata — group, versions, flags, clear `meta` — without opening the record.

        🇧🇷 O metadado do exame — grupo, versões, flags, `meta` em claro — sem abrir o registro.
        """
        return self._documents.get_index(exam_id)

    def create(self, record: ExamRecord | Mapping[str, Any], *, patient_id: str, security_group: str) -> Exam:
        """🇺🇸 Seals `record`, links it to `patient_id` in clear `meta`, and creates the exam.

        `patient_id` is required and clear on purpose — it is the axis the
        vault itself uses to route and authorize an exam without ever
        opening its encrypted content. Everything else, modality included,
        stays sealed.

        🇧🇷 Sela `record`, liga ao `patient_id` no `meta` em claro, e cria o exame.

        `patient_id` é obrigatório e em claro de propósito — é o eixo que o
        próprio cofre usa para rotear e autorizar um exame sem nunca abrir o
        conteúdo cifrado. Todo o resto, modalidade inclusive, fica selado.
        """
        group = require_single_group(security_group)
        exam_record = self._anonymize(coerce_record(ExamRecord, record))
        opened = self._documents.create(
            exam_record, security_group=group, summary=ExamSummary.of(exam_record), meta={"patient_id": patient_id}
        )
        return _exam(opened)

    def update(
        self,
        exam_id: str,
        record: ExamRecord | Mapping[str, Any],
        *,
        expected_latest_version_id: str | None = None,
    ) -> Exam:
        """🇺🇸 Seals a new complete version of `record` (see `Patients.update` for the conflict guard).

        🇧🇷 Sela uma versão nova e completa de `record` (ver `Patients.update` para a trava de conflito).
        """
        exam_record = self._anonymize(coerce_record(ExamRecord, record))
        opened = self._documents.update(
            exam_id,
            exam_record,
            summary=lambda _current: ExamSummary.of(exam_record),
            expected_latest_version_id=expected_latest_version_id,
        )
        return _exam(opened)

    def archive(self, exam_id: str) -> DocumentIndex:
        """🇺🇸 Marks the exam archived (no new version). 🇧🇷 Marca o exame arquivado (sem versão nova)."""
        return self._documents.set_flags(exam_id, is_archived=True)

    def unarchive(self, exam_id: str) -> DocumentIndex:
        """🇺🇸 Clears the archived flag (no new version). 🇧🇷 Tira a flag de arquivado (sem versão nova)."""
        return self._documents.set_flags(exam_id, is_archived=False)

    def delete(self, exam_id: str) -> DocumentIndex:
        """🇺🇸 Moves the exam to the trash — a flag, never a hard delete; `restore` undoes it.

        🇧🇷 Manda o exame para a lixeira — uma flag, nunca um apagar de verdade; `restore` desfaz.
        """
        return self._documents.set_flags(exam_id, is_deleted=True)

    def restore(self, exam_id: str) -> DocumentIndex:
        """🇺🇸 Takes the exam out of the trash. 🇧🇷 Tira o exame da lixeira."""
        return self._documents.set_flags(exam_id, is_deleted=False)

    def _anonymize(self, record: ExamRecord) -> ExamRecord:
        """🇺🇸 Truncates `exam_date` to `time_precision`, as the web app does before sealing.

        🇧🇷 Trunca `exam_date` em `time_precision`, como o app web faz antes de selar.
        """
        if self._time_precision is None or record.exam_date is None:
            return record
        return record.model_copy(update={"exam_date": truncate_timestamp(record.exam_date, self._time_precision)})


def _exam(opened: OpenedDocument[ExamRecord, ExamSummary]) -> Exam:
    """🇺🇸 The public `Exam` for one engine result. 🇧🇷 O `Exam` público de um resultado do motor."""
    return Exam(
        index=opened.index,
        record=opened.record,
        summary=opened.summary,
        version_id=opened.version_id,
        draft_rev=opened.draft_rev,
    )
