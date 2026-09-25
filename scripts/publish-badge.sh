#!/usr/bin/env bash
# 🇺🇸 Commits one badge JSON to the orphan `badges` branch (created on first
#    use) with the workflow's own GITHUB_TOKEN. Keeping badges off `develop`
#    means a coverage change never shows up as a commit in the code history.
#    Usage: scripts/publish-badge.sh <source.json> <name-on-branch.json>
# 🇧🇷 Faz commit de um JSON de badge na branch órfã `badges` (criada no
#    primeiro uso) com o GITHUB_TOKEN do próprio workflow. Manter os badges
#    fora da `develop` faz uma mudança de cobertura nunca aparecer como commit
#    no histórico do código.
#    Uso: scripts/publish-badge.sh <origem.json> <nome-na-branch.json>
set -euo pipefail

source_file="$1"
target_name="$2"
worktree="$(mktemp -d)"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

if git fetch --depth=1 origin badges 2>/dev/null; then
  git worktree add "$worktree" FETCH_HEAD
  git -C "$worktree" switch -c badges
else
  git worktree add --orphan -b badges "$worktree"
fi

cp "$source_file" "$worktree/$target_name"
git -C "$worktree" add "$target_name"
if git -C "$worktree" diff --cached --quiet; then
  echo "badge unchanged · badge sem mudança"
  exit 0
fi
git -C "$worktree" commit -m "chore(badges): update ${target_name} [skip ci]"
git -C "$worktree" push origin badges
