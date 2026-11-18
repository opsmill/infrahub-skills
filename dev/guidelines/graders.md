---
paths:
  - "graders/**/*.py"
  - "scripts/check*.py"
  - "tests/**/*.py"
  - "skills/*/scripts/**/*.py"
  - ".agents/skills/*/scripts/**/*.py"
---

# Grader Rules

Full reference: `dev/guides/adding-a-rule.md` §2 and §5,
`dev/guides/running-evals.md`

Graders are deterministic: no LLM grading, no network
calls. Inspect the parsed artifact and return a hard
pass/fail.

A gate is a grader too. A `scripts/check-*.py`, a
pytest asserting something about this repository's own
text, or a bundled script whose empty output means
"nothing found" makes the same mistakes, and every rule
below applies to it.

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

Failure modes that follow from matching raw text:

- **Comments and docstrings count as code.** Strip them
  before asserting, or a `# WRONG:` contrast block in
  the answer satisfies the check meant to fail it.
- **Skipping a labelled block cuts both ways.** Skip a
  fence only when its label stands alone (`# Bad
  example`, `# WRONG:`). A sentence that opens with a
  verdict word (`# Do not create a new group here, reuse
  it`) is part of the answer. Never skip a span that
  holds the forbidden command itself.
- **Only the first fence gets graded.** Extract every
  fenced block, and accept an answer whose entire output
  is fenced.
- **Adjacency is not structure.** A verb next to a path
  does not mean the command ran against that path.
- **A placeholder is not a value.** `<name>`, `{}`, `-`,
  `TBD`, and an unexpanded `$var` never satisfy a
  required target or a table cell.
- **One match is not every match.** A must-have check
  holds for every matching command or row, not the
  first one found.

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
- **Prompts are not part of the command.** Strip a
  leading `$` or `%` prompt, and a leading `>`
  continuation prompt in `console` fences only.
- **Data is not a command.** Arguments to `echo` or
  `printf`, and quoted text. A heredoc body is data
  unless the command holding `<<` runs stdin as a
  script: a shell with no script file and no `-c`,
  `ssh` with no remote command, `docker|kubectl exec -i`,
  or `cat <<EOF | sh`.
- **The program is argv[0] after wrappers.** Peel
  `sudo`, `env`, `VAR=value`, and `uv|poetry|pipx run`,
  each with its own option table. Short options parse
  getopt-style: `-uroot` carries its value.
- **The subcommand follows the global options and their
  values.** `git -C /repo push` is a push; `git stash
  push` is not.
- **A `\` continuation joins with no separator**, as the
  shell does.

Build `infrahubctl` command sets from `GROUPS` and
`LEAVES` in `graders/common/cli_tree.py`, never a
hand-kept list.

After the second review round that extends a shell
parser for one task, ask whether to narrow the task's
contract (one command per line, no heredocs) instead.
That is a decision for the maintainers, not the author.

## A must-not check fails closed

A check that fails on a forbidden shape passes whatever
its parser cannot read: an unparseable line, an unknown
wrapper, an empty input. That false pass reads as
compliance. Instead:

- Treat an unparseable line that names the binary as a
  violation.
- Back the parser with a plain scan for the forbidden
  pattern in runnable code.
- Fail on zero inputs: an empty output directory, a YAML
  file that parses to nothing, an unreadable file, an
  empty table, a listing cut at its `--limit`, a pipeline
  whose middle stage failed. A script must exit non-zero
  on any of these, not print an empty result.
- Exempt by a named list with a reason, never by a
  filter that decides what gets checked.

When the forbidden set is open-ended (any command that
can print a value, any wording of a request), invert it.
The allowed forms are short and fixed; the forbidden
ones are not, and listing them one review round at a
time never ends:

```python
# Non-compliant: every round adds a printing command
PRINTERS = {"echo", "printf", "cat", "tee", "envsubst"}
leaked = argv[0] in PRINTERS and "$INFRAHUB_API_TOKEN" in line
```

```python
# Compliant: every expansion fails unless it is a safe form
# ([ -n ... ] operand, curl header, ${TOKEN:+set})
leaked = any(not is_safe_use(line, m) for m in TOKEN_EXPANSION.finditer(line))
```

Bound the check to the answers its task can plausibly
produce. Record the known shapes it does not catch in
its docstring, and change it only for a plausible answer
or a shape an eval run produced.

## Grading prose: rank evidence, don't list phrasings

Some answers have nothing to parse: a
`verified_against` field, a `## Verification` section, a
justification sentence. Enumerating the phrasings a bad
answer might use is wrong in both directions at once.
Wording is unbounded.

