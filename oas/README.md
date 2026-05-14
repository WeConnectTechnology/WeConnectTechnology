# iPaaS Availability FHIR eAPI — OAS bundle

MuleSoft Anypoint Exchange export of the `ipaas-availability-fhir-eapi-spec`
API, plus a single-file bundle suitable for pasting into externally-hosted
OpenAPI editors (Swagger Editor, Redocly, Stoplight, etc.).

## Files

- `source/` — pristine extraction of the Anypoint zip (multi-file layout with
  `components/`, `examples/`, `exchange_modules/`).
- `ipaas-availability-fhir-eapi-spec.bundled.yaml` — single self-contained
  YAML produced by `redocly bundle`. All `$ref`s are internal
  (`#/components/...`).
- `rewrite_refs.py` — preprocessor that normalises Anypoint-style `$ref`
  paths (leading-`/` and `../../` clamped) to filesystem-relative paths so
  off-the-shelf bundlers can resolve them.

## Regenerating the bundle

```bash
rm -rf build && cp -r source build
python3 rewrite_refs.py build
npx --yes @redocly/cli@latest bundle \
    build/ipaas-availability-fhir-eapi-spec.yaml \
    -o ipaas-availability-fhir-eapi-spec.bundled.yaml
```

## Pasting into Swagger Editor

Open <https://editor.swagger.io> and paste the contents of
`ipaas-availability-fhir-eapi-spec.bundled.yaml`. Schemas with the same
short name across modules (e.g. `Bundle`, `Organization`) are auto-suffixed
(`Bundle-2`, `Organization-2`) by the bundler to keep them unambiguous —
this is expected and does not affect API behaviour.
