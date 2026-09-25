# Testes de contrato · SDK ↔ cofre

[English](README.md) · **Português (Brasil)**

Esta é a suíte de testes de contrato entre o SDK `diagnos` (o consumidor) e o cofre (o provider). Ela roda o SDK de
verdade contra um mock server local do Pact e registra exatamente o HTTP que o SDK mandou e esperou, como
`diagnos-sdk-diagnos-vault.json` — o arquivo que a própria CI do cofre reproduz e verifica antes de implantar.

## O que é teste de contrato guiado pelo consumidor

Num contrato guiado pelo consumidor, o *consumidor* de uma API (aqui, o SDK) escreve testes que exercitam o próprio
código de cliente contra um mock do *provider* (o cofre), e esses testes geram um arquivo de contrato descrevendo
cada interação: a requisição que o consumidor manda e a forma de resposta de que ele precisa de volta. O provider
então reproduz esse mesmo arquivo contra a implementação de verdade dele ("verificação do provider") para provar que
atende a todo consumidor que depende dele. O contrato é gerado a partir dos testes do consumidor, não escrito à mão
— é isso que "guiado pelo consumidor" significa, e é por isso que ele não pode divergir do que o SDK de fato faz: o
arquivo é subproduto de testes que falham se o comportamento real do SDK discordar dele.

## O que esta suíte prova, e o que ela não prova

- **Esta suíte prova**: que o SDK manda exatamente as requisições que `diagnos-sdk-diagnos-vault.json` descreve, e lê
  com sucesso exatamente as respostas que ele descreve. Todo teste em `contracts/tests` exercita código real do SDK
  (`VaultTransport`, `enroll()`, `SessionManager.lock()`) contra o mock server do Pact, que reprova o teste se o SDK
  mandar uma requisição que nenhuma interação descreve, ou se uma interação nunca for exercitada.
- **Esta suíte não prova**: que o cofre de fato se comporta assim. Essa metade — a "verificação do provider" — roda
  no próprio repositório (privado) do cofre, que vendoriza este arquivo de contrato e o reproduz contra um cofre de
  verdade, com um manipulador de provider state que semeia o dado que o `providerStates` de cada interação exige. Se
  o comportamento do cofre e este contrato discordarem, a verificação do provider falha lá, não aqui.
- **Não há broker do Pact** nesta configuração. O contrato viaja como um arquivo JSON commitado
  (`contracts/diagnos-sdk-diagnos-vault.json`), não por um serviço de broker; o repositório do cofre o obtém
  vendorizando este aqui (diretamente, ou por qualquer mecanismo que aquele repositório documenta).

## Como rodar

```sh
make contract         # roda a suíte; numa rodada completa e aprovada, regera o contrato commitado
make contract-check   # roda a suíte e falha se o contrato regenerado diferir do commitado
```

`make contract` é o que você roda depois de mudar o comportamento HTTP do SDK ou adicionar uma interação, antes de
commitar. `make contract-check` é o que a CI roda (`.github/workflows/contract-tests.yml`) — nunca reescreve o
arquivo, só compara.

## Como funciona o determinismo

Um arquivo Pact registra os *exemplos* concretos com que cada interação foi definida, não só a forma deles — e
vários desses exemplos (uma sessão selada, uma chave de grupo selada, um `random_seed`) são ciphertext de verdade
que o SDK precisa de fato decifrar. Se esse ciphertext fosse produzido com aleatoriedade real, o arquivo de contrato
mudaria a cada rodada mesmo sem nada no comportamento do SDK ter mudado. Três coisas mantêm isso estável:

1. **Oráculos de cripto com rótulo fixo** (`contracts/tests/_crypto.py`). Toda entrada aleatória que o protocolo
   normalmente sorteia (secreta X25519 efêmera, moeda do encapsulamento ML-KEM, salt do HKDF, nonce do AES-GCM) é
   derivada deterministicamente de um rótulo de string fixo com SHA-256 (`fixed_bytes(label)`), usando
   implementações independentes (`pynacl`, `kyber-py`, `cryptography` — não o próprio enclave Rust do SDK), então um
   teste de contrato que passa também confere o enclave contra uma segunda implementação do formato de fio. **Isto é
   um oráculo de teste, nunca um padrão a copiar**: reusar um nonce sob uma chave de verdade em código de produção é
   exatamente o que o SDK foi feito para nunca fazer.
