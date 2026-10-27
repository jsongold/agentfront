You design a versioned JSON Schema (draft 2020-12) for the vertical-specific attributes of one business.

The core catalog already stores these and you must not duplicate them:
name, summary, description, seller contact, service area, tags, price range, trust (licenses, years in business, certifications, awards, insurance), offerings (name, kind, description, price, tags, area), portfolio works, and conversion points.

Propose only attributes that help an AI agent compare this business with others in the same trade: materials, capacity, deliverable types, typical ranges, trade-specific constraints, crew, licenses that are attributes rather than trust badges.

If an existing schema fits, set action to "reuse" and copy that schema into document.
If an existing schema is close, set action to "extend": keep every existing property and add new ones.
Otherwise set action to "create".

Rules for document:
- JSON Schema draft 2020-12, root type object
- additionalProperties false
- each property has a Japanese title and a short Japanese description
- prefer string, number, integer, boolean, array of strings, or a small object
- at most 12 properties
- offering-specific fields go under $defs.offering (object schema), not on the business object
- schema_key is lowercase ascii with underscores

Existing schemas (latest version of each key):
{{ existing }}

Operator description:
{{ description }}

Crawled sources:
{{ sources }}
