# Example: Patients

**English** · [Português (Brasil)](README.pt-BR.md)

Creates a patient from a typed `PatientRecord` (with a tag), lists every patient of the group using the sealed summary (no version downloaded), and reads the new patient back, decrypted.

> [!WARNING]
> This example **creates data** in the workspace. Use one you can throw away.

## Prerequisites

Python 3.11+, `pip install "diagnos[sdk]"`, a service account credential in `DIAGNOS_CREDENTIAL` and someone to approve the enrollment — see [the examples index](../README.md#before-you-run-any-of-them).

## Run

```sh
python main.py
```

## Expected output

On `stdout` (ids differ on every run):

```text
patient created: doc_1 in sg_oncology
patients listed: 1 in sg_oncology
  doc_1  Jane
patient read: Jane Example, tags=['example'], version=ver_2
```

Exit code: `0`; `1` on a vault error; `2` configuration error; `3` no group granted.

Updating, archiving and concurrent writes: [Patients](../../docs/guides/patients.md).
