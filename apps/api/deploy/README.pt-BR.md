# Implantando o `diagnos-api`

[English](README.md) · **Português (Brasil)**

A API é uma casca fina sobre o SDK. Precisa de três coisas: o token da service account (`dgn_sk1_…`), um par de
certificados para servir HTTPS, e a CA que assina os certificados de **cliente** — mTLS é a única autenticação aceita,
então uma requisição sem certificado de cliente válido nunca chega ao código da aplicação. Num deployment o token mora
no OpenBao, nunca num arquivo de ambiente nem num Secret do Kubernetes: o `diagnos login --store openbao` o guarda uma
vez com um token de escrita, e a API o lê na subida com um token que só pode lê-lo. A sessão abre com uma requisição
assinada — sem aprovação humana, na primeira subida ou depois de um reinício.

## A imagem

Todo release publica `ghcr.io/diagnos-tech/diagnos-api` para `linux/amd64` e `linux/arm64`, construída pelo workflow
de release a partir dos mesmos wheels que ele envia ao PyPI, com SBOM e proveniência de build, e assinada com cosign
pelo digest. Faça o deploy **pelo digest**, depois de verificar esse digest — o `diagnos setup api` faz as duas
coisas e imprime o `docker run` (veja o [SECURITY.pt-BR.md](../../../SECURITY.pt-BR.md#verificando-um-release) para
os comandos à mão):

```sh
diagnos setup api                     # baixa, verifica o digest baixado, imprime o run pelo digest
docker build --target api -t diagnos-api .   # ou construa a partir de um checkout, na raiz do repositório
```

A imagem roda como uid/gid `10001` com o código do root e só leitura, não tem ferramenta de shell para instalar nada,
e informa a saúde pela porta 8443 aceitar conexões (`HEALTHCHECK`; o mTLS recusa uma sonda HTTP simples).

## Ambiente

| Variável | Obrigatória | Significado |
|---|---|---|
| `OPENBAO_ADDR` + `OPENBAO_TOKEN` ou `OPENBAO_TOKEN_FILE` | sim | Onde está o token da service account (`secret/diagnos/token`, guardado com `diagnos login --store openbao`), e um token do OpenBao que pode lê-lo — a política `diagnos-sdk`. |
| `DIAGNOS_TOKEN` | não | O próprio token (`dgn_sk1_…`), só para CI e containers efêmeros; quando definida, vence o OpenBao. |
| `DIAGNOS_API_MTLS_CA_FILE` | sim | Bundle PEM da(s) CA(s) autorizada(s) a assinar certificados de cliente. |
| `DIAGNOS_API_TLS_CERT_FILE` / `DIAGNOS_API_TLS_KEY_FILE` | sim | Certificado e chave do servidor (PEM). |
| `DIAGNOS_API_HOST` / `DIAGNOS_API_PORT` | não | Padrão `0.0.0.0` / `8443`. |
| `DIAGNOS_API_ALLOWED_CLIENT_CN` | não | CNs separados por vírgula; quando definida, só esses certificados de cliente passam. |
| `OPENBAO_MOUNT`, `OPENBAO_PATH_PREFIX`, `DIAGNOS_VAULT_URL`, `DIAGNOS_STORAGE_HOSTS`, `DIAGNOS_MEMORY_LOCK`, … | não | Toda variável do SDK vale também — veja [Configuração](../../../docs/guides/configuration.pt-BR.md). `OPENBAO_TOKEN_FILE` é como o Compose (`deploy/compose`) e Secrets do Kubernetes montados como arquivo entregam o token do OpenBao sem valor de ambiente. |

Sem token, a API se recusa a subir e diz onde procurou. Gerar os certificados e chamar a API: o
[guia da API REST](../../../docs/guides/api.pt-BR.md).

## Kubernetes

```sh
kubectl apply -k deploy/k8s     # edite o Secret antes (material TLS e o OPENBAO_TOKEN só de leitura)
```

`deploy/k8s` traz um Deployment (1 réplica — a sessão do SDK é por processo; escale com OpenBao e uma service
account por réplica se precisar de mais), um Service ClusterIP na 8443, um template de Secret e um ConfigMap.
Certificados de cliente são responsabilidade de quem chama; o bundle da CA é montado somente-leitura. O Secret não
guarda token do diagnos: a API o lê do OpenBao (veja [OpenBao no Kubernetes](#openbao-no-kubernetes)).

## Docker Compose

`deploy/compose` é o jeito mais rápido de ver a stack inteira — OpenBao e `diagnos-api` — rodando junto sem nada
pré-existente:

```sh
cd deploy/compose
cp .env.example .env   # preencha o workspace e o key id do token (svc_…) — o `diagnos whoami` imprime os dois
# certs/ precisa de clients-ca.pem/server.pem/server-key.pem — veja a receita de openssl deste mesmo arquivo, abaixo
docker compose --profile login run --rm login   # cole o token: ele vai para o OpenBao, não para o .env
docker compose up
```

Um serviço `openbao-bootstrap` de execução única inicializa o OpenBao (ou retoma, em execuções seguintes), habilita
o mount KV v2, escreve as políticas `diagnos-sdk` e `diagnos-token-writer`, e emite dois tokens: o que a API lê (a
sessão salva dela, e leitura do token do diagnos) e o token de escrita que só o serviço `login` monta —
`diagnos-api` só sobe depois que isso termina com sucesso. [`deploy/compose/README.pt-BR.md`](compose/README.pt-BR.md) tem o passo a passo
completo.

> [!WARNING]
> **Só para staging, leia antes de usar.** O `OPENBAO_SEAL=shamir` padrão mantém as chaves de unseal do OpenBao num
> volume Docker local para o serviço de bootstrap poder desselar de novo a cada reinício sem humano — uma
> conveniência deliberada para um ambiente descartável, e um alargamento de verdade de quem consegue ler toda sessão
> salva se esta configuração algum dia rodar em algo que importe. O `deploy/compose/.env.example` documenta as
> alternativas `aws`/`gcp`/`azure`/`transit`, compartilhando exatamente os mesmos arquivos `seal.hcl` dos overlays de
> Kubernetes abaixo.

## OpenBao no Kubernetes

`deploy/k8s/openbao` é uma base kustomize para o próprio OpenBao (namespace `openbao`, um StatefulSet raft de uma
réplica, o Service ClusterIP que o `OPENBAO_ADDR` acima já assume) — uma preocupação separada de `deploy/k8s` (a
API), para um time de plataforma poder ser dono dela de forma independente:

```sh
kubectl apply -k deploy/k8s/openbao          # dessela na mão (Shamir)
# ou, com auto-unseal de verdade:
kubectl apply -k deploy/k8s/autounseal/aws   # aws | gcp | azure | transit | static | shamir
```

Os overlays `deploy/k8s/autounseal/<provedor>` somam à base o seal que cada KMS precisa — cada um verificado campo a
campo contra a própria documentação do openbao.org, não lembrado do HashiCorp Vault (os dois já divergiram):

| Provedor | O que precisa |
|---|---|
| [`aws`](k8s/autounseal/aws/README.pt-BR.md) | IRSA (`eks.amazonaws.com/role-arn`) + `kms:Encrypt`/`Decrypt`/`DescribeKey` numa chave |
| [`gcp`](k8s/autounseal/gcp/README.pt-BR.md) | Workload Identity (`iam.gke.io/gcp-service-account`) + `roles/cloudkms.cryptoKeyEncrypterDecrypter` |
| [`azure`](k8s/autounseal/azure/README.pt-BR.md) | Federação de workload identity (`azure.workload.identity/client-id`) + Key Vault `get`/`wrapKey`/`unwrapKey` |
| [`transit`](k8s/autounseal/transit/README.pt-BR.md) | Um token, restrito a `encrypt`/`decrypt` numa chave, de outro OpenBao/Vault já desselado |
| [`static`](k8s/autounseal/static/README.pt-BR.md) | Uma chave de 32 bytes que você gera e guarda — leia o aviso de segurança daquele overlay antes |
| [`shamir`](k8s/autounseal/shamir/README.pt-BR.md) | Nada — o fallback; `bao operator unseal` na mão depois de todo reinício |

Depois do primeiro `kubectl apply`, faça o bootstrap do próprio OpenBao (mount `kv-v2`, as políticas `diagnos-sdk` e
`diagnos-token-writer`, os dois tokens) rodando o mesmo script que o bootstrap do Compose usa, dentro do pod já
rodando, e depois guarde o token do diagnos com `diagnos login --store openbao` por um port-forward:
`deploy/k8s/openbao/bootstrap-configmap.yaml` tem os comandos exatos e para onde vai cada token.

## Travamento de memória

O SDK chama `mlock()` em chaves de sessão e DEKs de grupo para o kernel nunca paginar isso para o swap — a garantia
"nunca envia uma chave ao cofre" de [`docs/PROTOCOL.pt-BR.md`](../../../docs/PROTOCOL.pt-BR.md) não significaria muito se a chave
pudesse ainda assim acabar num bloco de disco. Três coisas precisam se alinhar para essa chamada funcionar num
container:

1. **`RLIMIT_MEMLOCK`** — o padrão de 64 KiB não é suficiente; o `ulimits.memlock: { soft: -1, hard: -1 }` do
   `deploy/compose` (ou `docker run --ulimit memlock=-1:-1`) remove o limite por completo. Este é o mecanismo
   confiável.
2. **`CAP_IPC_LOCK`** — o `capabilities.add: [IPC_LOCK]` de `deploy/k8s/deployment.yaml` e o `cap_add: [IPC_LOCK]`
   de `deploy/compose` a concedem, e a imagem carrega `cap_ipc_lock` como file capability. Mas os dois manifestos
   também ligam o `no-new-privileges` (`allowPrivilegeEscalation: false` no Kubernetes), sob o qual o kernel ignora
   file capabilities — então, para um processo não-root, a capability é um recurso de reserva, não o mecanismo. O
   Kubernetes não tem campo de ulimit por container: travar além de 64 KiB lá depende do `RLIMIT_MEMLOCK` que o
   runtime de containers dos seus nós concede. Confira o `diagnos status` (ou o `memory_status()`) uma vez por
   cluster.
3. **`DIAGNOS_MEMORY_LOCK=require`** (comentado em `deploy/k8s/configmap.yaml`) — faz o processo se recusar a subir
   se `mlock` falhar em vez de continuar em silêncio com chaves que podem ir para swap; descomente assim que os dois
   primeiros estiverem confirmados funcionando nos seus nós.

Separadamente, `DIAGNOS_HARDEN_PROCESS` (padrão `"1"`) desliga core dumps e anexar via `ptrace` neste processo —
defina `"0"` só num deployment que você está depurando ativamente, e reverta logo depois.
