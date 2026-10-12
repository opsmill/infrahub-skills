---
title: brief-value-drivers
impact: HIGH
tags: brief, business, value, features, coaching
---

# Rule: brief-value-drivers

## The rule

The design names the value it is for, from these five
drivers, spelled exactly like this:

1. Reduced engineering effort
2. Faster service delivery
3. Lower change failure costs
4. Less duplicated operational work
5. Reduced risk of service disruption

- **Ask once, pick any.** The first business question
  offers the five drivers as options A to E, and the
  user picks any number. Recommend one or two from what
  the files and the request show. It is the only
  question that allows more than one answer
  ([interview-one-question-recommended.md](interview-one-question-recommended.md)).
- **Skipping is an answer.** "Skip", "not sure" or no
  reply takes the recommended drivers. Never ask for
  hours, costs or lead times.
- **Rank, do not ask again.** Order the chosen drivers
  by the evidence for them. The first one leads: F1 is
  the feature that delivers it, and the data questions
  start with the guesses that matter most for it. When
  the user picks four or five, say once in the next
  lead-in which driver leads, and go on.
- **Brief.** `## Business` opens with one `Value:` line,
  drivers in rank order, separated by `;`, each tagged
  `stated` or `recommended` in parentheses with what it
  rests on. The Features table has a `Value` column
  naming, for each feature, the drivers it serves from
  that line; F1's names the first. The format is in
  [../references/brief-format.md](../references/brief-format.md).
- **No invented figures.** A number, in digits or words,
  appears only on a
  `stated` entry, with its source: `answer Q<n>`,
  `request`, or `<input file>:<locator>`. A `Value`
  cell names drivers only. A missing number is not an
  open item.

## Why it matters

The person in the interview is usually a network
engineer or architect who wants a design going, not a
business case. Left alone, the design follows the data
they happen to have. Naming the value steers it: a pool
where clashes cost failed changes, a service object
where orders wait, one source of truth where the same
data is typed into three systems. The brief then shows
management, or OpsMill, what each feature is for before
anything is built. An invented saving does the
opposite: the first person who checks it stops trusting
the rest of the brief.

## How to apply

- Recommend from evidence: duplicate values in an export
  point to Lower change failure costs; values typed by
  hand to Reduced engineering effort; outages after
  changes to Reduced risk of service disruption; the
  same data in several systems to Less duplicated
  operational work; orders that wait to Faster service
  delivery.
- Coach through recommendations, not extra questions:
  when a choice serves the leading driver, the Basis
  says so ("a pool removes the duplicate route
  distinguishers in your export (strong)").
- Under the step 6 draft, add one or two lines on what
  the design gains for the leading driver, from the
  files and answers only.
- Name the leading driver in the Summary.
- When the user cannot reply, record the recommended
  drivers as `recommended`; they are not opened.

## Correct

```markdown
## Business

Value: Lower change failure costs (recommended: duplicate rd values in vpn-customers.xlsx); Reduced engineering effort (stated)

| ID | Feature | Intent | Value | ... |
| F1 | VPN service | One object per ordered VPN | Lower change failure costs | ... |
```

## Incorrect

A saving nobody stated, and a feature serving a driver
the line does not list.

```markdown
## Business

Value: Reduced engineering effort (recommended: saves 40 hours a month)

| ID | Feature | Intent | Value | ... |
| F1 | VPN service | One object per ordered VPN | Faster service delivery | ... |
```

## Common mistakes

| Mistake | Why it is wrong |
| ------- | --------------- |
| Asking for the hours or cost behind a driver | The engineer does not need to know it to get a design going |
| Opening an item for a missing figure | Open items are for what blocks the design |
| A paraphrased driver ("faster delivery") | Readers and tools match the five names |
| F1 chosen without the leading driver | The first thing built does not deliver what the design is for |
