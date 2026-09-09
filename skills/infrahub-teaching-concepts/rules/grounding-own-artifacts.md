# Teach Through the Learner's Own Artifacts

When the learner has a repo or an instance, their data is the lesson
material. Generic examples are the fallback, not the default.

## Why it matters

"Your TestbedSensor node declares this relationship" lands harder than
any toy example, and it answers the question learners actually bring:
why does my setup work the way it does. Generic examples are for empty
environments only.

## The rule

During environment detection, read the learner's schema and object files
(or query the instance read-only). Anchor the Explain section to their
node kinds, attribute names, and real objects. Instantiate the exercise
spec against their artifacts. Fall back to the concept map's generic
examples only when no learner artifacts exist.

## Correct

An Explain section that names the learner's actual node kinds and quotes
a snippet of their schema.

## Incorrect

The learner supplies a schema and the lesson explains relationships with
an invented `Person`/`Car` example anyway.
