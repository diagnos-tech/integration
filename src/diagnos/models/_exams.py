"""The exam domain: the sealed report record and its clear-index summary."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from ._shared import _Record
from ._temporal import IsoInstant


class ExamRecord(_Record):
    """The content of an exam version (`ExamContent` in the web app): the report and its clinical context.

    `report_lexical` is the web editor's state (Lexical JSON, as a string)
    and is the source of truth; `report_html` is derived from it for readers
    that never open the editor. Write both when you produce a report, or the
    web editor opens an empty document.

    Attributes:
        title: The exam title.
        modality: The imaging modality.
        exam_date: When the exam took place, as a UTC ISO 8601 instant. Accepts a `date`, an aware `datetime` or an
            ISO 8601 string on input.
        report_lexical: The report as the web editor's Lexical state (JSON text).
        report_html: The report rendered as HTML, derived from `report_lexical`.
        custom_attributes: Free-form workspace-defined attributes.
    """

    _MISPLACED: ClassVar[dict[str, str]] = {
        "patient_id": "clear metadata — pass patient_id=... to Exams.create",
        "report": "the report is report_lexical (editor state) plus report_html",
    }

    title: str | None = None
    modality: str | None = None
    exam_date: IsoInstant = None
    report_lexical: str | None = None
    report_html: str | None = None
    custom_attributes: dict[str, Any] | None = None


class ExamSummary(BaseModel):
    """The plaintext of an exam's `encrypted_index`: title, modality and date, derived from the record.

    Attributes:
        title: The exam title.
        modality: The imaging modality.
        exam_date: The exam date as a UTC ISO 8601 instant.
    """

    model_config = ConfigDict(frozen=True, extra="allow", hide_input_in_errors=True)

    title: str | None = None
    modality: str | None = None
    exam_date: str | None = None

    @classmethod
    def of(cls, record: ExamRecord) -> ExamSummary:
        """Build the summary the web app would write for `record`.

        Args:
            record: The exam record to summarize.

        Returns:
            A summary holding the record's title, modality and exam date.
        """
        return cls(title=record.title, modality=record.modality, exam_date=record.exam_date)
