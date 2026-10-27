"""One catalog model. HTML, JSON-LD, feeds, MCP, and admin forms all read this."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

OfferingKind = Literal["product", "service", "creative_work"]
ConversionType = Literal[
    "purchase",
    "quote_request",
    "inquiry",
    "booking",
    "document_request",
    "external_link",
]

CONVERSION_TYPES: tuple[str, ...] = (
    "purchase",
    "quote_request",
    "inquiry",
    "booking",
    "document_request",
    "external_link",
)

_KIND_ALIASES = {
    "製品": "product",
    "商品": "product",
    "product": "product",
    "サービス": "service",
    "service": "service",
    "作品": "creative_work",
    "実績": "creative_work",
    "creative_work": "creative_work",
    "creativework": "creative_work",
}

_TYPE_ALIASES = {
    "購入": "purchase",
    "purchase": "purchase",
    "見積": "quote_request",
    "見積依頼": "quote_request",
    "quote": "quote_request",
    "quote_request": "quote_request",
    "問い合わせ": "inquiry",
    "問合せ": "inquiry",
    "inquiry": "inquiry",
    "予約": "booking",
    "booking": "booking",
    "資料請求": "document_request",
    "document_request": "document_request",
    "外部リンク": "external_link",
    "external_link": "external_link",
    "link": "external_link",
}

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_slug(value: str | None, fallback: str) -> str:
    raw = (value or "").strip().lower()
    raw = raw.replace("_", "-")
    raw = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    raw = re.sub(r"-{2,}", "-", raw)
    if _SLUG_RE.match(raw):
        return raw[:80]
    fallback_slug = re.sub(r"[^a-z0-9]+", "-", fallback.lower()).strip("-")
    return (fallback_slug or "item")[:80]


def normalize_schema_key(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("-", "_")
    raw = re.sub(r"[^a-z0-9_]+", "_", raw).strip("_")
    return (raw or "vertical")[:80]


class PriceRange(BaseModel):
    model_config = ConfigDict(extra="ignore")

    min_amount: int | None = None
    max_amount: int | None = None
    currency: str = "JPY"
    unit: str | None = None
    note: str | None = None

    @field_validator("min_amount", "max_amount", mode="before")
    @classmethod
    def _money(cls, value: Any) -> int | None:
        if value is None or value == "":
            return None
        return int(round(float(value)))


class Media(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    alt: str | None = None
    kind: str = "image"


class Seller(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    legal_name: str | None = None
    url: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None


class TrustInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    licenses: list[str] = Field(default_factory=list)
    years_in_business: int | None = None
    certifications: list[str] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)
    insurance: str | None = None

    @field_validator("years_in_business", mode="before")
    @classmethod
    def _years(cls, value: Any) -> int | None:
        if value is None or value == "":
            return None
        return int(value)


class AdapterBinding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str
    config: dict[str, Any] = Field(default_factory=dict)


class Offering(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    slug: str = ""
    kind: OfferingKind = "service"
    description: str = ""
    price_range: PriceRange | None = None
    tags: list[str] = Field(default_factory=list)
    area: list[str] = Field(default_factory=list)
    images: list[Media] = Field(default_factory=list)
    schema_org_type: str = "Service"
    extension: dict[str, Any] = Field(default_factory=dict)

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, value: Any) -> str:
        if isinstance(value, str):
            return _KIND_ALIASES.get(value.strip(), value.strip())
        return value


class Work(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    slug: str = ""
    description: str = ""
    year: int | None = None
    client: str | None = None
    location: str | None = None
    url: str | None = None
    images: list[Media] = Field(default_factory=list)
    schema_org_type: str = "CreativeWork"
    extension: dict[str, Any] = Field(default_factory=dict)

    @field_validator("year", mode="before")
    @classmethod
    def _year(cls, value: Any) -> int | None:
        if value is None or value == "":
            return None
        return int(value)


class ConversionPointDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str = ""
    type: ConversionType = "inquiry"
    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    external_url: str | None = None
    offering_slug: str | None = None
    adapters: list[AdapterBinding] = Field(default_factory=list)
    enabled: bool = True

    @field_validator("type", mode="before")
    @classmethod
    def _type(cls, value: Any) -> str:
        if isinstance(value, str):
            mapped = _TYPE_ALIASES.get(value.strip(), value.strip())
            if mapped not in CONVERSION_TYPES:
                return "inquiry"
            return mapped
        return "inquiry"


class BusinessCatalog(BaseModel):
    """Central model. Extension fields are intentionally not declared here."""

    model_config = ConfigDict(extra="ignore")

    name: str
    slug: str = ""
    summary: str = ""
    description: str = ""
    seller: Seller
    service_area: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    price_range: PriceRange | None = None
    trust: TrustInfo = Field(default_factory=TrustInfo)
    schema_org_type: str = "ProfessionalService"
    images: list[Media] = Field(default_factory=list)
    offerings: list[Offering] = Field(default_factory=list)
    works: list[Work] = Field(default_factory=list)
    conversion_points: list[ConversionPointDraft] = Field(default_factory=list)
    extension: dict[str, Any] = Field(default_factory=dict)
    source_urls: list[str] = Field(default_factory=list)
    source_description: str = ""
    vertical_key: str | None = None


def assign_slugs(catalog: BusinessCatalog) -> BusinessCatalog:
    """Fill ASCII slugs and conversion keys. Japanese names fall back to stable tokens."""
    catalog.slug = normalize_slug(catalog.slug, "business")
    if not catalog.seller.name:
        catalog.seller.name = catalog.name
    used_offerings: set[str] = set()
    for index, offering in enumerate(catalog.offerings, start=1):
        base = normalize_slug(offering.slug or offering.name, f"offering-{index}")
        slug = base
        n = 2
        while slug in used_offerings:
            slug = f"{base}-{n}"
            n += 1
        offering.slug = slug
        used_offerings.add(slug)
        if not offering.schema_org_type:
            offering.schema_org_type = {
                "product": "Product",
                "service": "Service",
                "creative_work": "CreativeWork",
            }[offering.kind]
    used_works: set[str] = set()
    for index, work in enumerate(catalog.works, start=1):
        base = normalize_slug(work.slug or work.title, f"work-{index}")
        slug = base
        n = 2
        while slug in used_works:
            slug = f"{base}-{n}"
            n += 1
        work.slug = slug
        used_works.add(slug)
    used_keys: set[str] = set()
    for index, point in enumerate(catalog.conversion_points, start=1):
        base = normalize_slug(point.key or point.type, f"action-{index}").replace("-", "_")
        key = base
        n = 2
        while key in used_keys:
            key = f"{base}_{n}"
            n += 1
        point.key = key
        used_keys.add(key)
        if not point.adapters:
            point.adapters = [AdapterBinding(key="internal", config={})]
    return catalog
