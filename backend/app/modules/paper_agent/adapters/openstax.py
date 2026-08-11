"""First whitelisted website adapter: OpenStax open educational resources."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx


class WebsiteNotAllowedError(ValueError):
    pass


class WebsiteFetchError(RuntimeError):
    pass


class WebsiteContentError(ValueError):
    pass


class WebsiteTooLargeError(WebsiteContentError):
    pass


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.casefold() == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.parts.append(data)

    @property
    def title(self) -> str | None:
        value = " ".join(" ".join(self.parts).split())
        return value[:255] if value else None


@dataclass(frozen=True, slots=True)
class CollectedWebPage:
    final_url: str
    content: bytes
    content_type: str
    title: str | None


class OpenStaxWebsiteAdapter:
    name = "openstax"
    supported_hosts = frozenset({"openstax.org", "www.openstax.org"})
    redirect_statuses = frozenset({301, 302, 303, 307, 308})

    def canonical_url(self, value: str, allowed_hosts: frozenset[str]) -> str:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        if parsed.scheme.casefold() != "https":
            raise WebsiteNotAllowedError("website collection requires HTTPS")
        if parsed.username is not None or parsed.password is not None:
            raise WebsiteNotAllowedError("website URL cannot contain credentials")
        try:
            port = parsed.port
        except ValueError as exc:
            raise WebsiteNotAllowedError("website URL contains an invalid port") from exc
        if port not in {None, 443}:
            raise WebsiteNotAllowedError("website URL cannot use a custom port")
        if host not in self.supported_hosts or host not in allowed_hosts:
            raise WebsiteNotAllowedError(
                "website host is not on the OpenStax whitelist"
            )
        if not parsed.path.startswith("/"):
            raise WebsiteNotAllowedError("website URL path is invalid")
        return urlunsplit(("https", parsed.netloc.lower(), parsed.path, parsed.query, ""))

    async def collect(
        self,
        value: str,
        *,
        client: httpx.AsyncClient,
        allowed_hosts: frozenset[str],
        max_bytes: int,
        max_redirects: int = 3,
    ) -> CollectedWebPage:
        current_url = self.canonical_url(value, allowed_hosts)
        for redirect_count in range(max_redirects + 1):
            try:
                async with client.stream(
                    "GET",
                    current_url,
                    follow_redirects=False,
                    headers={
                        "Accept": "text/html,application/xhtml+xml",
                        "User-Agent": "FlowGate-PaperAgent/0.1",
                    },
                ) as response:
                    if response.status_code in self.redirect_statuses:
                        location = response.headers.get("location")
                        if location is None or redirect_count == max_redirects:
                            raise WebsiteFetchError("website redirect cannot be followed")
                        current_url = self.canonical_url(
                            urljoin(current_url, location),
                            allowed_hosts,
                        )
                        continue
                    if response.status_code != 200:
                        raise WebsiteFetchError(
                            f"website returned HTTP {response.status_code}"
                        )
                    content_type = response.headers.get("content-type", "")
                    media_type = content_type.split(";", maxsplit=1)[0].lower()
                    if media_type not in {"text/html", "application/xhtml+xml"}:
                        raise WebsiteContentError("website response is not HTML")
                    declared_length = response.headers.get("content-length")
                    if declared_length is not None:
                        try:
                            if int(declared_length) > max_bytes:
                                raise WebsiteTooLargeError(
                                    f"website response exceeds {max_bytes} bytes"
                                )
                        except ValueError as exc:
                            raise WebsiteTooLargeError(
                                "website returned an invalid content length"
                            ) from exc
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            raise WebsiteContentError(
                                f"website response exceeds {max_bytes} bytes"
                            )
                        chunks.append(chunk)
            except httpx.HTTPError as exc:
                raise WebsiteFetchError("website request failed") from exc

            content = b"".join(chunks)
            if not content:
                raise WebsiteContentError("website returned an empty page")
            encoding = response.encoding or "utf-8"
            try:
                html = content.decode(encoding, errors="replace")
            except LookupError:
                html = content.decode("utf-8", errors="replace")
            parser = _TitleParser()
            parser.feed(html)
            return CollectedWebPage(
                final_url=current_url,
                content=content,
                content_type=media_type,
                title=parser.title,
            )
        raise WebsiteFetchError("website redirect limit was exceeded")
