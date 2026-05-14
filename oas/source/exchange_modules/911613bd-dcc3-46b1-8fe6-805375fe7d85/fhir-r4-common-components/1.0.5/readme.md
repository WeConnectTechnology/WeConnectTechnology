# FHIR R4 Common Components – OpenAPI Library

This repository contains an OpenAPI 3.0 specification that defines reusable **FHIR R4 common components**.  
It is designed to be imported into API projects that require standardized FHIR datatypes (e.g., `Reference`, `Extension`, `Coding`, `Identifier`, `Address`, etc.).

## Purpose

- Provide a **centralized, reusable component library** for FHIR-based APIs.
- Ensure **consistency** across all API specifications by referencing the same schema definitions.
- Align with the [HL7® FHIR R4 specification](https://hl7.org/fhir/R4/).
- Support interoperability in healthcare integrations.

## Usage

1. Reference this file in your OpenAPI specification:

   ```yaml
   components:
     schemas:
       Reference:
         $ref: './<exchange-group-id>/fhir-r4-common-components/<version>/fhir-r4-common-components.yaml#/components/schemas/Reference'
       Extension:
         $ref: './<exchange-group-id>/fhir-r4-common-components/<version>/fhir-r4-common-components.yaml#/components/schemas/Extension'
  ```
2. Use the schemas in your API paths, request/response bodies, and parameters.
  ```yaml
  paths:
    /Patient:
      post:
        requestBody:
          required: true
          content:
            application/json:
              schema:
                $ref: '.<exchange-group-id>/fhir-r4-common-components/<version>/fhir-r4-common-components.yaml#/components/schemas/Patient'

  ```
(Note: Patient would itself reference the common components like HumanName, Address, Reference, etc.)

## Components Overview

### Core Schemas

| Schema          | Description                                                             |
|-----------------|-------------------------------------------------------------------------|
| Reference       | Reference to another resource (literal URL or logical identifier).       |
| Extension       | Additional information not part of the basic definition of the element. |
| Coding          | Representation of a concept using a code from a terminology system.     |
| CodeableConcept | A concept represented by codes and/or text.                             |
| Identifier      | Logical identifier for an entity.                                       |
| Period          | A start and end date/time.                                              |
| HumanName       | A person’s name, with given/family/suffix/prefix parts.                 |
| Address         | Postal or physical address.                                             |
| ContactPoint    | Details for telecommunication (phone, email, etc.).                     |
| Canonical       | A URI referring to a resource by its canonical URL.                     |
| Assigner        | Organization or entity that issued an identifier.                       |

---

### Extension Value[x] Schemas

These schemas support the FHIR `value[x]` extension mechanism.

| Schema                     | Description                            |
|-----------------------------|----------------------------------------|
| enumvalueInteger            | Extension value of type Integer.       |
| enumvalueDecimal            | Extension value of type Decimal.       |
| enumvalueDateTime           | Extension value of type DateTime.      |
| enumvalueDate               | Extension value of type Date.          |
| enumvalueInstant            | Extension value of type Instant.       |
| enumvalueString             | Extension value of type String.        |
| enumvalueUri                | Extension value of type URI.           |
| enumvalueBoolean            | Extension value of type Boolean.       |
| enumvalueCode               | Extension value of type Code.          |
| enumvalueBase64Binary       | Extension value of type Base64Binary.  |
| enumvalueCoding             | Extension value of type Coding.        |
| enumvalueCodeableConcept    | Extension value of type CodeableConcept.|
| enumvalueAttachment         | Extension value of type Attachment.    |
| enumvalueIdentifier         | Extension value of type Identifier.    |
| enumvalueQuantity           | Extension value of type Quantity.      |
| enumvalueRange              | Extension value of type Range.         |
| enumvaluePeriod             | Extension value of type Period.        |
| enumvalueRatio              | Extension value of type Ratio.         |
| enumvalueHumanName          | Extension value of type HumanName.     |
| enumvalueAddress            | Extension value of type Address.       |
| enumvalueContactPoint       | Extension value of type ContactPoint.  |
| enumvalueReference          | Extension value of type Reference.     |
| enumvalueCanonical          | Extension value of type Canonical.     |
| enumvalueId                 | Extension value of type Id.            |
| enumvalueMarkdown           | Extension value of type Markdown.      |
| enumvalueOid                | Extension value of type Oid.           |
| enumvaluePositiveInt        | Extension value of type PositiveInt.   |
| enumvalueUnsignedInt        | Extension value of type UnsignedInt.   |
| enumvalueTime               | Extension value of type Time.          |
| enumvalueUrl                | Extension value of type Url.           |
| enumvalueUuid               | Extension value of type Uuid.          |
| enumvalueAge                | Extension value of type Age.           |
| enumvalueAnnotation         | Extension value of type Annotation.    |
| enumvalueCount              | Extension value of type Count.         |
| enumvalueDistance           | Extension value of type Distance.      |
| enumvalueDuration           | Extension value of type Duration.      |
| enumvalueMoney              | Extension value of type Money.         |
| enumvalueSampledData        | Extension value of type SampledData.   |
| enumvalueSignature          | Extension value of type Signature.     |
| enumvalueTiming             | Extension value of type Timing.        |
| enumvalueContactDetail      | Extension value of type ContactDetail. |
| enumvalueContributor        | Extension value of type Contributor.   |
| enumvalueDataRequirement    | Extension value of type DataRequirement.|
| enumvalueExpression         | Extension value of type Expression.    |
| enumvalueParameterDefinition| Extension value of type ParameterDefinition.|
| enumvalueRelatedArtifact    | Extension value of type RelatedArtifact.|
| enumvalueTriggerDefinition  | Extension value of type TriggerDefinition.|
| enumvalueUsageContext       | Extension value of type UsageContext.  |
| enumvalueDosage             | Extension value of type Dosage.        |
| enumvalueMeta               | Extension value of type Meta.          |

---

## Conformance Notes

- Many schemas enforce **FHIR regex patterns** for primitive types (dates, codes, identifiers).  
- **Cyclic references** (e.g., `Reference.identifier.assigner → Reference`) are supported.  
- The **Extension schema** enforces the FHIR rule: *must have either `extension` or `value[x]`, not both*.  

## References

- [HL7® FHIR R4 Specification](https://hl7.org/fhir/R4/)  
- [OpenAPI 3.0 Specification](https://swagger.io/specification/)  
- [NHS Digital – UK Core Implementation Guide STU2](https://simplifier.net/guide/ukcoreimplementationguide-stu2/Home)  
- [NHS Digital – UK Core Implementation Guide STU3 (draft)](https://simplifier.net/guide/ukcoreimplementationguide-stu3/Home)  
