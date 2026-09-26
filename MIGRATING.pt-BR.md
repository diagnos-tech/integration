# Migrando do imgexam

[English](MIGRATING.md) · **Português (Brasil)**

Este projeto foi renomeado de `imgexam` para `diagnos`. Os pacotes nunca foram publicados no PyPI sob nenhum dos
dois nomes — se você só instalou `diagnos`, `diagnos-cli` ou `diagnos-api`, não há nada aqui para você. Este guia é
para quem rodava um checkout interno ou a partir do fonte do antigo monorepo `imgexam` (pacotes, uma cópia
vendorizada, ou um deploy construído a partir do fonte) e está migrando esse checkout para este repositório.

`0.1.0` é a primeira versão de `diagnos`, `diagnos-cli` e `diagnos-api` já publicada como tal — veja
[`CHANGELOG.md`](CHANGELOG.md). Os três reiniciam o versionamento em `0.1.0`, independente de quais eram os números
de versão internos do `imgexam`.

## O que mudou

### Pacotes, módulos, classes, exceções

| Antes (`imgexam`) | Depois (`diagnos`) |
|---|---|
| pacote `imgexam` | pacote `diagnos` |
| pacote `imgexam-cli` | pacote `diagnos-cli` |
| pacote `imgexam-api` | pacote `diagnos-api` |
| import `imgexam` | import `diagnos` |
| import `imgexam_cli` | import `diagnos_cli` |
| import `imgexam_api` | import `diagnos_api` |
| classe `Imgexam` | classe `Diagnos` |
| exceção `ImgexamError` | exceção `DiagnosError` |
| exceção `ImgexamPermissionError` | exceção `DiagnosPermissionError` |

```python no-run
# antes
from imgexam import Imgexam, ImgexamError

# depois
from diagnos import Diagnos, DiagnosError
```

### Comando da CLI e imagem Docker

| Antes | Depois |
|---|---|
| `imgexam` (comando) | `diagnos` (comando) |
| `imgexam-api` (imagem Docker) | `diagnos-api` (imagem Docker) |

### URL padrão do cofre

A URL padrão do cofre mudou do endereço interno anterior para `https://vault.diagnos.health`. Se você já define
`DIAGNOS_VAULT_URL` explicitamente (veja abaixo), isso não te afeta.

### Variáveis de ambiente

Toda variável de ambiente `IMGEXAM_*` foi renomeada para `DIAGNOS_*`, sem nenhuma outra mudança de significado ou
de valores aceitos:

| Antes | Depois | Onde é lida |
|---|---|---|
| `IMGEXAM_API_TOKEN` | `DIAGNOS_API_TOKEN` | SDK (`transport/config.py`, `transport/token.py`), CLI, API |
| `IMGEXAM_VAULT_URL` | `DIAGNOS_VAULT_URL` | SDK (`transport/config.py`), CLI (override `--vault-url`) |
| `IMGEXAM_TIMEOUT_SECONDS` | `DIAGNOS_TIMEOUT_SECONDS` | SDK (`transport/config.py`) |
| `IMGEXAM_SSE_C` | — (removida: arquivos sempre usam SSE-C, como o app web; documentos nunca) | — |
| `IMGEXAM_HARDEN_PROCESS` | `DIAGNOS_HARDEN_PROCESS` | SDK (`transport/config.py`), enclave Rust (`apps/sdk/native`) |
| `IMGEXAM_MEMORY_LOCK` | `DIAGNOS_MEMORY_LOCK` | enclave Rust (`apps/sdk/native/src/locked/mod.rs`, `error.rs`) |
| `IMGEXAM_API_MTLS_CA_FILE` | `DIAGNOS_API_MTLS_CA_FILE` | API (`diagnos_api/settings.py`), manifestos de deploy |
| `IMGEXAM_API_TLS_CERT_FILE` | `DIAGNOS_API_TLS_CERT_FILE` | API (`diagnos_api/settings.py`), manifestos de deploy |
| `IMGEXAM_API_TLS_KEY_FILE` | `DIAGNOS_API_TLS_KEY_FILE` | API (`diagnos_api/settings.py`), manifestos de deploy |
| `IMGEXAM_API_HOST` | `DIAGNOS_API_HOST` | API (`diagnos_api/settings.py`) |
| `IMGEXAM_API_PORT` | `DIAGNOS_API_PORT` | API (`diagnos_api/settings.py`), manifestos de deploy |
| `IMGEXAM_API_ALLOWED_CLIENT_CN` | `DIAGNOS_API_ALLOWED_CLIENT_CN` | API (`diagnos_api/settings.py`) |
| `IMGEXAM_WORKSPACE_ID` | `DIAGNOS_WORKSPACE_ID` | só em tempo de deploy — bootstrap da policy do OpenBao (`apps/api/deploy/k8s/openbao/`, `apps/api/deploy/compose/openbao/`) |
| `IMGEXAM_ACCOUNT_ID` | `DIAGNOS_ACCOUNT_ID` | só em tempo de deploy — bootstrap da policy do OpenBao (`apps/api/deploy/k8s/openbao/`, `apps/api/deploy/compose/openbao/`) |

