# Example: Quickstart

**English** · [Português (Brasil)](README.pt-BR.md)

Finds the service account token — `DIAGNOS_TOKEN`, or where `diagnos login` kept it — opens a session with one signed request (no approval, no code), then makes the first call: it lists the first page of patients. With only the legacy `DIAGNOS_API_TOKEN` set, it still runs, with a deprecation warning (removal on 2027-04-15).

## Prerequisites

Python 3.11+, `pip install "diagnos[sdk]"`, and a service account token in `DIAGNOS_TOKEN` (or stored by `diagnos login`) — see [the examples index](../README.md#before-you-run-any-of-them).

## Run

```sh
python main.py
```

## Expected output

On `stdout` (ids differ on every run):

```text
workspace: ws_1
token: svc_00000000000000000000000000000000@ws_1.diagnos.health (from DIAGNOS_TOKEN)
groups: sg_oncology, sg_radiology
first call ok: 0 patient(s) on the first page
```

Exit code: `0`; `2` configuration error (no token, or one pasted wrong), `3` the vault refused the token.

Next: [`03-patients`](../03-patients/README.md) to write data, [`05-error-handling`](../05-error-handling/README.md) for failures.
