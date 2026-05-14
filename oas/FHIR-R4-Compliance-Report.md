# FHIR R4 REST API Compliance Report

**Spec audited:** `oas/ipaas-availability-fhir-eapi-spec.bundled.yaml` (iPaaS
Availability FHIR eAPI v1.0.0).
**Targets:** FHIR R4 (4.0.1) base spec + FHIR REST API conventions + UK Core
profile expectations. Implementation Guide profile validation was attempted
with `validator_cli.jar` but the sandbox blocks `packages.fhir.org`,
`packages2.fhir.org`, `simplifier.net`, and `hl7.org`; the R4 OperationOutcome
checks below were therefore done with an offline structural validator
(`fhir-validation/validate_oo_r4.py`) that encodes the R4
StructureDefinition cardinalities and the `issue-severity` / `issue-type`
required bindings by hand.

## Summary

| Area | Verdict |
|---|---|
| Example payloads (OperationOutcome × 7) vs FHIR R4 base | **Pass** — 7/7 |
| Media types on responses | **Fail** — `application/json` used where `application/fhir+json` is required |
| Capability Statement (`/metadata`) | **Fail** — missing entirely |
| Search parameter names | **Fail in 2 places** (`schedule.location.identifier`, `CYPEnabled`); needs custom `SearchParameter` resources for `cyp-enabled`/`insurer` |
| Date prefix coverage | **Partial** — only `ge`/`le` accepted; spec strictly subsets FHIR's prefix set |
| `appointment-type` codings | **Fail** — `hl7.org` is not a real FHIR system URI |
| `Bundle` response constraints | **Gap** — no example payload, no enforcement of `type=searchset`, no `total`, no `link[self]` |
| Error envelope on `/health-check` | **Non-FHIR by design** — acceptable if endpoint is outside FHIR REST surface, but advertised on the FHIR API host |
| OperationOutcome examples — code/severity bindings | **Pass** — all 7 use legal `issue-type` and `issue-severity` codes |

## 1. Resource-level validation results

Offline validator output (`payloads/*.json` extracted from the spec's
inlined examples):

```
Validating 7 payload(s) against FHIR R4 OperationOutcome

PASS  400_invalid_date_range.json
PASS  400_invalid_input_parameter_badrequest.json
PASS  401_authentication_error.json
PASS  403_forbidden_error.json
PASS  500_internal_server_error.json
PASS  503_connectivity_error.json
PASS  504_request_timed_out.json

Summary: 7 pass, 0 fail
```

What was checked, per the FHIR R4 OperationOutcome StructureDefinition:
- `resourceType` literal `"OperationOutcome"`
- `issue` cardinality `1..*`, each item with required `severity` (bound to
  `http://hl7.org/fhir/ValueSet/issue-severity`) and `code` (bound to
  `http://hl7.org/fhir/ValueSet/issue-type`)
- Datatypes of `details`, `diagnostics`, `location`, `expression`

What was **not** checked (offline limitation):
- UK Core profile constraints (e.g.
  `https://fhir.hl7.org.uk/StructureDefinition/UKCore-*`)
- Reference target validity / `meta.profile` integrity
- Terminology bindings outside `issue-type` / `issue-severity` (no tx server)
- Full `Slot` / `Schedule` / `Location` / `HealthcareService` /
  `Practitioner` / `Organization` payload validation — **the spec ships no
  success example for the `/Slot` Bundle response**, so there's nothing to
  validate yet (see §3.7).

To finish this off in an environment with internet:

```bash
java -Xmx4g -jar validator_cli.jar payloads/*.json \
    -version 4.0 \
    -ig fhir.r4.ukcore.stu3.currentbuild \
    -profile https://fhir.hl7.org.uk/StructureDefinition/UKCore-Slot \
    -tx http://tx.fhir.org/r4
```

## 2. REST-level compliance findings

### 2.1 Media types on responses — Fail

`/Slot` advertises `application/json` for both the 200 success (which
returns a FHIR `Bundle`) and the 400 error (which carries an
`OperationOutcome` example). FHIR R4 §3.2.0.1.1 requires
`application/fhir+json` (or `application/fhir+xml`) for any payload that
**is** a FHIR resource. `application/json` is permitted as a fallback only
when negotiating with non-FHIR clients.

Inconsistent today: `/Slot` 401/403/500/503/504 already use
`application/fhir+json`. Only 200 and 400 are wrong.

**Fix:** change the `content:` key on the 200 and 400 responses to
`application/fhir+json` and give 400 the same `OperationOutcome` schema
the other error responses use.

