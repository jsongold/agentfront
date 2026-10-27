Extract one business catalog for AI agents. Keep Japanese prose when the source is Japanese. Be concrete and specific. Do not invent licenses, prices, awards, years, or client names that the sources do not support. Use null or an empty list when unknown.

slug and every nested slug must match ^[a-z0-9]+(-[a-z0-9]+)*$.

schema_org_type should be a schema.org type. Use ProfessionalService or LocalBusiness for a service firm, HomeAndConstructionBusiness when it is a contractor, and a more specific type when it clearly fits.

Offerings are services or products an agent can propose. Past projects belong in works, not offerings. Works use schema_org_type CreativeWork unless a more specific type is obvious.

conversion_points: choose the types that match how a client would reach this business. Allowed types are purchase, quote_request, inquiry, booking, document_request, external_link.
Each input_schema is a JSON Schema draft 2020-12 object with Japanese titles and additionalProperties false.
When a person must reply, require name and email.
Construction quote requests should ask for location, floor area, budget, and timing.
Video quote requests should ask for purpose, length, deadline, budget, and a reference.
booking must require desired_datetime as a string with format date-time.
external_link must set external_url and may use an input schema with no required fields.
purchase records intent only; there is no payment.

Required buyer-decision fields for this trade:
{{ required_fields }}

Fill these from the sources when they are stated. Leave a field empty rather than inventing a value. Core fields go on the catalog; extension-only fields go in extension (or offering.extension when the path mentions offerings).

extension must validate against this JSON Schema:
{{ schema }}

When that schema has $defs.offering, each offering.extension must validate against it. Otherwise use {}.

{{ retry_note }}

Operator note:
{{ description }}

Sources:
{{ sources }}
