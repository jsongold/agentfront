"""Two fictional businesses so the catalog, pages, and MCP work before any API key is set."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.config import get_settings
from app.crawl.url_crawl import parse_document
from app.db import session_scope
from app.domain.catalog import (
    AdapterBinding,
    BusinessCatalog,
    ConversionPointDraft,
    Media,
    Offering,
    PriceRange,
    Seller,
    TrustInfo,
    Work,
)
from app.domain.conversion_templates import CONSTRUCTION_QUOTE_SCHEMA, VIDEO_QUOTE_SCHEMA, default_input_schema
from app.models import Business, CrawlDocument, GenerationRun, utcnow
from app.services.persistence import apply_catalog, prepare_catalog, seal_catalog
from app.services.schemas import save_schema_version

logger = logging.getLogger(__name__)
FIXTURES = Path(__file__).resolve().parent / "fixtures"

ARCHITECTURE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "title": "建築・建設",
    "description": "住宅の設計施工を比べるための属性",
    "properties": {
        "structure_types": {
            "type": "array",
            "items": {"type": "string"},
            "title": "構造種別",
            "description": "主に扱う構造",
        },
        "project_types": {
            "type": "array",
            "items": {"type": "string"},
            "title": "得意な建物用途",
        },
        "typical_floor_area_sqm": {
            "type": "object",
            "additionalProperties": False,
            "title": "得意な延床面積（㎡）",
            "properties": {
                "min": {"type": "number", "title": "最小"},
                "max": {"type": "number", "title": "最大"},
            },
        },
        "design_styles": {"type": "array", "items": {"type": "string"}, "title": "設計の傾向"},
        "handles_construction": {"type": "boolean", "title": "施工まで請け負う"},
        "license_numbers": {"type": "array", "items": {"type": "string"}, "title": "登録番号"},
    },
    "$defs": {
        "offering": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "includes_construction": {"type": "boolean", "title": "施工を含む"},
                "typical_duration": {"type": "string", "title": "標準工期"},
            },
        }
    },
}

VIDEO_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "title": "映像制作",
    "description": "映像の発注前に比べるための属性",
    "properties": {
        "deliverable_types": {"type": "array", "items": {"type": "string"}, "title": "主な成果物種別"},
        "typical_duration_sec": {
            "type": "object",
            "additionalProperties": False,
            "title": "得意な尺（秒）",
            "properties": {
                "min": {"type": "integer", "title": "最短"},
                "max": {"type": "integer", "title": "最長"},
            },
        },
        "shooting_styles": {"type": "array", "items": {"type": "string"}, "title": "撮影スタイル"},
        "crew_size": {"type": "string", "title": "標準の撮影体制"},
        "can_travel": {"type": "boolean", "title": "都外ロケ可"},
    },
    "$defs": {
        "offering": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "duration": {"type": "string", "title": "想定尺"},
                "includes_shooting": {"type": "boolean", "title": "撮影を含む"},
                "revisions": {"type": "integer", "title": "標準の修正回数"},
            },
        }
    },
}


def _media(base: str, name: str, alt: str) -> Media:
    return Media(url=f"{base}/fixtures/assets/{name}", alt=alt)


def aoba_catalog(base: str) -> BusinessCatalog:
    return BusinessCatalog(
        name="青葉設計室",
        slug="aoba-sekkei",
        summary="鎌倉・湘南で木造住宅の設計と施工を行うアトリエ事務所。",
        description=(
            "株式会社青葉設計室は鎌倉市由比ガ浜を拠点に、木造の注文住宅と戸建リノベーションを"
            "設計から施工まで引き受けます。素地の木、通り庭、断熱性能の説明を大事にしています。"
        ),
        seller=Seller(
            name="青葉設計室",
            legal_name="株式会社青葉設計室",
            email="studio@aoba-sekkei.example",
            phone="0467-00-2108",
            address="神奈川県鎌倉市由比ガ浜2-8-3",
            url=f"{base}/fixtures/aoba",
        ),
        service_area=["鎌倉市", "逗子市", "葉山町", "藤沢市", "横浜市"],
        tags=["木造住宅", "リノベーション", "長期優良住宅", "高断熱"],
        price_range=PriceRange(min_amount=28000000, max_amount=65000000, currency="JPY", unit="棟"),
        trust=TrustInfo(
            licenses=["一級建築士事務所 神奈川県知事登録第00000号", "建設業許可 神奈川県知事（般-00）第00000号"],
            years_in_business=18,
            certifications=["長期優良住宅"],
            insurance="住宅瑕疵保険（住宅あんしん保証）",
        ),
        schema_org_type="HomeAndConstructionBusiness",
        images=[_media(base, "aoba.svg", "アトリエの外観")],
        offerings=[
            Offering(
                name="木造注文住宅の設計監理",
                slug="custom-house",
                kind="service",
                description="ヒアリングから確認申請、現場監理、希望があれば施工まで。木造の専用住宅が中心です。",
                price_range=PriceRange(min_amount=28000000, max_amount=65000000, currency="JPY", unit="棟"),
                tags=["新築", "木造"],
                area=["鎌倉市", "逗子市", "葉山町", "藤沢市", "横浜市"],
                schema_org_type="Service",
                extension={"includes_construction": True, "typical_duration": "設計6か月、工事8か月"},
            ),
            Offering(
                name="戸建リノベーション",
                slug="house-renovation",
                kind="service",
                description="1980年以降の木造戸建てを、断熱と間取りから見直します。",
                price_range=PriceRange(min_amount=12000000, max_amount=40000000, currency="JPY", unit="棟"),
                tags=["リノベーション"],
                schema_org_type="Service",
                extension={"includes_construction": True, "typical_duration": "設計3か月、工事5か月"},
            ),
        ],
        works=[
            Work(
                title="通り庭の家",
                slug="toriniwa",
                description="家族4人のための木造2階建て。通り庭が道路側と庭をつなぎます。延床132㎡。",
                year=2023,
                client="個人",
                location="鎌倉市由比ガ浜",
                schema_org_type="CreativeWork",
            ),
            Work(
                title="葉山の半平屋",
                slug="hayama-hiraya",
                description="庭に開いた平屋に小さな二階を載せた住宅。延床118㎡。",
                year=2021,
                client="個人",
                location="葉山町",
                schema_org_type="CreativeWork",
            ),
        ],
        conversion_points=[
            ConversionPointDraft(
                key="quote",
                type="quote_request",
                name="見積・設計相談",
                description="建設地、延床面積、予算、時期が分かると一次回答が早くなります。",
                input_schema=CONSTRUCTION_QUOTE_SCHEMA,
                adapters=[
                    AdapterBinding(key="internal"),
                    AdapterBinding(key="email", config={"to": "studio@aoba-sekkei.example"}),
                ],
            ),
            ConversionPointDraft(
                key="visit",
                type="booking",
                name="現地相談の予約",
                description="候補地や既存住宅を一緒に見る30分の枠です。",
                input_schema=default_input_schema("booking"),
                adapters=[AdapterBinding(key="internal")],
            ),
            ConversionPointDraft(
                key="brochure",
                type="document_request",
                name="事例集の請求",
                description="過去事例のPDFをメールで送ります。",
                input_schema=default_input_schema("document_request"),
                adapters=[AdapterBinding(key="internal")],
            ),
        ],
        extension={
            "structure_types": ["木造"],
            "project_types": ["専用住宅", "戸建リノベーション"],
            "typical_floor_area_sqm": {"min": 80, "max": 220},
            "design_styles": ["素地の木", "通り庭", "高断熱"],
            "handles_construction": True,
            "license_numbers": ["一級建築士事務所 神奈川県知事登録第00000号"],
        },
        source_urls=[f"{base}/fixtures/aoba"],
        source_description="鎌倉の木造住宅を設計施工する友人の事務所。見積と現地相談を受け付ける。",
        vertical_key="architecture",
    )


def kogaku_catalog(base: str) -> BusinessCatalog:
    return BusinessCatalog(
        name="光枠フィルム",
        slug="kogaku-film",
        summary="東京の企業と文化施設向けに、ブランドフィルムと記録映像を企画から仕上げまで行う。",
        description=(
            "合同会社光枠フィルムは世田谷区三軒茶屋を拠点に、少ない照明で人の話を聞き、"
            "場所の時間を残す映像を作っています。撮影は東京・神奈川、編集はリモートでも対応します。"
        ),
        seller=Seller(
            name="光枠フィルム",
            legal_name="合同会社光枠フィルム",
            email="hello@kogaku-film.example",
            phone="03-0000-4410",
            address="東京都世田谷区三軒茶屋2-14-6",
            url=f"{base}/fixtures/kogaku",
        ),
        service_area=["東京都", "神奈川県"],
        tags=["ブランドフィルム", "採用動画", "インタビュー", "ドキュメンタリー"],
        price_range=PriceRange(min_amount=400000, max_amount=3500000, currency="JPY", unit="本"),
        trust=TrustInfo(years_in_business=9, licenses=[], certifications=[]),
        schema_org_type="ProfessionalService",
        images=[_media(base, "kogaku.svg", "編集室")],
        offerings=[
            Offering(
                name="ブランドフィルム",
                slug="brand-film",
                kind="service",
                description="60秒から180秒。企画、撮影、編集、カラー、簡単なモーショングラフィックを含みます。",
                price_range=PriceRange(min_amount=1200000, max_amount=3500000, currency="JPY", unit="本"),
                tags=["ブランドフィルム"],
                schema_org_type="Service",
                extension={"duration": "60–180秒", "includes_shooting": True, "revisions": 2},
            ),
            Offering(
                name="採用・インタビュー動画",
                slug="interview-film",
                kind="service",
                description="社員や利用者のインタビューをまとめ、90秒前後に編集します。",
                price_range=PriceRange(min_amount=400000, max_amount=1500000, currency="JPY", unit="本"),
                tags=["採用", "インタビュー"],
                schema_org_type="Service",
                extension={"duration": "約90秒", "includes_shooting": True, "revisions": 2},
            ),
        ],
        works=[
            Work(
                title="海辺の醸造所",
                slug="seaside-brewery",
                description="沿岸の醸造所の仕事を90秒で追ったブランドフィルム。",
                year=2024,
                client="海辺の醸造所",
                location="神奈川県",
                schema_org_type="VideoObject",
            ),
            Work(
                title="市立図書館 開館50年",
                slug="library-50",
                description="館内と元職員のインタビューで構成した18分の周年記録。",
                year=2022,
                client="市立図書館",
                location="東京都",
                schema_org_type="VideoObject",
            ),
        ],
        conversion_points=[
            ConversionPointDraft(
                key="quote",
                type="quote_request",
                name="映像の見積",
                description="目的、尺、納期、予算、参考イメージがあると見積が具体になります。",
                input_schema=VIDEO_QUOTE_SCHEMA,
                adapters=[
                    AdapterBinding(key="internal"),
                    AdapterBinding(key="email", config={"to": "hello@kogaku-film.example"}),
                ],
            ),
            ConversionPointDraft(
                key="inquiry",
                type="inquiry",
                name="取材前の問い合わせ",
                description="まだ尺も予算も曖昧な段階の相談です。",
                input_schema=default_input_schema("inquiry"),
                adapters=[AdapterBinding(key="internal")],
            ),
            ConversionPointDraft(
                key="showreel",
                type="external_link",
                name="ショーリールを見る",
                description="過去作品のダイジェストです。",
                external_url="https://example.com/kogaku-showreel",
                input_schema=default_input_schema("external_link"),
                adapters=[AdapterBinding(key="internal")],
            ),
        ],
        extension={
            "deliverable_types": ["ブランドフィルム", "採用動画", "周年記録"],
            "typical_duration_sec": {"min": 45, "max": 180},
            "shooting_styles": ["定点の観察", "少ない照明のインタビュー", "閉館後の施設記録"],
            "crew_size": "監督・撮影・音声・制作の4名",
            "can_travel": True,
        },
        source_urls=[f"{base}/fixtures/kogaku"],
        source_description="世田谷の映像制作。ブランドフィルムとインタビューを見積で受ける。",
        vertical_key="video_production",
    )


def _seed_one(session, *, schema_key: str, schema_title: str, document: dict, catalog: BusinessCatalog, fixture: str) -> None:
    schema_row = save_schema_version(
        session,
        key=schema_key,
        title=schema_title,
        description=document.get("description") or "",
        document=document,
    )
    catalog = prepare_catalog(catalog)
    business = Business(
        slug=catalog.slug,
        name=catalog.name,
        status="draft",
        source_urls=list(catalog.source_urls),
        source_description=catalog.source_description,
        seller={"name": catalog.seller.name},
    )
    session.add(business)
    session.flush()
    apply_catalog(session, business, catalog, schema_row)
    business.status = "published"
    business.published_at = utcnow()
    run = GenerationRun(
        business_id=business.id,
        status="published",
        step="seed",
        model="seed",
        schema_proposal={"action": "create", "schema_key": schema_key},
        extracted=seal_catalog(catalog),
        vertical_schema_id=schema_row.id,
        finished_at=utcnow(),
    )
    session.add(run)
    session.flush()
    html = (FIXTURES / f"{fixture}.html").read_text(encoding="utf-8")
    parsed = parse_document(catalog.source_urls[0], html.encode("utf-8"))
    session.add(
        CrawlDocument(
            business_id=business.id,
            generation_run_id=run.id,
            url=catalog.source_urls[0],
            ok=True,
            title=parsed.title or catalog.name,
            text=parsed.text or catalog.description,
            metadata_json=parsed.metadata or {},
        )
    )


def seed() -> None:
    base = get_settings().public_base_url.rstrip("/")
    with session_scope() as session:
        if session.exec(select(Business).where(Business.slug == "aoba-sekkei")).first():
            return
        _seed_one(
            session,
            schema_key="architecture",
            schema_title="建築・建設",
            document=ARCHITECTURE_SCHEMA,
            catalog=aoba_catalog(base),
            fixture="aoba",
        )
        _seed_one(
            session,
            schema_key="video_production",
            schema_title="映像制作",
            document=VIDEO_SCHEMA,
            catalog=kogaku_catalog(base),
            fixture="kogaku",
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return
        logger.info("seeded aoba-sekkei and kogaku-film")
