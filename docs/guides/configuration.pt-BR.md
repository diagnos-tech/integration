# Configuração

[English](configuration.md) · **Português (Brasil)**

O SDK lê a configuração uma vez, do ambiente, quando um `Diagnos` é construído — ou a recebe inteira explicitamente
como um `Settings`, sem ambiente nenhum. A CLI e a API REST embutem o SDK, então toda variável daqui vale para elas
também; elas só acrescentam as próprias flags e variáveis por cima.

## O ambiente

| Variável | Padrão | O que faz |
|---|---|---|
| `DIAGNOS_TOKEN` | não definida — então o chaveiro do sistema, então o OpenBao | o token da conta de serviço, `dgn_sk1_…`: para CI e containers efêmeros; numa estação de trabalho o `diagnos login` o guarda no chaveiro, num servidor no OpenBao — veja [Autenticação](authentication.pt-BR.md#onde-o-token-mora) |
| `DIAGNOS_API_TOKEN` | não definida | **obsoleto, deixa de funcionar em 2027-04-15**: o token legado `apikey-<jwt>`, com um `LegacyTokenWarning` — veja o [MIGRATING.pt-BR.md](../../MIGRATING.pt-BR.md#do-token-apikey--para-o-token-de-conta-de-serviço-020) |
| `DIAGNOS_VAULT_URL` | `https://vault.diagnos.health` | onde o cofre mora; mude só para um cofre de staging ou self-hosted |
| `DIAGNOS_TIMEOUT_SECONDS` | `30` | o timeout de cada requisição HTTP, em segundos |
| `DIAGNOS_TIME_PRECISION` | não definida | a precisão de anonimização do workspace — `month`, `day`, `hour`, `minute` ou `second`; as datas são truncadas nela antes de selar ([por quê](patients.pt-BR.md#datas-e-precisão-de-tempo)) |
| `DIAGNOS_STORAGE_HOSTS` | `diagnosusercontent.com, r2.cloudflarestorage.com` | os hosts, e seus subdomínios, para onde uma URL de armazenamento pré-assinada pode apontar, só HTTPS; o resto é recusado antes de um byte sair, então ciphertext e chaves SSE-C só vão para onde o deployment escolheu |
| `DIAGNOS_MEMORY_LOCK` | `best-effort` | `require` se recusa a guardar uma chave que o SO não trava na RAM — veja [abaixo](#memória-e-hardening-do-processo) |
| `DIAGNOS_HARDEN_PROCESS` | `1` | `0` pula desligar core dumps e o attach de debugger no unlock — só enquanto depura |

Nenhum token em nenhuma das fontes lança `ConfigError` dizendo onde procurou; um token cortado ou colado errado lança
`TokenError` (o CRC não confere); um valor inválido lança `ConfigError` nomeando a variável — tudo quando o `Diagnos` é
construído, antes de qualquer chamada ao cofre, nunca depois, no meio de uma requisição.

## OpenBao

O OpenBao faz dois trabalhos, com o extra `openbao` (`pip install "diagnos[openbao]"`). É onde um servidor guarda o
**token** (`<prefixo>/token`, guardado com `diagnos login --store openbao`, lido quando `OPENBAO_ADDR` está definida,
não há `DIAGNOS_TOKEN` e o chaveiro não tem nenhum). E é onde a sessão é salva para o **auto-unseal**: ligado por
padrão só para o token legado `apikey-` com `OPENBAO_ADDR` definida, desligado para um token de conta de serviço a
menos que `Diagnos(auto_unseal=True)` peça — [Sessões](sessions.pt-BR.md#auto-unseal-com-openbao) explica o que isso
troca.

| Variável | Padrão | O que faz |
|---|---|---|
| `OPENBAO_ADDR` | não definida | o servidor OpenBao; defini-la deixa o SDK ler o token ali, e liga o auto-unseal para o token legado |
| `OPENBAO_TOKEN` | não definida | um token restrito aos paths deste deployment, e nada mais amplo: *leitura* do token, leitura e escrita da sessão salva quando o auto-unseal está ligado (`apps/api/deploy/compose/openbao/policy.hcl`) |
| `OPENBAO_TOKEN_FILE` | não definida | um arquivo com esse token, lido quando `OPENBAO_TOKEN` não está definida — como Kubernetes e Compose montam segredos |
| `OPENBAO_MOUNT` | `secret` | o mount KV v2 |
| `OPENBAO_PATH_PREFIX` | `diagnos` | o token mora em `<prefixo>/token`, a sessão salva em `<prefixo>/<workspace_id>/<key_id>` |
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
monte um `Settings` você mesmo. Ele é imutável e o `repr` dele mostra a identidade do token e redige tudo que é
segredo:

```python
import os

from diagnos import Diagnos, DiagnosToken, Settings

settings = Settings(
    token=DiagnosToken.parse(os.environ["DIAGNOS_TOKEN"]),
    timeout_seconds=10,
    time_precision="day",
)
vault = Diagnos(settings=settings)
print(settings)  # token=DiagnosToken(identity='svc_…@ws_….diagnos.health', seed='<redacted>')
```

`Settings(...)` ignora o ambiente por inteiro, OpenBao e chaveiro inclusive: todo campo não informado fica com o
padrão. `Settings.from_env(mapping)` lê as mesmas variáveis de acima de qualquer mapeamento (e nunca o chaveiro), e
`Diagnos(token=…)` troca só a identidade enquanto todo o resto continua vindo do ambiente.

## A CLI e a API REST

- A **CLI** aceita `--token` e `--vault-url` em qualquer lugar da linha, sobrescrevendo toda fonte de token e o
  `DIAGNOS_VAULT_URL` para uma invocação; as outras flags globais estão no [guia da CLI](cli.pt-BR.md#opções-globais).
  Ela também lê `DIAGNOS_GROUP`, o security group sob o qual uma gravação sela quando `--group` não é dado; e, para o
  agente de sessão do token legado, `DIAGNOS_AGENT` (`off` mantém cada comando no próprio processo) e
  `DIAGNOS_AGENT_IDLE_MINUTES`, quanto tempo o agente espera sem comando antes de encerrar a sessão (padrão `480`) —
  veja [O token legado no terminal](cli.pt-BR.md#o-token-legado-no-terminal).
- A **API REST** lê o token como o SDK — do OpenBao num deployment — e acrescenta as próprias variáveis
  `DIAGNOS_API_*` — certificados, host, porta, nomes de cliente permitidos — listadas em
  [Implantação](../../apps/api/deploy/README.pt-BR.md#ambiente).
