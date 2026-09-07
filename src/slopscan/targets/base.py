"""Base Target protocol.

Every target type (local dir, zip, URL, GitHub repo) implements `collect()`,
returning a `ScanCorpus`. Nothing downstream (analyzers, rules, scoring)
needs to know which target type produced the corpus.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from slopscan.core.source import ScanCorpus


class TargetError(Exception):
    """Raised for user-facing target errors (network, filesystem, security).

    The CLI layer catches this and prints a clean message instead of a
    traceback (spec section 66).
    """


class Target(ABC):
    @abstractmethod
    def collect(self) -> ScanCorpus: ...
