#!/usr/bin/env bash
# Re-validate every open proposed change with the fixed check.
# Follows the runbook: rebase each Infrahub branch, then retry the checks.
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
  infrahubctl branch rebase "$b"
done <<< "$open_pcs"

echo "Waiting for the repository sync to record the new commits"
sleep 120

while read -r pc_id b; do
  gql "{\"query\": \"mutation { CoreProposedChangeRunCheck(data: {id: \\\"$pc_id\\\"}) { ok } }\"}"
done <<< "$open_pcs"
