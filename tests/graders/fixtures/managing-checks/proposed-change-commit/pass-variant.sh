#!/usr/bin/env bash
# Same behaviour as the plain script, refactored: the Git steps live in a
# function, use `git -C`, rebase instead of merge, push with an explicit
# refspec to HEAD, span lines with continuations, and also rebase the
# Infrahub branch (harmless next to the Git step).
set -euo pipefail

WORKDIR=/tmp/infra-repo
: "${BASE:=main}"

refresh_branch() {
  git -C "$WORKDIR" fetch --prune origin
  git -C "$WORKDIR" checkout -B "$1" "origin/$1"
  git -C "$WORKDIR" rebase \
    "origin/$BASE"
  git -C "$WORKDIR" push \
    --force-with-lease \
    origin "HEAD:refs/heads/$1" 2>&1
  infrahubctl branch rebase "$1"
}

run_checks() {
  curl -sS -X POST "$INFRAHUB_ADDRESS/graphql" \
    -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H "Content-Type: application/json" \
    --data @- <<EOF
{"query": "mutation { CoreProposedChangeRunCheck(data: {id: \"$1\"}) { ok } }"}
EOF
}

git clone --quiet git@git.example.com:netops/infra-repo.git "$WORKDIR" || true

mapfile -t rows < <(curl -sS -X POST "$INFRAHUB_ADDRESS/graphql" \
  -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"query": "{ CoreProposedChange(state__value: \"open\") { edges { node { id source_branch { value } } } } }"}' \
  | jq -r '.data.CoreProposedChange.edges[].node | "\(.id)|\(.source_branch.value)"')

for row in "${rows[@]}"; do
  refresh_branch "${row#*|}"
done

sleep 90  # the repository sync runs every minute

for row in "${rows[@]}"; do
  run_checks "${row%%|*}"
done
