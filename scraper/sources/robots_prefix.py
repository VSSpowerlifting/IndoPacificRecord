"""
Prefix-only robots.txt evaluation shared by the Japan MOD and Philippines AFP
shadow collectors.

Both collectors used to drive ``urllib.robotparser`` through private hooks:
they replaced ``_add_entry`` so that repeated wildcard groups survived, then
installed a merged ``default_entry``. On Python 3.13 the stdlib parser keeps
its groups in a separate ``groups`` structure that ``can_fetch`` reads, so
the hook left it empty and every URL was allowed (fail open). This module is
a direct port of the Python 3.9 ``RobotFileParser`` parse/match semantics
those collectors were qualified against, with no stdlib parser internals, so
the verdicts are identical on every interpreter.

It deliberately keeps the 3.9 behaviour: plain prefix matching, the first
applicable rule wins, and an empty ``Disallow`` allows. It is not an
RFC 9309 matcher; callers still refuse ``*``/``$`` patterns before calling.
"""

from __future__ import annotations

import urllib.parse
from typing import List, Optional, Sequence, Tuple


class Rule:
    """One Allow/Disallow line, normalised exactly like 3.9 ``RuleLine``."""

    def __init__(self, path: str, allowance: bool) -> None:
        if path == "" and not allowance:
            # An empty Disallow means "allow everything".
            allowance = True
        path = urllib.parse.urlunparse(urllib.parse.urlparse(path))
        self.path = urllib.parse.quote(path)
        self.allowance = allowance

    def applies_to(self, filename: str) -> bool:
        return self.path == "*" or filename.startswith(self.path)


class Group:
    """One user-agent group: its agents, rules in file order and crawl-delay."""

    def __init__(self) -> None:
        self.useragents: List[str] = []
        self.rules: List[Rule] = []
        self.delay: Optional[int] = None


def parse(lines: Sequence[str]) -> List[Group]:
    """Return every group in file order, including repeated ``*`` groups."""
    groups: List[Group] = []
    # 0: start, 1: saw user-agent, 2: saw a rule
    state = 0
    group = Group()
    for line in lines:
        if not line:
            if state == 1:
                group = Group()
                state = 0
            elif state == 2:
                groups.append(group)
                group = Group()
                state = 0
        i = line.find("#")
        if i >= 0:
            line = line[:i]
        line = line.strip()
        if not line:
            continue
        parts = line.split(":", 1)
        if len(parts) != 2:
            continue
        key = parts[0].strip().lower()
        value = urllib.parse.unquote(parts[1].strip())
        if key == "user-agent":
            if state == 2:
                groups.append(group)
                group = Group()
            group.useragents.append(value)
            state = 1
        elif key in ("disallow", "allow"):
            if state != 0:
                group.rules.append(Rule(value, key == "allow"))
                state = 2
        elif key == "crawl-delay":
            if state != 0:
                if value.strip().isdigit():
                    group.delay = int(value)
                state = 2
        elif key == "request-rate":
            if state != 0:
                numbers = value.split("/")
                if (len(numbers) == 2 and numbers[0].strip().isdigit()
                        and numbers[1].strip().isdigit()):
                    # Parsed only for 3.9 parity (int() may raise); unused.
                    int(numbers[0]), int(numbers[1])
                state = 2
    if state == 2:
        groups.append(group)
    return groups


def select(groups: Sequence[Group], user_agent: str) -> List[Group]:
    """Pick the most specific named groups for ``user_agent``, else ``*``."""
    token = user_agent.split("/")[0].lower()
    matches = [(len(agent), group) for group in groups
               for agent in group.useragents
               if agent != "*" and agent.lower() in token]
    if matches:
        specificity = max(length for length, _ in matches)
        return [group for length, group in matches if length == specificity]
    return [group for group in groups if "*" in group.useragents]


def merged_rules(groups: Sequence[Group]) -> List[Rule]:
    """Longest path first; Allow beats Disallow on an equal-length tie."""
    return sorted([rule for group in groups for rule in group.rules],
                  key=lambda rule: (len(rule.path), rule.allowance), reverse=True)


def allows(rules: Sequence[Rule], url: str) -> bool:
    """3.9 ``can_fetch`` URL normalisation, then the first applicable rule."""
    parsed = urllib.parse.urlparse(urllib.parse.unquote(url))
    path = urllib.parse.urlunparse(
        ("", "", parsed.path, parsed.params, parsed.query, parsed.fragment))
    path = urllib.parse.quote(path) or "/"
    for rule in rules:
        if rule.applies_to(path):
            return rule.allowance
    return True


def evaluate(lines: Sequence[str], user_agent: str, url: str) -> Tuple[bool, List[int]]:
    """Return ``(allowed, crawl_delays)`` for the groups that apply to us."""
    groups = select(parse(lines), user_agent)
    delays = [group.delay for group in groups if group.delay is not None]
    return allows(merged_rules(groups), url), delays


def legacy_can_fetch(lines: Sequence[str], user_agent: str, url: str) -> bool:
    """Plain Python 3.9 ``RobotFileParser.parse`` + ``can_fetch`` verdict.

    For the callers that used the public stdlib API without hooks. Unlike
    ``evaluate`` it keeps 3.9's group choice: the first named group whose
    agent is a substring of our token wins, else the first ``*`` group (later
    ``*`` groups are dropped), and within that group the first rule in file
    order wins. Python 3.13's RFC 9309 parser gives different verdicts.
    """
    groups = parse(lines)
    token = user_agent.split("/")[0].lower()
    for group in groups:
        if "*" not in group.useragents and any(
                agent.lower() in token for agent in group.useragents):
            return allows(group.rules, url)
    default = next((g for g in groups if "*" in g.useragents), None)
    return allows(default.rules, url) if default else True
