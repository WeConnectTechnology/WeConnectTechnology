# FHIR Validator Deployment Knowledge Base

**Purpose:** Comprehensive technical and architectural knowledge base covering the evaluation of FHIR validator deployment options for an organization running MuleSoft (CloudHub 2.0) integrations against UK Core and Spire Core FHIR profiles, with an existing AKS-hosted validator + terminology service ("WEHub") available.

**Audience:** AI assistant training material, architecture reviewers, integration engineers.

---

## 1. Context and Problem Statement

### 1.1 Organization context
- **Integration platform:** MuleSoft, deployed on **CloudHub 2.0**
- **Mule Runtime:** 4.9 / 4.10
- **JDK:** 17
- **Licensing model:** Per-flow (with vCore consumption from CloudHub 2.0 entitlement pool)
- **Existing capability:** "WEHub" — an internal AKS-hosted service running the FHIR validator with co-located terminology server
- **Current pain point:** Active production performance issue with terminology calls hitting an external tx server

### 1.2 FHIR profile set in scope
- **FHIR R4** (base spec)
- **UK Core** — UK national FHIR profiles (~30 profiles: Patient, Encounter, Observation, MedicationRequest, etc.)
- **Spire Core** — internal IG package, ~20–30 FHIR resources

### 1.3 The architectural question
Where should FHIR validation logic actually run when Mule receives inbound FHIR Bundles for processing?

Three (plus one) candidate architectures:
1. Embed the FHIR validator JAR inside each Mule integration application
2. Centralize the validator as a dedicated Mule application on CloudHub 2.0
3. Use the existing WEHub (AKS) service via REST
4. Hybrid: validator in Mule, terminology in WEHub

### 1.4 Stakeholder dynamics
- **Mule architect (Govind):** Prefers staying within CloudHub. Reasoning: simplicity, single platform, skills alignment with Mule team. Comfortable with high memory but resists high CPU.
- **User (architect/analyst):** Has FHIR domain knowledge. Privately leans toward WEHub but wants the decision driven by evidence, not advocacy.

---

## 2. The FHIR Validator-Wrapper Repository

