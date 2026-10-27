"""schema.org JSON-LD built only from the central catalog."""

from __future__ import annotations

from typing import Any

from app.domain.catalog import BusinessCatalog, ConversionPointDraft, Offering, Work

_ACTIONS = {
    "purchase": "BuyAction",
    "quote_request": "AskAction",
    "inquiry": "CommunicateAction",
    "booking": "ReserveAction",
    "document_request": "DownloadAction",
    "external_link": "ViewAction",
}


def drop_empty(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {key: drop_empty(item) for key, item in value.items()}
        return {key: item for key, item in cleaned.items() if item not in (None, "", [], {})}
    if isinstance(value, list):
        return [item for item in (drop_empty(item) for item in value) if item not in (None, "", [], {})]
    return value


def _properties(data: dict[str, Any]) -> list[dict[str, Any]]:
    props = []
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            rendered = __import__("json").dumps(value, ensure_ascii=False)
        else:
            rendered = value
        props.append({"@type": "PropertyValue", "name": key, "value": rendered})
    return props


def _price(node: dict[str, Any], price) -> None:
    if price is None:
        return
    if price.min_amount is None and price.max_amount is None:
        return
    node["priceCurrency"] = price.currency or "JPY"
    if price.min_amount is not None and price.max_amount is not None and price.min_amount != price.max_amount:
        node["priceSpecification"] = {
            "@type": "PriceSpecification",
            "minPrice": price.min_amount,
            "maxPrice": price.max_amount,
            "priceCurrency": price.currency or "JPY",
        }
    else:
        node["price"] = price.min_amount if price.min_amount is not None else price.max_amount


def potential_action(point: ConversionPointDraft, base: str, slug: str) -> dict[str, Any]:
    if point.type == "external_link" and point.external_url:
        target = point.external_url
        method = "GET"
    else:
        target = f"{base}/b/{slug}/convert/{point.key}"
        method = "POST"
    return {
        "@type": _ACTIONS.get(point.type, "CommunicateAction"),
        "name": point.name,
        "description": point.description,
        "target": {"@type": "EntryPoint", "urlTemplate": target, "httpMethod": method},
    }


def offering_jsonld(offering: Offering, base: str, business_slug: str) -> dict[str, Any]:
    item: dict[str, Any] = {
        "@type": offering.schema_org_type or "Service",
        "name": offering.name,
        "description": offering.description,
        "url": f"{base}/b/{business_slug}/o/{offering.slug}",
    }
    if offering.extension:
        item["additionalProperty"] = _properties(offering.extension)
    offer: dict[str, Any] = {
        "@type": "Offer",
        "name": offering.name,
        "description": offering.description,
        "url": item["url"],
        "itemOffered": item,
    }
    _price(offer, offering.price_range)
    return drop_empty(offer)


def work_jsonld(work: Work, base: str, business_slug: str) -> dict[str, Any]:
    node: dict[str, Any] = {
        "@type": work.schema_org_type or "CreativeWork",
        "name": work.title,
        "description": work.description,
        "url": f"{base}/b/{business_slug}/w/{work.slug}",
    }
    if work.year:
        node["dateCreated"] = str(work.year)
    if work.client:
        node["creator"] = {"@type": "Organization", "name": work.client}
    if work.location:
        node["locationCreated"] = work.location
    if work.extension:
        node["additionalProperty"] = _properties(work.extension)
    return drop_empty(node)


def business_jsonld(catalog: BusinessCatalog, base: str) -> dict[str, Any]:
    seller = catalog.seller
    node: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": catalog.schema_org_type or "ProfessionalService",
        "name": catalog.name,
        "description": catalog.summary or catalog.description,
        "url": f"{base}/b/{catalog.slug}",
        "areaServed": catalog.service_area,
        "keywords": ", ".join(catalog.tags),
        "image": [image.url for image in catalog.images],
        "provider": {
            "@type": "Organization",
            "name": seller.name,
            "legalName": seller.legal_name,
            "email": seller.email,
            "telephone": seller.phone,
            "url": seller.url,
            "address": seller.address,
        },
        "makesOffer": [offering_jsonld(item, base, catalog.slug) for item in catalog.offerings],
        "subjectOf": [work_jsonld(item, base, catalog.slug) for item in catalog.works],
        "potentialAction": [potential_action(item, base, catalog.slug) for item in catalog.conversion_points if item.enabled],
    }
    if catalog.extension:
        node["additionalProperty"] = _properties(catalog.extension)
    if catalog.trust.licenses:
        node["hasCredential"] = [{"@type": "EducationalOccupationalCredential", "name": name} for name in catalog.trust.licenses]
    if catalog.trust.awards:
        node["award"] = catalog.trust.awards
    if catalog.price_range:
        _price(node, catalog.price_range)
    return drop_empty(node)