### 2.2 Capability Statement — Fail (missing)

Per FHIR R4 §3.2.0.1.2, a FHIR REST service MUST expose
`GET /metadata` returning a `CapabilityStatement`. The spec only defines
`/health-check` (Mule-style heartbeat) and `/Slot`. Without
`/metadata`, generic FHIR clients cannot discover supported interactions,
search parameters, or profiles.

**Fix:** add a `GET /metadata` path returning a
`CapabilityStatement` resource. At minimum it must list the `Slot`
resource, the `searchType` interaction, the search parameters in §2.4, and
the supported FHIR version (`4.0.1`).

### 2.3 `/health-check` endpoint — Non-FHIR by design

`/health-check` returns a Mule-style heartbeat JSON
(`name/status/hostname/businessGroupId/...`) and on error returns
`ErrorResponse` (`header.transactionId` + `eventDetail[].errorCode`).
Neither matches any FHIR resource. Acceptable as an out-of-band
operational endpoint, but two cleanups make it less surprising:

- Move it off the FHIR base path, or rename to `/_health` to signal it's
  not a FHIR resource (FHIR resource names are case-sensitive PascalCase
  and FHIR clients may attempt `GET /Health-check` validation).
- Document that this endpoint is **not** part of the FHIR REST contract.

### 2.4 Search parameter names — 2 failures + 2 gaps

| Param | Status | Notes |
|---|---|---|
| `schedule.actor:Practitioner.identifier` | OK | Valid R4 chained search: Slot → schedule → Schedule.actor (modifier `:Practitioner`) → Practitioner.identifier |
| `specialty` | OK | Standard `Slot-specialty` search param |
| `service-type` | OK | Standard `Slot-service-type` |
| `schedule.location.identifier` | **Fail** | `Schedule` has no `location` element; it has `actor` (a `Reference(Patient \| Practitioner \| ... \| Location \| ...)`). The chain must be `schedule.actor:Location.identifier`. |
| `schedule.actor:Practitioner.gender` | OK | Valid chained search |
| `start` | OK | Standard `Slot-start` |
| `appointment-type` | OK (name) | See §2.6 for the value coding issue |
| `CYPEnabled` | **Fail (naming)** | FHIR R4 §3.2.1.1 requires search parameter names to be lowercase, hyphen-separated (e.g. `cyp-enabled`). Mixed-case names are not interoperable. |
| `insurer` | Gap | Name is fine; **but** to be FHIR-conformant the API MUST publish a `SearchParameter` resource (and reference it in `CapabilityStatement.rest.resource.searchParam`) for this custom parameter. Same applies to `cyp-enabled`. |

### 2.5 Date prefix coverage — Partial

The `start` parameter's regex `^(ge|le)[0-9]{4}-[0-9]{2}-[0-9]{2}$`
restricts callers to only `ge` and `le` prefixes. FHIR R4 §3.2.1.2 defines
the full prefix set: `eq, ne, gt, lt, ge, le, sa, eb, ap`. A FHIR server
MAY restrict to a subset, **but** the restriction must be documented in
the `CapabilityStatement` (`searchParam.documentation`) and a request
using an unsupported prefix must yield an `OperationOutcome` with
`issue.code = not-supported`. Today the spec implicitly rejects via OAS
schema, which produces a generic 400 (`invalid`) — the surface contract
should advertise the restriction explicitly.

### 2.6 `appointment-type` enum values — Fail

The OAS declares `appointment-type` values as `"hl7.org|IMP"`,
`"hl7.org|AMB"`, `"hl7.org|SS"`. The token-search syntax `system|code`
is correct, but `hl7.org` is not a FHIR system URI. The R4 binding
for `Slot.appointmentType` points at the v2-0276 value set; if you're
deliberately overriding with v3 ActEncounterCode, the correct system is:

```
http://terminology.hl7.org/CodeSystem/v3-ActCode
```

So a conformant search becomes:

```
?appointment-type=http://terminology.hl7.org/CodeSystem/v3-ActCode|AMB
```

