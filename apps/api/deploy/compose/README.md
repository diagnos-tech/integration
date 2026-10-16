# diagnos-api · Docker Compose

**English** · [Português (Brasil)](README.pt-BR.md)

One `docker compose up` for OpenBao + `diagnos-api`, wired for local development and staging. For a production
Kubernetes deployment, see `../k8s/openbao` (OpenBao itself) and `../k8s` (the API) instead — this compose file
trades a few production concerns (a real KMS-backed seal by default, a multi-node raft cluster) for "one command,
nothing else to run."

## Quickstart

```sh
cp .env.example .env
# edit .env: the workspace and the token's key id (svc_…) — `diagnos whoami` prints both
```

Generate the mTLS material into `certs/` with the `openssl` recipe in the
[REST API guide](../../../../docs/guides/api.md#certificates); this compose stack expects `certs/clients-ca.pem`,
`certs/server.pem` (the recipe's `tls.pem`) and `certs/server-key.pem` (its `tls-key.pem`).

```sh
docker compose --profile login run --rm login   # paste the token (dgn_sk1_…): it goes into OpenBao, never .env
docker compose up
```

First run: `openbao` starts sealed and uninitialised, `openbao-bootstrap` initialises it, unseals it (only for
`OPENBAO_SEAL=shamir` — every other value auto-unseals on its own), enables KV v2, writes the `diagnos-sdk` and
`diagnos-token-writer` policies, and mints the two scoped tokens. `login` (and `api`) only start once that bootstrap
exits `0`; `login` checks the token's CRC, proves it against the vault (`whoami`) and stores it. `api` reads it at
startup.

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
   `.env` (the saved session, and *read* on `secret/diagnos/token`), and policy `diagnos-token-writer` from
   `openbao/token-writer-policy.hcl` (store, rotate or remove `secret/diagnos/token`, nothing else); keeps one version
   of that path (`max-versions=1`), so a rotated-out token does not stay readable.
6. Mints an orphan, renewable token scoped to `diagnos-sdk` and writes it to `/state/openbao-token` (`0600`), and one
   scoped to `diagnos-token-writer` into `/admin/openbao-token-writer` (the `openbao-admin` volume, mounted only by
   `login`) — each skipped if the one already there still passes `bao token lookup`. A missing writer token without a
   root token only logs how to reissue it: the API still starts.

> [!WARNING]
> **Staging only, read this.** With `OPENBAO_SEAL=shamir` (the default), step 3 only works because step 2 kept the
> unseal keys sitting in the `openbao-state` volume, unencrypted. That is a deliberate convenience for a disposable
> environment — it means anyone with access to that Docker volume can unseal OpenBao and read every saved session,
> no OpenBao credential required. Do not run this configuration anywhere that matters; set `OPENBAO_SEAL` to
> `aws`/`gcp`/`azure`/`transit` instead (`.env.example` has the credentials each one needs) or unseal by hand and
> keep the recovery keys off this machine entirely.

## The diagnos token

The service account token never goes in `.env`. `docker compose --profile login run --rm login` runs
`diagnos login --store openbao` in the command line image: hidden input, the CRC checked before any network call,
`whoami` against the vault (a session only opens when both the Ed25519 and the ML-DSA-65 signature verify), then a
write to `secret/diagnos/token` with the writer token. Run it again to rotate the token, then
`docker compose restart api`. The API's own OpenBao token may only *read* that path, so a compromised API cannot
replace the token or erase it.

**Upgrading from the `apikey-` token:** delete `DIAGNOS_API_TOKEN` from `.env`, set `DIAGNOS_ACCOUNT_ID` to the new
token's key id, set `BAO_ROOT_TOKEN_OVERRIDE` in `.env` for one `docker compose run --rm openbao-bootstrap` (it
writes the new policies and mints the writer token; remove it right after), then run the `login` service as above.

## `OPENBAO_TOKEN_FILE`

The `api` service never sees the OpenBao token as an environment value: `openbao-bootstrap` writes it to
`/state/openbao-token` (`0600`, owned by the API's uid 10001) and the SDK reads that path itself —
`diagnos.Settings.from_env()` honours `OPENBAO_TOKEN_FILE` whenever `OPENBAO_TOKEN` is unset. Nothing in this stack
ever puts the token in `docker inspect` output or a process environment. The `login` service reads the writer token
the same way, from `/admin/openbao-token-writer`.

## Tearing down

```sh
docker compose down        # keeps openbao-data/openbao-state/openbao-admin
docker compose down -v     # destroys them — see the volumes' warnings in docker-compose.yml
```
