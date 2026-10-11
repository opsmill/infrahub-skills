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
and writes no YAML or code: the `infrahub-managing-*`
skill for each artifact builds it from the brief.

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
   <domain>`) for a published schema to build on, and
   read the worked examples in
   [references/reference-designs.md](./references/reference-designs.md),
   including newer demos it tells you how to find. You
   choose one in step 5.
   Discovery that needs the network runs once: one
   Marketplace search for the domain, one listing of
   newer demos. A command that fails or does not return
   promptly is not retried; record it as an open item and
   go on. Never ask what these already answer. Extending a
   design means editing its brief, not starting another;
   see "Extending a brief" below.
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
   vague answer ("scalable", "everything"), then record
   what the user says. When the user compares their model
   to NetBox, read `../infrahub-common/netbox-vs-infrahub.md`
   and name the differences it states that matter for
   this design, instead of copying the NetBox shape. Keep the
   business and service layers short, about five
   questions together: the draft in step 6 shows which
   of their gaps matter, and you can return to them.
5. **Check the scope and choose the reference design
   after the service layer,** before the data questions.
   Read
   [rules/scope-split-before-data-layer.md](./rules/scope-split-before-data-layer.md)
   for the signals, the merge rule, and what a split
   leaves in the sketch, and
   [rules/brief-reference-design.md](./rules/brief-reference-design.md)
   to choose the closest worked example from the
   business and service answers and the user's inputs.
6. **Draft the sketch, then question the draft,** for
   F1 only. People correct a draft faster than they
   answer questions about a model they cannot see.
   - **Draft.** Before the first data question, show
     F1's sketch table, and the Features table after a
     split. Fill each cell with a guess marked `(guess)`
     that comes from the user's files, their answers,
     the reference design or an Infrahub default in the
     question bank. A cell none of these supports stays
     `?` and becomes a question. Do not invent
     attributes or peers nobody mentioned.
   - **Samples.** When the user gave rows of data, show
     two or three sample objects built from them under
     the draft (one VPN with two of its sites, say), so
     a wrong identity or cardinality shows on real data.
     Without rows, show none.
   - **Left out.** Add one line naming what you left out
     because nobody mentioned it (a vendor, a serial
     number, a status), so the user can bring it in.
   - **Ground each guess** in the current best-practice
     rules, which grow over time: list the file names in
     `../infrahub-managing-schemas/rules/` and the
     `yagni-*` files in `../infrahub-auditing-repo/rules/`,
     read only the rules that govern a decision in front
     of you, and name the rule in the question's basis
     by its plain name (uniqueness-constraints, not a
     link). The question bank's links are starting
     points, not the full set. When the design needs a
     generator, a check or a transform, do the same with
     that skill's rules (`../infrahub-managing-generators/`,
     `../infrahub-managing-checks/`,
     `../infrahub-managing-transforms/`) and ask what it
     needs: what drives it, what it produces, when it
     runs.
   - **Question the draft.** Ask about the guesses that
     change the design most, one question block per
     message with the draft as its lead-in, and after
     each answer show only the rows that changed.
   - **Stop** when every node kind has an identity, a
     source of truth and an owner, or an open item, and
     you can predict the answers to your next three
     questions. At about 25 questions, turn the
     remaining guesses into open items.
7. **Walk one scenario through the model, then restate
   and confirm.** Take one lifecycle event from the
   service layer (an order, a change, a decommission) and
   say which nodes it creates, changes or removes. A gap
   it shows, such as a missing peer or an unclear delete,
   becomes the next question, or an open item when the
   user cannot reply. Restate and confirm only when the
   user can reply (otherwise see "When the user cannot
   reply").
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
   Before writing Mechanisms, read
   [rules/brief-mechanisms-match-artifacts.md](./rules/brief-mechanisms-match-artifacts.md).
   Then draw the plan map and the model map from the
   finished tables; read
   [rules/brief-maps-match-tables.md](./rules/brief-maps-match-tables.md)
   first. Name in each open item the features it
   affects: [rules/brief-open-items-name-features.md](./rules/brief-open-items-name-features.md).
   Last, write Next steps:
   [rules/brief-next-steps.md](./rules/brief-next-steps.md).
9. **Point to the Next steps and stop.** They hand F1
   to the user's existing workflow, or name the skill for
   each of its artifacts. Do not invoke them.

### When the user cannot reply

Some requests come with every answer up front, or say
the user is away. When there are no answers at all,
write only the next question block. Otherwise do not
ask: take the answers as given, record each decision
with its provenance, and skip step 7. Build the draft
of step 6 for yourself but do not present it; go
straight to the brief. Turn every
design decision they did not answer, and every
recommendation you would have asked them to confirm,
into an `open` decision with an open item rather than a
default, and write the brief. Node kind names and the
outcome of the skill's own rules, such as not
splitting, are recorded, not opened.

### When the user asks for every question at once

Send one numbered set: the inputs question, then at
most five business and service questions, each in the
block layout of
[rules/interview-one-question-recommended.md](./rules/interview-one-question-recommended.md).
Follow it with the step 6 draft, and under the draft at
most three data questions, as blocks, on the guesses
that change the design most. The user corrects the rest
by marking up the draft. Whatever they leave unanswered or
uncorrected becomes an open item, as above.

### Extending a brief

- Keep what was agreed: existing features, sketch rows
  and decisions stay as they are unless the user changes
  them.
- Close what the user answers: an open item they settle
  becomes a `stated` decision, its `open: O<n>` cells
  take the answer, and the item leaves Open items and
  Next steps. Items still unanswered stay.
- Continue the numbering: the next feature ID, decision
  number and `O<n>` after the highest in the brief.
- A gap found in an agreed feature, such as a peer F1's
  intent needs, becomes an open item proposing the
  change, settled before that feature in Next steps.
  Do not edit agreed rows on your own.
- Update Summary, Business and Service with what the
  user said, and redraw the maps and Next steps.

### Coming back with an answer

A user returns with an answer to an open item ("O2 is
settled: the NOC owns cabling"). Read the brief, then:

1. Record the answer as a `stated` decision, put it in
   every cell that said `open: O2`, and remove O2 from
   Open items and Next steps.
2. Take the features O2 `affects`. For a `planned`
   feature, update its rows and Handoff.
3. For a `specified` or `built` feature, do not rewrite
   it silently. Add a dated line to its Handoff saying
   what changed, and a Next step that sends the change
   on: re-specify it in the user's workflow, or, for a
   loaded schema, change it with
   `infrahub-managing-schemas`, which handles the
   migration.
4. If the answer adds node kinds or a new domain, run
   the scope check of step 5 again; a new feature takes
   the next ID, and no ID changes.
5. Redraw the maps, and tell the user which features
   the answer changed.

## Rule Categories

| Priority | Category | Prefix | Description |
| -------- | -------- | ------ | ----------- |
| CRITICAL | Interview | `interview-` | One question per message with a recommended answer; every input used as evidence |
| HIGH | Scope | `scope-` | Split a too-big scope into ordered features before the data questions; sketch F1 only |
| HIGH | Brief | `brief-` | Complete sketch rows or open items; every decision tagged with its provenance; plan and model maps that match their tables; the closest reference design named; mechanisms that match the artifacts; open items that name the features they affect; next steps in order |

Full scope per prefix is in `rules/_sections.md`.

## Supporting References

- `references/brief-format.md`: the brief's location,
  sections and tables. The single home for that format.
- `references/question-bank.md`: questions by layer, the
  schema and YAGNI rules each one serves, and the
  Infrahub defaults a recommendation can rest on.
- `references/reference-designs.md`: OpsMill worked
  examples to build from, and how to find newer ones.
- `../infrahub-managing-*/`: build each feature's
  artifacts from the finished brief, schema first.
- `../infrahub-common/marketplace-reference.md`: the
  Marketplace commands and their minimum SDK version.