### 2.1 What it is
**Repo:** [`hapifhir/org.hl7.fhir.validator-wrapper`](https://github.com/hapifhir/org.hl7.fhir.validator-wrapper)

A Kotlin Ktor application that **wraps** the upstream FHIR validator (`org.hl7.fhir.core`) and exposes it three ways:
1. **REST API server** with KotlinJS web UI (`localhost:8080`)
2. **Desktop GUI** with embedded Chromium window
3. **Standalone JAR** built via Gradle

The wrapper itself is **not** the validator. It packages the validator and provides interfaces.

### 2.2 Wrapper-specific CLI flags
The wrapper has only two CLI flags (in `src/jvmMain/kotlin/Server.kt`):

| Flag | Effect |
|---|---|
| `-startServer` | Boots Ktor backend + JS frontend as full-stack server. Default behavior if no args supplied. Takes priority if both flags passed. |
| `-gui` | Boots Ktor on port 8080 wrapped in Chromium desktop window. |

Examples:
```bash
java -jar build/libs/validator-wrapper-jvm-*.jar -startServer
java -jar build/libs/validator-wrapper-jvm-*.jar -gui
```

### 2.3 Wrapper environment variables
| Var | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `dev` | Selects config block in `application.conf` |
| `PRELOAD_CACHE` | `false` | If `true`, preloads FHIR package cache on startup (recommended in production) |

### 2.4 Build commands
```bash
./gradlew build      # full build (JVM + JS)
./gradlew jvmJar     # JVM jar only
./gradlew jsJar      # JS frontend only
./gradlew run        # local server on :8080
```

---

## 3. The Underlying FHIR Validator CLI (`validator_cli.jar`)

This is the actual workhorse. The wrapper uses it; you can also use it directly. Source: [`hapifhir/org.hl7.fhir.core`](https://github.com/hapifhir/org.hl7.fhir.core).

### 3.1 Invocation form
```bash
java -jar validator_cli.jar <source> [options]
```

### 3.2 Common parameters

| Parameter | Purpose |
|---|---|
| `<source>` | One or more files / directories / URLs / glob patterns to validate (required, ≥1) |
| `-version <x.y>` | FHIR version: `1.0`, `3.0`, `4.0`, `4.3` (R4B), `5.0` (R5) |
| `-ig <pkg\|url\|path>` | Load an Implementation Guide (e.g. `hl7.fhir.us.core`, canonical URL, or local IG folder) |
| `-profile <url>` | Validate against a specific StructureDefinition canonical URL |
| `-tx <url>` | Override terminology server (default `tx.fhir.org`); `n/a` disables |
| `-txLog <file>` | Log all tx server traffic |
| `-txCache <dir>` | Persistent terminology cache directory |
| `-output <file>` | Write OperationOutcome to file (`.json` or `.xml`) |
| `-output-style <style>` | `eslint-compact`, `compact`, `text` |
| `-language <code>` | Resource language (e.g. `en`, `de`) |
| `-locale <code>` | Locale for error messages |
| `-questionnaire <none\|required\|all>` | Aggressiveness of Questionnaire answer validation |
| `-to-version <x.y>` | Convert resource to another FHIR version (use with `-output`) |
| `-snapshot` | Generate snapshots for profiles |
| `-watch-mode <none\|single\|all>` | Re-run on file changes |
| `-debug` | Verbose logging |
| `-recurse` | Recurse into subdirectories |
| `-no-internet` | Disable network access (offline mode) |
| `-jurisdiction <code>` | Restrict to a jurisdiction |
| `-extension <url>` | Allow specific known extension URLs |
| `-best-practice <ignore\|hint\|warning\|error>` | Severity for best-practice rules |
| `-help` | Print full param list |

### 3.3 Common invocations
```bash
# Validate against US Core
java -jar validator_cli.jar patient.json -version 4.0 -ig hl7.fhir.us.core

# Validate against a specific profile
java -jar validator_cli.jar obs.xml -version 4.0 \
  -profile http://hl7.org/fhir/StructureDefinition/heartrate

# Convert R3 → R4
java -jar validator_cli.jar obs.xml -version 3.0 -to-version 4.0 -output obs-r4.json

# Verbose terminology logging
java -jar validator_cli.jar bundle.json -version 4.0 -tx http://my.tx/r4 -txLog tx.log

# Validate with persistent tx cache
java -jar validator_cli.jar bundle.json -version 4.0 -ig hl7.fhir.us.core \
  -txCache /var/cache/fhir/tx
```

---

## 4. Conceptual Foundation — `-ig` vs `-profile`

This distinction is the most-confused thing about the validator and is essential to understand.

### 4.1 `-ig` = "stock the kitchen"
When you pass `-ig hl7.fhir.us.core`, you tell the validator:
> "Download/load the US Core package. Have all its profiles, extensions, value sets, code systems available in memory. Put them on the shelf."

**It does NOT say "validate against US Core."** It just makes US Core *available*.

### 4.2 `-profile` = "pick the recipe"
When you pass `-profile http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient`:
> "Now check my Patient resource against this specific profile from the shelf."

### 4.3 Why these are split
1. **One IG contains many profiles.** US Core has 30+ profiles. The validator can't guess which one applies.
2. **You often need multiple IGs loaded but validate against one.** Profiles depend on each other transitively.
3. **The resource doesn't always declare its profile.** That's where `meta.profile` comes in.

### 4.4 `meta.profile` — the resource's self-declaration
A resource can claim conformance via:
```json
{
  "resourceType": "Patient",
  "meta": {
    "profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"]
  }
}
```
If `meta.profile` is set, the validator picks it up automatically — **you don't need `-profile`**. If it's missing, the validator falls back to base FHIR rules unless `-profile` forces something.

### 4.5 Decision guide
| Situation | Approach |
|---|---|
| "Is this valid FHIR at all?" | `-version` only |
| Resource has `meta.profile` set | `-version` + `-ig` (validator picks profile from file) |
| Resource has no `meta.profile`, want US Core | `-version` + `-ig` + `-profile <url>` |
| Validating a custom/local IG | `-version` + `-ig /path/to/ig/` + `-profile <url>` |

---

## 5. Validating Bundles

### 5.1 Default Bundle handling
When the validator sees a Bundle, it automatically:
1. Validates the Bundle itself (structure, required fields)
2. Walks every `entry.resource` and validates each
3. Reports issues per-entry with paths like `Bundle.entry[3].resource`

No special "bundle mode" — same command as a single resource.

### 5.2 Profile application to bundle entries — three patterns

**Pattern A — Each entry declares its own profile (recommended).**
```json
{
  "resourceType": "Bundle",
  "entry": [
    { "resource": {
      "resourceType": "Patient",
      "meta": { "profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"] }
    }}
  ]
}
```
Then:
```bash
java -jar validator_cli.jar bundle.json -version 4.0 -ig hl7.fhir.us.core
```
**Cleanest pattern.** Validator picks up each `meta.profile` and applies the right rules per entry.

**Pattern B — Use a profiled Bundle StructureDefinition.**
Some IGs (IPS, IHE MHD, eCR) define profiled Bundles that constrain entries:
```bash
java -jar validator_cli.jar ips-bundle.json \
  -version 4.0 \
  -ig hl7.fhir.uv.ips \
  -profile http://hl7.org/fhir/uv/ips/StructureDefinition/Bundle-uv-ips
```
The Bundle profile cascades the right profile to each entry slot.

**Pattern C — Force top-level profile.**
`-profile` applies to the Bundle, not contents. Useful only when asserting the Bundle conforms to a specific Bundle profile.

### 5.3 Performance for large Bundles
Useful flags:
- `-output report.json` — send the wall of errors to a file
- `-output-style eslint-compact` — one line per issue
- `-tx n/a` — skip terminology checks (faster but misses real errors)
- `-no-internet` — speed up if everything is cached
- `-Xmx<size>` — JVM heap (e.g., `-Xmx8g`). Goes **before** `-jar`.

### 5.4 Memory advice
Big bundles eat RAM. Default heap often too small. For typical multi-thousand-entry bundles:
```bash
java -Xmx8g -jar validator_cli.jar bundle.json \
  -version 4.0 \
  -ig hl7.fhir.us.core \
  -tx n/a \
  -output report.json \
  -output-style eslint-compact
```

### 5.5 When the bundle is too big
- **Split the bundle** into smaller bundles by resource type or patient
- **Validate each entry individually** — extract entries to files, point validator at folder with `-recurse` (loses Bundle-level checks)
- Pre-load referenced resources via `-ig <local-folder>`

### 5.6 Reading Bundle output
Error paths look like:
```
Bundle.entry[7].resource.ofType(Observation).code.coding[0]
```
That's: 8th entry (zero-indexed), Observation, problem in first coding of `code`.

---

## 6. Profile Organization for Multi-Use-Case Servers

### 6.1 The question
A REST validation server may receive Bundles for different purposes (Appointment, DiagnosticReport, Referral, etc.). How to organize profiles?

### 6.2 Three options

**Option A — Separate Bundle profile per use case (recommended).**
```
http://yourorg/fhir/StructureDefinition/Bundle-Appointment
http://yourorg/fhir/StructureDefinition/Bundle-DiagnosticReport
http://yourorg/fhir/StructureDefinition/Bundle-Referral
```
This is what real IGs do (IPS, IHE PCC, eCR, Da Vinci). Each profile is independently versioned and testable.

**Option B — Single Bundle profile with slices.**
Slice `entry` by `resource.resourceType` or `resource.meta.profile`. Only works when use cases overlap heavily (e.g., document bundles). Breaks down for genuinely different purposes — cardinality rules conflict.

**Option C — L3/L4 hierarchy (`derivation = constraint`).**
Define `Bundle-Base` with cross-cutting rules, then derive:
```
Bundle-Base
  ├── Bundle-Appointment
  ├── Bundle-Lab
  └── Bundle-Referral
```
This is **A + inheritance**. Useful for genuine common rules. Each leaf still has its own canonical URL.

**Recommendation:** Option A as default, optionally with Option C inheritance. Avoid Option B unless use cases are structurally near-identical.

---

## 7. REST API Patterns for Validation Servers

### 7.1 Three ways the client tells the server which profile

**Pattern 1 — `$validate` operation with `profile` parameter (FHIR-standard).**
```http
POST /fhir/Bundle/$validate?profile=http://yourorg/fhir/StructureDefinition/Bundle-Appointment
Content-Type: application/fhir+json

{ "resourceType": "Bundle", ... }
```
Standard, supported by HAPI, Matchbox, validator-wrapper.

**Pattern 2 — Bundle declares via `meta.profile`.**
Server calls `$validate` with no profile param. Validator picks it up from the resource. Cleanest for self-describing bundles.

**Pattern 3 — Server-side routing.**
Server inspects bundle (`Bundle.type`, first entry, custom header, endpoint path) and chooses:
```
POST /validate/appointment   → forces Bundle-Appointment
POST /validate/lab           → forces Bundle-Lab
POST /validate                → reads meta.profile
```
Best when clients aren't trusted to declare correctly, or when business rules say "all bundles to /lab MUST conform regardless of meta.profile."

**Recommended hybrid:** expose `$validate` per resource type, accept `?profile=`, fall back to `meta.profile`, fall back to base FHIR.

---

## 8. Performance Architecture

### 8.1 Loading IGs — once at startup, never per-request
The `ValidationEngine` instance is a heavy object — tens to hundreds of MB. Build once at server boot, reuse across every request.

The validator-wrapper does this via `PRELOAD_CACHE=true`.

For custom servers using `org.hl7.fhir.validation.ValidationEngine`:
```java
// At server startup — ONCE
ValidationEngine engine = new ValidationEngine.ValidationEngineBuilder()
    .withVersion("4.0.1")
    .fromSource("hl7.fhir.us.core#6.1.0");
engine.loadIg("hl7.fhir.uv.ips#1.1.0", false);

// Per request — reuse
OperationOutcome outcome = engine.validate(bytes, FhirFormat.JSON, profileUrls);
```

### 8.2 Memory cost of loaded IGs
| IGs loaded | Heap needed |
|---|---|
| Just base FHIR R4 | ~500 MB |
| Base + US Core | ~1 GB |
| Base + US Core + 5 small IGs | ~2 GB |
| Base + 15–20 IGs (large enterprise) | 4–8 GB |
| Loaded + actively serving | add 1–2 GB headroom |

For **R4 + UK Core + Spire Core**:
| Component | Heap |
|---|---|
| FHIR R4 base | ~500 MB |
| UK Core (~30 profiles) | +800 MB – 1 GB |
| Spire Core (~20–30 resources) | +500 – 800 MB |
| Snapshot graph, ValueSets, indices | +1 GB |
| Per-validation working set | +500 MB – 1 GB |
| **Realistic total** | **~3.5 – 4.5 GB** |

### 8.3 Why memory holds derived data
The 2–8 GB heap is **not** holding raw JSON. It's holding:
| In memory | What it is | Why |
|---|---|---|
| Parsed object graph | Java/Kotlin objects representing every profile, extension, ValueSet | JSON-on-disk → object-in-memory parsing too slow per-request |
| Computed snapshots | Full element list of each profile | Snapshot generation is expensive — 5 levels of inheritance can take seconds |
| Profile dependency graph | Transitive resolution | O(n) lookups would be brutal per-validation |
| Indexed lookups | Hash maps: URL → profile, code → coding info | O(1) lookups |
| Pre-compiled FHIRPath | Invariant ASTs | Fast `where(...)` evaluation |

**Disk holds raw materials, memory holds the cooked meal.** Persisting the cooked meal isn't standard.

---

## 9. Terminology (`tx`) — The Critical Performance Lever

### 9.1 Why tx is slow
For every `Coding` in a resource, the validator may ask the tx server *"is this code valid in this ValueSet?"*. A bundle with 200 codings = 200 round trips. At 50–200 ms each, that's 10–40 seconds of network time.

### 9.2 Built-in caching
The validator has terminology caching built in:

**a) In-memory cache.** Default. Within one process, repeated lookups are free. Restart loses it.

**b) Persistent on-disk cache.** Pass `-txCache <dir>`:
```bash
java -jar validator_cli.jar bundle.json \
  -version 4.0 \
  -ig hl7.fhir.us.core \
  -txCache /var/cache/fhir/tx
```

