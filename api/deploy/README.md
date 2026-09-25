# Deploying `diagnos-api` · Implantando o `diagnos-api`

🇺🇸 The API is a thin shell over the SDK. It needs three things: the service
account token, a certificate pair to serve HTTPS, and the CA that signs the
**client** certificates — mutual TLS is the only authentication it accepts,
so a request without a valid client certificate never reaches application
code. With OpenBao configured, a pod restart resumes the SDK session without
a human approving again.
🇧🇷 A API é uma casca fina sobre o SDK. Precisa de três coisas: o token da
service account, um par de certificados para servir HTTPS, e a CA que assina
os certificados de **cliente** — mTLS é a única autenticação aceita, então
uma requisição sem certificado de cliente válido nunca chega ao código da
aplicação. Com OpenBao configurado, reiniciar um pod retoma a sessão do SDK
sem nova aprovação humana.

## Environment · Ambiente

| Variable | Required | 🇺🇸 Meaning · 🇧🇷 Significado |
|---|---|---|
| `DIAGNOS_API_TOKEN` | yes | service account token (`apikey-…`) · token da service account |
| `DIAGNOS_API_MTLS_CA_FILE` | yes | PEM bundle of the CA(s) allowed to sign client certificates · CA(s) que assinam certificados de cliente |
| `DIAGNOS_API_TLS_CERT_FILE` / `DIAGNOS_API_TLS_KEY_FILE` | yes | server certificate and key (PEM) · certificado e chave do servidor |
| `DIAGNOS_API_HOST` / `DIAGNOS_API_PORT` | no | default `0.0.0.0` / `8443` |
| `DIAGNOS_API_ALLOWED_CLIENT_CN` | no | comma-separated CNs; when set, only these client certificates pass · CNs permitidos |
| `OPENBAO_ADDR` / `OPENBAO_TOKEN` / `OPENBAO_MOUNT` / `OPENBAO_PATH_PREFIX` | no | auto-unseal (see `docs/PROTOCOL.md §11`) |
| `OPENBAO_TOKEN_FILE` | no | a file to read the OpenBao token from when `OPENBAO_TOKEN` is unset — how Compose (`deploy/compose`) and file-mounted Kubernetes Secrets hand it over without an environment value · um arquivo de onde ler o token do OpenBao quando `OPENBAO_TOKEN` não está definida — como o Compose (`deploy/compose`) e Secrets do Kubernetes montados como arquivo o entregam sem valor de ambiente |
| `DIAGNOS_VAULT_URL` | no | default `https://vault.diagnos.health` |

🇺🇸 Without OpenBao, the first start prints the approval link and code to the
container log; a workspace admin approves once per process lifetime.
🇧🇷 Sem OpenBao, o primeiro start imprime o link e o código no log do
container; um admin aprova uma vez por vida do processo.

## Kubernetes

```sh
kubectl apply -k deploy/k8s     # 🇺🇸 edit the Secret first · 🇧🇷 edite o Secret antes
```

🇺🇸 `deploy/k8s` ships a Deployment (1 replica — the SDK session is per
process; scale with OpenBao and one service account per replica if you need
more), a ClusterIP Service on 8443, a Secret template and a ConfigMap. Client
certificates are the callers' responsibility; the CA bundle is mounted read-only.
🇧🇷 `deploy/k8s` traz um Deployment (1 réplica — a sessão do SDK é por
processo; escale com OpenBao e uma service account por réplica), um Service
ClusterIP na 8443, um template de Secret e um ConfigMap. Certificados de
cliente são responsabilidade de quem chama; a CA é montada somente-leitura.

## Docker Compose

🇺🇸 `deploy/compose` is the fastest way to see the whole stack — OpenBao and
`diagnos-api` — running together with nothing pre-existing:

🇧🇷 `deploy/compose` é o jeito mais rápido de ver a stack inteira — OpenBao
e `diagnos-api` — rodando junto sem nada pré-existente:

```sh
cd deploy/compose
cp .env.example .env   # 🇺🇸 fill in DIAGNOS_API_TOKEN, then `diagnos status` for the two ids · 🇧🇷 preencha DIAGNOS_API_TOKEN, depois `diagnos status` para os dois ids
# 🇺🇸 certs/ needs clients-ca.pem/server.pem/server-key.pem — see this file's own openssl recipe below
# 🇧🇷 certs/ precisa de clients-ca.pem/server.pem/server-key.pem — veja a receita de openssl deste mesmo arquivo, abaixo
docker compose up
```

