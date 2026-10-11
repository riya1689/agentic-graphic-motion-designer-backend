"""Semantic icon resolution boundary for future Planner integration."""

from __future__ import annotations

from dataclasses import dataclass

from packages.icon_library.application.service import IconLibraryService
from packages.icon_library.domain.models import IconRecord, IconSearchQuery


@dataclass(frozen=True)
class IconIntent:
    """Provider-neutral icon requirement extracted from a design plan."""

    subject: str
    category: str | None = None
    style: str | None = None
    tags: tuple[str, ...] = ()


class IconResolver:
    """Find a reusable library icon without knowing persistence details."""

    def __init__(self, library: IconLibraryService) -> None:
        self._library = library

    def resolve(self, intent: IconIntent) -> IconRecord | None:
        query = IconSearchQuery(
            text=intent.subject,
            category=intent.category,
            style=intent.style,
            tags=tuple(tag.strip().lower() for tag in intent.tags if tag.strip()),
            limit=20,
        )
        candidates = list(self._library.search(query))
        if not candidates:
            return None
        return max(candidates, key=lambda icon: _score(icon, intent))


def _score(icon: IconRecord, intent: IconIntent) -> int:
    subject_tokens = _tokens(intent.subject)
    icon_tokens = _tokens(" ".join((icon.name, icon.category or "", *icon.tags)))
    score = len(subject_tokens & icon_tokens) * 3
    if intent.category and icon.category == intent.category:
        score += 5
    if intent.style and icon.style == intent.style:
        score += 2
    score += len(set(intent.tags) & set(icon.tags)) * 2
    return score


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in value.replace("-", " ").split() if token.strip()}
