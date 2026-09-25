# diagnos-api · Docker Compose

**English** · [Português (Brasil)](README.pt-BR.md)

One `docker compose up` for OpenBao + `diagnos-api`, wired for local development and staging. For a production
Kubernetes deployment, see `../k8s/openbao` (OpenBao itself) and `../k8s` (the API) instead — this compose file
trades a few production concerns (a real KMS-backed seal by default, a multi-node raft cluster) for "one command,
nothing else to run."

## Quickstart

```sh
cp .env.example .env
# edit .env: DIAGNOS_API_TOKEN, then `diagnos status` for the two ids
```

Generate the mTLS material into `certs/` — the exact `openssl` recipe is in
[`../../README.md`](../../README.md)'s "Generating a CA and certificates with openssl" section; this compose stack
expects `certs/clients-ca.pem`, `certs/server.pem`, `certs/server-key.pem`.

```sh
docker compose up
```

First run: `openbao` starts sealed and uninitialised, `openbao-bootstrap` initialises it, unseals it (only for
`OPENBAO_SEAL=shamir` — every other value auto-unseals on its own), enables KV v2, writes the `diagnos-sdk` policy
from `openbao/policy.hcl`, and mints the scoped token `api` reads. `api` only starts once that bootstrap exits `0`.

## What the bootstrap does

`openbao/bootstrap.sh` runs once as the `openbao-bootstrap` service (entrypoint `sh /bootstrap/bootstrap.sh` on the
same `openbao/openbao` image — no extra image to build or trust) and is idempotent across restarts: it re-checks
status every time and skips whatever is already done, using only POSIX `sh` plus `bao`/`grep`/`sed` (no `jq`, not
present in that image).

1. Waits for `openbao:8200` to answer (any status — sealed counts).
2. `bao operator init -format=json` if not yet initialised; writes the full output (recovery/unseal keys **and the
   root token**) to the `openbao-state` volume at `0600` and prints a loud warning to move them out.
3. Unseals with the saved keys — only meaningful for `OPENBAO_SEAL=shamir`, since every KMS-backed seal unseals
   itself as soon as the process starts.
4. Enables KV v2 at `secret` (idempotent — a second `enable` failing with "already in use" is the success path).
5. Writes policy `diagnos-sdk` from `openbao/policy.hcl` with `__WORKSPACE_ID__`/`__ACCOUNT_ID__` substituted from
   `.env`.
6. Mints an orphan, renewable token scoped to that policy and writes it to `/state/openbao-token` (`0600`) —
   skipped if a token already there still passes `bao token lookup`.

> [!WARNING]
> **Staging only, read this.** With `OPENBAO_SEAL=shamir` (the default), step 3 only works because step 2 kept the
> unseal keys sitting in the `openbao-state` volume, unencrypted. That is a deliberate convenience for a disposable
> environment — it means anyone with access to that Docker volume can unseal OpenBao and read every saved session,
> no OpenBao credential required. Do not run this configuration anywhere that matters; set `OPENBAO_SEAL` to
> `aws`/`gcp`/`azure`/`transit` instead (`.env.example` has the credentials each one needs) or unseal by hand and
> keep the recovery keys off this machine entirely.

## `OPENBAO_TOKEN_FILE`

The `api` service never sees the OpenBao token as an environment value: `openbao-bootstrap` writes it to
`/state/openbao-token` (`0600`, owned by the API's uid 10001) and the SDK reads that path itself —
`diagnos.Settings.from_env()` honours `OPENBAO_TOKEN_FILE` whenever `OPENBAO_TOKEN` is unset. Nothing in this stack
ever puts the token in `docker inspect` output or a process environment.

## Tearing down

```sh
docker compose down        # keeps openbao-data/openbao-state
docker compose down -v     # destroys them — see the volumes' warnings in docker-compose.yml
```
