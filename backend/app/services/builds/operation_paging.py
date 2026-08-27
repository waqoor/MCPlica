from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

type OperationScope = Literal[
    "all",
    "current-included",
    "current-excluded",
    "build-excluded",
    "changed",
]


@dataclass(frozen=True, slots=True)
class OperationPageCandidate:
    index: int
    method: str
    search_text: str
    excluded_in_build: bool
    currently_excluded: bool

    @property
    def changed(self) -> bool:
        return self.excluded_in_build != self.currently_excluded


def page_operation_candidates(
    candidates: Iterable[OperationPageCandidate],
    *,
    search: str | None,
    method: str | None,
    scope: OperationScope,
    offset: int,
    limit: int,
) -> tuple[list[OperationPageCandidate], int, int]:
    """Return one bounded page, filtered count, and all-operation policy drift count."""
    normalized_search = search.strip().casefold() if search else ""
    normalized_method = method.strip().upper() if method else ""
    selected: list[OperationPageCandidate] = []
    total = 0
    policy_change_count = 0
    for candidate in candidates:
        if candidate.changed:
            policy_change_count += 1
        if normalized_search and normalized_search not in candidate.search_text.casefold():
            continue
        if normalized_method and candidate.method != normalized_method:
            continue
        if scope == "current-included" and candidate.currently_excluded:
            continue
        if scope == "current-excluded" and not candidate.currently_excluded:
            continue
        if scope == "build-excluded" and not candidate.excluded_in_build:
            continue
        if scope == "changed" and not candidate.changed:
            continue
        if offset <= total < offset + limit:
            selected.append(candidate)
        total += 1
    return selected, total, policy_change_count
