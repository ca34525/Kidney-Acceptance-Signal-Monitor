"""Small published-count examples protect the separate waiting-list screen."""

from dataclasses import replace
from datetime import datetime

import pytest

from kasm.config import SourceRecord
from kasm.data.parse import ParseError, WorkbookSheet
from kasm.waiting_list.parse import AnnualRecord, parse_release, select_vintages

LABELS = {
    "ADDCEN": "New Listings",
    "END": "On waitlist at end",
    "REMDET": "Deteriorated",
    "REMDIED": "Died",
    "REMOTH": "Other Reasons",
    "REMREC": "Recovered",
    "REMTFER": "Transferred to another center",
    "REMTXC": "Received deceased donor tx",
    "REMTXL": "Received living donor tx",
    "REMTXOC": "Transplanted at another center",
    "ST": "On waitlist at start",
}
HEADERS = ("ENTIRE_NAME", "CTR_CD", "CTR_TY", "RELEASE_DATE", "ORG") + tuple(
    f"WLA_{name}_{suffix}" for name in LABELS for suffix in ("NC1", "NC2", "PCZ", "PRZ", "PUZ")
)


def source() -> SourceRecord:
    return SourceRecord(
        release_code="1808",
        cohort_year=1970,  # The B1 years must come from separate release-bound evidence.
        transport="xls",
        url="https://example.org/source.xls",
        download_bytes=1,
        download_sha256="a" * 64,
        published_value="2018-10",
        published_precision="month",
        expected_rows=900,  # The offer-acceptance population is unrelated to Table B1.
    )


def sheet(overrides: dict[str, object] | None = None) -> WorkbookSheet:
    labels = ("Center Name", "Center Code", "Center Type", "Release Date", "Organ") + tuple(
        LABELS[header.split("_")[1]] for header in HEADERS[5:]
    )
    values: dict[str, object] = dict.fromkeys(HEADERS, 0)
    values.update(
        ENTIRE_NAME="Example program",
        CTR_CD="AB12",
        CTR_TY="TX1",
        RELEASE_DATE=datetime(2018, 10, 8, 19),
        ORG="KI",
        WLA_ST_NC1=100,
        WLA_END_NC1=110,
        WLA_ADDCEN_NC1=30,
        WLA_REMTXC_NC1=10,
        WLA_REMTXL_NC1=5,
        WLA_REMTXOC_NC1=2,
        WLA_REMTFER_NC1=1,
        WLA_REMDIED_NC1=1,
        WLA_REMDET_NC1=1,
    )
    values.update(overrides or {})
    return WorkbookSheet("Table B1", (HEADERS, labels, tuple(values[h] for h in HEADERS)), 60)


def example() -> AnnualRecord:
    return parse_release(source(), (sheet(),), (2016, 2017))[0]


def test_annual_identity_and_years_use_separate_evidence() -> None:
    records = parse_release(source(), (sheet(),), (2016, 2017))
    first, second = records
    assert (first.program_key, first.year, second.year) == ("AB12:TX1", 2016, 2017)
    assert first.removals == (10, 5, 2, 1, 1, 1, 0, 0)
    assert first.removal_total == 20
    assert first.growth == 10
    assert first.residual == 0
    assert first.clean
    assert first.published_value == "2018-10"
    assert first.published_precision == "month"
    assert second.start == 0
    assert second.clean


@pytest.mark.parametrize("marker", [None, "", "-", "--", ".", "NA", "N/A", "NULL"])
def test_missing_counts_remain_unknown(marker: object) -> None:
    record = parse_release(source(), (sheet({"WLA_REMDIED_NC1": marker}),), (2016, 2017))[0]
    assert record.removals[4] is None
    assert record.removal_total is None
    assert record.residual is None
    assert record.growth == 10
    assert not record.clean


@pytest.mark.parametrize("value", [-1, 0.5, True, float("inf"), "suppressed?", "abc"])
def test_invalid_counts_fail(value: object) -> None:
    with pytest.raises(ParseError, match="WLA_ADDCEN_NC1"):
        parse_release(source(), (sheet({"WLA_ADDCEN_NC1": value}),), (2016, 2017))


def test_residual_is_retained_without_repair() -> None:
    record = parse_release(source(), (sheet({"WLA_END_NC1": 112}),), (2016, 2017))[0]
    assert record.end == 112
    assert record.growth == 12
    assert record.residual == 2
    assert not record.clean


def test_composite_identity_keeps_program_types_separate() -> None:
    original = sheet()
    second = sheet({"CTR_TY": "VA"})
    combined = replace(original, rows=original.rows + (second.rows[2],))
    records = parse_release(source(), (combined,), (2016, 2017))
    assert {record.program_key for record in records} == {"AB12:TX1", "AB12:VA"}
    duplicate = replace(original, rows=original.rows + (original.rows[2],))
    with pytest.raises(ParseError, match="duplicate program"):
        parse_release(source(), (duplicate,), (2016, 2017))


