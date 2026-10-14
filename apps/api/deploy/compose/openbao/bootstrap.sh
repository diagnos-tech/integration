#!/bin/sh
# One-shot bootstrap for the Compose OpenBao: initialise (or resume), unseal when the seal is Shamir, enable KV v2, and
# issue the scoped token `diagnos-api` reads via `OPENBAO_TOKEN_FILE`. Runs once per `docker compose up` as the
# `openbao-bootstrap` service, using only POSIX `sh` and the binaries already in the `openbao/openbao` image (no `jq`;
# see the `_json_field`/`_json_array` helpers below) because that image is all this container has.
#
# STAGING-ONLY WARNING: with `OPENBAO_SEAL=shamir` this script keeps the unseal keys on the `openbao-state` volume so it
# can re-unseal on every `docker compose restart` without a human. That is a deliberate convenience for a throwaway
# environment, not a production posture. In production, either configure a real auto-unseal backend
# (`OPENBAO_SEAL=aws|gcp|azure|transit`, see `../k8s/autounseal/*/README.md`) or unseal by hand and keep the recovery
# keys off any machine that also holds the encrypted data.
set -eu

BAO_ADDR="${OPENBAO_ADDR:-http://openbao:8200}"
export BAO_ADDR
STATE_DIR="/state"
INIT_FILE="$STATE_DIR/openbao-init.json"
TOKEN_FILE="$STATE_DIR/openbao-token"
POLICY_NAME="diagnos-sdk"
POLICY_SRC="/bootstrap/policy.hcl"
POLICY_RENDERED="/tmp/diagnos-sdk-policy.hcl"

log() {
  # This is the one place an operator actually reads this container's output, so every message stands on its own.
  printf '[openbao-bootstrap] %s\n' "$1"
}

# Pulls one `"key": "value"` scalar out of a `-format=json` blob with grep+sed instead of jq (not present in this
# image). Assumes the CLI's own pretty-printer, which puts each scalar field on its own line; that holds for every
# `bao`/`vault` JSON output this script parses.
_json_field() {
  field="$1"
  file="$2"
  grep -o "\"${field}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$file" | head -n1 | sed -E 's/.*:[[:space:]]*"([^"]*)"$/\1/'
}

_json_bool() {
  field="$1"
  file="$2"
  grep -o "\"${field}\"[[:space:]]*:[[:space:]]*(true|false)" "$file" | head -n1 | sed -E 's/.*:[[:space:]]*//'
}

# Pulls every string out of a `"field": [ "a", "b", ... ]` array, one per line. Used for `unseal_keys_b64`, which only
# Shamir populates.
_json_array() {
  field="$1"
  file="$2"
  sed -n "/\"${field}\"/,/\]/p" "$file" | grep -o '"[A-Za-z0-9+/=]\{20,\}"' | tr -d '"'
}

wait_for_openbao() {
  # `bao status` exits 0 unsealed and 2 sealed (uninitialised counts as sealed); both mean "reachable". Only exit 1 (or
  # the process not being up yet at all) means "keep waiting". This loop must not require unsealed, because unsealing
  # is this very script's job.
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
  log "timed out waiting for $BAO_ADDR to answer"
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
  # Shamir-only path: re-unseal a restarted `openbao` container using the keys this same script saved to `$INIT_FILE` on
  # first boot. There is nothing to do for an auto-unseal backend: the KMS/Transit call happens inside `bao` itself as
  # soon as the process starts, before this script even gets to check.
  if [ ! -f "$INIT_FILE" ]; then
    log "sealed, but no saved keys at $INIT_FILE. This is expected right after a fresh init with an auto-unseal backend (it should already be unsealing itself); for Shamir it means the state volume was lost and someone must unseal by hand."
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
  # `bao secrets enable` has no `-force`/idempotent flag; the second run always fails with "path is already in use" on
  # stderr, which is exactly the success case here, so it is matched and swallowed instead of treated as an error.
  if ! bao secrets enable -path=secret kv-v2 >/tmp/enable.out 2>&1; then
    if ! grep -q "already in use" /tmp/enable.out; then
      cat /tmp/enable.out
      exit 1
    fi
  fi
}

