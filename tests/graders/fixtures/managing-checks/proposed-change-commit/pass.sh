#!/usr/bin/env bash
# Re-validate every open proposed change with the fixed check.
# The pipeline runs the code at the repository commit recorded on each source
# branch, so main has to be merged into each branch's Git branch first.
set -euo pipefail

REPO_URL="git@git.example.com:netops/infra-repo.git"
DEFAULT_BRANCH="main"
WORKDIR="$(mktemp -d)"

gql() {
  curl -sS -X POST "$INFRAHUB_ADDRESS/graphql" \
    -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$1"
}

open_pcs=$(gql '{"query": "{ CoreProposedChange(state__value: \"open\") { edges { node { id source_branch { value } } } } }"}' \
  | jq -r '.data.CoreProposedChange.edges[].node | "\(.id) \(.source_branch.value)"')

git clone --quiet "$REPO_URL" "$WORKDIR"
cd "$WORKDIR"

while read -r pc_id b; do
  git fetch origin
  git checkout "$b"
  git merge --no-edit "origin/$DEFAULT_BRANCH"
  git push origin "$b"
done <<< "$open_pcs"

echo "Waiting for the repository sync to record the new commits"
sleep 120

while read -r pc_id b; do
  gql "{\"query\": \"mutation { CoreProposedChangeRunCheck(data: {id: \\\"$pc_id\\\"}) { ok } }\"}"
done <<< "$open_pcs"
