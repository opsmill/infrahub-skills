---
paths:
  - "graders/**/*.py"
  - "scripts/check*.py"
  - "tests/test_*.py"
---

# Grader Rules

Full reference: `dev/guides/adding-a-rule.md` §2 and §5,
`dev/guides/running-evals.md`

Graders are deterministic: no LLM grading, no network
calls. Inspect the parsed artifact and return a hard
pass/fail.

A gate is a grader too. A `scripts/check-*.py` or a
pytest asserting something about this repository's own
text (frontmatter, a reference against an upstream
model) makes the same mistakes, and every rule below
applies to it.

## Parse the answer; never substring-match it

`"x" in text` is the reflexive first draft, and the
commonest way a check goes wrong. It passes an answer
that merely mentions the trap and fails a correct answer
that words it differently. Parse the artifact instead:

| Artifact | Parse with |
| -------- | ---------- |
| Schema / object / menu YAML | `yaml.safe_load`, then walk the structure |
| Python (checks, generators, transforms) | `ast` |
| Shell commands | `shlex` over the whole line, after joining `\` continuations; see "Reading commands out of Markdown" |
| Prose reports | locate the section, then rank evidence — see "Grading prose" below |

Three failure modes follow from matching raw text:

- **Comments and docstrings count as code.** Strip them
  before asserting, or a `# WRONG:` contrast block in
  the answer satisfies the check meant to fail it.
- **Only the first fence gets graded.** Extract every
  fenced block, and accept an answer whose entire output
  is fenced.
- **Adjacency is not structure.** A verb next to a path
  does not mean the command ran against that path.

## Reading commands out of Markdown

A check asking "did the answer run X" counts only a
command that would run. Splitting on operators first and
then tokenizing each piece is the tempting shape, and it
fabricates segments inside quotes:

```python
# Non-compliant: "a; b" becomes two commands
for piece in re.split(r"&&|\|\||;|\|", line):
    tokens = shlex.split(piece)
```

```python
# Compliant: operators become their own tokens
lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
lexer.whitespace_split = True
tokens = list(lexer)
```

Each case below shipped as a false pass or a false fail:

- **Fences.** A fence may be indented under a list item.
  It closes on a run of the same character at least as
  long as the opener.
- **Data is not a command.** Arguments to `echo` or
  `printf`, quoted text, and heredoc bodies.
- **The program is argv[0] after wrappers.** Peel
  `sudo`, `env`, `VAR=value`, and `uv|poetry|pipx run`,
  each with its own option table.
- **The subcommand is positional.** It is the first
  non-option argument: `git stash push` is not a push.
- **A placeholder is not a value.** `<name>`, `{}`, and
  an unexpanded `$var` never satisfy a required target.
- **A `\` continuation joins with no separator**, as the
  shell does.

Build `infrahubctl` command sets from `GROUPS` and
`LEAVES` in `graders/common/cli_tree.py`, never a
hand-kept list.

## A must-not check fails closed

A check that fails on a forbidden shape passes whatever
its parser cannot read: an unparseable line, an unknown
wrapper, an empty input. That false pass reads as
compliance, and enumerating wrappers one review round at
a time never ends. Instead:

- Treat an unparseable line that names the binary as a
  violation.
- Back the parser with a plain scan for the forbidden
  pattern in runnable code.
- Fail a gate that read zero inputs.
- Assert over every item. Exempt by a named list with a
  reason, never by a filter that decides what gets
  checked.

## Grading prose: rank evidence, don't list phrasings

Some answers have nothing to parse: a
`verified_against` field, a `## Verification` section, a
justification sentence. Enumerating the phrasings a bad
answer might use is wrong in both directions at once,
and both are the same bug. Wording is unbounded.

Ask what the check is really for, then test for that
directly, strongest evidence first:

1. An explicitly declared non-verification passes. The
   rule asks for exactly that honesty.
2. A named artifact or version passes, and may then
   discuss an analogy freely. Reasoning about evidence
   is not evidence by analogy.