@pytest.mark.parametrize(("field", "value"), [("CTR_CD", "bad"), ("CTR_TY", ""), ("ORG", "LI")])
def test_identity_drift_fails(field: str, value: object) -> None:
    with pytest.raises(ParseError, match=field):
        parse_release(source(), (sheet({field: value}),), (2016, 2017))


def test_duplicate_or_nonconsecutive_years_fail() -> None:
    for years in ((2017, 2017), (2017, 2019), (2017, 2016)):
        with pytest.raises(ParseError, match="consecutive"):
            parse_release(source(), (sheet(),), years)


@pytest.mark.parametrize("published", [datetime(2018, 9, 30), None, "invalid"])
def test_publication_date_drift_fails(published: object) -> None:
    with pytest.raises(ParseError, match="RELEASE_DATE"):
        parse_release(source(), (sheet({"RELEASE_DATE": published}),), (2016, 2017))


def test_day_publication_accepts_documented_one_day_date_offset_only() -> None:
    day_source = replace(source(), published_value="2018-10-09", published_precision="day")
    assert parse_release(day_source, (sheet(),), (2016, 2017))[0].published_value == "2018-10-09"
    with pytest.raises(ParseError, match="RELEASE_DATE"):
        parse_release(replace(day_source, published_value="2018-10-11"), (sheet(),), (2016, 2017))


def test_machine_column_drift_and_nonexclusive_total_fail() -> None:
    original = sheet()
    for replacement in ("WLA_REMALL_NC1", "WLA_ADDCEN_NC1"):
        headers = list(HEADERS)
        headers[7] = replacement
        changed = replace(original, rows=(tuple(headers), *original.rows[1:]))
        with pytest.raises(ParseError, match="machine fields"):
            parse_release(source(), (changed,), (2016, 2017))
    extra = replace(
        original,
        rows=tuple(
            row + ("WLA_REMALL_NC1" if index == 0 else 0,)
            for index, row in enumerate(original.rows)
        ),
        column_count=61,
    )
    with pytest.raises(ParseError, match="machine fields"):
        parse_release(source(), (extra,), (2016, 2017))


def test_description_changes_cannot_silently_change_category_meaning() -> None:
    original = sheet()
    labels = list(original.rows[1])
    labels[HEADERS.index("WLA_REMTXC_NC1")] = "All transplant removals"
    changed = replace(original, rows=(original.rows[0], tuple(labels), original.rows[2]))
    with pytest.raises(ParseError, match="description"):
        parse_release(source(), (changed,), (2016, 2017))


def test_missing_duplicate_empty_table_and_short_row_fail() -> None:
    original = sheet()
    for sheets in ((), (original, original), (replace(original, rows=original.rows[:2]),)):
        with pytest.raises(ParseError):
            parse_release(source(), sheets, (2016, 2017))
    short = replace(original, rows=(*original.rows[:2], original.rows[2][:-1]))
    with pytest.raises(ParseError, match="row width"):
        parse_release(source(), (short,), (2016, 2017))


def test_earliest_year_vintage_retains_changes_without_backfilling() -> None:
    first = example()
    later = replace(first, release_code="1905", published_value="2019-07", end=113)
    added = replace(later, program_key="CD34:TX1")
    selected, revisions = select_vintages((later, added, first), ("1808", "1905"))
    assert selected == (first,)
    changed = next(row for row in revisions if row.program_key == first.program_key)
    assert changed.canonical == first
    assert changed.later == later
    assert changed.changed_fields == ("end",)
    absent = next(row for row in revisions if row.program_key == added.program_key)
    assert absent.canonical is None
    assert absent.later == added
    assert absent.changed_fields == ("program_presence",)


def test_revision_records_program_missing_from_later_release() -> None:
    first = example()
    earlier_extra = replace(first, program_key="CD34:TX1")
    later = replace(first, release_code="1905", published_value="2019-07")
    _, revisions = select_vintages((first, earlier_extra, later), ("1808", "1905"))
    absent = next(row for row in revisions if row.program_key == earlier_extra.program_key)
    assert absent.canonical == earlier_extra
    assert absent.later is None
    assert absent.later_release == "1905"


def test_vintage_duplicates_unknown_and_reversed_releases_fail() -> None:
    first = example()
    later = replace(first, release_code="1905", published_value="2019-07")
    for records, order in (
        ((first, first), ("1808",)),
        ((first,), ("1808", "1808")),
        ((first,), ("1905",)),
        ((first, later), ("1905", "1808")),
    ):
        with pytest.raises(ParseError):
            select_vintages(records, order)