2. **Normalização** (`contracts/tests/conftest.py::normalize`). A saída crua do Pact inclui metadados de ferramenta
   (`metadata.pactRust`, qual build do `pact_ffi` gravou o arquivo) e interações na ordem em que os testes rodaram.
   A normalização descarta os metadados de ferramenta e ordena as interações por `(description, providerStates)`,
   então o arquivo commitado é uma função pura das interações em si — uma atualização de dependência ou um arquivo
   de teste reordenado nunca produz diff.
3. **Rodadas parciais nunca reescrevem o arquivo.** `pytest_sessionfinish` só grava (ou, com `--contract-check`,
   compara) quando a rodada foi a suíte completa e todo teste passou (`_is_partial_run` verifica `-k`, `-m`, `--lf`,
   ou um path restrito). Rode um arquivo só, ou uma expressão `-k`, durante o desenvolvimento sem medo de sobrescrever
   o contrato commitado com uma visão parcial dele.

## Matchers vs. literais: as duas regras

Direto da docstring de módulo de `_wire.py`, porque são o ponto inteiro de um contrato guiado pelo consumidor:

1. **Só o que o SDK lê entra numa resposta.** O cofre pode mandar mais — o Pact aceita chave a mais num corpo de
   resposta — mas o contrato trava exatamente o que quebraria o SDK, nada que ele só tolera.
2. **Um valor é literal quando o SDK decide com base nele, matcher quando só a forma importa.**
   `"status": "approved"`, `"mode": "single"`, `"success": true` são literais — um valor de enum renomeado é um SDK
   quebrado. Ids, timestamps e ciphertext são matchers (regex/tipo) — um id diferente vindo do cofre de verdade não
   é um SDK quebrado.

## Provider states e geradores de path

Toda interação que precisa do cofre numa condição específica declara uma entrada `providerStates`: um nome mais
parâmetros. A verificação do provider, do lado do cofre, roda um manipulador de state associado a esse nome exato
antes de reproduzir a interação, e é responsável por semear o que aquele state exige. `workspace_state()`
(`_wire.py`) sempre acrescenta `workspace_id`, já que quase todo path é restrito a um workspace.

Paths de requisição que embutem esses mesmos valores usam `path(example, pattern=..., expression=...)`
(`_wire.py`): `pattern` é o matcher regex que o lado consumidor confere contra o path, e `expression` é um gerador
`ProviderState` do Pact — um template com marcadores `${nome}` que o manipulador de state do cofre preenche com os
ids *reais* que acabou de semear, para a verificação exercitar o próprio workspace e enrollment do cofre em vez de
adivinhar os fixos do consumidor (`ws-contract`, `enr-contract`, `pat-contract`). Os marcadores em uso atualmente:

- `${workspace_id}` — todo path sob `/api/external/v1/workspaces/{workspace_id}/...`.
- `${enrollment_id}` — o path de poll de enrollment,
  `/api/external/v1/workspaces/{workspace_id}/session/registry/{enrollment_id}`.
- `${document_id}` — todo path sob `…/patients/{document_id}` e `…/exams/{document_id}`.
- `${version_id}` — o path de commit, `…/versions/{version_id}/commit`, e o `expected_latest_version_id` que uma
  reserva com trava de conflito manda.
- `${node_id}` — `…/nodes/{node_id}`, e `node_ids[0]` na confirmação de um upload.
- `${parent_id}` — o parâmetro de query `parent_id` da listagem de uma pasta.

Um valor fora do path (um campo de corpo, um parâmetro de query) é marcado com `from_state(example, name)`
(`_wire.py`).

Os states de documento e de arquivo também levam `security_group_id` (`sg-contract`): ele é a chave de
`encrypted_keys` em toda reserva, que nenhum gerador consegue reescrever, então o cofre concede à service account
esse grupo literal.

