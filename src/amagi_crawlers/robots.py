"""robots.txt parsing and matching, following RFC 9309.

- Consecutive ``User-agent`` lines share one group; a ``User-agent`` line after rules starts a new one.
- A crawler uses every group that names its product token (merged), case-insensitively. Only when
  no group names it does it fall back to the ``*`` groups. No group at all means everything is allowed.
- The longest matching path wins. On a tie, ``Allow`` wins. ``*`` matches any run of characters and a
  trailing ``$`` anchors the end. An empty ``Disallow:`` is not a rule.
- ``/robots.txt`` itself is always allowed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import quote


@dataclass
class Rule:
    allow: bool
    pattern: str
    line: int

    def __post_init__(self):
        self._re = _compile(self.pattern)

    def matches(self, path: str) -> bool:
        return self._re.match(path) is not None

    def __str__(self) -> str:
        return f"{'Allow' if self.allow else 'Disallow'}: {self.pattern}"


@dataclass
class Group:
    agents: List[str]   # as written in the file
    rules: List[Rule] = field(default_factory=list)
    line: int = 0


@dataclass
class Decision:
    allowed: bool
    group: str            # the agent name the decision came from ("GPTBot", "*"), "" if no group applied
    rule: Optional[Rule]  # the rule that decided it, None if no rule matched

    def explain(self) -> str:
        if not self.group:
            return "no rules for this bot"
        where = "(*)" if self.group == "*" else "(own group)"
        if self.rule is None:
            return f"allowed {where}"
        return f"{self.rule} {where}"


def _compile(pattern: str) -> "re.Pattern[str]":
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    rx = ".*".join(re.escape(_normalise(part)) for part in body.split("*"))
    return re.compile(rx + ("$" if anchored else ""), re.DOTALL)


def _normalise(path: str) -> str:
    """Percent-encode non-ASCII and upper-case existing escapes so both sides compare alike."""
    path = quote(path, safe="/?=&;:@!$'()*+,%-._~")
    return re.sub(r"%[0-9a-fA-F]{2}", lambda m: m.group(0).upper(), path)


def product_token(value: str) -> str:
    """'GPTBot/1.1 (+https://...)' -> 'gptbot'."""
    value = value.strip()
    if not value:
        return ""
    return value.split()[0].split("/")[0].lower()


class Robots:
    def __init__(self, groups: List[Group], sitemaps: List[str]):
        self.groups = groups
        self.sitemaps = sitemaps

    @classmethod
    def parse(cls, text: str) -> "Robots":
        groups: List[Group] = []
        sitemaps: List[str] = []
        current: Optional[Group] = None
        in_agent_run = False
        for lineno, raw in enumerate(text.lstrip("﻿").splitlines(), start=1):
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower().replace(" ", "-").replace("_", "-")
            value = value.strip()
            if key in ("user-agent", "useragent"):
                if current is None or not in_agent_run:
                    current = Group(agents=[], line=lineno)
                    groups.append(current)
                current.agents.append(value)
                in_agent_run = True
            elif key in ("allow", "disallow"):
                in_agent_run = False
                if current is None or not value:
                    continue  # rules before any User-agent, or an empty Disallow (= no rule)
                if not value.startswith(("/", "*")):
                    value = "/" + value
                current.rules.append(Rule(key == "allow", value, lineno))
            elif key == "sitemap":
                sitemaps.append(value)
            # other keys (Crawl-delay, Host, ...) neither end nor start a group
        return cls(groups, sitemaps)

    def groups_for(self, token: str):
        """Return (label, rules) for a product token: its own groups merged, else '*', else ('', [])."""
        want = product_token(token)
        own = [g for g in self.groups if any(product_token(a) == want for a in g.agents)]
        if own:
            label = next(a for a in own[0].agents if product_token(a) == want)
            return label.strip(), [r for g in own for r in g.rules]
        star = [g for g in self.groups if any(a.strip() == "*" for a in g.agents)]
        if star:
            return "*", [r for g in star for r in g.rules]
        return "", []

    def decide(self, token: str, path: str = "/") -> Decision:
        path = _normalise(path or "/")
        label, rules = self.groups_for(token)
        if path == "/robots.txt":
            return Decision(True, label, None)
        best: Optional[Rule] = None
        for rule in rules:
            if not rule.matches(path):
                continue
            if (best is None or len(rule.pattern) > len(best.pattern)
                    or (len(rule.pattern) == len(best.pattern) and rule.allow and not best.allow)):
                best = rule
        return Decision(best is None or best.allow, label, best)

    def names(self) -> List[str]:
        """Every agent the file names, in file order, without duplicates."""
        seen: List[str] = []
        for g in self.groups:
            for a in g.agents:
                if a not in seen:
                    seen.append(a)
        return seen
