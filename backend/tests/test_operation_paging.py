from collections.abc import Iterator

from app.services.builds.operation_paging import (
    OperationPageCandidate,
    page_operation_candidates,
)


def _candidates(count: int) -> Iterator[OperationPageCandidate]:
    for index in range(count):
        yield OperationPageCandidate(
            index=index,
            method="GET" if index % 2 == 0 else "POST",
            search_text=f"operation {index} /resources/{index}",
            excluded_in_build=index % 20 == 0,
            currently_excluded=index % 10 == 0,
        )


def test_operation_paging_handles_documented_thousand_operation_scale() -> None:
    page, total, policy_changes = page_operation_candidates(
        _candidates(1_000),
        search=None,
        method="GET",
        scope="all",
        offset=200,
        limit=50,
    )

    assert len(page) == 50
    assert page[0].index == 400
    assert page[-1].index == 498
    assert total == 500
    assert policy_changes == 50


def test_operation_paging_stays_bounded_at_configurable_ceiling() -> None:
    page, total, policy_changes = page_operation_candidates(
        _candidates(100_000),
        search=None,
        method=None,
        scope="changed",
        offset=4_800,
        limit=200,
    )

    assert len(page) == 200
    assert page[0].index == 96_010
    assert page[-1].index == 99_990
    assert total == 5_000
    assert policy_changes == 5_000