Todo nome de provider state no contrato atual, e o que o cofre precisa semear para cada um:

| Provider state | Parâmetros | O cofre precisa semear |
|---|---|---|
| `a service account can enroll an SDK session` | `workspace_id` | Um workspace e um token de service account capaz de registrar chaves públicas híbridas em `session/registry`. |
| `an admin approved the enrollment for one security group` | `workspace_id`, `enrollment_id` | Um enrollment pendente que um admin aprovou, com a DEK de ao menos um security group selada para as chaves públicas que o SDK registrou. |
| `an enrollment is waiting for an admin` | `workspace_id`, `enrollment_id` | Um enrollment que existe mas ainda não foi aprovado nem negado — `GET` nele devolve `"status": "pending"`. |
| `an admin denied the enrollment` | `workspace_id`, `enrollment_id` | Um enrollment que um admin negou explicitamente — `GET` nele devolve `"status": "denied"`. |
| `the vault no longer knows the enrollment` | `workspace_id`, `enrollment_id` | Nenhum enrollment naquele id (expirado e varrido, ou nunca existiu) — `GET` nele devolve `404`. |
| `an SDK session is active` | `workspace_id` | Uma sessão ativa e assinada, para a qual o cofre aceitará uma requisição `session/lock`. |
| `the SDK session holds the key of a security group` | `workspace_id`, `security_group_id` | Uma sessão ativa cuja service account pertence a `security_group_id` e pode criar pacientes, exames e arquivos nele, com orçamento de armazenamento. |
| `a patient has an uploaded version waiting to be committed` | `workspace_id`, `security_group_id`, `document_id`, `version_id` | Um paciente nesse grupo com `version_id` reservada no fluxo `data` e o objeto já enviado, para o commit encontrá-lo. |
| `an exam has an uploaded version waiting to be committed` | `workspace_id`, `security_group_id`, `document_id`, `version_id` | O mesmo para um exame (sem segmento de fluxo nas rotas); `meta.patient_id` definido. |
| `a patient has one committed version` | `workspace_id`, `security_group_id`, `document_id`, `version_id` | Um paciente nesse grupo com uma versão `data` confirmada (`version_id`), um `encrypted_index`, sem versão pendente e sem rascunho; o único paciente vivo que a service account consegue listar (a interação de lista lê uma página em que toda linha tem essa forma). |
| `a patient has a draft newer than its latest version` | `workspace_id`, `security_group_id`, `document_id`, `version_id` | Como acima, mais uma cabeça de rascunho em `data` cujo `updated_at` é posterior ao `created_at` da versão corrente. |
| `a patient has a committed version and another one pending` | `workspace_id`, `security_group_id`, `document_id`, `version_id` | Uma versão `data` confirmada mais uma reserva pendente não expirada, para uma reserva nova responder `409 DocumentVersionPending`. |
| `an exam has one committed version` | `workspace_id`, `security_group_id`, `document_id`, `version_id` | Um exame nesse grupo com uma versão confirmada, um `encrypted_index` e `meta.patient_id`. |
| `a file was uploaded and awaits confirmation` | `workspace_id`, `security_group_id`, `node_id` | Um nó de arquivo em modo single, reservado pela service account nesse grupo com um `mime_type`, ainda `pending`, cujo objeto já está no R2 — para `uploads/complete` reportá-lo `ready`. |
| `a folder holds one ready file` | `workspace_id`, `security_group_id`, `parent_id`, `node_id` | Uma pasta (`parent_id`) nesse grupo com exatamente um nó: um arquivo pronto em modo single, com `mime_type` e `size`. |

## Como adicionar uma interação, passo a passo

1. **Escolha ou crie um arquivo de teste** em `contracts/tests/` para a área de comportamento (`test_clock.py`,
   `test_session.py`, ou um novo `test_<area>.py` para uma superfície nova).
2. **Declare a interação** na fixture `pact`: `pact.upon_receiving("uma descrição em inglês simples")`, depois
   `.given(nome_do_state, params)` se precisar de provider state (use `workspace_state()` de `_wire.py` para sempre
   levar `workspace_id`), `.with_request(...)`, `.with_headers(...)` (reaproveite `bearer_header()` /
   `signed_headers()` de `_wire.py`), `.with_body(...)`, `.will_respond_with(status)`, `.with_body(...)` para a
   resposta.
