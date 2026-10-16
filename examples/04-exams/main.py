"""🇺🇸 Create a patient and an exam with a report, attach a file to the exam, read it all back.

An exam belongs to one patient and one security group. Its `patient_id` is
the single clear field (it is how the vault routes and authorizes without
opening anything); title, modality, date and the report are sealed. Files
(images, DICOM, PDF) are not part of the record: they are drive nodes linked
to the exam by `exam_id`.

The SDK has no call to create a share link for a report: sharing is done in
the web app (see this folder's README).

🇧🇷 Cria um paciente e um exame com laudo, anexa um arquivo ao exame e lê tudo de volta.

Um exame pertence a um paciente e a um security group. O `patient_id` é o
único campo em claro (é como o cofre roteia e autoriza sem abrir nada);
título, modalidade, data e laudo são selados. Arquivos (imagens, DICOM, PDF)
não fazem parte do registro: são nós do drive ligados ao exame por `exam_id`.

O SDK não tem chamada para criar link de compartilhamento de um laudo: o
compartilhamento é feito no app web (ver o README desta pasta).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from typing import Any

from diagnos import ConfigError, Diagnos, DiagnosError, ExamRecord, PatientRecord, to_iso_instant

REPORT_TEXT = "No acute findings. Heart size within normal limits."


def lexical_paragraph(text: str) -> str:
    """🇺🇸 A one-paragraph Lexical state (the web editor). 🇧🇷 Um estado Lexical de um parágrafo (o editor web)."""
    leaf: dict[str, Any] = {
        "detail": 0,
        "format": 0,
        "mode": "normal",
        "style": "",
        "text": text,
        "type": "text",
        "version": 1,
    }
    block: dict[str, Any] = {
        "children": [leaf],
        "direction": "ltr",
        "format": "",
        "indent": 0,
        "type": "paragraph",
        "version": 1,
    }
    root: dict[str, Any] = {
        "children": [block],
        "direction": "ltr",
        "format": "",
        "indent": 0,
        "type": "root",
        "version": 1,
    }
    return json.dumps({"root": root})


def main() -> int:
    """🇺🇸 Creates patient, exam and file; returns the exit code. 🇧🇷 Cria paciente, exame, arquivo; devolve o código."""
    try:
        with Diagnos() as vault:
            if not vault.security_groups:
                print("this token's scope has no security group", file=sys.stderr)
                return 3
            group = os.environ.get("DIAGNOS_GROUP") or vault.security_groups[0]

            patient = vault.patients.create(
                PatientRecord(legal_name="John Example", display_name="John"), security_group=group
            )
            # 🇺🇸 Write both report fields: with only `report_html` the web editor opens an empty document.
            # 🇧🇷 Grave os dois campos do laudo: só com `report_html` o editor web abre um documento vazio.
            record = ExamRecord(
                title="Chest X-ray",
                modality="CR",
                exam_date=to_iso_instant(datetime.now(UTC)),
                report_lexical=lexical_paragraph(REPORT_TEXT),
                report_html=f"<p>{REPORT_TEXT}</p>",
            )
            exam = vault.exams.create(record, patient_id=patient.id, security_group=group)
            print(f"exam created: {exam.id} for patient {exam.patient_id}")

            node = vault.drives.drive(group).upload(b"DICM" + bytes(128), name="chest.dcm", exam_id=exam.id)
            print(f"file attached: {node.node_id} -> exam {node.exam_id}")

            same = vault.exams.get(exam.id)
            print(f"exam read: {same.record.title} ({same.record.modality}), report: {same.record.report_html}")
            mine = [
                row
                for row in vault.exams.iter_all(security_group=group)
                if row.index.meta.get("patient_id") == patient.id
            ]
            print(f"exams of the patient: {len(mine)}")
    except ConfigError as error:
        print(f"configuration: {error}", file=sys.stderr)
        return 2
    except DiagnosError as error:
        print(f"{error.__class__.__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
