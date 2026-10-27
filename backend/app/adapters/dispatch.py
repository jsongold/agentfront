"""Fan a conversion out to every adapter configured on the point."""

from __future__ import annotations

from app.adapters.base import DeliveryContext, DeliveryResult
from app.adapters.registry import adapter_map
from app.domain.catalog import AdapterBinding


def dispatch(bindings: list[AdapterBinding], base: DeliveryContext) -> list[tuple[str, DeliveryResult]]:
    adapters = adapter_map()
    outcomes: list[tuple[str, DeliveryResult]] = []
    for binding in bindings:
        adapter = adapters.get(binding.key)
        ctx = base.model_copy(update={"config": binding.config})
        if adapter is None:
            outcomes.append((binding.key, DeliveryResult(status="failed", detail=f"unknown adapter {binding.key}")))
            continue
        try:
            outcomes.append((binding.key, adapter.send(ctx)))
        except Exception as exc:  # noqa: BLE001
            outcomes.append((binding.key, DeliveryResult(status="failed", detail=str(exc))))
    return outcomes
