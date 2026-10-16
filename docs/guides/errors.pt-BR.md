# Erros

[English](errors.md) · **Português (Brasil)**

Toda exceção que o SDK lança pode ser importada de `diagnos`, e cada uma nomeia uma decisão que você precisa tomar:
corrigir a entrada, esperar, guardar o token de novo, pedir a um admin, ou reportar um bug. Capture por classe, nunca por
mensagem — mensagens são para pessoas e podem mudar; classes e `code`s são o contrato. A CLI e a API REST traduzem as
mesmas classes em códigos de saída e status HTTP, então esta página é a tabela única para os três.

## A hierarquia

```mermaid
classDiagram
    DiagnosError <|-- ConfigError
    ConfigError <|-- TokenError
    ConfigError <|-- TokenStoreError
    DiagnosError <|-- EnrollmentDeniedError
    DiagnosError <|-- EnrollmentExpiredError
    DiagnosError <|-- SessionExpiredError
    DiagnosError <|-- GroupKeyUnavailable
    DiagnosError <|-- CryptoError
    DiagnosError <|-- ProtocolError
    DiagnosError <|-- VaultError
    VaultError <|-- ValidationError
    VaultError <|-- AuthenticationError
    VaultError <|-- QuotaError
    VaultError <|-- DiagnosPermissionError
    VaultError <|-- NotFoundError
    VaultError <|-- ConflictError
    VaultError <|-- RateLimitError
    VaultError <|-- CredentialError
    CredentialError <|-- CredentialSignatureError
    CredentialError <|-- CredentialReplayError
    CredentialError <|-- ClockSkewError
    CredentialError <|-- CredentialRevokedError
    CredentialError <|-- CredentialExpiredError
    CredentialError <|-- CredentialUnknownError
    CredentialError <|-- WorkspaceMismatchError
    CredentialError <|-- ScopeMissingError
```