For validator-wrapper, configured via `application.conf`. Default location `~/.fhir/`.

### 9.3 When the cache alone is enough
- Code universe is finite and warm-able
- Standard public terminologies only
- Moderate volume (no rate limits)
- No privacy concerns about sending codes externally

This describes most deployments.

### 9.4 When you need a local tx server
| Reason | Why cache can't solve it |
|---|---|
| Custom/private ValueSets | tx.fhir.org doesn't know your codes; caches "not found" forever |
| Privacy / data residency | Each cache miss leaks codes to a third party |
| Rate limits | tx.fhir.org throttles high-volume callers |
| Air-gapped / offline | Cache misses fail without network |
| Unbounded code variety | Cache always partly cold |
| `$expand`, `$translate`, hierarchical lookups | Can't cache as simple key→value |

### 9.5 Local tx server options
- **OntoServer** (CSIRO, commercial, very fast)
- **HAPI FHIR with terminology services** enabled
- **tx.fhir.org local mirror** — `grahamegrieve/tx-fhir-org` Docker image
- **Snowstorm** (SNOMED-heavy workloads)

### 9.6 Honest recommendation
Start with `tx.fhir.org` + persistent disk cache. Add local tx server **only when** specific blockers force it. Don't pay the operational cost preemptively.

---

