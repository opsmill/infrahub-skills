#!/usr/bin/env bash

# Detect if this is an Infrahub project and activate schema skills

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
    "additionalContext": "This is an Infrahub project. When the user asks about schema design, data modeling, or infrastructure data management tasks, use the `infrahub-schema-creator` skill from the infrahub plugin.\n\nThe skill documentation is located at: ${CLAUDE_PLUGIN_ROOT}/skills/schema-creator/\n\nKey files to reference:\n- SKILL.md - Overview and quick start\n- reference.md - Complete schema property reference (nodes, attributes, relationships, generics)\n- validation.md - Schema validation commands and migration guide\n- examples.md - Ready-to-use schema templates\n\nWhen working with Infrahub schemas:\n1. Read the relevant skill documentation files before making schema changes\n2. Follow Infrahub naming conventions (PascalCase for nodes/generics, snake_case for attributes)\n3. Always include human_friendly_id for nodes\n4. Set identifier on bidirectional relationships\n5. Use generics for shared attributes across multiple node types\n6. Validate schemas with `infrahubctl schema check` before loading"
  }
}
EOF
fi

exit 0
