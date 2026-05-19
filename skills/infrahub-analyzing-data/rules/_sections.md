# Infrahub Analyst - Rule Sections

1. **MCP Tools (mcp-)** — CRITICAL. Available
   Infrahub MCP server tools, invocation patterns,
   how to pass GraphQL queries, and interpreting
   responses. Required before running any analysis
   query.

2. **Query Patterns (query-)** — CRITICAL. GraphQL
   structures for analysis use cases: fetching all
   objects of a kind, filtering by attribute,
   traversing relationships across node types.
   Getting queries right determines what data is
   available for correlation.

3. **Correlation (correlation-)** — HIGH. Techniques
   for matching, diffing, and joining data returned
   from multiple MCP queries: set operations,
   ID-based joins, attribute lookups,
   design-to-reality comparison, and service impact
   tracing. Correlation logic is where findings are
   identified.

4. **Reporting Output (reporting-)** — HIGH.
   Presenting findings clearly: summary tables with
   counts, per-object detail, remediation hints,
   and structured output for stakeholders. Good
   reporting makes analysis findings actionable.

5. **Approach Selection (approach-)** — MEDIUM.
   Decision guide for choosing between interactive
   MCP analysis (this skill), automated
   InfrahubCheck (infrahub-managing-checks), or
   artifact-producing Transform
   (infrahub-managing-transforms). Each has different
   trade-offs around automation, enforcement, and
   repeatability.
