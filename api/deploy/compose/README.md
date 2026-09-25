# diagnos-api · Docker Compose

🇺🇸 One `docker compose up` for OpenBao + `diagnos-api`, wired for local
development and staging. For a production Kubernetes deployment, see
`../k8s/openbao` (OpenBao itself) and `../k8s` (the API) instead — this
compose file trades a few production concerns (a real KMS-backed seal by
default, a multi-node raft cluster) for "one command, nothing else to run."

🇧🇷 Um único `docker compose up` para OpenBao + `diagnos-api`, montado para
desenvolvimento local e staging. Para um deployment de produção em
Kubernetes, veja `../k8s/openbao` (o próprio OpenBao) e `../k8s` (a API) —
este compose troca algumas preocupações de produção (um seal de verdade
apoiado em KMS por padrão, um cluster raft multi-nó) por "um comando só,
nada mais para rodar."

## Quickstart · Início rápido

```sh
cp .env.example .env
# 🇺🇸 edit .env: DIAGNOS_API_TOKEN, then `diagnos status` for the two ids
# 🇧🇷 edite .env: DIAGNOS_API_TOKEN, depois `diagnos status` para os dois ids
```

🇺🇸 Generate the mTLS material into `certs/` — the exact `openssl` recipe is
in [`../../README.md`](../../README.md)'s "Generating a CA and certificates
with openssl" section; this compose stack expects `certs/clients-ca.pem`,
`certs/server.pem`, `certs/server-key.pem`.

🇧🇷 Gere o material de mTLS em `certs/` — a receita exata de `openssl` está
na seção "Gerando uma CA e certificados com openssl" de
[`../../README.md`](../../README.md); esta stack de compose espera
`certs/clients-ca.pem`, `certs/server.pem`, `certs/server-key.pem`.

```sh
docker compose up
```

🇺🇸 First run: `openbao` starts sealed and uninitialised, `openbao-bootstrap`
initialises it, unseals it (only for `OPENBAO_SEAL=shamir` — every other
value auto-unseals on its own), enables KV v2, writes the `diagnos-sdk`
policy from `openbao/policy.hcl`, and mints the scoped token `api` reads.
`api` only starts once that bootstrap exits `0`.

🇧🇷 Primeira execução: `openbao` sobe selado e não inicializado,
`openbao-bootstrap` inicializa, dessela (só para `OPENBAO_SEAL=shamir` —
todo outro valor se dessela sozinho), habilita o KV v2, escreve a política
`diagnos-sdk` a partir de `openbao/policy.hcl`, e emite o token restrito que
`api` lê. `api` só sobe depois que esse bootstrap sai com `0`.

## What the bootstrap does · O que o bootstrap faz

🇺🇸 `openbao/bootstrap.sh` runs once as the `openbao-bootstrap` service
(entrypoint `sh /bootstrap/bootstrap.sh` on the same `openbao/openbao`
image — no extra image to build or trust) and is idempotent across
restarts: it re-checks status every time and skips whatever is already
done, using only POSIX `sh` plus `bao`/`grep`/`sed` (no `jq`, not present in
that image).

🇧🇷 `openbao/bootstrap.sh` roda uma vez como o serviço `openbao-bootstrap`
(entrypoint `sh /bootstrap/bootstrap.sh` na mesma imagem `openbao/openbao` —
sem imagem extra para construir ou confiar) e é idempotente entre
reinícios: reconfere o status toda vez e pula o que já está feito, usando
só `sh` POSIX mais `bao`/`grep`/`sed` (sem `jq`, ausente naquela imagem).

1. 🇺🇸 Waits for `openbao:8200` to answer (any status — sealed counts). ·
   🇧🇷 Espera `openbao:8200` responder (qualquer status — selado conta).
2. 🇺🇸 `bao operator init -format=json` if not yet initialised; writes the
   full output (recovery/unseal keys **and the root token**) to the
   `openbao-state` volume at `0600` and prints a loud warning to move them
   out. · 🇧🇷 `bao operator init -format=json` se ainda não inicializado;
   escreve a saída completa (chaves de recovery/unseal **e o root token**)
   no volume `openbao-state` em `0600` e imprime um aviso para movê-los
   para fora.
