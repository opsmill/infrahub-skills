# Diagnostics bundle — flag-emission fixture (violating)

Worker log contains an `OutOfMemoryError` but the bundle's
`flags.yml` does NOT include an `oom-in-logs` entry — the
flag-checker missed the signal. Used by the grader test
suite to confirm violations are caught.
