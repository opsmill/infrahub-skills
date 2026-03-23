# Running Evaluations

## Overview

Evaluations test that skills produce correct output.
Each skill can have an eval file in
`evaluations/<skill-name>.json` that defines test
scenarios with prompts, expected outputs, and
assertions.

The eval workflow uses the `/skill-creator` skill,
which handles running test prompts, grading outputs,
and showing results in a browser-based viewer.

## Eval File Format

```json
{
  "skill_name": "infrahub-schema-creator",
  "evals": [
    {
      "id": 1,
      "prompt": "Create an Infrahub schema...",
      "expected_output": "A schema with correct types",
      "files": [],
      "expectations": [
        "VLAN id attribute is renamed",
        "Status uses kind: Dropdown"
      ],
      "assertions": [
        {
          "name": "attr-min-length",
          "check": "VLAN id renamed to >= 3 chars"
        },
        {
          "name": "dropdown-for-status",
          "check": "Status uses kind: Dropdown"
        }
      ]
    }
  ]
}
```

### Fields

| Field | Purpose |
| ----- | ------- |
| `prompt` | The user request — make it realistic and specific |
| `expected_output` | Human-readable description of what correct output looks like |
| `files` | Input files to include (usually empty for Infrahub skills) |
| `expectations` | Human-readable list of verifiable outcomes |
| `assertions` | Machine-checkable criteria with descriptive names |

## Writing Good Eval Prompts

**Be realistic.** Write the kind of thing an actual
user would type — with specific names, namespaces,
field types, and context. Not "create a schema" but
"Create an Infrahub schema for a VLAN management
system with an id attribute, a name, a status
dropdown, and a role field."

**Cover different complexity levels.** Include:

- A basic scenario that exercises core functionality
- A moderate scenario with relationships and
  cross-references
- An advanced scenario with generics, hierarchies,
  or edge cases

**Include known trouble spots.** If the skill has
rules for common mistakes (e.g., using deprecated
field names, missing bidirectional identifiers), write
eval prompts that would expose these mistakes without
the skill's guidance.

## Writing Good Assertions

**Make them objectively verifiable.** "Output looks
nice" is not an assertion. "Status uses kind: Dropdown
with choice objects" is.

**Use descriptive names.** The name appears in the
eval viewer and benchmark reports. Someone scanning
results should understand what `dropdown-for-status`
checks without reading the full description.

**Focus on what the skill uniquely provides.** If a
model would get something right even without the
skill, testing it isn't very informative. Test the
things the skill's rules specifically address.

## Running Evals

### Using /skill-creator

1. Open this repository in Claude Code
2. Invoke `/skill-creator` and tell it you want to
   evaluate an existing skill
3. Point it to the skill directory and the eval file
4. It will run each prompt with and without the skill,
   grade outputs, and open the eval viewer

### The Eval Viewer

The viewer has two tabs:

- **Outputs** — Click through each test case, see the
  prompt, output, and formal grades. Leave feedback
  in the textbox.
- **Benchmark** — Quantitative comparison: pass rates,
  timing, and token usage for with-skill vs.
  without-skill runs.

### Iteration Loop

1. Run evals, review in viewer, identify issues
2. Improve the skill (rules, examples, descriptions)
3. Re-run evals into a new iteration directory
4. Compare with previous iteration in the viewer
5. Repeat until satisfied

## Existing Evals

| Skill | Eval File | Scenarios |
| ----- | --------- | --------- |
| infrahub-schema-creator | `evaluations/schema-creator.json` | 3 (VLAN management, circuit management, location hierarchy) |

Other skills don't have evals yet — adding them is a
good contribution. Focus on skills with the most
complex rules first (object-creator, check-creator,
generator-creator).
