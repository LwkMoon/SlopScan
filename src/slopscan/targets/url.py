"""Live website target (spec section 32/33).

Fetches the requested page over HTTP first (no browser required). Also
fetches a small, bounded number of same-origin linked stylesheets so the
CSS-based rules (gradients, glow, etc, which usually live in stylesheets
rather than inline) have something to work with. Every hop -- including
redirects -- is re-validated through utils.security.validate_url.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

import httpx

from slopscan.core.source import ScanCorpus, SourceFile, SourceKind
from slopscan.targets.base import Target, TargetError
from slopscan.utils.security import UnsafeURLError, validate_url

DEFAULT_TIMEOUT = 15.0
MAX_RESPONSE_BYTES = 8_000_000
MAX_REDIRECTS = 5
MAX_LINKED_STYLESHEETS = 6


class UrlTarget(Target):
    def __init__(self, url: str, timeout: float = DEFAULT_TIMEOUT, max_pages: int = 1) -> None:
        self.url = url
        self.timeout = timeout
        self.max_pages = max_pages  # reserved for --crawl (spec section 32); MVP fetches the one page

    def collect(self) -> ScanCorpus:
        corpus = ScanCorpus(rendered=False, source_available=True)
        html, final_url = self._safe_get(self.url, expect_html=True)
        corpus.files.append(SourceFile(path=final_url, content=html, kind=SourceKind.HTML))

        for css_url in self._extract_stylesheet_urls(html, final_url)[:MAX_LINKED_STYLESHEETS]:
            try:
                css, css_final = self._safe_get(css_url, expect_html=False)
            except (TargetError, UnsafeURLError):
                corpus.skipped_count += 1
                continue
            corpus.files.append(SourceFile(path=css_final, content=css, kind=SourceKind.CSS))

        return corpus

    def _safe_get(self, url: str, expect_html: bool) -> tuple[str, str]:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            try:
                validate_url(current)
            except UnsafeURLError as exc:
                raise TargetError(str(exc)) from exc

            try:
                with httpx.Client(
                    timeout=httpx.Timeout(self.timeout),
                    follow_redirects=False,
                    headers={"User-Agent": "SlopScan/0.1 (+https://github.com/slopscan/slopscan)"},
                ) as client:
                    with client.stream("GET", current) as resp:
                        if resp.status_code in (301, 302, 303, 307, 308):
                            location = resp.headers.get("location")
                            if not location:
                                raise TargetError(f"Redirect from {current} had no Location header")
                            current = urljoin(current, location)
                            continue
                        if resp.status_code >= 400:
                            raise TargetError(f"HTTP {resp.status_code} fetching {current}")

                        chunks = []
                        total = 0
                        for chunk in resp.iter_bytes():
                            total += len(chunk)
                            if total > MAX_RESPONSE_BYTES:
                                raise TargetError(
                                    f"Response from {current} exceeded the {MAX_RESPONSE_BYTES} byte limit"
                                )
                            chunks.append(chunk)
                        body = b"".join(chunks).decode(resp.encoding or "utf-8", errors="ignore")
                        return body, current
            except httpx.TimeoutException as exc:
                raise TargetError(
                    f"Connection to {current} timed out after {self.timeout}s. Try --timeout 30."
                ) from exc
            except httpx.HTTPError as exc:
                raise TargetError(f"Failed to fetch {current}: {exc}") from exc
        raise TargetError(f"Too many redirects while fetching {url} (> {MAX_REDIRECTS})")

    @staticmethod
    def _extract_stylesheet_urls(html: str, base_url: str) -> list[str]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        base_host = urlparse(base_url).hostname
        urls: list[str] = []
        for link in soup.find_all("link", rel=lambda v: v and "stylesheet" in v):
            href = link.get("href")
            if not href:
                continue
            full = urljoin(base_url, str(href))
            if urlparse(full).hostname == base_host:  # same-origin only, keeps this bounded and safe
                urls.append(full)
        return urls