🇺🇸 A one-shot `openbao-bootstrap` service initialises OpenBao (or resumes,
on later runs), enables the KV v2 mount, writes the scoped `diagnos-sdk`
policy, and mints the token the API reads — `diagnos-api` only starts once
that finishes successfully. `deploy/compose/README.md` has the full
walkthrough.

🇧🇷 Um serviço `openbao-bootstrap` de execução única inicializa o OpenBao
(ou retoma, em execuções seguintes), habilita o mount KV v2, escreve a
política restrita `diagnos-sdk`, e emite o token que a API lê —
`diagnos-api` só sobe depois que isso termina com sucesso. O
`deploy/compose/README.md` tem o passo a passo completo.

**Staging-only, read before using this**: the default `OPENBAO_SEAL=shamir`
keeps OpenBao's unseal keys sitting on a local Docker volume so the
bootstrap service can re-unseal on every restart without a human — a
deliberate convenience for a disposable environment, and a real widening of
who can read every saved session if this configuration ever runs anywhere
that matters. `deploy/compose/.env.example` documents the
`aws`/`gcp`/`azure`/`transit` alternatives, sharing the exact same
`seal.hcl` files as the Kubernetes overlays below.

**Só para staging, leia antes de usar**: o `OPENBAO_SEAL=shamir` padrão
mantém as chaves de unseal do OpenBao num volume Docker local para o
serviço de bootstrap poder desselar de novo a cada reinício sem humano —
uma conveniência deliberada para um ambiente descartável, e um alargamento
de verdade de quem consegue ler toda sessão salva se esta configuração
algum dia rodar em algo que importe. O `deploy/compose/.env.example`
documenta as alternativas `aws`/`gcp`/`azure`/`transit`, compartilhando
exatamente os mesmos arquivos `seal.hcl` dos overlays de Kubernetes abaixo.

## OpenBao on Kubernetes

🇺🇸 `deploy/k8s/openbao` is a kustomize base for OpenBao itself (namespace
`openbao`, a one-replica raft StatefulSet, the ClusterIP Service the
`OPENBAO_ADDR` above already assumes) — a separate concern from `deploy/k8s`
(the API), so a platform team can own it independently:

🇧🇷 `deploy/k8s/openbao` é uma base kustomize para o próprio OpenBao
(namespace `openbao`, um StatefulSet raft de uma réplica, o Service
ClusterIP que o `OPENBAO_ADDR` acima já assume) — uma preocupação separada
de `deploy/k8s` (a API), para um time de plataforma poder ser dono dela de
forma independente:

```sh
kubectl apply -k deploy/k8s/openbao          # 🇺🇸 unseals manually (Shamir) · 🇧🇷 dessela na mão (Shamir)
# 🇺🇸/🇧🇷 ou, com auto-unseal de verdade:
kubectl apply -k deploy/k8s/autounseal/aws   # 🇺🇸/🇧🇷 aws | gcp | azure | transit | static | shamir
```

🇺🇸 `deploy/k8s/autounseal/<provider>` overlays the base with the seal each
KMS needs — every one verified field-by-field against openbao.org's own
docs, not remembered from HashiCorp Vault (the two have diverged):

🇧🇷 Os overlays `deploy/k8s/autounseal/<provedor>` somam à base o seal que
cada KMS precisa — cada um verificado campo a campo contra a própria
documentação do openbao.org, não lembrado do HashiCorp Vault (os dois já
divergiram):

| Provider · Provedor | What it needs · O que precisa |
|---|---|
| `aws` | IRSA (`eks.amazonaws.com/role-arn`) + `kms:Encrypt`/`Decrypt`/`DescribeKey` on one key |
| `gcp` | Workload Identity (`iam.gke.io/gcp-service-account`) + `roles/cloudkms.cryptoKeyEncrypterDecrypter` |
| `azure` | Workload identity federation (`azure.workload.identity/client-id`) + Key Vault `get`/`wrapKey`/`unwrapKey` |
| `transit` | A token, scoped to `encrypt`/`decrypt` on one key, from another already-unsealed OpenBao/Vault |
| `static` | A 32-byte key you generate and hold — read that overlay's security warning first |
| `shamir` | Nothing — the fallback; manual `bao operator unseal` after every restart |

