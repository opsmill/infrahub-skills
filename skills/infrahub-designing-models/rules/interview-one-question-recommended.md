---
title: interview-one-question-recommended
impact: CRITICAL
tags: interview, question, recommendation, no-yaml
---

# Rule: interview-one-question-recommended

## The rule

Every interview message is exactly one question block,
and nothing else that asks anything:

1. One line `**Q<n> (<layer>):** <question>?`, where the
   layer is `inputs`, `business`, `service`, `scope`,
   `direction` or `data`.
2. Two to four options, `- A. ...`, each saying what it
   means in Infrahub.
3. Exactly one option ends with `**(Recommended)**`.
4. One `**Basis:**` line saying what the recommendation
   rests on, ending with its strength, written exactly
   `(strong)`, `(medium)` or `(weak basis)`. The Basis
   line is the last line of the message.

One exception: the value question. Its options are
exactly the five value drivers, A to E, optionally
followed by `F. Other (say which)`, never recommended.
The user may pick any number of them, and one or two
drivers carry `**(Recommended)**`
([brief-value-drivers.md](brief-value-drivers.md)). No
other question allows more than one answer.

A short lead-in before the block is fine if it asks
nothing, so it contains no question mark: the starting point, the current draft sketch
during the data questions (SKILL.md step 6), or the
restated brief before the final confirmation question
(SKILL.md step 7). When the user explicitly asks for
every question at once, follow "When the user asks for
every question at once" in
[../references/interview-paths.md](../references/interview-paths.md)
instead. No schema YAML, ever, even when the user asks
for it: the schema is written from the finished brief.

## Why it matters

A batch of questions turns into a form the user fills in
once, without thinking about how one answer changes the
next question. A question with no recommendation stalls
users who do not know the Infrahub options; a
recommendation with no stated basis gets accepted out of
habit. Writing a schema before the questions is the
failure this skill exists to stop: the model is then a
guess, and every answer after it only adjusts the guess.

## How to apply

- Pick the question whose answer changes the design
  most, from
  [../references/question-bank.md](../references/question-bank.md).
- Ground the recommendation in, in this order: the
  user's own files or earlier answers, then an Infrahub
  default from the question bank. With neither, say
  `(weak basis)` so the user does not accept it out of
  habit.
- When the user asks for something the skill does not
  do, such as schema YAML now or copying a demo's schema
  files, say so plainly in the lead-in, with the reason,
  then send the block. "Just give me the schema" gets a
  flat statement such as "The schema comes after a few
  short answers; written now, it would guess how each
  item is identified and who owns it." List what it
  would guess as statements, never as questions: the
  block holds the only question.

## Correct

```markdown
**Q1 (business):** Which task fails today because out-of-band console data is wrong or missing?

- A. Outage recovery: engineers cannot find the console port of a failed device  **(Recommended)**
- B. Audits: nobody can prove which devices have console access
- C. Provisioning: new devices are cabled to ports already in use

**Basis:** you said console access is checked by hand after every incident (medium)
```

## Incorrect

A schema draft, then a second question in prose.

```markdown
Here is a first draft:

    nodes:
      - name: ConsoleServer
        namespace: Oob

Does this look right? Also, which system owns console servers today?
```

## Common mistakes

| Mistake | Why it is wrong |
| ------- | --------------- |
| Two questions in one message | The second answer is given without the first one's effect |
| Two options marked Recommended outside the value question | The user has nothing to accept or reject |
| "Pick any" on a question other than the value question | Each other answer is one decision; several answers hide which one the design follows |
| `**Basis:**` left empty or without a strength | The user cannot tell a guess from a fact |
| Schema YAML "to save time" | The model is guessed before anything is known |
