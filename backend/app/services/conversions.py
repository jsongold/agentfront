"""Validate a conversion payload and fan it out to the configured adapters."""

from __future__ import annotations

import uuid

from sqlmodel import Session

from app.adapters.base import DeliveryContext
from app.adapters.dispatch import dispatch
from app.analytics.user_agent import classify_user_agent
from app.crypto import decrypt_json
from app.domain.catalog import AdapterBinding
from app.domain.validation import validate_conversion_payload
from app.models import Business, Conversion, ConversionPoint, Delivery


class ConversionNotFound(LookupError):
    pass


def submit_conversion(
    session: Session,
    *,
    conversion_point_id: uuid.UUID,
    payload: dict,
    agent_name: str = "",
    request_text: str = "",
    user_agent: str = "",
) -> Conversion:
    point = session.get(ConversionPoint, conversion_point_id)
    if point is None or not point.enabled:
        raise ConversionNotFound("コンバージョン地点が見つかりません")
    business = session.get(Business, point.business_id)
    if business is None or business.status != "published":
        raise ConversionNotFound("この事業者は公開されていません")
    validate_conversion_payload(point.input_schema or {}, payload)

    conversion = Conversion(
        conversion_point_id=point.id,
        business_id=business.id,
        payload=payload,
        agent_name=(agent_name or "")[:200],
        request_text=(request_text or "")[:8000],
        user_agent=(user_agent or "")[:2000],
        agent_class=classify_user_agent(user_agent) if user_agent else ((agent_name or "unknown")[:80]),
        status="recorded",
    )
    session.add(conversion)
    session.flush()

    bindings: list[AdapterBinding] = []
    prefailed: list[tuple[str, str]] = []
    for stored in point.adapters or []:
        key = stored.get("key") or "internal"
        if stored.get("config_encrypted"):
            try:
                config = decrypt_json(stored["config_encrypted"])
            except Exception as exc:  # noqa: BLE001
                prefailed.append((key, f"config decrypt failed: {exc}"))
                continue
        else:
            config = stored.get("config") or {}
        bindings.append(AdapterBinding(key=key, config=config))
    if not bindings and not prefailed:
        bindings = [AdapterBinding(key="internal", config={})]

    base = DeliveryContext(
        conversion_id=str(conversion.id),
        business_id=str(business.id),
        business_name=business.name,
        business_slug=business.slug,
        conversion_point_id=str(point.id),
        conversion_type=point.type,
        conversion_name=point.name,
        payload=payload,
        agent_name=agent_name or "",
        request_text=request_text or "",
    )
    outcomes = dispatch(bindings, base)
    any_failed = bool(prefailed)
    any_ok = False
    for key, detail in prefailed:
        session.add(Delivery(conversion_id=conversion.id, adapter_key=key, status="failed", detail=detail[:2000]))
    for key, result in outcomes:
        session.add(
            Delivery(
                conversion_id=conversion.id,
                adapter_key=key,
                status=result.status,
                detail=(result.detail or "")[:2000],
            )
        )
        if result.status == "failed":
            any_failed = True
        else:
            any_ok = True
    if any_ok and any_failed:
        conversion.status = "partial_failure"
    elif any_ok:
        conversion.status = "dispatched"
    elif any_failed:
        conversion.status = "failed"
    session.commit()
    session.refresh(conversion)
    return conversion
