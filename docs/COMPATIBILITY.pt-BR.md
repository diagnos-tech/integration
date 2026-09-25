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
| Arquivos e pastas | `vault.drives` (`/nodes`: reservar, `PUT`, confirmar, multipart, listar, ler, pastas) | ✅ Compatível | contrato + vetores do app web |

A CLI (`diagnos-cli`) e a API (`diagnos-api`) são cascas finas sobre o SDK: todo comando e rota herda a sua linha.

"Verificado por contrato" significa que o lado do SDK está travado em
[`contracts/diagnos-sdk-diagnos-vault.json`](../contracts/diagnos-sdk-diagnos-vault.json) e o cofre o reproduz no
próprio repositório (verificação de provider). "Vetores do app web" significa que o SDK abre bytes selados pelo
próprio código do app web ([`document_content.json`](../apps/sdk/tests/vectors/document_content.json),
[`node_content.json`](../apps/sdk/tests/vectors/node_content.json)) e os oráculos do contrato os selam com uma
implementação independente — o que o SDK grava é o que o app web abre, e vice-versa.

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

## Arquivos e pastas

`vault.drives` segue o pipeline de upload do app web (`@repo/magic-files`) passo a passo:

- Todo arquivo e toda pasta é um nó com a própria chave de dados, embrulhada para o security group dele; o nome é
  selado sob essa chave.
- O corpo é secretstream da libsodium em frames de 1 MiB, sob uma chave derivada da chave do nó e do
  `security_context` que o cofre devolve na reserva. O tamanho é calculado antes de cifrar, e o cofre assina o
  upload para exatamente esse tamanho.
- Até 100 arquivos por reserva. Arquivos de até 64 MiB sobem cada um num `PUT` assinado e são confirmados juntos;
  os maiores sobem em partes de 32 MiB, assinadas em ondas de até 200 conforme o upload avança, e são abortados em
  caso de falha, para o cofre liberar na hora os bytes reservados.
- A camada SSE-C do R2 usa a chave do app web (a irmã da chave de conteúdo) no `PUT`, em toda parte e no `GET`.
- Pastas: `create_folder`, e `parent_id` no upload e na listagem.
- Ler precisa só do id do nó: o nome, o conteúdo e a chave de SSE-C abrem todos com a chave do grupo.

O contrato trava reservar → `PUT` → confirmar, ler + baixar, listar e criar pasta. Uploads multipart são cobertos
por testes unitários contra um dublê das rotas do cofre: o cofre os abre e fecha pelo endpoint S3 do R2, que a
verificação do provider (um `wrangler dev` local) não tem.

### Limites conhecidos

- **Variantes otimizadas** (miniaturas, transcodificações para a web) só são produzidas pelo cofre quando a chave
  do nó também está em escrow para o processador de mídia (`system:smartlake:v1` em `encrypted_keys`). O app web
  não manda esse escrow hoje e o SDK também não, então nenhum dos dois ganha variantes; `optimized_variants` é
  reportado como o cofre devolve.
- **Apagar, mover e renomear** ainda não têm rota externa.
- **Progresso de upload**: `upload_many` bloqueia por lote de 100; ainda não há callback de progresso por byte.
- **Nomes são caminhos**: o app web sela um caminho relativo como nome do arquivo. A CLI e a API só usam o último
  segmento dele como nome de arquivo local.

### Em aberto do lado do cofre

Nenhum destes muda um byte do que o SDK manda. São questões para o cofre, registradas para ninguém precisar
redescobri-las:

- **Headers de SSE-C sem assinatura.** O cofre assina só `content-length` (e `content-type`) e deixa os headers de
  SSE-C fora da assinatura de propósito, já que assiná-los exigiria conhecer a chave. O próprio `TODO` dele pergunta
  se o R2 aceita headers `x-amz-server-side-encryption-*` não assinados numa URL pré-assinada; se não aceitar, o
  plano é abandonar o SSE-C. Enquanto isso, o código de upload do app web exige que esses headers *estejam*
  assinados e para antes de enviar. Um dos dois vai mudar; o SDK manda o que o cofre documenta hoje e vai seguir o
  desfecho.
- **SSE-C no multipart.** As partes vão com SSE-C, como o app web faz, mas o cofre abre uploads multipart sem
  parâmetros de SSE-C. A semântica do S3 espera que os dois concordem; isto precisa ser confirmado contra o R2 para
  arquivos acima de 64 MiB.
- **O visualizador web** ainda não lê nós (`fileViewer.ts`). A interoperabilidade está provada no nível dos bytes —
  vetores gerados pelo código de upload do app web — e não pelo visualizador.

## O que vem a seguir

1. ~~Documentos~~ — feito: rotas e modelos atuais, vetores do app web, interações de contrato.
2. ~~Arquivos~~ — feito: rotas `/nodes`, chave por arquivo, nomes selados, chaves de conteúdo por
   `security_context`, SSE-C, pastas.
3. Multipart no contrato, quando a verificação do provider tiver um dublê de S3 para o R2.
4. Entropia: contribuir o `random_seed` do próprio SDK nos corpos de requisição (o cofre já aceita; hoje o SDK só
   consome o do cofre).

Acompanhe no [issue tracker](https://github.com/diagnos-tech/integration/issues).