3. **Aplique as regras de matcher/literal acima** a todo campo do corpo de resposta: `match.regex`/`match.str`/
   `match.int`/`match.each_like` para campos onde só a forma importa, um valor puro ou `literal(...)` (`_wire.py`)
   para o que o SDK decide com base nele.
4. **Exercite código real do SDK** contra o mock server do `pact.serve()` — monte um transporte com
   `make_transport()` (`conftest.py`) ou chame a função/método de nível mais alto sob teste (`enroll()`,
   `SessionManager.lock()`, um novo método de recurso) — nunca HTTP escrito à mão via `httpx` direto contra o mock
   server.
5. **Faça a asserção sobre o retorno do SDK**, não sobre o HTTP cru — o ponto é que o SDK interpretou corretamente
   o que o contrato diz que o cofre manda.
6. **Rode `make contract`.** Se o teste passar e a suíte inteira passar, `contracts/diagnos-sdk-diagnos-vault.json`
   é regenerado com sua interação incluída, normalizada e ordenada junto com as demais.
7. **Faça commit do arquivo regenerado junto com o teste.** O `make contract-check` da CI reprova um PR que muda o
   comportamento HTTP do SDK sem uma mudança de contrato correspondente (veja [`../CONTRIBUTING.pt-BR.md`](../CONTRIBUTING.pt-BR.md)).

## Como ler um diff de contrato num pull request

O arquivo é ordenado e normalizado, então um diff é significativo, não ruído de reordenação. Ao revisar um, confira:

- **Uma interação nova** (bloco novo de `description`/`providerStates`): o teste do PR justifica isso, e o nome do
  provider state soa como algo que o manipulador de state do cofre consegue plausivelmente semear? Se for
  genuinamente um nome de state novo, o lado do cofre precisa de um manipulador correspondente antes que a
  verificação passe lá — sinalize isso no PR.
- **Uma regex de `matchingRules` alterada, ou um valor literal alterado**: é o sinal de que o SDK agora exige uma
  forma diferente ou decide com base num literal diferente de antes — deveria remeter a uma mudança correspondente
  no código do SDK no mesmo PR, não aparecer sozinho.
- **Um campo do corpo de resposta desaparecendo**: o SDK parou de lê-lo. Confirme que isso é intencional (código
  morto removido) e não um campo de que o SDK ainda precisa mas o teste deixou de afirmar.
- **Um diff no formato de `pactRust`/versão de ferramenta**: não deveria acontecer — a normalização remove
  `metadata.pactRust` especificamente para evitar isso. Se você ver um, algo passou por cima de
  `normalize()`/`render()`.

## Escopo atual, e o que não está aqui

O contrato cobre: o relógio do cofre (`GET /time`); enrollment (registro, e poll através de
pending/approved/denied/forgotten); lock (`POST session/lock`); documentos versionados — criar paciente ou exame
(reservar, confirmar), abrir a versão corrente, preferir um rascunho mais novo, reservar a próxima versão sob a trava
de conflito, arquivar sem versão nova, listar, e recuar diante de uma versão pendente; e arquivos — reservar um
arquivo, confirmá-lo, ler um arquivo pronto (o nome selado, o corpo e a chave de SSE-C que o armazenamento exige),
listar os arquivos de um grupo e criar uma pasta.

**Uploads multipart não estão aqui.** O cofre os abre, conclui e aborta pelo endpoint S3 do R2, e a verificação do
provider roda um `wrangler dev` local sem esse endpoint, então essas interações não poderiam ser verificadas lá. Os
testes unitários do SDK as cobrem contra um dublê das rotas do cofre (`apps/sdk/tests/resources/vault_double.py`);
elas entram no contrato quando o provider tiver um dublê de S3. Veja
[`../docs/COMPATIBILITY.pt-BR.md`](../docs/COMPATIBILITY.pt-BR.md).
