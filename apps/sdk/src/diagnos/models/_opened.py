"""🇺🇸 `Patient`/`Exam`: what an application actually holds after opening a document — index, record, summary.

🇧🇷 `Patient`/`Exam`: o que uma aplicação de fato guarda após abrir um documento — índice, registro, resumo.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ._exams import ExamRecord, ExamSummary
from ._index import DocumentIndex
from ._patients import PatientRecord, PatientSummary


class _OpenedDocument(BaseModel):
    """🇺🇸 Fields shared by `Patient` and `Exam`: the index, where the content came from, and shorthands.

    🇧🇷 Campos comuns a `Patient` e `Exam`: o índice, de onde veio o conteúdo, e atalhos.
    """

    model_config = ConfigDict(frozen=True)

    index: DocumentIndex
    version_id: str | None = None
    """🇺🇸 The committed version the record came from; `None` when it came from the draft head.

    🇧🇷 A versão confirmada de onde o registro veio; `None` quando veio da cabeça de rascunho.
    """
    draft_rev: int | None = None
    """🇺🇸 The draft revision the record came from, when the draft was newer.

    🇧🇷 A revisão do rascunho de onde o registro veio, quando ele era mais novo.
    """

    @property
    def id(self) -> str:
        """🇺🇸 The document id — shorthand for `index.document_id`.

        🇧🇷 O id do documento — atalho para `index.document_id`.
        """
        return self.index.document_id

    @property
    def updated_at(self) -> str:
        """🇺🇸 Shorthand for `index.updated_at`. 🇧🇷 Atalho para `index.updated_at`."""
        return self.index.updated_at

    @property
    def security_group_id(self) -> str:
        """🇺🇸 Shorthand for `index.security_group_id`. 🇧🇷 Atalho para `index.security_group_id`."""
        return self.index.security_group_id

    @property
    def from_draft(self) -> bool:
        """🇺🇸 `True` when the record is the (newer) draft head, not a committed version.

        🇧🇷 `True` quando o registro é a cabeça de rascunho (mais nova), não uma versão confirmada.
        """
        return self.draft_rev is not None


class Patient(_OpenedDocument):
    """🇺🇸 A patient as an application wants it: the index, the decrypted record and its summary.

    🇧🇷 Um paciente do jeito que uma aplicação quer: o índice, o registro decifrado e o resumo.
    """

    record: PatientRecord
    summary: PatientSummary | None = None

    @property
    def tags(self) -> list[str]:
        """🇺🇸 The sealed list/search tags (`summary.tags`). 🇧🇷 As tags seladas de lista/busca (`summary.tags`)."""
        return list(self.summary.tags) if self.summary is not None else []


class Exam(_OpenedDocument):
    """🇺🇸 An exam as an application wants it: the index, the decrypted record and its summary.

    🇧🇷 Um exame do jeito que uma aplicação quer: o índice, o registro decifrado e o resumo.
    """

    record: ExamRecord
    summary: ExamSummary | None = None

    @property
    def patient_id(self) -> str | None:
        """🇺🇸 The exam's patient, read from clear `meta` (`docs/PROTOCOL.md §8`) — never guessed from content.

        🇧🇷 O paciente do exame, lido do `meta` em claro (`docs/PROTOCOL.md §8`) — nunca adivinhado do conteúdo.
        """
        patient_id = self.index.meta.get("patient_id")
        return str(patient_id) if patient_id is not None else None

    @property
    def report_status(self) -> str | None:
        """🇺🇸 `draft` or `published`, from clear `meta`; `None` when never set.

        🇧🇷 `draft` ou `published`, do `meta` em claro; `None` quando nunca definido.
        """
        status = self.index.meta.get("report_status")
        return str(status) if status is not None else None