(Side note: `SS` is not a standard `ActCode`; you may want `EMER`,
`HH`, `IMP`, `AMB`, `PRENC`, `OBSENC`, `SS` is in some local extensions
but isn't in v3 ActCode core. Verify against the upstream code system.)

### 2.7 `Bundle` response constraints — Gap (no example)

`/Slot` 200 returns `#/components/schemas/Bundle` but **no example
payload** is provided, and the OAS schema does not pin the FHIR-required
fields for a searchset Bundle:

- `Bundle.type` MUST be `"searchset"` for search responses
- `Bundle.total` SHOULD be present (count of matches)
- `Bundle.link` SHOULD include at least `{relation: "self", url: "..."}`
  and `next` if paginating

The bundled `Bundle` schema inlines the FHIR base `Bundle` and adds an
`entry` overlay — it doesn't constrain `type`, `total`, or `link`. Add an
example payload showing a `searchset` Bundle with at least one `Slot`
entry and a self link.

### 2.8 Headers — Mostly fine

`Content-Security-Policy`, `X-Content-Type-Options`, `Cache-Control`,
`Referrer-Policy`, `X-Correlation-Id` are all reasonable. Two
considerations:

- FHIR uses `ETag` (resource-version) and `Last-Modified` on read/vread.
  Not relevant to this search-only API, just noting absence.
- `X-Correlation-Id` is on errors but not on the 200. For consistency,
  include it everywhere — FHIR doesn't mandate it but tracing needs it.

### 2.9 `ErrorResponse` envelope leaking onto FHIR endpoints — OK *so far*

The `ErrorResponse` envelope (`header.transactionId`, `eventDetail[]`) is
defined in `components/schemas/api-response.yaml` and used only by
`/health-check`. None of the `/Slot` error responses reference it.
Make sure that stays true in implementation — if a CloudHub APIKit error
ever bubbles up from `/Slot`, the response must still be an
`OperationOutcome`, not the Mule `ErrorResponse`.

## 3. Verbatim resource-level checks (offline)

The seven OperationOutcome examples are minimal and valid. All use legal
codes:

| File | severity | code | Verdict |
|---|---|---|---|
| `400_invalid_date_range.yaml` | `error` | `invalid` | OK |
| `400_invalid_input_parameter_badrequest.yaml` | `error` | `invalid` | OK |
| `401_authentication_error.yaml` | `error` | `login` | OK |
| `403_forbidden_error.yaml` | `error` | `forbidden` | OK |
| `500_internal_server_error.yaml` | `error` | `exception` | OK |
| `503_connectivity_error.yaml` | `error` | `transient` | OK |
| `504_request_timed_out.yaml` | `error` | `timeout` | OK |

One stylistic note: each `OperationOutcome.id` is a numeric-looking
string (`"6007"` etc.). `id` is a `string` so that's valid, but for
transient error payloads you don't really need a stable id. Either drop
it, or use it as a correlation handle and document the mapping.

## 4. Priority fix list

Numbered roughly by impact on interoperability:

1. **Add `GET /metadata` returning a `CapabilityStatement`** (§2.2).
2. **Change `application/json` to `application/fhir+json`** on `/Slot`
   200 and 400; give 400 the `OperationOutcome` schema like its siblings
   (§2.1).
3. **Rename `schedule.location.identifier` to
   `schedule.actor:Location.identifier`** (§2.4).
4. **Rename `CYPEnabled` to `cyp-enabled`** and publish a
   `SearchParameter` resource for it and `insurer` (§2.4).
5. **Replace `hl7.org` system URI with
   `http://terminology.hl7.org/CodeSystem/v3-ActCode`** in
   `appointment-type` values (§2.6).
6. **Add a `Bundle` searchset example payload** on `/Slot` 200, with
   `type=searchset`, `total`, and `link[self]` (§2.7).
7. **Document the `start` prefix restriction** (only `ge`/`le`
   supported) in the search parameter's CapabilityStatement entry
   (§2.5).
8. **Move `/health-check` to `/_health`** or otherwise mark it as
   non-FHIR (§2.3).

## 5. Reproducing the validation

```bash
# (1) Pull OperationOutcome JSON from the spec's YAML examples
python3 - <<'PY'
import yaml, json
from pathlib import Path
src = Path("oas/source/examples/errors/fhir")
out = Path("oas/fhir-validation/payloads"); out.mkdir(parents=True, exist_ok=True)
for f in src.glob("*.yaml"):
    out.joinpath(f.stem + ".json").write_text(
        json.dumps(yaml.safe_load(f.read_text())["value"], indent=2))
PY

# (2) Offline structural check (sandbox-friendly)
python3 oas/fhir-validation/validate_oo_r4.py

# (3) Full check (needs internet to packages.fhir.org + tx.fhir.org)
java -Xmx4g -jar oas/fhir-validation/validator_cli.jar \
    oas/fhir-validation/payloads/*.json \
    -version 4.0 \
    -tx http://tx.fhir.org/r4
```