## 10. Production Deployment Blueprint

```
┌──────────────────────────────────────────────────────────────┐
│  Validation Service (long-running process)                   │
│                                                              │
│  Startup (once, 30–60s):                                     │
│    - Load all IGs into ValidationEngine                      │
│    - Warm package cache (~/.fhir/packages)                   │
│    - Connect to internal tx server                           │
│                                                              │
│  Per request (<1s for typical bundle):                       │
│    POST /fhir/Bundle/$validate?profile=...                   │
│    1. Reuse engine                                           │
│    2. Profile lookup hits in-memory snapshots                │
│    3. Tx lookups hit local tx server (cached)                │
│    4. Return OperationOutcome                                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
       │
       ├─► Internal tx server (OntoServer / HAPI / tx-mirror)
       │     ├─► Persistent code system cache
       │     └─► (rarely) tx.fhir.org for unknown codes
       │
       └─► Persistent disk cache: ~/.fhir/packages/, ~/.fhir/txCache/
```

**Sizing:**
- 4–8 GB heap typical multi-IG service
- 50–200 GB disk for FHIR package + tx cache
- 2–4 vCPU per replica
- Horizontal scaling via replicas (CPU-bound)

---

## 11. MuleSoft as a Validation Host — Evaluation

### 11.1 Mule Runtime versions
| Mule version | Released | Java version |
|---|---|---|
| 3.x | 2014–2018 (legacy) | Java 7 / 8 |
| 4.0 – 4.2 | 2018–2019 | Java 8 |
| 4.3 | 2020 | Java 8 / 11 |
| 4.4 | 2021 | Java 8 / 11 |
| 4.5 | 2023 | Java 8 / 11 / 17 |
| 4.6 | 2024 | Java 17 (Java 8 deprecated) |
| 4.7 | 2024 | Java 17 |
| 4.8 | 2024 | Java 17 |
| 4.9 | 2025 | Java 17 / 21 |

### 11.2 Compatibility with FHIR validator
- **Older `org.hl7.fhir.validation` (~6.x):** Java 11 minimum, works on Mule 4.3+
- **Recent (6.5+):** Java 17 minimum, needs Mule 4.6+
- **Latest:** Java 17 baseline, some features assume Java 17+ APIs

For Mule 4.9/4.10 + JDK 17, the validator pairing is current and clean.

### 11.3 "Mule JVM" vs "Mule worker" distinction
Mule Runtime is itself a JVM application. A "Mule worker" (CloudHub) or RTF pod is a JVM running Mule Runtime. So "running Java in the Mule JVM" means embedding Java code into the same JVM as Mule Runtime.

