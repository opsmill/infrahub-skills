# Infrahub Transform Creator - Rule Sections

1. **Transform Types (types-)** -- CRITICAL. Python vs
   Jinja2 transforms, when to use which, output formats.
   Choosing wrong type leads to unnecessary complexity.

2. **Python Transform (python-)** -- CRITICAL.
   InfrahubTransform base class, transform() method,
   return types (dict=JSON, str=text), sync or async.

3. **Jinja2 Transform (jinja2-)** -- CRITICAL. Template
   syntax, data variable containing GraphQL response,
   netutils filters, template imports.

4. **Hybrid (hybrid-)** -- HIGH. Combining Python data
   preparation with Jinja2 rendering. Platform-specific
   template selection, FileSystemLoader setup.

5. **Artifacts (artifacts-)** -- HIGH. Connecting
   transforms to output files via artifact_definitions,
   content types, targets (CoreArtifactTarget),
   parameter mapping.

6. **API Reference (api-)** -- HIGH. Class attributes
   (query, timeout), instance properties (client,
   root_directory, server_url), methods, return types.

7. **Patterns (patterns-)** -- MEDIUM. Data extraction
   utilities (common.py), CSV output pattern, shared
   functions (get_data, get_interfaces).

8. **Testing (testing-)** -- LOW. infrahubctl transform
   and render commands, REST API endpoints.
