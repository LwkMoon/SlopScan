"""GitHub repository target (spec section 29).

Uses the public GitHub REST API to list a repo's file tree and fetch raw
file contents -- no `git clone`, no local execution of anything from the
repo. Works without authentication for public repositories; an optional
token (GITHUB_TOKEN / SLOPSCAN_GITHUB_TOKEN) raises the unauthenticated
rate limit if the user has one, but is never required.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import httpx

from slopscan.core.ignore import MAX_FILE_BYTES_DEFAULT, is_ignored, is_supported_file
from slopscan.core.source import ScanCorpus, SourceFile, kind_for_path
from slopscan.targets.base import Target, TargetError

_REPO_URL_RE = re.compile(
    r"^https?://(www\.)?github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(\.git)?/?(?:/tree/(?P<ref>[^/]+))?/?$",
    re.IGNORECASE,
)
API_ROOT = "https://api.github.com"
MAX_FILES_DEFAULT = 300
API_TIMEOUT = 15.0


@dataclass
class ParsedRepoUrl:
    owner: str
    repo: str
    ref: str | None


def parse_github_url(url: str) -> ParsedRepoUrl:
    match = _REPO_URL_RE.match(url.strip())
    if not match:
        raise TargetError(f"Could not parse GitHub repository URL: {url}")
    return ParsedRepoUrl(owner=match.group("owner"), repo=match.group("repo"), ref=match.group("ref"))


class GithubTarget(Target):
    def __init__(
        self,
        url: str,
        max_files: int = MAX_FILES_DEFAULT,
        max_file_bytes: int = MAX_FILE_BYTES_DEFAULT,
        timeout: float = API_TIMEOUT,
    ) -> None:
        self.url = url
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes
        self.timeout = timeout

    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "SlopScan/0.1"}
        token = os.environ.get("SLOPSCAN_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def collect(self) -> ScanCorpus:
        parsed = parse_github_url(self.url)
        corpus = ScanCorpus(rendered=False, source_available=True)

        with httpx.Client(timeout=self.timeout, headers=self._headers()) as client:
            ref = parsed.ref or self._default_branch(client, parsed)
            tree = self._get_tree(client, parsed, ref)

            candidates = [
                item for item in tree
                if item.get("type") == "blob"
                and not is_ignored(item["path"])
                and is_supported_file(item["path"])
                and item.get("size", 0) <= self.max_file_bytes
            ]
            if len(candidates) > self.max_files:
                corpus.truncated = True
                candidates = candidates[: self.max_files]

            for item in candidates:
                content = self._get_raw_file(client, parsed, ref, item["path"])
                if content is None:
                    corpus.skipped_count += 1
                    continue
                corpus.files.append(
                    SourceFile(
                        path=item["path"],
                        content=content,
                        kind=kind_for_path(item["path"]),
                        size_bytes=item.get("size", 0),
                    )
                )

        return corpus

    def _default_branch(self, client: httpx.Client, parsed: ParsedRepoUrl) -> str:
        resp = client.get(f"{API_ROOT}/repos/{parsed.owner}/{parsed.repo}")
        self._raise_for_status(resp, context=f"{parsed.owner}/{parsed.repo}")
        return resp.json().get("default_branch", "main")

    def _get_tree(self, client: httpx.Client, parsed: ParsedRepoUrl, ref: str) -> list[dict]:
        resp = client.get(
            f"{API_ROOT}/repos/{parsed.owner}/{parsed.repo}/git/trees/{ref}",
            params={"recursive": "1"},
        )
        self._raise_for_status(resp, context=f"{parsed.owner}/{parsed.repo}@{ref}")
        data = resp.json()
        if data.get("truncated"):
            pass  # GitHub itself truncated a huge tree -- we still work with what we got
        return data.get("tree", [])

    def _get_raw_file(self, client: httpx.Client, parsed: ParsedRepoUrl, ref: str, path: str) -> str | None:
        url = f"https://raw.githubusercontent.com/{parsed.owner}/{parsed.repo}/{ref}/{path}"
        try:
            resp = client.get(url)
        except httpx.HTTPError:
            return None
        if resp.status_code != 200:
            return None
        return resp.text

    @staticmethod
    def _raise_for_status(resp: httpx.Response, context: str) -> None:
        if resp.status_code == 404:
            raise TargetError(f"GitHub repository not found or private: {context}")
        if resp.status_code == 403:
            raise TargetError(
                f"GitHub API rate limit hit while fetching {context}. "
                "Set GITHUB_TOKEN to raise the limit, or try again later."
            )
        if resp.status_code >= 400:
            raise TargetError(f"GitHub API error ({resp.status_code}) fetching {context}")