As variáveis `OPENBAO_*` (`OPENBAO_ADDR`, `OPENBAO_TOKEN`, `OPENBAO_TOKEN_FILE`, `OPENBAO_MOUNT`,
`OPENBAO_PATH_PREFIX`, `OPENBAO_NAMESPACE`) nunca tiveram prefixo `IMGEXAM_` e não mudaram — o OpenBao é um produto
separado, com nomenclatura própria. Uma delas, porém, muda de comportamento: veja a próxima seção.

### Auto-unseal do OpenBao: o prefixo padrão do path na KV

O valor **padrão** do prefixo de path da KV do OpenBao (`DEFAULT_OPENBAO_PATH_PREFIX` em
`apps/sdk/src/diagnos/transport/config.py`) mudou de `"imgexam"` para `"diagnos"`. Ele continua podendo ser sobrescrito
pela variável de ambiente `OPENBAO_PATH_PREFIX`, cujo nome não mudou.

Se você já roda o auto-unseal do OpenBao contra um deploy `imgexam` e atualiza no local sem definir
`OPENBAO_PATH_PREFIX`, o SDK vai passar a ler e escrever sob `diagnos/...` em vez de `imgexam/...` — um path que
ainda não existe, então vai parecer que a sessão salva sumiu. Você tem duas opções:

1. **Manter o path antigo.** Defina `OPENBAO_PATH_PREFIX=imgexam` explicitamente, e mais nada muda.
2. **Fazer o enrollment de novo.** Deixe o novo padrão (`diagnos`) como está e passe pelo fluxo de
   enrollment/aprovação outra vez; o SDK salva a nova sessão sob o novo prefixo assim que der certo.

Qualquer uma das duas é segura — não há perda silenciosa de dado, só uma sessão salva que precisa ser encontrada de
novo ou recriada.

### O que NÃO mudou, de propósito

Duas categorias de constante foram deliberadamente **não** renomeadas, porque são constantes criptográficas de fio
persistidas, não nomes de produto:

- Os rótulos HKDF/AAD `imgexam-*-v1` (`apps/sdk/src/diagnos/crypto/hkdf.py`, `hybrid.py`, `keys.py`,
  `apps/sdk/native/src/hybrid.rs`) — por exemplo `imgexam-sdk-hybrid-seal-v1`, `imgexam-patient-dek-v1`,
  `imgexam-drive-node-key-v1`.
- O id de chave de seal estático do OpenBao `imgexam-static-v1` (`apps/api/deploy/k8s/autounseal/static/seal.hcl`).

