#!/bin/sh
# 🇺🇸 One-shot bootstrap for the Compose OpenBao: initialise (or resume),
# unseal when the seal is Shamir, enable KV v2, and issue two scoped tokens:
# the one `diagnos-api` reads via `OPENBAO_TOKEN_FILE` (policy `diagnos-sdk`:
# its saved session, and *read* on the diagnos token), and the writer token
# `diagnos login --store openbao` uses to store that token (policy
# `diagnos-token-writer`, in the `openbao-admin` volume the API never
# mounts). The diagnos token itself never passes through here. Runs once per `docker
# compose up` as the `openbao-bootstrap` service, using only POSIX `sh` and
# the binaries already in the `openbao/openbao` image (no `jq` — see the
# `_json_field`/`_json_array` helpers below) because that image is all this
# container has.
#
# STAGING-ONLY WARNING: with `OPENBAO_SEAL=shamir` this script keeps the
# unseal keys on the `openbao-state` volume so it can re-unseal on every
# `docker compose restart` without a human. That is a deliberate convenience
# for a throwaway environment, not a production posture — in production,
# either configure a real auto-unseal backend (`OPENBAO_SEAL=aws|gcp|azure|
# transit`, see `../k8s/autounseal/*/README.md`) or unseal by hand and keep
# the recovery keys off any machine that also holds the encrypted data.
#
# 🇧🇷 Bootstrap de execução única para o OpenBao do Compose: inicializa (ou
# retoma), dessela quando o seal é Shamir, habilita o KV v2 e emite dois
# tokens restritos: o que o `diagnos-api` lê via `OPENBAO_TOKEN_FILE`
# (política `diagnos-sdk`: a sessão salva dele, e *leitura* do token do
# diagnos), e o token de escrita que o `diagnos login --store openbao` usa
# para guardar esse token (política `diagnos-token-writer`, no volume
# `openbao-admin` que a API nunca monta). O token do diagnos em si nunca
# passa por aqui. Roda uma vez por
# `docker compose up` como o serviço `openbao-bootstrap`, usando só `sh`
# POSIX e os binários que já estão na imagem `openbao/openbao` (sem `jq` —
# veja os helpers `_json_field`/`_json_array` abaixo) porque é só isso que
# este container tem.
#
# AVISO SÓ-PARA-STAGING: com `OPENBAO_SEAL=shamir` este script guarda as
# chaves de unseal no volume `openbao-state` para poder desselar de novo a
# cada `docker compose restart` sem humano. É uma conveniência deliberada
# para um ambiente descartável, não uma postura de produção — em produção,
# configure um backend de auto-unseal de verdade (`OPENBAO_SEAL=aws|gcp|
# azure|transit`, veja `../k8s/autounseal/*/README.md`) ou dessela na mão e
# mantenha as chaves de recovery fora de qualquer máquina que também guarde
# os dados cifrados.
set -eu

BAO_ADDR="${OPENBAO_ADDR:-http://openbao:8200}"
export BAO_ADDR
STATE_DIR="/state"
INIT_FILE="$STATE_DIR/openbao-init.json"
TOKEN_FILE="$STATE_DIR/openbao-token"
POLICY_NAME="diagnos-sdk"
POLICY_SRC="/bootstrap/policy.hcl"
POLICY_RENDERED="/tmp/diagnos-sdk-policy.hcl"
# 🇺🇸 `/admin` in Compose (the `openbao-admin` volume, never mounted by `api`);
# Kubernetes passes `OPENBAO_ADMIN_DIR=/state/admin`, since that pod has no
# `/admin` (`../../k8s/openbao/bootstrap-configmap.yaml`).
# 🇧🇷 `/admin` no Compose (o volume `openbao-admin`, que o `api` nunca monta);
# o Kubernetes passa `OPENBAO_ADMIN_DIR=/state/admin`, já que aquele pod não
# tem `/admin` (`../../k8s/openbao/bootstrap-configmap.yaml`).
WRITER_DIR="${OPENBAO_ADMIN_DIR:-/admin}"
WRITER_TOKEN_FILE="$WRITER_DIR/openbao-token-writer"
WRITER_POLICY_NAME="diagnos-token-writer"
WRITER_POLICY_SRC="/bootstrap/token-writer-policy.hcl"
# 🇺🇸 Where `diagnos login --store openbao` keeps the diagnos token (the SDK's
# `token_store/openbao.py`: `<OPENBAO_PATH_PREFIX>/token` under the `secret`
# mount) — the literal path both policies name.
# 🇧🇷 Onde o `diagnos login --store openbao` guarda o token do diagnos (o
# `token_store/openbao.py` do SDK: `<OPENBAO_PATH_PREFIX>/token` sob o mount
# `secret`) — o caminho literal que as duas políticas citam.
DIAGNOS_TOKEN_PATH="diagnos/token"

