---
title: python-classes
impact: CRITICAL
tags: audit, python, checks, generators, transforms
---

# Rule: python-classes

**Severity**: CRITICAL
**Category**: Python Components

## What It Checks

Validates that Python classes for checks,
generators, and transforms inherit from the
correct base class, implement the required
methods with the right signatures, and avoid
methods that don't exist on the base.

## Why it matters

The Infrahub runner introspects each registered
Python file at execution time, not at registration
time — a class that doesn't subclass
`InfrahubCheck` / `InfrahubGenerator` /
`InfrahubTransform` registers cleanly but throws
`AttributeError` the first time the pipeline tries
to call its entrypoint, usually mid-proposed-
change so the failure shows up to reviewers, not
the author. The `log_warning()` trap is a frequent
one: it autocompletes alongside `log_error()` but
doesn't exist, raising `AttributeError` only on
the code path that triggers it. Missing
`allow_upsert=True` on generator saves means the
first run succeeds and every subsequent run blows
up on duplicate-key errors, making the generator
look intermittent. These are all caught cheaply
by static inspection of the class definitions.

## Checks

### Check Classes

1. Class inherits from `InfrahubCheck`
2. Implements `validate(self, data: dict)` (sync or async)
3. Has `query` class attribute
4. Does NOT call `log_warning()` (method does not exist)
5. Uses `self.log_error()` for failure conditions

### Generators

1. Class inherits from `InfrahubGenerator`
2. Implements `async generate(self, data: dict)`
3. Calls `save(allow_upsert=True)` on created objects
4. Handles empty data gracefully

### Transforms

1. Class inherits from `InfrahubTransform`
2. Implements `transform(self, data: dict)` (sync or async)
3. Has `query` class attribute
4. Return type matches expected format (dict for JSON, str for text)

## Common Issues

- Generator `generate()` method not declared as `async`
- Missing `allow_upsert=True` on generator saves (causes failures on re-run)
- Check using `log_warning()` which doesn't exist
- Transform missing `query` class attribute
