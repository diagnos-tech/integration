# Deploying `diagnos-api`

**English** · [Português (Brasil)](README.pt-BR.md)

The API is a thin shell over the SDK. It needs three things: the service account token (`dgn_sk1_…`), a certificate
pair to serve HTTPS, and the CA that signs the **client** certificates — mutual TLS is the only authentication it
accepts, so a request without a valid client certificate never reaches application code. In a deployment the token
lives in OpenBao, never in an environment file or a Kubernetes Secret: `diagnos login --store openbao` stores it once
with a writer token, and the API reads it at startup with a token that may only read it. The session opens with one
signed request — no human approval, on the first start or after a restart.

## The image

Every release publishes `ghcr.io/diagnos-tech/diagnos-api` for `linux/amd64` and `linux/arm64`, built by the
release workflow from the same wheels it uploads to PyPI, with an SBOM and build provenance, and signed with cosign
by digest. Deploy it **by digest**, after verifying that digest — `diagnos setup api` does both and prints the
`docker run` (see [SECURITY.md](../../../SECURITY.md#verifying-a-release) for the commands by hand):

```sh
diagnos setup api                     # pull, verify the pulled digest, print the run by digest
docker build --target api -t diagnos-api .   # or build it from a checkout, at the repository root
```

The image runs as uid/gid `10001` with its code root-owned and read-only, has no shell tooling to install anything,
and reports health by whether port 8443 accepts connections (`HEALTHCHECK`; mTLS turns a plain HTTP probe away).

## Environment

| Variable | Required | Meaning |
|---|---|---|
| `OPENBAO_ADDR` + `OPENBAO_TOKEN` or `OPENBAO_TOKEN_FILE` | yes | Where the service account token is (`secret/diagnos/token`, stored with `diagnos login --store openbao`), and an OpenBao token that may read it — the `diagnos-sdk` policy. |
| `DIAGNOS_TOKEN` | no | The token itself (`dgn_sk1_…`), for CI and ephemeral containers only; when set it wins over OpenBao. |
| `DIAGNOS_API_MTLS_CA_FILE` | yes | PEM bundle of the CA(s) allowed to sign client certificates. |
| `DIAGNOS_API_TLS_CERT_FILE` / `DIAGNOS_API_TLS_KEY_FILE` | yes | Server certificate and key (PEM). |
| `DIAGNOS_API_HOST` / `DIAGNOS_API_PORT` | no | Default `0.0.0.0` / `8443`. |
| `DIAGNOS_API_ALLOWED_CLIENT_CN` | no | Comma-separated CNs; when set, only these client certificates pass. |
| `OPENBAO_MOUNT`, `OPENBAO_PATH_PREFIX`, `DIAGNOS_VAULT_URL`, `DIAGNOS_STORAGE_HOSTS`, `DIAGNOS_MEMORY_LOCK`, … | no | Every SDK variable applies too — see [Configuration](../../../docs/guides/configuration.md). `OPENBAO_TOKEN_FILE` is how Compose (`deploy/compose`) and file-mounted Kubernetes Secrets hand over the OpenBao token without an environment value. |

Without a token, the API refuses to start and says where it looked. Generating the certificates and calling the API:
the [REST API guide](../../../docs/guides/api.md).

## Kubernetes

```sh
kubectl apply -k deploy/k8s     # edit the Secret first (TLS material and the read-only OPENBAO_TOKEN)
```

`deploy/k8s` ships a Deployment (1 replica — the SDK session is per process; scale with OpenBao and one service
account per replica if you need more), a ClusterIP Service on 8443, a Secret template and a ConfigMap. Client
certificates are the callers' responsibility; the CA bundle is mounted read-only. The Secret holds no diagnos token:
the API reads it from OpenBao (see [OpenBao on Kubernetes](#openbao-on-kubernetes)).

## Docker Compose

`deploy/compose` is the fastest way to see the whole stack — OpenBao and `diagnos-api` — running together with
nothing pre-existing:

```sh
cd deploy/compose
cp .env.example .env   # fill in the workspace and the token's key id (svc_…) — `diagnos whoami` prints both
# certs/ needs clients-ca.pem/server.pem/server-key.pem — see this file's own openssl recipe below
docker compose --profile login run --rm login   # paste the token: it goes into OpenBao, not .env
docker compose up
```

A one-shot `openbao-bootstrap` service initialises OpenBao (or resumes, on later runs), enables the KV v2 mount,
writes the `diagnos-sdk` and `diagnos-token-writer` policies, and mints two tokens: the one the API reads (read-only access to the
diagnos token, and its saved session when auto-unseal is on — never by default with the service account token) and the writer token only the `login` service mounts —
`diagnos-api` only starts once that finishes successfully. [`deploy/compose/README.md`](compose/README.md) has the full walkthrough.

> [!WARNING]
> **Staging only, read before using this.** The default `OPENBAO_SEAL=shamir` keeps OpenBao's unseal keys sitting on
> a local Docker volume so the bootstrap service can re-unseal on every restart without a human — a deliberate
> convenience for a disposable environment, and a real widening of who can read every saved session if this
> configuration ever runs anywhere that matters. `deploy/compose/.env.example` documents the `aws`/`gcp`/`azure`/
> `transit` alternatives, sharing the exact same `seal.hcl` files as the Kubernetes overlays below.

## OpenBao on Kubernetes

`deploy/k8s/openbao` is a kustomize base for OpenBao itself (namespace `openbao`, a one-replica raft StatefulSet,
the ClusterIP Service the `OPENBAO_ADDR` above already assumes) — a separate concern from `deploy/k8s` (the API), so
a platform team can own it independently:

```sh
kubectl apply -k deploy/k8s/openbao          # unseals manually (Shamir)
# or, with real auto-unseal:
kubectl apply -k deploy/k8s/autounseal/aws   # aws | gcp | azure | transit | static | shamir
```

`deploy/k8s/autounseal/<provider>` overlays the base with the seal each KMS needs — every one verified field-by-field
against openbao.org's own docs, not remembered from HashiCorp Vault (the two have diverged):

| Provider | What it needs |
|---|---|
| [`aws`](k8s/autounseal/aws/README.md) | IRSA (`eks.amazonaws.com/role-arn`) + `kms:Encrypt`/`Decrypt`/`DescribeKey` on one key |
| [`gcp`](k8s/autounseal/gcp/README.md) | Workload Identity (`iam.gke.io/gcp-service-account`) + `roles/cloudkms.cryptoKeyEncrypterDecrypter` |
| [`azure`](k8s/autounseal/azure/README.md) | Workload identity federation (`azure.workload.identity/client-id`) + Key Vault `get`/`wrapKey`/`unwrapKey` |
| [`transit`](k8s/autounseal/transit/README.md) | A token, scoped to `encrypt`/`decrypt` on one key, from another already-unsealed OpenBao/Vault |
| [`static`](k8s/autounseal/static/README.md) | A 32-byte key you generate and hold — read that overlay's security warning first |
| [`shamir`](k8s/autounseal/shamir/README.md) | Nothing — the fallback; manual `bao operator unseal` after every restart |

After the first `kubectl apply`, bootstrap OpenBao itself (`kv-v2` mount, the `diagnos-sdk` and
`diagnos-token-writer` policies, the two tokens) by running the same script the Compose bootstrap uses, inside the
already-running pod, then store the diagnos token with `diagnos login --store openbao` through a port-forward:
`deploy/k8s/openbao/bootstrap-configmap.yaml` has the exact commands and where each token goes.

## Memory locking

The SDK calls `mlock()` on session keys and group DEKs so the kernel never pages them to swap —
[`docs/PROTOCOL.md`](../../../docs/PROTOCOL.md)'s "never sends a key to the vault" guarantee would not mean much if the
key could still end up on a disk block. Three things have to line up for that call to succeed in a container:

1. **`RLIMIT_MEMLOCK`** — the default 64 KiB is not enough; `deploy/compose`'s `ulimits.memlock: { soft: -1, hard:
   -1 }` (or `docker run --ulimit memlock=-1:-1`) removes the limit entirely. This is the reliable mechanism.
2. **`CAP_IPC_LOCK`** — `deploy/k8s/deployment.yaml`'s `capabilities.add: [IPC_LOCK]` and `deploy/compose`'s
   `cap_add: [IPC_LOCK]` grant it, and the image carries `cap_ipc_lock` as a file capability. But both manifests also
   set `no-new-privileges` (`allowPrivilegeEscalation: false` in Kubernetes), under which the kernel ignores file
   capabilities — so for a non-root process the capability is a fallback, not the mechanism. Kubernetes has no
   per-container ulimit field: locking past 64 KiB there depends on the `RLIMIT_MEMLOCK` your nodes' container
   runtime grants. Check `diagnos status` (or `memory_status()`) once per cluster.
3. **`DIAGNOS_MEMORY_LOCK=require`** (commented out in `deploy/k8s/configmap.yaml`) — makes the process refuse to
   start if `mlock` fails instead of silently continuing with swappable keys; uncomment it once the first two are
   confirmed working on your nodes.

Separately, `DIAGNOS_HARDEN_PROCESS` (default `"1"`) disables core dumps and `ptrace` attach for the process — set
`"0"` only on a deployment you are actively debugging, and revert right after.