log() {
  # 🇺🇸 Every line bilingual, like every other file here — this is the one
  # place an operator actually reads this container's output.
  # 🇧🇷 Toda linha bilíngue, como todo outro arquivo aqui — é o único lugar
  # onde um operador de fato lê a saída deste container.
  printf '[openbao-bootstrap] %s\n' "$1"
}

# 🇺🇸 Pulls one `"key": "value"` scalar out of a `-format=json` blob with
# grep+sed instead of jq (not present in this image). Assumes the CLI's own
# pretty-printer, which puts each scalar field on its own line — true for
# every `bao`/`vault` JSON output this script parses.
# 🇧🇷 Extrai um escalar `"key": "value"` de um JSON de `-format=json` com
# grep+sed em vez de jq (ausente nesta imagem). Assume o pretty-printer da
# própria CLI, que põe cada campo escalar em sua própria linha — verdade
# para todo JSON de `bao`/`vault` que este script interpreta.
_json_field() {
  field="$1"
  file="$2"
  grep -o "\"${field}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$file" | head -n1 | sed -E 's/.*:[[:space:]]*"([^"]*)"$/\1/'
}

# 🇺🇸 `-E`: `(true|false)` is an alternation only in extended regex; as a
# basic regex it matched nothing, so `is_initialized` was always false and a
# second `docker compose up` re-ran `bao operator init` and failed.
# 🇧🇷 `-E`: `(true|false)` só é alternativa em regex estendida; como regex
# básica não casava nada, então `is_initialized` era sempre falso e um
# segundo `docker compose up` rodava `bao operator init` de novo e falhava.
_json_bool() {
  field="$1"
  file="$2"
  grep -oE "\"${field}\"[[:space:]]*:[[:space:]]*(true|false)" "$file" | head -n1 | sed -E 's/.*:[[:space:]]*//'
}

# 🇺🇸 Pulls every string out of a `"field": [ "a", "b", ... ]` array,
# one per line — used for `unseal_keys_b64`, which only Shamir populates.
# 🇧🇷 Extrai toda string de um array `"field": [ "a", "b", ... ]`, uma por
# linha — usado em `unseal_keys_b64`, que só o Shamir preenche.
_json_array() {
  field="$1"
  file="$2"
  sed -n "/\"${field}\"/,/\]/p" "$file" | grep -o '"[A-Za-z0-9+/=]\{20,\}"' | tr -d '"'
}

wait_for_openbao() {
  # 🇺🇸 `bao status` exits 0 unsealed, 2 sealed (uninitialised counts as
  # sealed) — both mean "reachable". Only exit 1 (or the process not being
  # up yet at all) means "keep waiting"; this loop must not require
  # unsealed, because unsealing is this very script's job.
  # 🇧🇷 `bao status` sai 0 desselado, 2 selado (não inicializado conta como
  # selado) — os dois significam "alcançável". Só o exit 1 (ou o processo
  # ainda nem estar de pé) significa "continue esperando"; este laço não
  # pode exigir desselado, porque desselar é o trabalho deste script.
  tries=0
  max_tries=60
  while [ "$tries" -lt "$max_tries" ]; do
    ec=0
    bao status >/tmp/status.out 2>&1 || ec=$?
    if [ "$ec" -eq 0 ] || [ "$ec" -eq 2 ]; then
      return 0
    fi
    tries=$((tries + 1))
    sleep 2
  done
  log "🇺🇸 timed out waiting for $BAO_ADDR to answer · 🇧🇷 tempo esgotado esperando $BAO_ADDR responder"
  cat /tmp/status.out || true
  exit 1
}

