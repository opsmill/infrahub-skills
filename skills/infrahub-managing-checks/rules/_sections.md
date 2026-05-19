# Infrahub Check Creator - Rule Sections

1. **Architecture (architecture-)** -- CRITICAL. Three-
   component structure (query + Python + config), global
   vs targeted checks, when each runs. Foundational
   understanding required before writing checks.

2. **Python Class (python-)** -- CRITICAL. InfrahubCheck
   base class, validate() method signature, log_error()
   causes failure, log_info() is safe, no log_warning().
   Getting logging wrong causes silent pass or
   unexpected fail.

3. **API Reference (api-)** -- HIGH. Class attributes
   (query, timeout), instance properties (client,
   branch_name, params), execution lifecycle
   (collect_data, validate, count errors).

4. **Registration (registration-)** -- HIGH.
   .infrahub.yml check_definitions config, query name
   matching, targets for targeted checks, parameters
   mapping.

5. **Patterns (patterns-)** -- MEDIUM. Error collection
   before logging, shared utility functions (common.py),
   scoped validation for performance on large datasets.

6. **Testing (testing-)** -- LOW. infrahubctl check
   commands, listing checks, running against specific
   branches.