Mechanisms:
| Mechanism | Lifecycle |
|---|---|
| Java module (`java:invoke`, `java:invoke-static`, `java:new`) | App-scoped |
| Custom Mule connector / extension (Mule SDK) | App or domain scoped |
| Java in `src/main/java` | App-scoped |
| Domain-shared libraries | Survives app redeploys, dies with domain |
| Server-level libraries (`MULE_HOME/lib/user/`) | Lives as long as the server (on-prem only) |

### 11.4 CloudHub 2.0 sizing constraints
Source: [CloudHub 2.0 Architecture docs](https://docs.mulesoft.com/cloudhub-2/ch2-architecture)

| vCore | Total memory | Heap | Storage |
|---|---|---|---|
| 0.1 | 1.2 GB | 480 MB | 8 GB |
| 0.2 | 2 GB | 1 GB | 8 GB |
| 0.5 | 2.6 GB | 1.3 GB | 10 GB |
| 1 | 4 GB | 2 GB | 12 GB |
| 1.5 | 6 GB | 3 GB | 20 GB |
| 2 | 8 GB | 4 GB | 20 GB |
| 2.5 | 9.5 GB | 4.75 GB | 20 GB |
| 3 | 11 GB | 5.5 GB | 20 GB |
| 3.5 | 13 GB | 6.5 GB | 20 GB |
| 4 | 15 GB | 7.5 GB | 20 GB |

Plus `.mem` variants — *"memory-intensive options with the same compute"* — that bump memory while keeping CPU at a lower tier.

**Implication for R4 + UK Core + Spire Core (~3.5–4.5 GB heap):** minimum 2.5 vCore, comfortable at 3 vCore.

### 11.5 Why FHIR validation is CPU-bound (not just memory-bound)
The engineer's framing of "high memory, low CPU" is partially wrong. Validation is genuinely CPU-intensive:

1. **FHIRPath invariant evaluation.** Each profile defines invariants like:
   ```
   Observation.value.exists() implies Observation.code.coding.exists()
   ```
   The validator parses these into ASTs and executes them against every element. A complex resource against UK Core can run **30–80 invariants per validation**. CPU-bound, not cacheable per-bundle.

2. **Snapshot generation.** When a profile inherits from another, the validator must compute the full element list by walking the inheritance chain. Done at IG load and on-demand for transitive references. Pure CPU work.

3. **Slicing discrimination.** Bundles with sliced entries require evaluating discriminator FHIRPaths to assign each entry to the right slice. CPU per discriminator.

4. **JVM garbage collection at large heaps.** With 5–7 GB heap and high allocation rate, GC threads need CPU to keep up. Big heap + small CPU = unpredictable GC pauses.

5. **Concurrency.** vCore ≈ thread of work. With 0.5 vCore, you get one thread of useful work; concurrency falls off a cliff and bundles queue serially.

### 11.6 Realistic CPU cost per bundle
- **Small bundle (1–10 entries, simple profiles):** ~50–200 ms CPU
- **Medium bundle (50–100 entries, profiled):** ~500 ms – 2 s CPU
- **Large bundle (500+ entries, deep profiling, slicing):** 5–30 s CPU

These are CPU-time, not wall-time. With 0.5 vCore (≈half a thread), a 2-second-CPU bundle takes ~4 seconds wall-time.

### 11.7 Why Mule is generally wrong for FHIR validation
Mule is an integration runtime: route, transform, mediate. FHIR validation is the opposite — long-running stateful compute.

| Workload concern | Mule worker | FHIR validator |
|---|---|---|
| Heap | 1 vCore ≈ 1.5 GB; 2 vCore ≈ 3 GB | 4–8 GB recommended |
| State per worker | ~stateless | 2–8 GB of loaded IG snapshots |
| Cold start | seconds | 30–60 s loading IGs |
| Lifecycle | Frequent redeploys | Wants to stay warm |
| Classloader | Pinned versions | FHIR validator brings 50+ transitive deps |

### 11.8 Where Mule embedding becomes more viable
- **On-prem Mule** or **Runtime Fabric** with full JVM sizing control
- Validator installed at **domain or server level** so it survives app redeploys
- **Custom Mule SDK connector** (cleaner than `java:invoke`, handles classloader properly)
- IG set is small and stable
- Single-platform operational footprint matters more than scaling independence

---

## 12. The Four Deployment Options Compared

### Option A — Embed validator in each Mule integration app
Each consuming Mule app loads its own copy of the FHIR validator + IGs.

**Pros:**
- Single platform (CloudHub)
- No cross-team dependency
- Mule team owns everything
- Lowest network latency (no inter-service hop)

**Cons:**
- IGs loaded N times (one per app) → vCore/memory multiplied
- Cold start (30–60s) on every redeploy of every app
- Tx perf issue **multiplied** — every replica calls tx independently
- No reuse for non-Mule consumers

### Option B — Centralized validator as a Mule app on CloudHub
One dedicated Mule app hosting the validator; other Mule apps call it via internal HTTP.

**Pros:**
- Single platform
- IG loaded once
- Decoupled from integration app lifecycle
- Mule team can own it

**Cons:**
- Still inside CloudHub sizing constraints
- Tx perf issue still unsolved (unless tx is also moved/replaced)
- Cold start on app redeploy (less frequent than Option A)
- Limited to CloudHub vCore tiers for sizing

### Option C — WEHub (existing AKS-hosted validator + tx)
Mule calls the existing WEHub service via REST.

**Pros:**
- **Solves the tx perf issue** (co-located tx server already exists)
- No CloudHub vCore consumption for validation
- Independent scaling
- Reusable by non-Mule consumers
- Always-on (no cold start per Mule deploy)

**Cons:**
- Cross-platform estate (Mule + AKS)
- Cross-team dependency on WEHub team
- Network hop from Mule to AKS
- Auth / firewall / networking integration needed

### Option D — Hybrid (validator in Mule, tx via WEHub)
Validator embedded or centralized in CloudHub; terminology calls re-pointed at WEHub's tx server.

**Pros:**
- **Solves tx perf issue** via WEHub tx
- Validator stays in CloudHub (Govind's preference)
- Partial reuse of existing capability

**Cons:**
- Still need to size CloudHub for validator
- Two systems to maintain (validator on Mule, tx on AKS)
- Partial cross-team dependency (only for tx)

---

## 13. Weighted Decision Matrix

### 13.1 Criteria and weights (total 100)

| # | Category / Criterion | Weight | Measures |
|---|---|---|---|
| **A. Functional fit** | | **30** | |
| 1 | Resolves existing terminology perf issue | 12 | Does it fix the tx round-trip pain? |
| 2 | Validation throughput at expected concurrency | 6 | Parallel bundle handling |
| 3 | End-to-end validation latency for typical bundle | 6 | Wall-time per validation |
| 4 | Cold-start / availability after redeploy | 6 | Time from deploy to first request |
| **B. Delivery / time-to-value** | | **20** | |
| 5 | Time to first production validation | 10 | Calendar weeks |
| 6 | Procurement / governance / approval length | 5 | New infra/licenses/security reviews? |
| 7 | Reuse of existing investment | 5 | Leverage of what we already have |
| **C. Operational sustainability** | | **20** | |
| 8 | Day-to-day operational complexity | 7 | Monitoring, on-call, IG updates |
| 9 | Skill alignment with current team | 5 | Existing engineers can run it |
| 10 | Lifecycle decoupling from integration apps | 4 | Redeploys don't bounce validator |
| 11 | Failure isolation / blast radius | 4 | Validator misbehavior containment |
| **D. Cost & commercial** | | **15** | |
| 12 | CloudHub 2.0 vCore consumption from entitlement | 6 | Cost from shared pool |
| 13 | 3-year TCO | 5 | Rolled-forward total cost |
| 14 | Resource duplication overhead | 4 | IGs loaded N times? |
| **E. Strategic / organizational** | | **15** | |
| 15 | Reusability beyond Mule | 5 | Other consumers (.NET, batch, UI) |
| 16 | Cross-team dependency clarity | 4 | Coordination overhead |
| 17 | Future extensibility (more IGs, profiles) | 3 | Cost of adding next IG |
| 18 | Single-platform simplicity | 3 | CloudHub-only vs split estate |

### 13.2 Scoring rubric
- **5** — strongly meets / actively helps
- **4** — good fit
- **3** — acceptable / neutral
- **2** — partial issue
- **1** — significant problem

### 13.3 Baseline scores

| # | Criterion | Wt | A: Embed | B: Mule centralized | C: WEHub | D: Hybrid |
|---|---|---|---|---|---|---|
| 1 | Tx perf fixed | 12 | 1 | 2 | 5 | 4 |
| 2 | Throughput | 6 | 3 | 3 | 5 | 3 |
| 3 | Latency per bundle | 6 | 4 | 3 | 3 | 3 |
| 4 | Cold-start | 6 | 1 | 2 | 5 | 2 |
| 5 | Time to market | 10 | 3 | 3 | 4 | 2 |
| 6 | Procurement length | 5 | 5 | 5 | 5 | 5 |
| 7 | Reuse existing | 5 | 1 | 2 | 5 | 4 |
| 8 | Ops complexity | 7 | 2 | 3 | 4 | 3 |
| 9 | Skills on team | 5 | 5 | 5 | 3 | 4 |
| 10 | Lifecycle decoupling | 4 | 1 | 4 | 5 | 3 |
| 11 | Failure isolation | 4 | 2 | 4 | 5 | 3 |
| 12 | vCore consumption | 6 | 1 | 3 | 5 | 3 |
| 13 | TCO 3yr | 5 | 2 | 3 | 4 | 3 |
| 14 | Resource duplication | 4 | 1 | 4 | 5 | 4 |
| 15 | Non-Mule reusability | 5 | 1 | 3 | 5 | 3 |
| 16 | Cross-team simplicity | 4 | 5 | 5 | 2 | 3 |
| 17 | Future extensibility | 3 | 2 | 4 | 5 | 3 |
| 18 | Single-platform | 3 | 5 | 5 | 1 | 3 |
| **Weighted total / 500** | | | **237** | **326** | **432** | **320** |
| **% of max** | | | **47%** | **65%** | **86%** | **64%** |

### 13.4 Interpretation
- **Option C (WEHub)** wins decisively, primarily on the terminology criterion
- **Option B (centralized Mule)** is a reasonable middle ground if WEHub is off the table
- **Option D (hybrid)** preserves Govind's CloudHub preference while solving tx perf
- **Option A (embed)** loses on multiplication of cost and unresolved tx

### 13.5 How to use the matrix fairly
1. **Agree weights before scoring.** Get sign-off on weights independently of who picks them.
2. **Score independently.** Mule architect scores, FHIR architect scores, compare deltas of 2+.
3. **Document disagreements.** Capture *why* in a notes column. The audit trail matters more than the totals.
4. **Make weight changes explicit.** If anyone wants to lower the tx-perf weight, write down why and initial.

---

## 14. Conversation Strategy with the Mule Architect

### 14.1 Stakeholder profile
Govind:
- Prefers embedding in Mule on CloudHub
- Comfortable with high memory but resists high CPU
- May not fully appreciate FHIR-specific compute characteristics
- Is technically right that CloudHub 2.0 `.mem` variants exist

### 14.2 The Socratic question sequence
Designed to surface constraints, not advocate. Each question leads him to articulate a constraint that narrows his options.

**Round 1 — Quantify the existing tx pain.**
> "How bad is the current tx perf issue, concretely? What's a typical validation taking today, and how much is tx round-trips vs structural validation?"

**Round 2 — Trace tx call path.**
> "When validation runs today, what's the path of a tx call? Direct to external, or through a cache anywhere?"

**Round 3 — The pivot.**
> "If we embed the validator inside Mule, the embedded validator still has to resolve codes against a tx server for every Coding. Does the tx call path change at all by moving the validator into Mule?"

He must say no. Then:

> "So if today's pain is tx call latency × hundreds of codings per bundle, embedding makes that worse per replica. Are we OK with that?"

**Round 4 — Force co-location conclusion.**
> "What would actually fix the tx perf issue? My read: a tx server with persistent caching, ideally co-located with the validator. Does that match your view?"

> "If we agree validator and tx need to be co-located with caching, does it matter architecturally whether 'co-located' means inside CloudHub or inside an AKS cluster the validator team already runs?"

**Round 5 — Frame two paths neutrally.**
> "Two options: (a) stand up a colocated validator + tx pair inside CloudHub — own building and operating both. Or (b) point at the existing colocated pair we already have. The validator location is a separate question."

### 14.3 Handling resistance
If he says "I want it in CloudHub" without technical justification:
> "Totally fair. Just so I can document the rationale — what's the specific concern with calling out to AKS? Networking, security, ownership? I want to make sure we capture the constraint properly."

If the reason is soft, follow up:
> "If we go CloudHub-hosted, what's our 90-day plan to actually solve the existing tx perf issue?"

### 14.4 Addressing the `.mem` argument
Concede the technical point, then add the CPU-bound justifications:
> "Fair on `.mem` — happy to use it if budget supports. Two things on CPU though:
> 1. FHIR validation is CPU-bound: 30–80 FHIRPath invariants per validation, slicing, snapshot computation. None cached per-request.
> 2. GC at 5–7 GB heap needs CPU. A `.mem` variant with starved CPU risks GC pauses showing as random latency.
>
> Concretely: pull `.mem` variant sizing, pick one giving ~5 GB heap and ≥1.5–2 vCore equivalent compute, run a benchmark with a representative bundle. Measure CPU time and GC pause distribution. Better than guessing."

### 14.5 The graceful-fallback move
If Govind digs in on validator location:
> "OK let's keep the validator in Mule. Can we at least re-point tx at WEHub?"

This is **Option D (Hybrid)** — captures the tx perf win without the cross-platform validator optics. Lands ~80% of the architectural benefit.

---

## 15. Questions to Ask the Mule Engineer (Checklist)

When validating Mule deployment specifics, send these:

### 15.1 Runtime & deployment
- Mule Runtime version (exact minor)
- Upgrade plans next 6 months
- Deployment platform: CloudHub 1.0 / 2.0 / Runtime Fabric / on-prem / hybrid

### 15.2 JVM
- JDK version
- Worker/pod sizing today (vCores, memory, configured `-Xmx`)
- Upper bound on heap we can request

### 15.3 Library / dependency model
- Mule domain project in use?
- Server-level libraries (on-prem / RTF)?
- Policy on adding third-party JARs

### 15.4 Lifecycle & deploy cadence
- Redeploy frequency
- Typical app cold-start time tolerance
- Domain-shared model that survives redeploys?

### 15.5 Existing FHIR / validation footprint
- MuleSoft FHIR/HL7 modules in use?
- Existing custom connectors wrapping Java libs?

### 15.6 WEHub-side
- Network reachability from Mule
- RTT to WEHub
- Auth / mTLS requirements

### 15.7 The minimum-viable three
1. Mule Runtime version and JDK in production
2. Deployment platform and per-worker heap limit
3. Network reachability and auth from Mule to WEHub

---

## 16. Architectural Recommendation Summary

### 16.1 If WEHub is reachable and approved
**Option C — Use WEHub via REST.**
- Solves tx perf issue (co-located cached tx)
- No CloudHub vCore drain for validation
- Reusable beyond Mule
- Independent scaling and lifecycle

### 16.2 If WEHub is blocked organizationally
**Option D — Hybrid (validator in Mule, tx via WEHub).**
- Preserves CloudHub validator location
- Still solves the tx perf issue
- Acceptable middle ground

### 16.3 If both WEHub and AKS are off-limits
**Option B — Centralized Mule validator app.**
- Sized at ≥3 vCore (`.mem` variant if budget-tight on CPU)
- Internal HTTP from integration apps
- Tx remains a separate problem to solve

### 16.4 Avoid
**Option A — Embedding in every integration app.**
- Multiplies vCore consumption
- Multiplies cold-start pain
- Multiplies the tx perf problem
- Defensible only if IG set is tiny and apps are few

---

## 17. Key Numbers Reference Card

| Metric | Value |
|---|---|
| FHIR R4 base heap | ~500 MB |
| UK Core heap | +800 MB – 1 GB |
| Spire Core heap | +500 – 800 MB |
| Total heap (R4 + UK Core + Spire Core + working) | ~3.5 – 4.5 GB |
| Cold-start time loading IGs | 30 – 60 s |
| Tx call to remote server | 50 – 200 ms |
| Tx call to local cached server | < 5 ms |
| Small bundle CPU | 50 – 200 ms |
| Medium bundle CPU | 500 ms – 2 s |
| Large bundle CPU | 5 – 30 s |
| FHIRPath invariants per validation (UK Core) | 30 – 80 |
| Min CloudHub 2.0 vCore for our IG load | 2.5 vCore (4.75 GB heap) |
| Comfortable CloudHub 2.0 vCore | 3 vCore (5.5 GB heap) |
| Generous CloudHub 2.0 vCore | 4 vCore (7.5 GB heap) |

---

## 18. Glossary

- **FHIR** — Fast Healthcare Interoperability Resources. HL7 standard for healthcare data exchange.
- **IG** — Implementation Guide. A package of profiles, extensions, value sets defining a use case (e.g., US Core, UK Core, IPS).
- **Profile** — A `StructureDefinition` constraining a base FHIR resource for a specific purpose. Identified by canonical URL.
- **Bundle** — A FHIR container holding multiple resources. Used for transactions, documents, search results.
- **Snapshot** — The full element list of a profile after merging its differential with all parent profiles.
- **Differential** — The delta a profile applies on top of its base profile.
- **Invariant** — A FHIRPath expression defining a rule that must hold on every conforming resource.
- **Slicing** — A way to constrain repeating elements (like Bundle entries) into named "slices" by some discriminator.
- **`meta.profile`** — A claim on a resource declaring it conforms to one or more profiles.
- **`$validate`** — FHIR-defined REST operation for validating a resource.
- **OperationOutcome** — FHIR resource representing a validation result (errors, warnings, info).
- **tx server** — Terminology server. Resolves codes against value sets and code systems.
- **Validator-wrapper** — Kotlin Ktor app wrapping `org.hl7.fhir.core` validator for REST/desktop/CLI use.
- **Validator (`org.hl7.fhir.core`)** — The actual HL7 reference validator engine, used by all wrappers.
- **WEHub** — Internal AKS-hosted service running FHIR validator + co-located tx server.
- **CloudHub 2.0** — MuleSoft's managed Kubernetes-based deployment platform.
- **Runtime Fabric (RTF)** — MuleSoft's self-managed Kubernetes-based deployment.
- **vCore** — MuleSoft's compute/memory bundling unit. Each tier defines a fixed CPU + RAM allocation.
- **`.mem` variant** — CloudHub 2.0 memory-intensive replica size with the same compute as a smaller standard tier.

---

## 19. References

- [hapifhir/org.hl7.fhir.validator-wrapper](https://github.com/hapifhir/org.hl7.fhir.validator-wrapper) — wrapper repository
- [hapifhir/org.hl7.fhir.core](https://github.com/hapifhir/org.hl7.fhir.core) — actual validator source
- [validator-wrapper docs](https://hl7.github.io/docs/validator-wrapper)
- [Using the FHIR Validator — HL7 Confluence](https://confluence.hl7.org/display/FHIR/Using+the+FHIR+Validator)
- [HAPI FHIR Instance Validator docs](https://hapifhir.io/hapi-fhir/docs/validation/instance_validator.html)
- [CloudHub 2.0 Architecture (MuleSoft)](https://docs.mulesoft.com/cloudhub-2/ch2-architecture)
- [MuleSoft CloudHub Worker Sizing Guide](https://www.imarkinfotech.com/salesforce/blogs/mulesoft-cloudhub-worker-sizing-performance-guide/)
- [tx.fhir.org](https://tx.fhir.org/) — public FHIR terminology server
- [OntoServer](https://ontoserver.csiro.au/) — commercial terminology server
- [validator.fhir.org](https://validator.fhir.org/) — public hosted FHIR validator instance

---

*End of knowledge base.*