is_sealed() {
  bao status -format=json >/tmp/status.json 2>/dev/null || true
  [ "$(_json_bool sealed /tmp/status.json)" = "true" ]
}

is_initialized() {
  bao status -format=json >/tmp/status.json 2>/dev/null || true
  [ "$(_json_bool initialized /tmp/status.json)" = "true" ]
}

unseal_with_saved_keys() {
  # 🇺🇸 Shamir-only path: re-unseal a restarted `openbao` container using
  # the keys this same script saved to `$INIT_FILE` on first boot. Nothing
  # to do for an auto-unseal backend — the KMS/Transit call happens inside
  # `bao` itself as soon as the process starts, before this script even
  # gets to check.
  # 🇧🇷 Caminho só-Shamir: dessela de novo um container `openbao` reiniciado
  # usando as chaves que este mesmo script salvou em `$INIT_FILE` na
  # primeira subida. Nada a fazer para um backend de auto-unseal — a
  # chamada ao KMS/Transit acontece dentro do próprio `bao` assim que o
  # processo sobe, antes deste script sequer checar.
  if [ ! -f "$INIT_FILE" ]; then
    log "🇺🇸 sealed, but no saved keys at $INIT_FILE — this is expected right after a fresh init with an auto-unseal backend (it should already be unsealing itself); for Shamir it means the state volume was lost and someone must unseal by hand. · 🇧🇷 selado, mas sem chaves salvas em $INIT_FILE — isso é esperado logo após um init novo com backend de auto-unseal (ele já deveria estar se desselando sozinho); para Shamir significa que o volume de estado se perdeu e alguém precisa desselar na mão."
    return 0
  fi
  threshold="$(_json_field unseal_threshold "$INIT_FILE")"
  [ -n "$threshold" ] || threshold="$(_json_field recovery_threshold "$INIT_FILE")"
  count=0
  for key in $(_json_array unseal_keys_b64 "$INIT_FILE"); do
    [ -n "$threshold" ] && [ "$count" -ge "$threshold" ] && break
    bao operator unseal "$key" >/dev/null
    count=$((count + 1))
  done
}

ensure_kv_v2() {
  # 🇺🇸 `bao secrets enable` has no `-force`/idempotent flag; the second run
  # always fails with "path is already in use" on stderr, which is exactly
  # the success case here, so it is matched and swallowed instead of
  # treated as an error.
  # 🇧🇷 `bao secrets enable` não tem flag `-force`/idempotente; a segunda
  # execução sempre falha com "path is already in use" no stderr, que é
  # exatamente o caso de sucesso aqui, então é reconhecido e engolido em
  # vez de tratado como erro.
  if ! bao secrets enable -path=secret kv-v2 >/tmp/enable.out 2>&1; then
    if ! grep -q "already in use" /tmp/enable.out; then
      cat /tmp/enable.out
      exit 1
    fi
  fi
}

write_policy() {
  : "${DIAGNOS_WORKSPACE_ID:?DIAGNOS_WORKSPACE_ID must be set in .env — run \`diagnos status\` with the token this deployment will use to find it. / precisa estar no .env — rode \`diagnos status\` com o token que este deployment vai usar para descobrir.}"
  : "${DIAGNOS_ACCOUNT_ID:?DIAGNOS_ACCOUNT_ID must be set in .env — same \`diagnos status\` output. / precisa estar no .env — mesma saída de \`diagnos status\`.}"
  sed -e "s/__WORKSPACE_ID__/${DIAGNOS_WORKSPACE_ID}/g" -e "s/__ACCOUNT_ID__/${DIAGNOS_ACCOUNT_ID}/g" "$POLICY_SRC" >"$POLICY_RENDERED"
  bao policy write "$POLICY_NAME" "$POLICY_RENDERED" >/dev/null
  bao policy write "$WRITER_POLICY_NAME" "$WRITER_POLICY_SRC" >/dev/null
  # 🇺🇸 One version only: rotating the token (`diagnos login` again) must not
  # leave the old one readable in the KV history. Idempotent; works before
  # the secret exists.
  # 🇧🇷 Uma versão só: girar o token (`diagnos login` de novo) não pode deixar
  # o antigo legível no histórico do KV. Idempotente; funciona antes do
  # segredo existir.
  bao kv metadata put -mount=secret -max-versions=1 "$DIAGNOS_TOKEN_PATH" >/dev/null
}

