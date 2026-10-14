# Policy `diagnos-sdk`: the *only* thing the diagnos-api process's OpenBao token may do. `docs/guides/sessions.md`'s
# "Auto-unseal with OpenBao" section states the trade plainly — whoever can read this one path can decrypt exactly what
# the SDK process can — so this policy is the enforcement of that boundary, not a formality.
# `__WORKSPACE_ID__`/`__ACCOUNT_ID__` are substituted by `bootstrap.sh` from `DIAGNOS_WORKSPACE_ID`/
# `DIAGNOS_ACCOUNT_ID` in `.env` before the policy is written (`bao policy write`); this file on disk is the template,
# never the literal policy.

# `secret/data/...` is where KV v2 keeps the actual secret version — the SDK's `OpenBaoStore` reads and writes it on
# every enroll/restore (`apps/sdk/src/diagnos/session/unseal.py`). No wildcard, no parent path: a token scoped here
# cannot list, read, or write any other workspace's or account's saved session.
path "secret/data/diagnos/__WORKSPACE_ID__/__ACCOUNT_ID__" {
  capabilities = ["create", "update", "read", "delete"]
}

# `secret/metadata/...` is KV v2's separate path for version history and soft-delete/destroy — `delete` on `data/` alone
# only soft-deletes the current version; the SDK needs `metadata/` too so a saved-session rotation does not silently
# pile up old versions it can never clean.
path "secret/metadata/diagnos/__WORKSPACE_ID__/__ACCOUNT_ID__" {
  capabilities = ["create", "update", "read", "delete"]
}
