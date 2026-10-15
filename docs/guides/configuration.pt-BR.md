# Configuração

[English](configuration.md) · **Português (Brasil)**

O SDK lê a configuração uma vez, do ambiente, quando um `Diagnos` é construído — ou a recebe inteira explicitamente
como um `Settings`, sem ambiente nenhum. A CLI e a API REST embutem o SDK, então toda variável daqui vale para elas
também; elas só acrescentam as próprias flags e variáveis por cima.

## O ambiente

| Variável | Padrão | O que faz |
|---|---|---|
| `DIAGNOS_CREDENTIAL` | — (uma das três fontes de credencial é obrigatória) | a credencial da service account, numa linha: `svc_<hex>@<workspace_id>.diagnos.health:<chave>` — veja [Autenticação](authentication.pt-BR.md) |
| `DIAGNOS_CREDENTIALS_FILE` | não definida | o caminho do JSON da credencial baixado na criação, lido quando `DIAGNOS_CREDENTIAL` não existe; na falta dele, `~/.config/diagnos/credentials.json` |
| `DIAGNOS_API_TOKEN` | não definida | **obsoleto, deixa de funcionar em 2027-04-15**: o token legado `apikey-<jwt>`, usado só quando nenhuma credencial é achada, com um `LegacyTokenWarning` — veja o [MIGRATING.pt-BR.md](../../MIGRATING.pt-BR.md#do-token-apikey--para-uma-credencial-de-conta-de-serviço-020) |
| `DIAGNOS_VAULT_URL` | `https://vault.diagnos.health` | onde o cofre mora; mude só para um cofre de staging ou self-hosted |
| `DIAGNOS_TIMEOUT_SECONDS` | `30` | o timeout de cada requisição HTTP, em segundos |
| `DIAGNOS_TIME_PRECISION` | não definida | a precisão de anonimização do workspace — `month`, `day`, `hour`, `minute` ou `second`; as datas são truncadas nela antes de selar ([por quê](patients.pt-BR.md#datas-e-precisão-de-tempo)) |
| `DIAGNOS_STORAGE_HOSTS` | `diagnosusercontent.com, r2.cloudflarestorage.com` | os hosts, e seus subdomínios, para onde uma URL de armazenamento pré-assinada pode apontar, só HTTPS; o resto é recusado antes de um byte sair, então ciphertext e chaves SSE-C só vão para onde o deployment escolheu |
| `DIAGNOS_MEMORY_LOCK` | `best-effort` | `require` se recusa a guardar uma chave que o SO não trava na RAM — veja [abaixo](#memória-e-hardening-do-processo) |
| `DIAGNOS_HARDEN_PROCESS` | `1` | `0` pula desligar core dumps e o attach de debugger no unlock — só enquanto depura |

Nenhuma credencial em nenhuma das fontes, uma malformada ou um valor inválido lança `ConfigError` nomeando a
variável, quando o `Diagnos` é construído — antes de qualquer chamada de rede, nunca depois, no meio de uma requisição.

## OpenBao

O auto-unseal está ligado exatamente quando `OPENBAO_ADDR` está definida, e precisa do extra `openbao`
(`pip install "diagnos[openbao]"`). [Sessões](sessions.pt-BR.md#auto-unseal-com-openbao) explica o que ele troca.

| Variável | Padrão | O que faz |
|---|---|---|
| `OPENBAO_ADDR` | não definida | o servidor OpenBao; defini-la liga o auto-unseal |
| `OPENBAO_TOKEN` | não definida | um token restrito ao path desta service account, e nada mais amplo |
| `OPENBAO_TOKEN_FILE` | não definida | um arquivo com esse token, lido quando `OPENBAO_TOKEN` não está definida — como Kubernetes e Compose montam segredos |
| `OPENBAO_MOUNT` | `secret` | o mount KV v2 |
| `OPENBAO_PATH_PREFIX` | `diagnos` | a sessão salva mora em `<prefixo>/<workspace_id>/<account_id>` |
| `OPENBAO_NAMESPACE` | não definida | um namespace do OpenBao, se você os usa |

## Memória e hardening do processo

Toda chave que o SDK guarda vive em memória travada em página, gerida pelo enclave Rust dele, então nunca chega ao
swap. Travar conta contra o `ulimit -l` — muitas vezes 64 KiB num container. Quando o SO recusa, o SDK mantém toda
outra proteção e emite um `MemoryLockWarning`; com `DIAGNOS_MEMORY_LOCK=require`, ele se recusa a rodar assim.

```python
import diagnos

status = diagnos.memory_status()
print(status["lock_policy"], status["backend"], status["unlocked_allocations"])
```

`memory_status()` diz o que o enclave garante nesta máquina agora: a política, se guard pages e zerar-no-fork estão
disponíveis, quantas alocações não puderam ser travadas, e se `CAP_IPC_LOCK` é permitida. Para o travamento dar
certo num container, conceda `CAP_IPC_LOCK` ou aumente o limite —
[Implantação](../../apps/api/deploy/README.pt-BR.md#travamento-de-memória) tem as três configurações, e [o
enclave](../../apps/sdk/native/README.pt-BR.md#operando) o raciocínio.

`DIAGNOS_HARDEN_PROCESS=1`, o padrão, desliga core dumps e nega o attach de debugger no instante em que o processo
desbloqueia — o instante em que ele começa a guardar chaves clínicas. Use `0` só para anexar um debugger, e reverta
logo depois.

## Sem o ambiente: `Settings`

Para testes, para um processo que fala como várias service accounts, ou quando a configuração vem de outro lugar,
monte um `Settings` você mesmo. Ele é imutável e o `repr` dele mascara a credencial e redige o token legado:

```python
import os

from diagnos import Diagnos, ServiceAccountCredential, Settings

settings = Settings(
    credential=ServiceAccountCredential.parse(os.environ["DIAGNOS_CREDENTIAL"]),
    timeout_seconds=10,
    time_precision="day",
)
vault = Diagnos(settings=settings)
print(settings)  # credential='svc_0000…0000@ws_1.diagnos.health' — nunca a chave
```

`Settings(...)` ignora o ambiente por inteiro, OpenBao inclusive: todo campo não informado fica com o padrão.
`Settings.from_env(mapping)` lê as mesmas variáveis de acima de qualquer mapeamento, e `Diagnos(credential=…)` troca só
a identidade enquanto todo o resto continua vindo do ambiente (o obsoleto `Diagnos(token=…)` faz o mesmo com o
token legado).

## A CLI e a API REST

- A **CLI** aceita `--token` e `--vault-url` em qualquer lugar da linha, sobrescrevendo `DIAGNOS_VAULT_URL` (e, para
  o token legado, `DIAGNOS_API_TOKEN`) para uma invocação; as outras flags globais estão no [guia da CLI](cli.pt-BR.md#opções-globais).
  Ela também lê `DIAGNOS_GROUP`, o security group sob o qual uma gravação sela quando `--group` não é dado;
  `DIAGNOS_AGENT`, em que `off` mantém cada comando no próprio processo; e `DIAGNOS_AGENT_IDLE_MINUTES`, quanto tempo
  o agente de sessão espera sem comando antes de encerrar a sessão (padrão `480`) — veja
  [Sem aprovar todo comando](cli.pt-BR.md#sem-aprovar-todo-comando).
- A **API REST** acrescenta as próprias variáveis `DIAGNOS_API_*` — certificados, host, porta, nomes de cliente
  permitidos — listadas em [Implantação](../../apps/api/deploy/README.pt-BR.md#ambiente).
