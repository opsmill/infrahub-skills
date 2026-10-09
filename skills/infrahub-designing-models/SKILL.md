---
name: infrahub-designing-models
description: >-
  Interviews the user about the business, the service and the data they
  want in Infrahub, and writes a design brief with a data model sketch
  and ordered features, before any schema YAML exists.
  TRIGGER when: someone has an idea or a problem but no agreed model,
  asks "what should I model" or "help me design my data model", wants
  diagrams, spreadsheets or exports turned into a design, has a scope
  too big for one feature and needs it split, or is updating, extending
  or fixing an existing design brief.
  DO NOT TRIGGER when: a design or model sketch already exists and the
  user wants schema YAML (use infrahub-managing-schemas), wants to load
  data (use infrahub-managing-objects or infrahub-importing-data), or
  wants to learn concepts (use infrahub-teaching-concepts).
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
argument-hint: "[idea, problem or existing brief]"
metadata:
  version: 1.3.0
  author: OpsMill
---

# Infrahub Model Designer

## Overview

An interview that ends in a design brief. It asks why
the data matters, what is delivered, and only then what
the model is, so the schema written later models the
service rather than guessing node kinds from a short
prompt. It recommends an answer to every question,
splits a scope that is too big into ordered features,
and writes no schema YAML: `infrahub-managing-schemas`
does that from the brief.

## When to Use

- "We want our L3VPN service in Infrahub" with no agreed
  model behind it.
- A customer or an OpsMill engineer brings diagrams,
  spreadsheets or a requirements document and needs a
  design out of them.
- A request covers several domains ("fiber plant, DWDM
  and customer wavelengths in one go").
- An existing brief needs another feature or a changed
  decision.

## Workflow

1. **Read before asking.** Read `.infrahub.yml`,
   `schemas/`, and any existing `design-brief.md`. Check
   the Marketplace (`infrahubctl marketplace search
   <domain>`) for a published schema to build on.
   Never ask what these already answer. Extending a
   design means editing its brief, not starting another.
2. **Ask for inputs once, first.** Before reading the
   inputs and on every later turn, read
   [rules/interview-inputs-digested.md](./rules/interview-inputs-digested.md):
   every file the user provides is listed and used as
   evidence, even when they say to skip it.
3. **State the starting point** in one line, with a
   confidence from 0 to 100. Below 70, name what is
   missing.
4. **Interview: business, then service, then data.**
   Draw questions from
   [references/question-bank.md](./references/question-bank.md).
   Every message you send during the interview is one
   question block; read
   [rules/interview-one-question-recommended.md](./rules/interview-one-question-recommended.md)
   before writing the first one. Push back once on a
   vague answer ("scalable", "everything", "like
   NetBox"), then record what the user says.
5. **Check the scope after the service layer,** before
   the data questions. Read
   [rules/scope-split-before-data-layer.md](./rules/scope-split-before-data-layer.md)
   for the signals, the merge rule, and what a split
   leaves in the sketch.
6. **Data layer, for F1 only.** Stop when every node
   kind in the sketch has an identity, a source of truth
   and an owner, or an open item, and you can predict
   the answers to your next three questions. At about
   25 questions, turn the remaining gaps into open
   items.
7. **Restate and confirm,** only when the user can
   reply (otherwise see "When the user cannot reply").
   First ask again about each accepted recommendation
   whose basis was weak, one question block per
   message, in the layout from the one-question rule.
   Then restate the brief and end that message with one
   question block asking for an explicit yes, with
   options such as `A. Yes, write the brief` and
   `B. Change something`; "sounds good" is not a yes.
8. **Write the brief** in the format in
   [references/brief-format.md](./references/brief-format.md).
   Before writing the sketch, read
   [rules/brief-sketch-rows-complete.md](./rules/brief-sketch-rows-complete.md);
   before writing the decision log, read
   [rules/brief-decision-provenance.md](./rules/brief-decision-provenance.md).
   Last, draw the plan map and the model map from the
   finished tables; read
   [rules/brief-maps-match-tables.md](./rules/brief-maps-match-tables.md)
   first.
9. **Name the next step and stop.** Hand F1 to the
   user's existing specification, planning or
   implementation workflow. If none is established,
   recommend `infrahub-managing-schemas` for the
   schema-first implementation, but do not invoke it.

### When the user cannot reply

Some requests come with every answer up front, or say
the user is away. Do not ask: take the answers as
given, record each decision with its provenance, and
skip step 7. Turn whatever they did not answer, and
every recommendation they did not confirm, into an
`open` decision with an open item rather than a
default, and write the brief. When there are no
answers at all, write only the next question block.

## Rule Categories

| Priority | Category | Prefix | Description |
| -------- | -------- | ------ | ----------- |
| CRITICAL | Interview | `interview-` | One question per message with a recommended answer; every input used as evidence |
| HIGH | Scope | `scope-` | Split a too-big scope into ordered features before the data questions; sketch F1 only |
| HIGH | Brief | `brief-` | Complete sketch rows or open items; every decision tagged with its provenance; plan and model maps that match their tables |

Full scope per prefix is in `rules/_sections.md`.

## Supporting References

- `references/brief-format.md`: the brief's location,
  sections and tables. The single home for that format.
- `references/question-bank.md`: questions by layer, and
  the Infrahub defaults a recommendation can rest on.
- `../infrahub-managing-schemas/`: turns the finished
  brief into schema YAML.
- `../infrahub-common/marketplace-reference.md`: the
  Marketplace commands and their minimum SDK version.
