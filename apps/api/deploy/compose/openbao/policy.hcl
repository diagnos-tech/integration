# 🇺🇸 Policy `diagnos-sdk`: the *only* thing the diagnos-api process's
# OpenBao token may do. `apps/sdk/README.md`'s "Auto-unseal with OpenBao" section
# states the trade plainly — whoever can read this one path can decrypt
# exactly what the SDK process can — so this policy is the enforcement of
# that boundary, not a formality. `__WORKSPACE_ID__`/`__ACCOUNT_ID__` are
# substituted by `bootstrap.sh` from `DIAGNOS_WORKSPACE_ID`/
# `DIAGNOS_ACCOUNT_ID` in `.env` before the policy is written (`bao policy
# write`); this file on disk is the template, never the literal policy.
# 🇧🇷 Política `diagnos-sdk`: a *única* coisa que o token de OpenBao do
# processo diagnos-api pode fazer. A seção "Auto-unseal com OpenBao" de
# `apps/sdk/README.md` diz o tradeoff sem rodeios — quem consegue ler este único
# path decifra exatamente o que o processo do SDK decifra — então esta
# política é a aplicação prática dessa fronteira, não uma formalidade.
# `__WORKSPACE_ID__`/`__ACCOUNT_ID__` são substituídos pelo `bootstrap.sh` a
# partir de `DIAGNOS_WORKSPACE_ID`/`DIAGNOS_ACCOUNT_ID` no `.env` antes da
# política ser escrita (`bao policy write`); este arquivo em disco é o
# modelo, nunca a política literal.

# 🇺🇸 `secret/data/...` is where KV v2 keeps the actual secret version — the
# SDK's `OpenBaoStore` reads and writes it on every enroll/restore
# (`apps/sdk/src/diagnos/session/unseal.py`). No wildcard, no parent path: a
# token scoped here cannot list, read, or write any other workspace's or
# account's saved session.
# 🇧🇷 `secret/data/...` é onde o KV v2 guarda a versão de fato do segredo —
# o `OpenBaoStore` do SDK lê e escreve ali a cada enroll/restore
# (`apps/sdk/src/diagnos/session/unseal.py`). Sem wildcard, sem path pai: um
# token restrito aqui não lista, lê nem escreve a sessão salva de nenhum
# outro workspace ou conta.
path "secret/data/diagnos/__WORKSPACE_ID__/__ACCOUNT_ID__" {
  capabilities = ["create", "update", "read", "delete"]
}

# 🇺🇸 `secret/metadata/...` is KV v2's separate path for version history and
# soft-delete/destroy — `delete` on `data/` alone only soft-deletes the
# current version; the SDK needs `metadata/` too so a saved-session
# rotation does not silently pile up old versions it can never clean.
# 🇧🇷 `secret/metadata/...` é o path separado do KV v2 para histórico de
# versão e soft-delete/destroy — só `delete` em `data/` apenas apaga a
# versão atual; o SDK também precisa de `metadata/` para uma rotação de
# sessão salva não acumular em silêncio versões antigas que nunca consegue
# limpar.
path "secret/metadata/diagnos/__WORKSPACE_ID__/__ACCOUNT_ID__" {
  capabilities = ["create", "update", "read", "delete"]
}