# 🇺🇸 `issue_token <policy> <display name> <file>`: an orphan token with only
# that policy, written `0600` to `<file>` and handed to the uid the
# `diagnos` images run as.
# 🇧🇷 `issue_token <política> <nome> <arquivo>`: um token órfão só com essa
# política, escrito `0600` em `<arquivo>` e entregue ao uid com que as
# imagens do `diagnos` rodam.
issue_token() {
  policy="$1"
  display_name="$2"
  file="$3"
  bao token create -orphan -policy="$policy" -display-name="$display_name" -renewable=true -format=json >/tmp/token.json
  client_token="$(_json_field client_token /tmp/token.json)"
  rm -f /tmp/token.json
  if [ -z "$client_token" ]; then
    log "🇺🇸 could not parse client_token from bao token create output · 🇧🇷 não consegui extrair client_token da saída de bao token create"
    exit 1
  fi
  mkdir -p "$(dirname "$file")"
  printf '%s' "$client_token" >"$file"
  chmod 600 "$file"
  # 🇺🇸 The API container reads this file as uid 10001 (the root `Dockerfile`);
  # in Compose this script runs as root and hands the file over. Under
  # Kubernetes it runs as the `openbao` user via `kubectl exec`, the chown
  # is not permitted, and the operator copies the token into a Secret
  # instead (`../../k8s/openbao/bootstrap-configmap.yaml`) — hence the
  # soft failure.
  # 🇧🇷 O container da API lê este arquivo como uid 10001 (o `Dockerfile` da raiz);
  # no Compose este script roda como root e entrega o arquivo. No
  # Kubernetes ele roda como o usuário `openbao` via `kubectl exec`, o chown
  # não é permitido, e o operador copia o token para um Secret
  # (`../../k8s/openbao/bootstrap-configmap.yaml`) — daí a falha suave.
  chown "${DIAGNOS_API_UID:-10001}" "$file" 2>/dev/null \
    || log "🇺🇸 could not chown $file to uid ${DIAGNOS_API_UID:-10001} (expected under Kubernetes) · 🇧🇷 não consegui fazer chown de $file para o uid ${DIAGNOS_API_UID:-10001} (esperado no Kubernetes)"
}

# 🇺🇸 `token_is_valid <file>`: the file exists and its token still resolves.
# 🇧🇷 `token_is_valid <arquivo>`: o arquivo existe e o token dele ainda resolve.
token_is_valid() {
  [ -f "$1" ] || return 1
  BAO_TOKEN="$(cat "$1")" bao token lookup >/dev/null 2>&1
}

