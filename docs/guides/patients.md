# Patients

**English** · [Português (Brasil)](patients.pt-BR.md)

`vault.patients` creates, reads, lists and changes patient records. Everything clinical is sealed in your process
before it leaves; what the vault stores is a versioned, encrypted document it can route but never read. The model
behind it — versions, drafts, the sealed summary — is in [Concepts](concepts.md#documents-patients-and-exams).

## Create

```python
from datetime import date

from diagnos import Diagnos

vault = Diagnos()
patient = vault.patients.create(
    {"legal_name": "Jane Doe", "display_name": "Jane", "birth_date": date(1990, 1, 31)},
    security_group="sg_oncology",  # exactly one group per document
    tags=["diabetes"],  # list and search labels, sealed inside the summary
    specialist_ids=["specialist_123"],  # clear metadata the vault filters by
)
print(patient.id, patient.version_id, patient.tags)
```

The record can be a `dict` or a `PatientRecord`; either way it is validated before anything is encrypted. `tags`
and `specialist_ids` are arguments, not record fields, because they live in different places: tags are sealed with
the summary, specialist ids stay in clear metadata so the vault can filter by them.

### The record

`PatientRecord` mirrors the web app's patient data field for field, so what you write is what the web app reads:

| Field | Notes |
|---|---|
| `legal_name`, `display_name` | required |
| `external_id` | your system's id for this patient — plain text, sealed with the rest |
| `birth_date` | a `date`, an aware `datetime` or an ISO string — see [Dates](#dates-and-time-precision) |
| `biological_sex` | `MALE`, `FEMALE`, `INTERSEX`, `UNDEFINED` |
| `gender_identity` | `CIS_MALE`, `CIS_FEMALE`, `TRANS_MALE`, `TRANS_FEMALE`, `NON_BINARY`, `AGENDER`, `FLUID`, `OTHER`, `PREFER_NOT_TO_SAY` |
| `race_identity` | `WHITE`, `BLACK`, `BROWN`, `YELLOW`, `INDIGENOUS`, `NOT_DECLARED` |
| `email`, `phone` | free text |
| `address` | `postal_code`, `street`, `number`, `complement`, `district`, `city`, `state`, `country` — all optional |
| `internal_notes` | a list of strings |
| `custom_attributes` | any JSON object |
| `identifiers` | identity documents, sealed by the vault — see [Identity documents](#identity-documents) |

Every field is sealed. Types and defaults are in the [SDK reference](../reference/sdk.json).

### Typos are refused, unknown fields are kept

The vault never sees plaintext, so nothing downstream would ever notice a misspelled field — it would be stored
under a key nobody reads. The record is the last check, and it handles two opposite failures:

- a key that **looks like a typo** of a real field (`birthdate`) is refused, naming the field it resembles; so is a
  key that belongs elsewhere (`tags` inside the record);
- any **other unknown key is kept** as it came, so a field the web app added after this SDK was released survives a
  read-modify-write instead of being silently deleted.

```python
import pydantic

try:
    vault.patients.create(
        {"legal_name": "Jane Doe", "display_name": "Jane", "birthdate": "1990-01-31"}, security_group="sg_oncology"
    )
except pydantic.ValidationError as error:  # raised before anything is encrypted or sent
    print(error.errors()[0]["msg"])
```

> [!NOTE]
> A bad record raises `pydantic.ValidationError` (a `ValueError`) locally. `diagnos.ValidationError` is different:
> it is the vault refusing a request — see [Errors](errors.md).

### Dates and time precision

`birth_date` accepts a `date`, an aware `datetime` or an ISO 8601 string, and is stored the way the web app stores
it: a UTC instant, `YYYY-MM-DDTHH:MM:SS.sssZ`. A date alone means midnight UTC; a time without a UTC offset is
refused, because it would mean a different instant on every machine.

A workspace can also fix an **anonymization precision** — `month`, `day`, `hour`, `minute` or `second` — that the
web app truncates every date to before encrypting. The external API does not expose that setting, so set
`DIAGNOS_TIME_PRECISION` to your workspace's value and the SDK applies the same truncation on every write:

```python
from datetime import date

from diagnos import to_iso_instant, truncate_timestamp

print(to_iso_instant(date(1990, 1, 31)))  # 1990-01-31T00:00:00.000Z
print(truncate_timestamp("1990-01-31T15:42:10Z", "month"))  # 1990-01-01T00:00:00.000Z
```

### Identity documents

`identifiers` (CPF, passport…) are sealed by the vault's sensitive-data route, and opening one is audited — the
external API cannot seal a new one. The SDK carries existing values through a read-modify-write untouched and
refuses a plain-text value. For an id from another system, use `external_id`.

## Read

```python
same = vault.patients.get(patient.id)  # the newest content: a newer web-editor draft wins
print(same.record.legal_name, same.from_draft, same.version_id)

committed = vault.patients.get(patient.id, include_draft=False)  # committed versions only
pinned = vault.patients.get(patient.id, version_id=patient.version_id)  # one exact version
```

`get()` downloads and decrypts one version (or the draft). A `Patient` carries the decrypted `record`, its `summary`
and `tags`, where the content came from (`version_id`, or `draft_rev` when `from_draft`), and the `index` the vault
keeps — `security_group_id`, `versions`, `updated_at` and the flags.

## List

```python
for row in vault.patients.iter_all(security_group="sg_oncology"):
    summary = row.summary  # decrypted locally from the sealed summary: no version downloaded
    print(row.id, summary.display_name if summary else "—", summary.tags if summary else [])

page = vault.patients.list(limit=20)  # one page; follow page.next_cursor for the next
```

Rows are `PatientListItem`s: the index plus the decrypted `summary`. `summary` is `None` for a patient whose group
this session does not hold, instead of failing the page. `include_deleted=True` adds patients in the trash. Paging
is described in [Concepts](concepts.md#lists-and-cursors).

## Update

An update writes a **complete** new version — there are no partial updates. Read, change, write:

```python
current = vault.patients.get(patient.id)
renamed = current.record.model_copy(update={"display_name": "Jane R."})
patient = vault.patients.update(
    patient.id,
    renamed,
    expected_latest_version_id=current.index.latest_version_id,  # refuse if someone saved meanwhile
)
```

`model_copy` keeps every other field — including ones this SDK does not model. `tags=None` (the default) keeps the
current tags; pass a list to replace them. `specialist_ids` works the same way.

### Safe concurrent writes

Without `expected_latest_version_id`, the last writer wins silently. With it, the vault refuses a write when another
version was committed since your read, and you decide what to do:

```python
from diagnos import ConflictError

stale = patient.index.latest_version_id
vault.patients.update(patient.id, patient.record, tags=["diabetes", "follow-up"])  # someone else saves

try:
    vault.patients.update(patient.id, renamed, expected_latest_version_id=stale)
except ConflictError as error:
    print(error.code)  # DocumentVersionMismatch: read again, merge, write again
```

## Archive, delete, restore

```python
vault.patients.archive(patient.id)  # a flag, no new version
vault.patients.unarchive(patient.id)
vault.patients.delete(patient.id)  # to the trash; the encrypted history stays
vault.patients.restore(patient.id)
```

Each returns the updated `DocumentIndex`. Delete is never a hard delete: the patient disappears from lists until
`restore`, or until listed with `include_deleted=True`.

## What is not here yet

- The patient's `file` stream — the web editor's rich document — is not exposed; the SDK reads and writes the
  structured record.
- Drafts are read, never written.

Both, and the rest of the known limits, are tracked in [COMPATIBILITY.md](../COMPATIBILITY.md#known-limits).
