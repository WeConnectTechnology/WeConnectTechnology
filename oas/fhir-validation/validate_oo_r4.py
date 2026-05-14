#!/usr/bin/env python3
"""Offline FHIR R4 OperationOutcome structural validator.

Encodes the FHIR R4 OperationOutcome StructureDefinition cardinalities,
datatypes and required ValueSet bindings as code so we can validate the
spec's example payloads without internet access to packages.fhir.org.

Source of truth: http://hl7.org/fhir/R4/operationoutcome.html  (R4 4.0.1)
"""

import json
import sys
from pathlib import Path

# FHIR R4 OperationOutcome.issue.severity — required binding to
# http://hl7.org/fhir/ValueSet/issue-severity
ISSUE_SEVERITY = {"fatal", "error", "warning", "information"}

# FHIR R4 OperationOutcome.issue.code — required binding to
# http://hl7.org/fhir/ValueSet/issue-type
ISSUE_TYPE = {
    "invalid", "structure", "required", "value", "invariant",
    "security", "login", "unknown", "expired", "forbidden", "suppressed",
    "processing", "not-supported", "duplicate", "multiple-matches",
    "not-found", "deleted", "too-long", "code-invalid", "extension",
    "too-costly", "business-rule", "conflict",
    "transient", "lock-error", "no-store", "exception", "timeout",
    "incomplete", "throttled",
    "informational",
}


def validate(payload, path):
    errs = []

    if not isinstance(payload, dict):
        return [f"{path}: payload root must be a JSON object"]
    if payload.get("resourceType") != "OperationOutcome":
        errs.append(f"{path}: resourceType must equal 'OperationOutcome', got {payload.get('resourceType')!r}")

    if "id" in payload and not isinstance(payload["id"], str):
        errs.append(f"{path}: .id must be a string")

    issues = payload.get("issue")
    if not isinstance(issues, list) or len(issues) < 1:
        errs.append(f"{path}: .issue is required, MUST be a non-empty array (cardinality 1..*)")
        return errs

    for idx, issue in enumerate(issues):
        loc = f"{path}.issue[{idx}]"
        if not isinstance(issue, dict):
            errs.append(f"{loc}: must be an object")
            continue
        sev = issue.get("severity")
        if sev is None:
            errs.append(f"{loc}.severity: required, missing")
        elif sev not in ISSUE_SEVERITY:
            errs.append(f"{loc}.severity: {sev!r} not in required ValueSet issue-severity {sorted(ISSUE_SEVERITY)}")
        code = issue.get("code")
        if code is None:
            errs.append(f"{loc}.code: required, missing")
        elif code not in ISSUE_TYPE:
            errs.append(f"{loc}.code: {code!r} not in required ValueSet issue-type")
        # details is CodeableConcept (optional); if present, must be object
        d = issue.get("details")
        if d is not None and not isinstance(d, dict):
            errs.append(f"{loc}.details: must be a CodeableConcept object")
        # diagnostics must be string
        if "diagnostics" in issue and not isinstance(issue["diagnostics"], str):
            errs.append(f"{loc}.diagnostics: must be a string")
        # location / expression: each is string[]
        for arr_field in ("location", "expression"):
            if arr_field in issue:
                if not isinstance(issue[arr_field], list) or not all(isinstance(s, str) for s in issue[arr_field]):
                    errs.append(f"{loc}.{arr_field}: must be array of strings")
    return errs


def main():
    payload_dir = Path("/home/user/WeConnectTechnology/oas/fhir-validation/payloads")
    files = sorted(payload_dir.glob("*.json"))
    print(f"Validating {len(files)} payload(s) against FHIR R4 OperationOutcome\n")

    fail = 0
    for f in files:
        payload = json.loads(f.read_text())
        errs = validate(payload, f.name)
        if errs:
            fail += 1
            print(f"FAIL  {f.name}")
            for e in errs:
                print(f"    {e}")
        else:
            print(f"PASS  {f.name}")
    print(f"\nSummary: {len(files) - fail} pass, {fail} fail")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
