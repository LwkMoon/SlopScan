"""Dependency/stack detection.

Per spec section 28: dependencies alone must never prove or score AI
generation. Using Tailwind, shadcn, Framer Motion, or React is completely
normal. This module exists purely to populate the "detected stack" context
shown in reports (and passed to the optional AI layer) -- it never creates
Findings and never touches the score.
"""

from __future__ import annotations

import json
import re

from slopscan.core.source import ScanCorpus

_NOTABLE_PACKAGES = {
    "tailwindcss": "CSS framework",
    "@shadcn/ui": "component library",
    "shadcn-ui": "component library",
    "framer-motion": "animation library",
    "gsap": "animation library",
    "aos": "scroll-animation library",
    "react": "UI framework",
    "next": "React framework",
    "vue": "UI framework",
    "svelte": "UI framework",
    "lucide-react": "icon library",
    "react-icons": "icon library",
    "@heroicons/react": "icon library",
    "three": "3D/WebGL library",
    "lottie-web": "animation library",
    "openai": "AI SDK",
    "@anthropic-ai/sdk": "AI SDK",
}


def detect_dependencies(corpus: ScanCorpus) -> dict[str, str]:
    """Returns {package_name: category} for recognized, notable packages
    found in package.json / requirements.txt / pyproject.toml."""
    found: dict[str, str] = {}
    for f in corpus.files:
        name = f.path.rsplit("/", 1)[-1].lower()
        if name == "package.json":
            found.update(_from_package_json(f.content))
        elif name == "requirements.txt":
            found.update(_from_requirements_txt(f.content))
        elif name == "pyproject.toml":
            found.update(_from_pyproject(f.content))
    return found


def _from_package_json(content: str) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return out
    deps: dict[str, str] = {}
    for key in ("dependencies", "devDependencies"):
        deps.update(data.get(key, {}) or {})
    for pkg in deps:
        lower = pkg.lower()
        if lower in _NOTABLE_PACKAGES:
            out[pkg] = _NOTABLE_PACKAGES[lower]
    return out


def _from_requirements_txt(content: str) -> dict[str, str]:
    out = {}
    for line in content.splitlines():
        pkg = re.split(r"[=<>!~\s]", line.strip())[0].lower()
        if pkg in _NOTABLE_PACKAGES:
            out[pkg] = _NOTABLE_PACKAGES[pkg]
    return out


def _from_pyproject(content: str) -> dict[str, str]:
    out = {}
    for pkg, category in _NOTABLE_PACKAGES.items():
        if re.search(rf'["\']{re.escape(pkg)}["\']', content, re.IGNORECASE):
            out[pkg] = category
    return out
