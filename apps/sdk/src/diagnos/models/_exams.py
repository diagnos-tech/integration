"""🇺🇸 The exam domain: the sealed report record and its clear-index summary.

🇧🇷 O domínio de exame: o registro selado do laudo e o resumo do índice em claro.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from ._shared import _Record
from ._temporal import IsoInstant


class ExamRecord(_Record):
    """🇺🇸 The content of an exam version (`ExamContent` in the web app) — the report and its clinical context.

    `report_lexical` is the web editor's state (Lexical JSON, as a string)
    and is the source of truth; `report_html` is derived from it for readers
    that never open the editor. Write both when you produce a report, or the
    web editor opens an empty document.

    🇧🇷 O conteúdo de uma versão de exame (`ExamContent` no app web) — o laudo e o contexto clínico.

    `report_lexical` é o estado do editor web (JSON do Lexical, como string)
    e é a fonte da verdade; `report_html` é derivado dele para leitores que
    nunca abrem o editor. Grave os dois ao produzir um laudo, senão o editor
    web abre um documento vazio.
    """

    _MISPLACED: ClassVar[dict[str, str]] = {
        "patient_id": "clear metadata — pass patient_id=... to Exams.create · metadado em claro — passe patient_id=...",
        "report": "the report is report_lexical (editor state) plus report_html · o laudo é report_lexical (estado do "
        "editor) mais report_html",
    }

    title: str | None = None
    modality: str | None = None
    exam_date: IsoInstant = None
    report_lexical: str | None = None
    report_html: str | None = None
    custom_attributes: dict[str, Any] | None = None


class ExamSummary(BaseModel):
    """🇺🇸 The plaintext of an exam's `encrypted_index`: title, modality and date, derived from the record.

    🇧🇷 O texto claro do `encrypted_index` de um exame: título, modalidade e data, derivados do registro.
    """

    model_config = ConfigDict(frozen=True, extra="allow", hide_input_in_errors=True)

    title: str | None = None
    modality: str | None = None
    exam_date: str | None = None

    @classmethod
    def of(cls, record: ExamRecord) -> ExamSummary:
        """🇺🇸 The summary the web app would write for `record`. 🇧🇷 O resumo que o app web gravaria para `record`."""
        return cls(title=record.title, modality=record.modality, exam_date=record.exam_date)