Ask what the check is really for, then test for that
directly, strongest evidence first:

1. An explicitly declared non-verification passes. The
   rule asks for exactly that honesty.
2. A named artifact or version passes, and may then
   discuss an analogy freely. Reasoning about evidence
   is not evidence by analogy.
3. Only then does a bare analogy fail.

The same idea applies to other prose:

- **Read the structure the rule prescribes.** If the
  rule says to write a `- Root:` line or an
  `## Open questions` section, read that line or
  section, not the heading wording around it.
- **Match the subject, not the sentence.** To decide
  which rows are about a decision, match the decision
  itself, not word-order filters for each way a row can
  be phrased.
- **Scope a negation to its clause.** In "Paste the
  token here; I will not log it", the `not` belongs to
  `log`, not to `paste`. Each clause boundary (`;`,
  `and`, a colon that is not in a URL) gets a fixture on
  both sides.

The measurement behind this, on a check that shipped, is
in
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
actually broke. A check that raises reports
`Error running check: <exc>`, which the sandbox tests
read as a crash, not a verdict.

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
before adding to it; the shape above describes every
other grader.

## Verify both directions

The obvious compliant/violating pair catches neither
failure mode. Hand-craft **four** fixtures:

| Fixture | Expected |
| ------- | -------- |
| Compliant, written the way the rule shows | 1.0 |
| Compliant, refactored the way the check's traversal is vulnerable to | 1.0 |
| Violating, obviously | < 1.0 |
| Violating **near-miss**: carries every token the check reads, bound to the wrong subject or holding the wrong value; one per binding the check draws (file to row, flag to command, call to receiver) | < 1.0 |

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
  `{value: ..., source: ...}` form. If it reads a field
  or flag that has a default, leave it out: the check
  must score the value the tool resolves (an omitted
  `on_delete` on a Component is `cascade`), not the
  literal token. Field order and synonyms exercise
  nothing.
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
`tests/graders/test_<skill>_lib.py`. Fixtures you only
run once in a terminal protect nothing from the next
refactor. The compliant fixture is the rule's example
copied verbatim; when a review round edits the example,
copy it again.

## Changing an existing check

A fix for a false fail is the usual way a check starts
passing violations. Every fix in a review round tends to
break the opposite direction, so:

- Run the base-branch grader and the new one on the same
  inputs. Every input whose result flips gets a
  committed fixture, and each flip must be intended.
- Keep every existing reject fixture failing. Add a
  near-miss for the shape the change now accepts.
- Before you remove or swap a check in a task, run the
  task's violating fixtures without it. It may have been
  the only check failing them.
- A regression test for the fix must fail on the parent
  commit. A fallback path can make it pass without the
  new code running.
- Re-read the check's docstring, its assertion text, and
  the task's `expected_output`. Each claim must still be
  one the grader scores.

## Don't hold a second copy of the prose

A grader that hard-codes a command tree, a kind list, or
a set of valid flags holds a second copy of the skill's
prose, and the two diverge the first time the prose
changes. Derive it from one place, or assert the shape
rather than the membership. When the source is outside
the sandbox, keep the copy and add a pytest that pins it
to the source.

## Task grader scripts

`graders/<skill>/check_<task>.py` calls the shared
`run_checks` library. The score is the share of checks
passed, against a 0.8 threshold. With five or more
checks, the rule's own check can fail and the task still
passes. Gate the task on its core check, so its failure
zeroes the score, and let neighbouring rules lower the
score by their share: `neighbours=` in
`graders/designing-models/lib.py`, `gate_checks=` in
`graders/auditing-repo/lib.py`.

For `infrahub-auditing-repo` `yagni-*` rules, wire the
shared parameterized grader from `eval.yaml`
(`check_yagni_rule.py <rule> <severity> <ladder-step>`)
instead of adding a bespoke script. Write a dedicated
script only for file-attribution or carve-out checks the
parameterized grader cannot express.
