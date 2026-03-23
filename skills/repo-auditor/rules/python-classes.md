# Rule: python-classes

**Severity**: CRITICAL
**Category**: Python Components

## What It Checks

Validates that Python classes for checks, generators,
and transforms inherit from the correct base class and
implement required methods.

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
