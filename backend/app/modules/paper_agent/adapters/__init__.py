"""Whitelisted website adapters for Paper Agent ingestion."""

from app.modules.paper_agent.adapters.openstax import (
    OpenStaxWebsiteAdapter,
    WebsiteContentError,
    WebsiteFetchError,
    WebsiteNotAllowedError,
    WebsiteTooLargeError,
)

__all__ = [
    "OpenStaxWebsiteAdapter",
    "WebsiteContentError",
    "WebsiteFetchError",
    "WebsiteNotAllowedError",
    "WebsiteTooLargeError",
]
