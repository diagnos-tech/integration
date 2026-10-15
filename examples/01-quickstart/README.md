# Example: Quickstart

**English** · [Português (Brasil)](README.pt-BR.md)

Reads the credential from `DIAGNOS_CREDENTIAL`, enrolls (the SDK prints an approval link and a 6-digit code on `stderr`), then makes the first call: it lists the first page of patients. If only the legacy `DIAGNOS_API_TOKEN` is set, it says it is deprecated (removal on 2027-04-15) and keeps going.

## Prerequisites

Python 3.11+, `pip install "diagnos[sdk]"`, a service account credential in `DIAGNOS_CREDENTIAL` and someone to approve the enrollment — see [the examples index](../README.md#before-you-run-any-of-them).

## Run

```sh
python main.py
```

## Expected output

On `stdout` (ids differ on every run):

```text
workspace: ws_1
credential: ed25519 svc_00000000000000000000000000000000
groups: sg_oncology, sg_radiology
first call ok: 0 patient(s) on the first page
```

Exit code: `0`; `2` configuration error, `3` enrollment denied or expired, or the credential was refused.

Next: [`03-patients`](../03-patients/README.md) to write data, [`05-error-handling`](../05-error-handling/README.md) for failures.
