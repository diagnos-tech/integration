# Example: Exams

**English** · [Português (Brasil)](README.pt-BR.md)

Creates a patient and an exam for them with a report (both `report_lexical` and `report_html`, so the web editor opens it), uploads a file linked to the exam, then reads the exam back and finds it among the patient's exams.

Sharing a report by link is not in the SDK: create the link in the web app. The public link viewer is a vault route for the person who receives the link, not an SDK call.

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
exam created: doc_3 for patient doc_1
file attached: node_5 -> exam doc_3
exam read: Chest X-ray (CR), report: <p>No acute findings. Heart size within normal limits.</p>
exams of the patient: 1
```

Exit code: `0`; `1` on a vault error; `2` configuration error; `3` no group granted.

The record fields and the report: [Exams](../../docs/guides/exams.md).
