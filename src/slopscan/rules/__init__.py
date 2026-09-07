"""Rule package. Importing this module populates rules.registry.REGISTRY
by importing every rule-definition module below (each uses the @rule
decorator to self-register). Add a new rule module and import it here to
plug it into the engine -- no other wiring is required."""

from slopscan.rules import (  # noqa: F401
    animation,
    code,
    components,
    copy,
    layout,
    typography,
    visual,
)
from slopscan.rules.registry import REGISTRY, Rule, all_rules, get_rule, rules_by_category

__all__ = ["REGISTRY", "Rule", "all_rules", "get_rule", "rules_by_category"]