main() {
  mkdir -p "$STATE_DIR"
  wait_for_openbao

  root_token="${BAO_ROOT_TOKEN_OVERRIDE:-}"

  if ! is_initialized; then
    log "🇺🇸 not initialized — running \`bao operator init\` (once, ever, for this raft volume) · 🇧🇷 não inicializado — rodando \`bao operator init\` (uma vez, para sempre, para este volume raft)"
    bao operator init -format=json >"$INIT_FILE"
    chmod 600 "$INIT_FILE"
    root_token="$(_json_field root_token "$INIT_FILE")"
    log "############################################################"
    log "🇺🇸 SECURITY: $INIT_FILE now holds the recovery/unseal keys AND"
    log "the root token, in cleartext, on the openbao-state volume. Copy"
    log "them to an offline secret store NOW and delete them from this"
    log "volume — anyone who can read this file owns this OpenBao."
    log "🇧🇷 SEGURANÇA: $INIT_FILE agora tem as chaves de recovery/unseal E"
    log "o root token, em texto claro, no volume openbao-state. Copie"
    log "para um cofre de segredos offline AGORA e apague deste volume —"
    log "quem ler este arquivo é dono deste OpenBao."
    log "############################################################"
  fi

  if is_sealed; then
    unseal_with_saved_keys
  fi

  api_ok=false
  writer_ok=false
  token_is_valid "$TOKEN_FILE" && api_ok=true
  token_is_valid "$WRITER_TOKEN_FILE" && writer_ok=true
  if [ "$api_ok" = true ] && [ "$writer_ok" = true ]; then
    log "🇺🇸 existing $TOKEN_FILE and $WRITER_TOKEN_FILE still resolve via \`bao token lookup\` — keeping them, no root privileges needed. · 🇧🇷 $TOKEN_FILE e $WRITER_TOKEN_FILE existentes ainda resolvem via \`bao token lookup\` — mantendo, sem precisar de privilégio de root."
    exit 0
  fi

  if [ -z "$root_token" ] && [ -f "$INIT_FILE" ]; then
    root_token="$(_json_field root_token "$INIT_FILE")"
  fi
  if [ -z "$root_token" ] && [ "$api_ok" = true ]; then
    # 🇺🇸 The API can still start; only storing or rotating the diagnos
    # token waits for a privileged run. Never block the stack on that.
    # 🇧🇷 A API ainda sobe; só guardar ou girar o token do diagnos espera
    # uma execução privilegiada. Nunca trava a stack por isso.
    log "🇺🇸 no usable writer token at $WRITER_TOKEN_FILE and no root token: \`diagnos login --store openbao\` cannot store the diagnos token until BAO_ROOT_TOKEN_OVERRIDE is set for one run (this also writes the current policies — needed once after upgrading to the service account token). The API keeps its token. · 🇧🇷 nenhum token de escrita utilizável em $WRITER_TOKEN_FILE e nenhum root token: o \`diagnos login --store openbao\` não consegue guardar o token do diagnos até BAO_ROOT_TOKEN_OVERRIDE ser definido por uma execução (isso também grava as políticas atuais — necessário uma vez depois de atualizar para o token de conta de serviço). A API mantém o token dela."
    exit 0
  fi
  if [ -z "$root_token" ]; then
    log "🇺🇸 no usable token at $TOKEN_FILE and no root token available (no fresh init this run, $INIT_FILE absent or already cleaned up). Set BAO_ROOT_TOKEN_OVERRIDE in .env to a privileged token for one run to reissue it. TODO(gustavo): a real recovery flow (recovery-key-based root generation) is out of scope for a staging bootstrap script."
    log "🇧🇷 nenhum token utilizável em $TOKEN_FILE e nenhum root token disponível (sem init novo nesta execução, $INIT_FILE ausente ou já limpo). Defina BAO_ROOT_TOKEN_OVERRIDE no .env com um token privilegiado por uma execução para reemitir. TODO(gustavo): um fluxo de recovery de verdade (geração de root a partir das chaves de recovery) está fora do escopo de um script de bootstrap de staging."
    exit 1
  fi

  BAO_TOKEN="$root_token"
  export BAO_TOKEN
  ensure_kv_v2
  write_policy
  if [ "$api_ok" = false ]; then
    issue_token "$POLICY_NAME" diagnos-api "$TOKEN_FILE"
    log "🇺🇸 wrote scoped token to $TOKEN_FILE (policy: $POLICY_NAME) · 🇧🇷 token restrito escrito em $TOKEN_FILE (política: $POLICY_NAME)"
  fi
  if [ "$writer_ok" = false ]; then
    issue_token "$WRITER_POLICY_NAME" diagnos-token-writer "$WRITER_TOKEN_FILE"
    log "🇺🇸 wrote writer token to $WRITER_TOKEN_FILE (policy: $WRITER_POLICY_NAME) — store the diagnos token with \`docker compose --profile login run --rm login\` · 🇧🇷 token de escrita escrito em $WRITER_TOKEN_FILE (política: $WRITER_POLICY_NAME) — guarde o token do diagnos com \`docker compose --profile login run --rm login\`"
  fi
}

main "$@"
