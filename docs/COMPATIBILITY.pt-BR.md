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
| Pacientes, exames | `vault.patients`, `vault.exams` (documentos versionados) | ⚠️ Revisão anterior do protocolo | — |
| Arquivos | `vault.drives` | ⚠️ Revisão anterior do protocolo | — |

A CLI (`diagnos-cli`) e a API (`diagnos-api`) são cascas finas sobre o SDK: `login`, `status` e os comandos de sessão
funcionam hoje; comandos e rotas de pacientes, exames e arquivos herdam as linhas ⚠️.

As primitivas criptográficas em si não são o problema: a suíte do SDK passa contra vetores regerados agora mesmo a
partir da implementação de referência do cofre (assinatura de requisição, envelope de chave, envelope de conteúdo,
selo híbrido, framing do secretstream). O que mudou foi como o cofre *compõe* essas primitivas para documentos e
arquivos.

## O que mudou no cofre

As camadas de documentos e de arquivos do SDK foram escritas contra uma revisão anterior do protocolo do cofre. Desde
então o cofre mudou de formas que não são renomeações:

**Documentos versionados (pacientes, exames)**

- Um documento pertence a exatamente um security group: `security_group_id` (uma string) substituiu `security_groups`
  (uma lista), nas requisições e no índice.
- O estado das versões foi para `document.streams.<fluxo>` (`latest_version_id`, `versions`, `pending_version_id`).
  Paciente tem dois fluxos (`data`, `file`), então as rotas de versão dele ganharam um segmento:
  `…/{document_id}/streams/{fluxo}/versions[/{version_id}/commit]`.
- Criar um paciente exige um `encrypted_index`: um resumo pequeno cifrado sob a chave do documento, para listagem e
  busca nunca abrirem a ficha inteira.
- O conteúdo de cada versão é cifrado sob uma chave por versão, derivada de um `security_context` que o cofre devolve
  junto de toda URL assinada de upload/download, e o corpo do objeto é binário cru (`salt ‖ nonce ‖ ciphertext`), não
  um envelope JSON.

**Arquivos**

- As rotas de drive saíram de `…/drives/{security_group_id}/…` para `…/nodes/…`, com `security_group_id` no corpo ou
  na query string.
- Todo arquivo ganha a própria chave de dados, embrulhada para cada security group em `encrypted_keys`; o nome do
  arquivo é cifrado sob essa chave, e as chaves de conteúdo são derivadas pelo mesmo esquema de `security_context` dos
  documentos.

## O que isso significa para você

- Fazer enrollment, manter uma sessão e fazer requisições assinadas funciona hoje.
- Não use `vault.patients`, `vault.exams` nem `vault.drives` contra o cofre de produção ainda. Hoje essas chamadas
  falham alto — um erro de validação, um `400` ou um `404` — antes de qualquer coisa ser gravada, então nenhum dado
  que o app web não conseguiria ler chega a ser escrito. Elas continuam no pacote como prévia, para o formato da API
  poder ser revisado.

## O caminho de volta ao verde

Cada item entra no seu próprio pull request, junto com as interações de contrato dele, para a verificação de provider
do cofre prová-lo antes de ser publicado:

1. Documentos: modelos (`security_group_id`, `streams`), rotas cientes do fluxo, `encrypted_index` para pacientes,
   chaves de conteúdo por `security_context` e corpos em binário cru — com vetores regerados a partir da implementação
   de referência do cofre.
2. Arquivos: rotas `/nodes`, chave por arquivo, nomes cifrados, chaves de conteúdo por `security_context`.
3. Entropia: contribuir com o `random_seed` do próprio SDK no corpo das requisições (o cofre já aceita; hoje o SDK só
   consome o do cofre).

Acompanhe no [issue tracker](https://github.com/diagnos-tech/integration/issues).
