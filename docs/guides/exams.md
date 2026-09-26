# Exams

**English** · [Português (Brasil)](exams.pt-BR.md)

`vault.exams` works like [`vault.patients`](patients.md) — versioned, sealed documents — with two differences that
matter: every exam belongs to one patient, and its content is a clinical report the web editor opens.

## Create

```python
from diagnos import Diagnos, ExamRecord

vault = Diagnos()
patient = vault.patients.create({"legal_name": "Jane Doe", "display_name": "Jane"}, security_group="sg_radiology")

exam = vault.exams.create(
    ExamRecord(title="Chest CT", modality="CT", exam_date="2026-09-01", report_html="<p>Unremarkable.</p>"),
    patient_id=patient.id,  # required, and the one field sent in clear
    security_group="sg_radiology",
)
print(exam.id, exam.patient_id, exam.version_id)
```

`patient_id` is required and travels in clear on purpose: it is how the vault links an exam to its patient — to
route and authorize — without opening either. Everything else, the modality included, is sealed. Like any document,
an exam belongs to exactly one security group.

### The record

| Field | Notes |
|---|---|
| `title` | e.g. `Chest CT` |
| `modality` | e.g. `CT`, `MR`, `US` — sealed, not metadata |
| `exam_date` | a `date`, an aware `datetime` or an ISO string; stored and truncated like a [patient's dates](patients.md#dates-and-time-precision) |
| `report_lexical` | the web editor's state, as a JSON string — the source of truth for the report |
| `report_html` | HTML derived from it, for readers that never open the editor |
| `custom_attributes` | any JSON object |

A `dict` works as well as an `ExamRecord`, with the same [typo protection](patients.md#typos-are-refused-unknown-fields-are-kept).
`patient_id` or `report` inside the record are refused with a pointer to where they belong.

### The report

The web editor stores a report as Lexical state (`report_lexical`) and derives `report_html` from it. When you
produce a report that people will open in the web app, write **both**: with only `report_html`, the editor opens an
empty document. A reader that only displays reports can rely on `report_html` alone — the CLI does exactly that,
printing it as plain text.

Whether a report is a draft or published (`exam.report_status`: `draft`, `published`, or `None` when never set)
is clear metadata on the exam's index. The SDK reads it and never sets it.

## Read

```python
exam = vault.exams.get(exam.id)  # the newest content; a newer web-editor draft wins
print(exam.record.title, exam.patient_id, exam.report_status, exam.from_draft)
print(exam.record.report_html)

committed = vault.exams.get(exam.id, include_draft=False)
```

Drafts, versions and the `index` behave exactly as for [patients](patients.md#read).

## List

```python
for row in vault.exams.iter_all(security_group="sg_radiology"):
    summary = row.summary  # title, modality and date, decrypted locally
    print(row.id, row.index.meta.get("patient_id"), summary.title if summary else "—")

of_patient = [row for row in vault.exams.iter_all() if row.index.meta.get("patient_id") == patient.id]
print(len(of_patient), "exam(s) of", patient.id)
```

Lists filter by `security_group` and `include_deleted`. There is no server-side filter by patient; the patient id is
in each row's clear `meta`, so filtering locally costs nothing but the walk.

## Update

```python
current = vault.exams.get(exam.id)
signed_off = current.record.model_copy(update={"report_html": "<p>Unremarkable. No nodules.</p>"})
exam = vault.exams.update(exam.id, signed_off, expected_latest_version_id=current.index.latest_version_id)
```

Like patients: a complete new version every time, and `expected_latest_version_id` turns a concurrent save into a
`ConflictError` instead of a silent overwrite — see [Safe concurrent writes](patients.md#safe-concurrent-writes).
Exams have no tags.

## Archive, delete, restore

```python
vault.exams.archive(exam.id)  # a flag, no new version
vault.exams.unarchive(exam.id)
vault.exams.delete(exam.id)  # to the trash, never a hard delete
vault.exams.restore(exam.id)
```

## Files of an exam

Images, DICOM series and PDFs are not part of the record: they are [files](files.md) linked to the exam by
`exam_id`, each under its own key.

```python
drive = vault.drives.drive("sg_radiology")
drive.upload("scans/IM-0001.dcm", exam_id=exam.id)
print([drive.name_of(node) for node in drive.iter_all(exam_id=exam.id)])
```