`VaultError` e as subclasses significam *o cofre respondeu com um erro*; carregam o `code` do cofre, o `status` HTTP,
e o `trace_id` e o `request_id` de que um chamado de suporte precisa. Todo o resto sob `DiagnosError` é decidido
localmente, antes ou depois de falar com o cofre. `TokenError` e `TokenStoreError` são decididos antes de qualquer
chamada de rede: um token colado errado, ou nenhum lugar seguro para guardar um. `CredentialError` e as subclasses são
o cofre recusando o próprio token da service account; cada uma é *também* um `AuthenticationError` (401) ou um `DiagnosPermissionError`
(403), então o código que captura os pais continua funcionando — veja [Falhas de credencial](#falhas-de-credencial).

## Toda exceção

| Classe | Lançada quando | O que fazer | Saída da CLI | Status da API |
|---|---|---|---|---|
| `ConfigError` | nenhum token no `DIAGNOS_TOKEN`, no chaveiro do sistema ou no OpenBao (nem o `DIAGNOS_API_TOKEN` legado); uma variável de ambiente inválida; OpenBao configurado sem o extra `openbao`, negado ou inalcançável | corrija a configuração; a mensagem diz onde procurou | `2` | sai com `2` na subida |
| `TokenError` | o texto não é um token de conta de serviço: prefixo errado, cortado ou colado errado (o CRC não confere), um workspace ruim — `reason` diz qual | copie o token de novo, inteiro, de onde ele foi guardado | `2` | sai com `2` na subida |
| `TokenStoreError` | o `diagnos login` / `save_token` não achou lugar seguro: nenhum chaveiro que cifra em repouso e nenhum OpenBao | use um chaveiro seguro, ou configure o OpenBao; `DIAGNOS_TOKEN` em CI | `2` | — |
| `EnrollmentDeniedError` | só token legado: um admin negou o enrollment | nada a retentar — pergunte o motivo | `3` | a subida falha |
| `EnrollmentExpiredError` | só token legado: ninguém aprovou antes de `expires_at` | rode de novo para um link e um código novos | `3` | a subida falha |
| `SessionExpiredError` | uma chamada assinada sem sessão viva | `unlock()` de novo (as chamadas de recurso fazem isso por você) | `3` | `401` `session_expired` |
| `GroupKeyUnavailable` | o security group do dado não está no escopo do token | um token novo que o inclua | `3` | `403` `group_key_unavailable` |
| `CryptoError` | um envelope não abriu: chave errada ou bytes adulterados, indistinguíveis de propósito | não retente; reporte | `1` | `500` `crypto_error` |
| `ProtocolError` | o cofre respondeu algo que o protocolo não permite | não retente; reporte com a versão do SDK, ou atualize | `1` | `502` `protocol_error` |
| `ValidationError` | o cofre recusou a requisição como inválida (400, 413) | corrija a entrada | `1` | `400` |
| `AuthenticationError` | token, sessão ou assinatura recusados (401) | confira o token; o token legado refaz o enrollment | `3` | `401` |
| `QuotaError` | o workspace não tem crédito para isto (402); nada foi feito | compre crédito, ou espere o orçamento | `5` | `402` |
| `DiagnosPermissionError` | esta service account não pode fazer isto aqui (403), inclusive o token de outro workspace ou uma permissão faltando | peça a um admin | `3` | `403` |
| `NotFoundError` | documento, versão ou arquivo inexistente (404) | confira o id | `4` | `404` |
| `ConflictError` | uma versão pendente ou mais nova, um replay, ou um upload que não chegou ao armazenamento (409) | leia de novo e combine, ou suba de novo | `7` | `409` |
| `RateLimitError` | ainda com limite de taxa depois do backoff do próprio SDK (429) | vá mais devagar; tente depois | `6` | `429` |
| `VaultError` | qualquer outro erro do cofre — um 5xx depois de uma retentativa, ou uma resposta que não era JSON (`InvalidResponse`) | tente depois; reporte com o `trace_id` se persistir | `1` | `502` |

Qual `code` do cofre vira qual classe — `DocumentVersionMismatch`, `QuotaExceeded`, `ServiceAccountRevoked` e o resto
— é normativo, e mora no [PROTOCOL.pt-BR.md §12](../PROTOCOL.pt-BR.md#12-erros).

Três falhas não são `DiagnosError`s, porque são erros de programação pegos antes de qualquer coisa ser enviada:

| Exceção | Quando |
|---|---|
| `pydantic.ValidationError` | um registro com um campo digitado errado ou inválido — veja [Pacientes](patients.pt-BR.md#erros-de-digitação-são-recusados-campos-desconhecidos-são-mantidos) |
| `TypeError` | `security_group` passado como lista — um documento pertence a exatamente um grupo |
| `ValueError` | um `datetime` sem fuso, uma data ilegível, um upload de `bytes` sem `name` |

`MemoryLockWarning` é um aviso, não um erro: o SO recusou travar uma chave na RAM, e o processo segue com toda outra
proteção. `DIAGNOS_MEMORY_LOCK=require` o transforma numa falha dura — veja
[Configuração](configuration.pt-BR.md#memória-e-hardening-do-processo).

## O que o SDK já retenta

Antes de envolver uma chamada num laço de retentativa: o SDK já retenta tudo que é seguro retentar, com uma
assinatura nova a cada vez, e só lança quando retentar deixou de fazer sentido.

| Condição | O que o SDK faz | Depois lança |
|---|---|---|
| a primeira requisição assinada de um processo | sincroniza o relógio com `GET /time` (mediana de três) | — |
| `401 SignatureTimestampSkew` | ressincroniza o relógio, retenta uma vez | `AuthenticationError` |
| `401 CredentialClockSkew` | ressincroniza o relógio, retenta uma vez | `ClockSkewError` |
| `401 CredentialReplayed` | nada: a primeira cópia pode ter passado | `CredentialReplayError` |
| `401 SessionNotFound` | abre uma sessão nova com o token e retenta uma vez (não com o token legado) | `AuthenticationError` |
| `409 ReplayDetected` | retenta uma vez com um nonce novo | `ConflictError` |
| `429` | espera o `Retry-After` se veio, senão 0,5 s, 1 s, 2 s com jitter — três retentativas | `RateLimitError` |
| qualquer `5xx` | uma retentativa depois de 1 s | `VaultError` |
| `409 DocumentVersionPending` numa gravação | outro escritor segura o slot: retenta depois de 1,5 s e 3 s | `ConflictError` |
| um commit perdido na rede ou para um `5xx` | repete depois de 0,5 s e 1 s — commits são idempotentes | `VaultError` |
| um upload multipart que falha no meio | aborta, para o cofre liberar o espaço | o erro original |

Um conflito é uma classe com muitas causas; `code` diz qual. O que sobra para você: `ConflictError` com
`DocumentVersionMismatch` significa *alguém salvou no meio-tempo* — leia de novo, combine, grave de novo
([exemplo](patients.pt-BR.md#gravações-concorrentes-seguras)). `ConflictError` com `UploadIncomplete` significa que os
bytes de um arquivo nunca chegaram ao armazenamento — suba aquele arquivo de novo. `RateLimitError` e `VaultError`
valem mais uma tentativa depois de uma pausa maior.

## Falhas de credencial

O token da service account assina toda requisição — Ed25519 e ML-DSA-65 — e o cofre confere as duas assinaturas
antes de olhar qualquer outra coisa. Quando ele recusa, o SDK lança a classe abaixo e acrescenta o que fazer à mensagem do cofre, então um traceback
às 3 da manhã basta. Capture a classe específica sobre a qual você pode agir, depois `CredentialError` para o resto —
a ordem importa, porque cada uma é também um `AuthenticationError` ou um `DiagnosPermissionError`.

| Classe | `code` do cofre | Também | Significado | O que fazer |
|---|---|---|---|---|
| `CredentialSignatureError` | `CredentialSignatureInvalid` | `AuthenticationError` | uma assinatura não confere | guarde o token de novo (`diagnos login`); procure um proxy que altere requisições |
| `CredentialReplayError` | `CredentialReplayed` | `AuthenticationError` | o cofre já viu este nonce | algo reenviou a requisição; o SDK não a retenta |
| `ClockSkewError` | `CredentialClockSkew` | `AuthenticationError` | este relógio está fora de ±60 s | ative o NTP; `skew_seconds` e `server_time` dizem por quanto |
| `CredentialRevokedError` | `CredentialKeyRevoked` | `AuthenticationError` | um admin revogou este token | crie um token novo e guarde-o |
| `CredentialExpiredError` | `CredentialKeyExpired` | `AuthenticationError` | o token passou da validade | crie um token novo e guarde-o |
| `CredentialUnknownError` | `CredentialKeyUnknown` | `AuthenticationError` | o cofre não conhece esta chave | confira se `DIAGNOS_VAULT_URL` aponta para onde o token foi criado |
| `WorkspaceMismatchError` | `CredentialWorkspaceMismatch` | `DiagnosPermissionError` | o token é de outro workspace | use o token do workspace de destino |
| `ScopeMissingError` | `CredentialScopeMissing` | `DiagnosPermissionError` | falta uma permissão ao token | peça a um admin um token novo com ela; `resource`, `action` e `security_group_id` a nomeiam |

```python
from diagnos import ClockSkewError, CredentialError, Diagnos, ScopeMissingError

vault = Diagnos()
try:
    vault.patients.list()
except ClockSkewError as error:  # as classes mais específicas primeiro
    print(f"este relógio está {error.skew_seconds} s fora do cofre ({error.server_time})")
except ScopeMissingError as error:
    print("falta", error.action, "em", error.resource, "no grupo", error.security_group_id)
except CredentialError as error:  # revogada, expirada, desconhecida, outro workspace, assinatura ruim…
    print("token recusado:", error)
```

O [`examples/05-error-handling`](../../examples/05-error-handling/README.pt-BR.md) transforma cada classe desta
página numa mensagem que diz o que fazer.

## Diferença de relógio

Toda requisição assinada carrega um horário que o cofre só aceita dentro de ±60 segundos (a assinatura do token)
ou ±120 segundos (a assinatura da sessão) do próprio relógio. Um notebook com relógio errado ou um container sem NTP
assinaria toda requisição rumo a uma recusa, então o SDK mede a diferença contra o cofre antes da primeira chamada
assinada e a aplica a toda assinatura, e ressincroniza uma vez se o cofre ainda reclamar. Quando nem isso resolve,
lança `ClockSkewError`, cujo `skew_seconds` é a hora local menos a do cofre (positivo: adiantado). Você não configura
nada disso.

> [!NOTE]
> A diferença corrige só as assinaturas. A expiração da sessão é julgada pelo relógio local, então um relógio horas
> fora faz as sessões parecerem expiradas cedo ou tarde demais. Mantenha o NTP rodando em tudo que guarda uma sessão.

## Lendo um erro

```python
from diagnos import Diagnos, NotFoundError, VaultError

vault = Diagnos()
try:
    vault.patients.get("pat_nao_existe")
except NotFoundError as error:
    print(error.code, error.status)  # DocumentNotFound 404
except VaultError as error:
    print("erro do cofre", error.code, error.status, error.trace_id, error.request_id)
```

Logue `code`, `status`, `trace_id` e `request_id` — nunca o registro que você estava gravando. O `trace_id` é o que o
suporte do diagnos precisa para achar o evento do lado do cofre.

## Na CLI e na API REST

A CLI imprime em `stderr` um rótulo bilíngue de uma linha e a mensagem, e sai com o código da tabela acima — `0` no
sucesso. Decida pelo código de saída em scripts; nunca faça grep no texto:

```sh
diagnos --quiet patients get "$PATIENT_ID" > patient.txt
case $? in
  0) echo "ok" ;;
  3) echo "confira o token, ou peça acesso a um admin" ;;
  4) echo "paciente inexistente" ;;
  *) echo "falhou" ;;
esac
```

Um problema de arquivo local — um `-o` para um diretório que não existe, um upload ilegível — não é um
`DiagnosError`: a CLI imprime `I/O error` e sai com `1`, nunca um traceback.

A API REST responde todo não-2xx com um envelope só, cujo `code` é o do próprio cofre quando a falha veio do cofre:

```json
{ "error": { "code": "DocumentNotFound", "message": "…", "trace_id": "…" } }
```

Além dos status da tabela, ela responde `422` (`invalid_request`) para um corpo ou query que falha na validação,
`401` (`client_certificate_required`) e `403` (`client_certificate_cn_not_allowed`) para falhas de TLS mútuo, e
`404`/`405` para rota ou método desconhecidos — sempre no mesmo envelope. A [referência da
API](../reference/openapi.json) os documenta por rota.
