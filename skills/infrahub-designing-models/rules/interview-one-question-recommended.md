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
   layer is `inputs`, `business`, `service`, `scope` or
   `data`.
2. Two to four options, `- A. ...`, each saying what it
   means in Infrahub.
3. Exactly one option ends with `**(Recommended)**`.
4. One `**Basis:**` line saying what the recommendation
   rests on, ending with its strength, written exactly
   `(strong)`, `(medium)` or `(weak basis)`. The Basis
   line is the last line of the message.

A one-line lead-in before the block is fine if it asks
nothing. No schema YAML, ever, even when the user asks
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
- When the user says "just give me the schema", still
  send the block. Say in the lead-in, without a
  question, that the schema comes after a few answers.

## Correct

```markdown
**Q1 (business):** Which task fails today because out-of-band console data is wrong or missing?

- A. Outage recovery: engineers cannot find the console port of a failed device  **(Recommended)**
- B. Audits: nobody can prove which devices have console access
- C. Provisioning: new devices are cabled to ports already in use

**Basis:** you said console access is checked by hand after every incident (medium).
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
| Two options marked Recommended | The user has nothing to accept or reject |
| `**Basis:**` left empty or without a strength | The user cannot tell a guess from a fact |
| Schema YAML "to save time" | The model is guessed before anything is known |