3. 🇺🇸 Unseals with the saved keys — only meaningful for `OPENBAO_SEAL=
   shamir`, since every KMS-backed seal unseals itself as soon as the
   process starts. · 🇧🇷 Dessela com as chaves salvas — só relevante para
   `OPENBAO_SEAL=shamir`, já que todo seal apoiado em KMS se dessela
   sozinho assim que o processo sobe.
4. 🇺🇸 Enables KV v2 at `secret` (idempotent — a second `enable` failing
   with "already in use" is the success path). · 🇧🇷 Habilita o KV v2 em
   `secret` (idempotente — um segundo `enable` falhar com "already in use"
   é o caminho de sucesso).
5. 🇺🇸 Writes policy `diagnos-sdk` from `openbao/policy.hcl` with
   `__WORKSPACE_ID__`/`__ACCOUNT_ID__` substituted from `.env`. · 🇧🇷 Escreve
   a política `diagnos-sdk` a partir de `openbao/policy.hcl` com
   `__WORKSPACE_ID__`/`__ACCOUNT_ID__` substituídos a partir do `.env`.
6. 🇺🇸 Mints an orphan, renewable token scoped to that policy and writes it
   to `/state/openbao-token` (`0600`) — skipped if a token already there
   still passes `bao token lookup`. · 🇧🇷 Emite um token órfão e renovável
   restrito a essa política e escreve em `/state/openbao-token` (`0600`) —
   pulado se um token já ali ainda passa em `bao token lookup`.

**STAGING-ONLY, read this**: with `OPENBAO_SEAL=shamir` (the default), step
3 only works because step 2 kept the unseal keys sitting in the
`openbao-state` volume, unencrypted. That is a deliberate convenience for a
disposable environment — it means anyone with access to that Docker volume
can unseal OpenBao and read every saved session, no OpenBao credential
required. Do not run this configuration anywhere that matters; set
`OPENBAO_SEAL` to `aws`/`gcp`/`azure`/`transit` instead (`.env.example` has
the credentials each one needs) or unseal by hand and keep the recovery
keys off this machine entirely.

**SÓ PARA STAGING, leia isto**: com `OPENBAO_SEAL=shamir` (o padrão), o
passo 3 só funciona porque o passo 2 deixou as chaves de unseal no volume
`openbao-state`, sem cifrar. É uma conveniência deliberada para um ambiente
descartável — significa que qualquer um com acesso a esse volume Docker
consegue desselar o OpenBao e ler toda sessão salva, sem precisar de
credencial nenhuma do OpenBao. Não rode esta configuração em nada que
importe; use `OPENBAO_SEAL=aws`/`gcp`/`azure`/`transit` (o `.env.example`
tem as credenciais que cada um precisa) ou dessela na mão e mantenha as
chaves de recovery totalmente fora desta máquina.

## `OPENBAO_TOKEN_FILE` · `OPENBAO_TOKEN_FILE`

🇺🇸 The `api` service never sees the OpenBao token as an environment value:
`openbao-bootstrap` writes it to `/state/openbao-token` (`0600`, owned by
the API's uid 10001) and the SDK reads that path itself —
`diagnos.Settings.from_env()` honours `OPENBAO_TOKEN_FILE` whenever
`OPENBAO_TOKEN` is unset. Nothing in this stack ever puts the token in
`docker inspect` output or a process environment.

🇧🇷 O serviço `api` nunca vê o token do OpenBao como valor de ambiente: o
`openbao-bootstrap` o escreve em `/state/openbao-token` (`0600`, com o uid
10001 da API) e o próprio SDK lê esse caminho — `diagnos.Settings.from_env()`
respeita `OPENBAO_TOKEN_FILE` sempre que `OPENBAO_TOKEN` não está definida.
Nada nesta stack põe o token na saída de `docker inspect` nem no ambiente de
um processo.

## Tearing down · Desmontando

```sh
docker compose down        # 🇺🇸 keeps openbao-data/openbao-state · 🇧🇷 mantém openbao-data/openbao-state
docker compose down -v     # 🇺🇸 destroys them — see the volumes' warnings in docker-compose.yml · 🇧🇷 destrói — veja os avisos dos volumes em docker-compose.yml
```