Renomear qualquer um deles tornaria todo ciphertext já produzido sob o rótulo antigo — ou uma instalação existente
do OpenBao com static seal usando a chave `imgexam-static-v1` — permanentemente ilegível. Eles estão documentados
como congelados ao lado de suas definições e em [`CONTRIBUTING.pt-BR.md`](CONTRIBUTING.pt-BR.md); não os renomeie
em um fork ou patch.

## Checklist de busca/substituição

Percorrendo um checkout ou um fork downstream, mais ou menos na ordem que pega mais coisa com menos risco de um
falso positivo:

- [ ] Nomes de pacote no seu próprio `pyproject.toml`/`requirements`: `imgexam` → `diagnos`, `imgexam-cli` →
      `diagnos-cli`, `imgexam-api` → `diagnos-api`.
- [ ] Imports Python: `from imgexam` / `import imgexam` → `diagnos` (e as variantes `_cli`/`_api`). Cuidado com uma
      substituição de texto livre aqui — faça como instruções de import, não texto solto, ou você também vai
      atingir os rótulos congelados `imgexam-*-v1` abaixo.
- [ ] `Imgexam` → `Diagnos`, `ImgexamError` → `DiagnosError`, `ImgexamPermissionError` → `DiagnosPermissionError`.
- [ ] Toda variável de ambiente `IMGEXAM_*` nos seus perfis de shell, arquivos `.env`, secrets de CI, manifestos
      `ConfigMap`/`Secret` do Kubernetes e arquivos Docker Compose, conforme a tabela acima.
- [ ] O comando `imgexam` da CLI → `diagnos` em scripts, cron jobs, unidades systemd, aliases de shell.
- [ ] A referência à imagem Docker `imgexam-api` → `diagnos-api` em arquivos Compose, manifestos Kubernetes, CI.
- [ ] Se você fixa a URL do cofre: confirme que ainda aponta para onde você quer — o padrão mudou, conforme acima.
- [ ] Se você usa auto-unseal do OpenBao: decida entre as duas opções da seção acima (`OPENBAO_PATH_PREFIX` ou
      fazer o enrollment de novo) **antes** de fazer o deploy da renomeação, não depois.
- [ ] **Não toque**: toda string `imgexam-*-v1` em `crypto/`, `native/src/hybrid.rs`, `apps/sdk/tests/vectors/`, e
      `imgexam-static-v1` em `apps/api/deploy/k8s/autounseal/static/seal.hcl`.

## Um comando de exemplo para adaptar

Isso cobre só as renomeações mecânicas — imports, os nomes de classe/exceção, o comando da CLI e a imagem Docker.
De propósito **não** toca em variáveis de ambiente (revise essas à mão contra a tabela acima, já que algumas vivem
em secrets perto dos quais você não quer uma reescrita cega) nem em nada sob `crypto/`, `native/src/`,
`apps/sdk/tests/vectors/` ou `autounseal/` (os rótulos congelados `imgexam-*-v1` / `imgexam-static-v1`):

```sh
# Ajuste a lista de arquivos para o seu checkout; rode numa árvore git limpa para poder revisar o diff.
grep -rlZ --include='*.py' --include='*.toml' --include='*.md' \
  -e 'imgexam' -e 'Imgexam' . \
  --exclude-dir={.git,crypto,native,vectors,autounseal} \
  | xargs -0 perl -pi -e '
      s/\bimgexam_(cli|api)\b/diagnos_$1/g;
      s/\bImgexam(PermissionError|Error)?\b/Diagnos$1/g;
      s/\bimgexam\b(?!-[a-z0-9-]*-v\d)/diagnos/g'
git diff   # revise antes de commitar — isso é um instrumento sem muita finesse
```

Adapte a lista `--exclude-dir` e os globs de arquivo ao layout do seu próprio checkout, e sempre revise o diff: uma
passada automática ainda pode pegar uma string inesperada; a guarda `(?!…-vN)` mantém intactos os rótulos congelados `imgexam-*-vN`.
