# Compatibilidade com o cofre

[English](COMPATIBILITY.md) · **Português (Brasil)**

O que neste repositório funciona contra o cofre de hoje (`https://vault.diagnos.health`), o que ainda não funciona, e
por quê. Quem mantém isto honesto são os [testes de contrato](../contracts/README.pt-BR.md): uma interação só entra no
contrato quando o SDK já fala, para ela, o protocolo atual do cofre.

## Visão geral

| Área | Superfície do SDK | Situação | Verificado por |
|---|---|---|---|
| Relógio | `GET /time`, correção de skew | ✅ Compatível | contrato |
| Identidade | `DIAGNOS_API_TOKEN` (`apikey-<jwt>`), `Authorization: Bearer` | ✅ Compatível | contrato |
| Assinatura da requisição | `X-Signature-Timestamp` / `-Nonce` / `-Hmac` | ✅ Compatível | contrato + vetores |
| Enrollment | `session/registry` (registro, poll: pendente, aprovado, negado, expirado) | ✅ Compatível | contrato |
| Chaves de sessão | selo híbrido (X25519 + ML-KEM-768), `random_seed` | ✅ Compatível | contrato + vetores |
| Lock | `session/lock` | ✅ Compatível | contrato |
| Auto-unseal com OpenBao | salvar/restaurar a sessão desbloqueada | ✅ Só do lado do cliente | testes unitários |
| Pacientes, exames | `vault.patients`, `vault.exams` (documentos versionados) | ✅ Compatível | contrato + vetores do app web |
| Arquivos | `vault.drives` | ⚠️ Revisão anterior do protocolo | — |

A CLI (`diagnos-cli`) e a API (`diagnos-api`) são cascas finas sobre o SDK: todo comando e rota herda a sua linha.
Comandos e rotas de arquivos herdam o ⚠️.

"Verificado por contrato" significa que o lado do SDK está travado em
[`contracts/diagnos-sdk-diagnos-vault.json`](../contracts/diagnos-sdk-diagnos-vault.json) e o cofre o reproduz no
próprio repositório (verificação de provider). "Vetores do app web" significa que o SDK abre bytes selados pelo
próprio código do app web ([`document_content.json`](../apps/sdk/tests/vectors/document_content.json)) e os oráculos
do contrato os selam com uma implementação independente — um documento que o SDK grava é um que o app web abre, e
vice-versa.

## Pacientes e exames

O SDK segue o app web passo a passo:

- Um documento pertence a exatamente um security group (`security_group_id`). A chave de dados dele (DEK) é selada
  para esse grupo com o mesmo rótulo que o app web usa para todo documento.
- Gravar é reservar → `PUT` assinado → confirmar. Cada versão é selada sob a própria chave, derivada da DEK e do
  `security_context` que o cofre devolve junto da URL assinada; o corpo é `salt ‖ nonce ‖ ciphertext` cru. Paciente
  tem dois fluxos, então as rotas de versão dele levam `/streams/data`; as de exame não.
- Toda gravação leva o resumo selado (`encrypted_index`: nomes e tags, ou título, modalidade e data), então listas
  abrem sem baixar nenhuma versão — `vault.patients.list()` já os devolve decifrados.
- Ler segue a regra do app web: o rascunho do editor vence quando é mais novo que a versão corrente
  (`include_draft=False` lê só versões confirmadas).
- Arquivar e apagar são trocas de flag sem versão nova (`restore` desfaz um apagar).
- `expected_latest_version_id` faz o cofre recusar uma gravação se alguém salvou no meio-tempo; uma reserva que
  encontra a versão pendente de outro escritor é retentada por pouco tempo, depois lançada.

### Limites conhecidos

- **O fluxo `file` do paciente** (o documento rico do editor web, Lexical + Yjs) não é exposto; o SDK lê e grava o
  fluxo estruturado `data`.
- **Documentos de identidade** (`identifiers[].value`, ex.: CPF) são selados pela rota de dado sensível do cofre, que
  a API externa não oferece. O SDK carrega os valores existentes intactos num ler-modificar-gravar e recusa um valor
  em texto claro.
- **Precisão de anonimização**: o app web trunca toda data na `time_precision` do workspace antes de cifrar. A API
  externa não expõe essa configuração; defina `DIAGNOS_TIME_PRECISION` com o valor do workspace e o SDK aplica o mesmo
  truncamento.
- **Rascunhos** são lidos, nunca gravados: as gravações do SDK são versões confirmadas.
- **Modelos de laudo** não têm rota externa; existem só no app web.
- **SSE-C**: objetos de documento são guardados sem SSE-C, exatamente como o app web os guarda (uma segunda camada
  que só um lado mandasse tornaria o objeto ilegível para o outro). O corpo é cifrado ponta a ponta de qualquer jeito.

## Arquivos

A camada de arquivos do SDK foi escrita contra uma revisão anterior do protocolo do cofre:

- As rotas de drive saíram de `…/drives/{security_group_id}/…` para `…/nodes/…`, com `security_group_id` no corpo ou
  na query string.
- Todo arquivo ganha a própria chave de dados, embrulhada para cada security group em `encrypted_keys`; o nome do
  arquivo é cifrado sob essa chave, e as chaves de conteúdo são derivadas pelo mesmo esquema de `security_context` dos
  documentos.

Não use `vault.drives` contra o cofre de produção ainda. As chamadas dele falham alto — um erro de validação, um `400`
ou um `404` — antes de qualquer coisa ser gravada, então nenhum dado que o app web não conseguiria ler é escrito.

## O caminho de volta ao verde

1. ~~Documentos~~ — feito: rotas e modelos atuais, vetores do app web, interações de contrato.
2. Arquivos: rotas `/nodes`, chave por arquivo, nomes cifrados, chaves de conteúdo por `security_context`.
3. Entropia: contribuir com o `random_seed` do próprio SDK no corpo das requisições (o cofre já aceita; hoje o SDK só
   consome o do cofre).

Acompanhe no [issue tracker](https://github.com/diagnos-tech/integration/issues).
