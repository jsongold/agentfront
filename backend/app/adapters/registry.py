"""Load adapters and ingestion sources via pluggy and package entry points."""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import entry_points

import pluggy

from app.adapters.email import plugin as email_plugin
from app.adapters.internal import plugin as internal_plugin
from app.adapters.webhook import plugin as webhook_plugin
from app.crawl.url_crawl import plugin as url_crawl_plugin

hookspec = pluggy.HookspecMarker("agentfront")


class CatalogHooks:
    @hookspec
    def catalog_adapter(self):
        """Return a delivery Adapter."""

    @hookspec
    def catalog_ingestion(self):
        """Return an ingestion source."""


def _register_group(manager: pluggy.PluginManager, group: str) -> None:
    try:
        points = entry_points(group=group)
    except Exception:  # noqa: BLE001
        return
    for point in points:
        try:
            loaded = point.load()
            plugin = loaded() if callable(loaded) else loaded
            manager.register(plugin)
        except Exception:  # noqa: BLE001
            # A broken optional plugin must not take down the process.
            continue


@lru_cache
def plugin_manager() -> pluggy.PluginManager:
    manager = pluggy.PluginManager("agentfront")
    manager.add_hookspecs(CatalogHooks)
    for factory in (internal_plugin, email_plugin, webhook_plugin, url_crawl_plugin):
        manager.register(factory())
    _register_group(manager, "agentfront.adapters")
    _register_group(manager, "agentfront.ingestion")
    return manager


def adapter_map() -> dict:
    found: dict = {}
    for adapter in plugin_manager().hook.catalog_adapter():
        found.setdefault(adapter.key, adapter)
    return found


def ingestion_map() -> dict:
    found: dict = {}
    for source in plugin_manager().hook.catalog_ingestion():
        found.setdefault(source.key, source)
    return found
