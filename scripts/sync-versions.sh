#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?Usage: sync-versions.sh <version>}"

echo "Syncing version to: $VERSION"

# Update all SKILL.md frontmatter metadata version fields.
# The 2-space indent targets only the frontmatter "  version: X.Y.Z"
# under the metadata: block, not schema examples like version: "1.0".
for f in skills/*/SKILL.md; do
  if [ -f "$f" ]; then
    sed -i.bak "s/^  version: .*/  version: $VERSION/" "$f" && rm -f "${f}.bak"
    echo "  Updated: $f"
  fi
done

# Update .github/.release-manifest.json
if [ -f ".github/.release-manifest.json" ]; then
  jq --arg v "$VERSION" '.version = $v' .github/.release-manifest.json > /tmp/release-manifest.json \
    && mv /tmp/release-manifest.json .github/.release-manifest.json
  echo "  Updated: .github/.release-manifest.json"
fi

# Update pyproject.toml
if [ -f "pyproject.toml" ]; then
  sed -i.bak "s/^version = .*/version = \"$VERSION\"/" pyproject.toml && rm -f pyproject.toml.bak
  echo "  Updated: pyproject.toml"
fi

echo "Done."