write_policy() {
  : "${DIAGNOS_WORKSPACE_ID:?DIAGNOS_WORKSPACE_ID must be set in .env. Run \`diagnos status\` with the token this deployment will use to find it.}"
  : "${DIAGNOS_ACCOUNT_ID:?DIAGNOS_ACCOUNT_ID must be set in .env. It is in the same \`diagnos status\` output.}"
  sed -e "s/__WORKSPACE_ID__/${DIAGNOS_WORKSPACE_ID}/g" -e "s/__ACCOUNT_ID__/${DIAGNOS_ACCOUNT_ID}/g" "$POLICY_SRC" >"$POLICY_RENDERED"
  bao policy write "$POLICY_NAME" "$POLICY_RENDERED" >/dev/null
}

issue_token() {
  bao token create -orphan -policy="$POLICY_NAME" -display-name=diagnos-api -renewable=true -format=json >/tmp/token.json
  client_token="$(_json_field client_token /tmp/token.json)"
  if [ -z "$client_token" ]; then
    log "could not parse client_token from bao token create output"
    cat /tmp/token.json
    exit 1
  fi
  printf '%s' "$client_token" >"$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"
  # The API container reads this file as uid 10001 (the root `Dockerfile`); in Compose this script runs as root and hands
  # the file over. Under Kubernetes it runs as the `openbao` user via `kubectl exec`, the chown is not permitted, and
  # the operator copies the token into a Secret instead (`../../k8s/openbao/bootstrap-configmap.yaml`), hence the soft
  # failure.
  chown "${DIAGNOS_API_UID:-10001}" "$TOKEN_FILE" 2>/dev/null \
    || log "could not chown $TOKEN_FILE to uid ${DIAGNOS_API_UID:-10001} (expected under Kubernetes)"
}

token_is_valid() {
  [ -f "$TOKEN_FILE" ] || return 1
  BAO_TOKEN="$(cat "$TOKEN_FILE")" bao token lookup >/dev/null 2>&1
}

main() {
  mkdir -p "$STATE_DIR"
  wait_for_openbao

  root_token="${BAO_ROOT_TOKEN_OVERRIDE:-}"

  if ! is_initialized; then
    log "not initialized, running \`bao operator init\` (once, ever, for this raft volume)"
    bao operator init -format=json >"$INIT_FILE"
    chmod 600 "$INIT_FILE"
    root_token="$(_json_field root_token "$INIT_FILE")"
    log "############################################################"
    log "SECURITY: $INIT_FILE now holds the recovery/unseal keys AND"
    log "the root token, in cleartext, on the openbao-state volume. Copy"
    log "them to an offline secret store NOW and delete them from this"
    log "volume — anyone who can read this file owns this OpenBao."
    log "############################################################"
  fi

  if is_sealed; then
    unseal_with_saved_keys
  fi

  if token_is_valid; then
    log "existing $TOKEN_FILE still resolves via \`bao token lookup\`; keeping it, no root privileges needed."
    exit 0
  fi

  if [ -z "$root_token" ] && [ -f "$INIT_FILE" ]; then
    root_token="$(_json_field root_token "$INIT_FILE")"
  fi
  if [ -z "$root_token" ]; then
    log "no usable token at $TOKEN_FILE and no root token available (no fresh init this run, $INIT_FILE absent or already cleaned up). Set BAO_ROOT_TOKEN_OVERRIDE in .env to a privileged token for one run to reissue it. TODO(gustavo): a real recovery flow (recovery-key-based root generation) is out of scope for a staging bootstrap script."
    exit 1
  fi

  BAO_TOKEN="$root_token"
  export BAO_TOKEN
  ensure_kv_v2
  write_policy
  issue_token
  log "wrote scoped token to $TOKEN_FILE (policy: $POLICY_NAME)"
}

main "$@"