🇺🇸 After the first `kubectl apply`, bootstrap OpenBao itself (`kv-v2`
mount, the `diagnos-sdk` policy, the token) by running the same script the
Compose bootstrap uses, inside the already-running pod:
`deploy/k8s/openbao/bootstrap-configmap.yaml` has the exact command and
where the resulting token goes.

🇧🇷 Depois do primeiro `kubectl apply`, faça o bootstrap do próprio OpenBao
(mount `kv-v2`, a política `diagnos-sdk`, o token) rodando o mesmo script
que o bootstrap do Compose usa, dentro do pod já rodando:
`deploy/k8s/openbao/bootstrap-configmap.yaml` tem o comando exato e para
onde vai o token resultante.

## Memory locking · Travamento de memória

🇺🇸 The SDK calls `mlock()` on session keys and group DEKs so the kernel
never pages them to swap — `docs/PROTOCOL.md`'s "never sends a key to the
vault" guarantee would not mean much if the key could still end up on a
disk block. Three things have to line up for that call to succeed in a
container:

🇧🇷 O SDK chama `mlock()` em chaves de sessão e DEKs de grupo para o kernel
nunca paginar isso para o swap — a garantia "nunca envia uma chave ao
cofre" de `docs/PROTOCOL.md` não significaria muito se a chave pudesse
ainda assim acabar num bloco de disco. Três coisas precisam se alinhar para
essa chamada funcionar num container:

1. 🇺🇸 **`CAP_IPC_LOCK`** — `deploy/k8s/deployment.yaml`'s
   `capabilities.add: [IPC_LOCK]` and `deploy/compose`'s `cap_add:
   [IPC_LOCK]` both grant it; the image itself carries `cap_ipc_lock` as a
   file capability so a non-root process can use it. · 🇧🇷 **`CAP_IPC_LOCK`**
   — o `capabilities.add: [IPC_LOCK]` de `deploy/k8s/deployment.yaml` e o
   `cap_add: [IPC_LOCK]` do `deploy/compose` concedem os dois; a própria
   imagem carrega `cap_ipc_lock` como file capability para um processo
   não-root conseguir usar.
2. 🇺🇸 **`RLIMIT_MEMLOCK`** — the default 64 KiB is not enough; `deploy/
   compose`'s `ulimits.memlock: { soft: -1, hard: -1 }` removes the limit
   entirely (Kubernetes has no per-container ulimit field, which is exactly
   why the capability above matters more there). · 🇧🇷 **`RLIMIT_MEMLOCK`**
   — o padrão de 64 KiB não é suficiente; o `ulimits.memlock: { soft: -1,
   hard: -1 }` do `deploy/compose` remove o limite por completo (o
   Kubernetes não tem campo de ulimit por container, exatamente por isso a
   capability acima importa mais lá).
3. 🇺🇸 **`DIAGNOS_MEMORY_LOCK=require`** (commented out in `deploy/k8s/
   configmap.yaml`) — makes the process refuse to start if `mlock` fails
   instead of silently continuing with swappable keys; uncomment it once
   the first two are confirmed working on your nodes. · 🇧🇷
   **`DIAGNOS_MEMORY_LOCK=require`** (comentado em `deploy/k8s/
   configmap.yaml`) — faz o processo se recusar a subir se `mlock` falhar
   em vez de continuar em silêncio com chaves que podem ir para swap;
   descomente assim que os dois primeiros estiverem confirmados
   funcionando nos seus nós.

🇺🇸 Separately, `DIAGNOS_HARDEN_PROCESS` (default `"1"`) disables core dumps
and `ptrace` attach for the process — set `"0"` only on a deployment you are
actively debugging, and revert right after.

🇧🇷 Separadamente, `DIAGNOS_HARDEN_PROCESS` (padrão `"1"`) desliga core
dumps e anexar via `ptrace` neste processo — defina `"0"` só num deployment
que você está depurando ativamente, e reverta logo depois.
