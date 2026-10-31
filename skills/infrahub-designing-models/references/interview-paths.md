# Other Paths Through the Interview

The workflow in [../SKILL.md](../SKILL.md) assumes a user
who answers one question at a time on a new design. These
sections cover the four cases that change it. Each keeps
the brief format in [brief-format.md](brief-format.md).

## When the user cannot reply

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
splitting, are recorded, not opened. So are the value
drivers: record the ones you recommend as
`recommended`. Build on the recommended design direction
and record it as an `open` decision whose open item
names the directions not taken.

## When the user asks for every question at once

Send one numbered set: the inputs question, then at
most five business and service questions, each in the
block layout of
[rules/interview-one-question-recommended.md](../rules/interview-one-question-recommended.md),
then the design-direction block of step 5. Follow it
with the step 6 draft for the recommended direction, and under the draft at
most three data questions, as blocks, on the guesses
that change the design most. The user corrects the rest
by marking up the draft. Whatever they leave unanswered or
uncorrected becomes an open item, as above.

## Extending a brief

- Keep what was agreed: existing features, sketch rows
  and decisions stay as they are unless the user changes
  them.
- Close each open item the user answers as in "Coming
  back with an answer" below. Items still unanswered
  stay.
- Continue the numbering: the next feature ID, decision
  number and `O<n>` after the highest in the brief.
- A gap found in an agreed feature, such as a peer F1's
  intent needs, becomes an open item proposing the
  change, settled before that feature in Next steps.
  Do not edit agreed rows on your own.
- Update Summary, Business and Service with what the
  user said, and redraw the maps and Next steps.

## Coming back with an answer

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
