#!/usr/bin/env bash

# Detect if this is an Infrahub project and activate all Infrahub skills

INFRAHUB_DETECTED=false

# Check for Infrahub config files
if [[ -f ".infrahub.yml" ]] || [[ -f "infrahub.toml" ]]; then
    INFRAHUB_DETECTED=true
fi

# Check for schema files with Infrahub markers
if [[ "$INFRAHUB_DETECTED" == "false" ]]; then
    for schema_file in schemas/*.yml schemas/*.yaml *.yml *.yaml; do
        if [[ -f "$schema_file" ]]; then
            if grep -q 'version: "1.0"' "$schema_file" 2>/dev/null && \
               (grep -q '^nodes:' "$schema_file" 2>/dev/null || grep -q '^generics:' "$schema_file" 2>/dev/null); then
                INFRAHUB_DETECTED=true
                break
            fi
        fi
    done
fi

# If Infrahub project detected, output context for Claude
if [[ "$INFRAHUB_DETECTED" == "true" ]]; then
    cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "This is an Infrahub project. When the user asks about schema design, data modeling, or infrastructure data management tasks, use the `infrahub-managing-schemas` skill from the infrahub plugin.\n\nThe skill documentation is located at: ${CLAUDE_PLUGIN_ROOT}/skills/infrahub-managing-schemas/\n\nKey files to reference:\n- SKILL.md - Overview and quick start\n- reference.md - Complete schema property reference (nodes, attributes, relationships, generics)\n- validation.md - Schema validation commands and migration guide\n- examples.md - Ready-to-use schema templates\n\nWhen working with Infrahub schemas:\n1. Read the relevant skill documentation files before making schema changes\n2. Follow Infrahub naming conventions (PascalCase for nodes/generics, snake_case for attributes)\n3. Always include human_friendly_id for nodes\n4. Set identifier on bidirectional relationships\n5. Use generics for shared attributes across multiple node types\n6. Validate schemas with `infrahubctl schema check` before loading\n\nAdditional skills available:\n- `infrahub-managing-objects` - Create data objects (devices, locations, etc.) at ${CLAUDE_PLUGIN_ROOT}/skills/infrahub-managing-objects/\n- `infrahub-managing-checks` - Create validation checks at ${CLAUDE_PLUGIN_ROOT}/skills/infrahub-managing-checks/\n- `infrahub-managing-generators` - Create design-driven generators at ${CLAUDE_PLUGIN_ROOT}/skills/infrahub-managing-generators/\n- `infrahub-managing-transforms` - Create data transforms at ${CLAUDE_PLUGIN_ROOT}/skills/infrahub-managing-transforms/\n- `infrahub-managing-menus` - Create navigation menus at ${CLAUDE_PLUGIN_ROOT}/skills/infrahub-managing-menus/\n- `infrahub-analyzing-data` - Query and correlate live Infrahub data via the MCP server at ${CLAUDE_PLUGIN_ROOT}/skills/infrahub-analyzing-data/\n- `infrahub-auditing-repo` - Audit the repository against all rules and best practices at ${CLAUDE_PLUGIN_ROOT}/skills/infrahub-auditing-repo/\n- Shared references and rules at ${CLAUDE_PLUGIN_ROOT}/skills/infrahub-common/\n\nBefore running any `infrahubctl` command, detect the correct Python environment: try `uv run infrahubctl info`, then `poetry run infrahubctl info`, then `infrahubctl info` directly — use the first that succeeds as the prefix for all subsequent commands. See ${CLAUDE_PLUGIN_ROOT}/skills/infrahub-common/rules/connectivity-python-environment.md for the full detection rule and ${CLAUDE_PLUGIN_ROOT}/skills/infrahub-common/rules/connectivity-server-check.md for server connectivity troubleshooting."
  }
}
EOF
fi

exit 0
