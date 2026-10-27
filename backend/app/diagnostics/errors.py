"""Errors shared by the diagnostics fetcher and the SSRF guard."""

from __future__ import annotations


class InvalidTargetError(ValueError):
    """The target is not an absolute http(s) URL."""


class BlockedAddressError(ValueError):
    """The target resolves to a local or private address."""
