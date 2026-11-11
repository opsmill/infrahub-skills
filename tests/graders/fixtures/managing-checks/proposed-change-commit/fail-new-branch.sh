#!/usr/bin/env bash
# Re-validate every open proposed change with the fixed check.
# A new branch starts from the current commit on main, so open a new branch
# and a new proposed change for each one.
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

while read -r pc_id b; do
  infrahubctl branch create --sync-with-git "$b-v2"
  gql "{\"query\": \"mutation { CoreProposedChangeCreate(data: {name: {value: \\\"$b\\\"}, source_branch: {value: \\\"$b-v2\\\"}, destination_branch: {value: \\\"$DEFAULT_BRANCH\\\"}}) { ok } }\"}"
done <<< "$open_pcs"

echo "Waiting for the repository sync to record the new commits"
sleep 120

while read -r pc_id b; do
  gql "{\"query\": \"mutation { CoreProposedChangeRunCheck(data: {id: \\\"$pc_id\\\"}) { ok } }\"}"
done <<< "$open_pcs"