3. Only then does a bare analogy fail.

Ordering it this way lets step 3 be broad without
punishing an answer resting on something real. Getting
it wrong compounds: a check that grades wording teaches
the next author to write what satisfies the regex rather
than what is correct. The measurement behind this, on a
check that shipped, is in
[adding-a-rule.md](../guides/adding-a-rule.md#why-ranking-evidence-beats-listing-phrasings).

## Check function shape

`graders/<skill>/lib.py` exposes a `CHECKS` registry
mapping assertion names to functions:

```python
def check_my_assertion(schema: dict, **_) -> tuple[bool, str]:
    """One-line summary of what this asserts."""
    if not_compliant:
        return False, "Specific failure message"
    return True, "Concise success message"
```

The failure message must name the assertion that
actually broke.

A rule cutting across multiple skills (rare) gets the
check duplicated in each `graders/<skill>/lib.py` rather
than hoisted to a shared module — the skills are
deliberately independently owned. Rules belonging to
`infrahub-common` grade from `graders/common/`.

`graders/auditing-repo/lib.py` is the one exception, and
this rule loads when you open it: its registry is
`_CHECKS`, private, keyed by colon-encoded
`<check>[:<arg>...]` names resolved through `_dispatch`,
and its check functions take `(findings, ...)` rather
than a parsed artifact. Read that file's own docstring
before adding to it; the shape above describes the other
fourteen.

## Verify both directions

The obvious compliant/violating pair catches neither
failure mode. Hand-craft **four** fixtures:

| Fixture | Expected |
| ------- | -------- |
| Compliant, written the way the rule shows | 1.0 |
| Compliant, refactored the way the check's traversal is vulnerable to | 1.0 |
| Violating, obviously | < 1.0 |
| Violating **near-miss**: carries every token the check reads, bound to the wrong subject or holding the wrong value | < 1.0 |

Build each violating fixture from a compliant one by
changing one shape, and assert the failure message, not
only the score. A fixture that fails for a reason other
than the one it names proves nothing.

The last of each pair finds the bugs:

- **False fail.** A correct answer scores < 1.0. Vary
  what the check actually reads, not the cosmetics. If
  it walks the AST for call order, extract the calls
  into a helper; if it reads a comparison in a test
  position, hoist it into a variable; if it keys on a
  node name, put two relationships on one node; if it
  reads an object-YAML attribute, use the
  `{value: ..., source: ...}` form. Field order and
  synonyms exercise nothing.
- **Laundering.** A violating answer scores 1.0 because
  it mentions the right word, imports the right module,
  or names the right helper somewhere in the file. Reach
  the subject another way: another API spelling, an
  aliased or rebound name, a helper two calls deep, a
  same-named method on an unrelated receiver. If a
  comment or a bare string makes the violating fixture
  pass, the check grades vocabulary, not substance.
- **Omission.** A check that reads a field only when
  present passes the answer that deletes it. Where the
  task's input guarantees the field, assert it is there.
- **Boundaries.** Every boundary the check draws (a gap
  width, a clause anchor, a function scope, a word edge)
  gets a fixture on each side.

Commit the four as accept and reject cases in
`tests/graders/test_<skill>_lib.py`. Run once in a
terminal, they protect nothing from the next refactor.

## Don't hold a second copy of the prose

A grader that hard-codes a command tree, a kind list, or
a set of valid flags holds a second copy of the skill's
prose, and the two diverge the first time the prose
changes. Derive it from one place, or assert the shape
rather than the membership.

## Task grader scripts

`graders/<skill>/check_<task>.py` calls the shared
`run_checks` library and bundles the new assertion with
related baseline assertions (schema version, naming) so
the task catches regressions in neighbouring rules.

For `infrahub-auditing-repo` `yagni-*` rules, wire the
shared parameterized grader from `eval.yaml`
(`check_yagni_rule.py <rule> <severity> <ladder-step>`)
instead of adding a bespoke script. Write a dedicated
script only for file-attribution or carve-out checks the
parameterized grader cannot express.
