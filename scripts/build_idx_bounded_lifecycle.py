import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

DEFAULT_IPO_SNAPSHOT = "data/derived/idx_ipo_history_snapshot.json"
DEFAULT_LIFECYCLE_SNAPSHOT = "data/derived/idx_lifecycle_evidence_batch.json"
DEFAULT_MEMBERSHIP_SNAPSHOT = "data/derived/idx_monthly_membership_delta.json"
DEFAULT_OUTPUT = "data/derived/idx_bounded_lifecycle_2023_2025.json"

WINDOW_START = date(2023, 1, 1)
WINDOW_END = date(2025, 12, 31)

QUALITY_VALID = "VALID"
QUALITY_WARNING = "WARNING"

EVENT_LISTING = "LISTED"
EVENT_DELISTING = "DELISTED"
EVENT_RELISTING = "RELISTED"


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    source_type: str
    source_name: str
    url: str
    note: str


@dataclass(frozen=True, slots=True)
class AdjudicatedDelisting:
    symbol: str
    effective_date: str
    quality: str
    evidence: tuple[EvidenceRef, ...]


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    symbol: str
    effective_date: str
    event_type: str
    quality: str
    source_code: str
    evidence_status: str


@dataclass(frozen=True, slots=True)
class MonthlyReplay:
    year: int
    month: int
    observed_symbols: int
    replayed_symbols: int
    missing_from_replay: tuple[str, ...]
    extra_in_replay: tuple[str, ...]
    tolerated_same_month_delisting: tuple[str, ...]
    passed: bool


@dataclass(frozen=True, slots=True)
class UniverseInterval:
    symbol: str
    valid_from: str
    valid_to: str | None
    start_reason: str
    end_reason: str | None
    point_in_time_safe: bool
    availability_status: str


@dataclass(frozen=True, slots=True)
class BoundedLifecycleSnapshot:
    generated_at: str
    snapshot_version: str
    window_start: str
    window_end: str
    baseline_symbols: int
    listing_events: int
    relisting_events: int
    delisting_events: int
    candidate_symbols: tuple[str, ...]
    adjudicated_candidate_symbols: tuple[str, ...]
    missing_candidate_evidence: tuple[str, ...]
    extra_adjudication_symbols: tuple[str, ...]
    monthly_replay: tuple[MonthlyReplay, ...]
    monthly_replay_passed: int
    monthly_replay_total: int
    intervals: tuple[UniverseInterval, ...]
    event_date_ready: bool
    monthly_presence_replay_ready: bool
    bounded_universe_ready: bool
    strict_pit_ready: bool
    events: tuple[LifecycleEvent, ...]
    adjudicated_delistings: tuple[AdjudicatedDelisting, ...]


def evidence(
    source_name: str,
    url: str,
    note: str,
) -> EvidenceRef:
    return EvidenceRef(
        source_type="CORROBORATED_PUBLIC_REPORTING_OF_IDX_ANNOUNCEMENT",
        source_name=source_name,
        url=url,
        note=note,
    )


DELISTING_REGISTRY = (
    AdjudicatedDelisting(
        symbol="TURI",
        effective_date="2023-04-06",
        quality=QUALITY_WARNING,
        evidence=(
            evidence(
                "Kontan",
                "https://insight.kontan.co.id/news/tak-sampai-berusia-28-tahun-di-bursa-efek-turi-delisting-6-april-2023",
                "Reports IDX approval effective 6 April 2023.",
            ),
            evidence(
                "IDNFinancials announcement mirror",
                "https://www.idnfinancials.com/id/announcement/11472/penghapusan-pencatatan-efek-tunas-ridean-pada-april",
                "Mirrors exchange announcement and states effective 6 April 2023.",
            ),
        ),
    ),
    AdjudicatedDelisting(
        symbol="RMBA",
        effective_date="2024-01-16",
        quality=QUALITY_WARNING,
        evidence=(
            evidence(
                "Brights",
                "https://www.brights.id/id/pengumuman/pengumuman-penghapusan-pencatatan-efek-delisting-pt-bentoel-internasional-investama-tbk-rmba",
                "Reports IDX delisting effective 16 January 2024.",
            ),
            evidence(
                "IDNFinancials announcement mirror",
                "https://www.idnfinancials.com/id/announcement/12483/penghapusan-pencatatan-efek-bentoel-internasional-investama-pada-januari",
                "Mirrors exchange announcement and states effective 16 January 2024.",
            ),
        ),
    ),
    AdjudicatedDelisting(
        symbol="FREN",
        effective_date="2025-04-17",
        quality=QUALITY_WARNING,
        evidence=(
            evidence(
                "DetikFinance",
                "https://finance.detik.com/bursa-dan-valas/d-7874280/smartfren-resmi-hengkang-dari-bursa",
                "Reports IDX delisting effective 17 April 2025.",
            ),
            evidence(
                "IDNFinancials",
                "https://www.idnfinancials.com/news/53855/fren-is-officially-delisted",
                "Reports IDX formally delisted FREN on 17 April 2025.",
            ),
        ),
    ),
    *tuple(
        AdjudicatedDelisting(
            symbol=symbol,
            effective_date="2025-07-21",
            quality=QUALITY_WARNING,
            evidence=(
                evidence(
                    "IDNFinancials announcement mirror",
                    url,
                    "Mirrors IDX delisting announcement with effective date 21 July 2025.",
                ),
            ),
        )
        for symbol, url in (
            (
                "MAMI",
                "https://www.idnfinancials.com/id/announcement/13869/exchange-decided-delist-securities-listed-companies-in-bankrupt-effective-july?sl=id",
            ),
            (
                "FORZ",
                "https://www.idnfinancials.com/id/announcement/13871/delisting-forza-land-indonesia-july",
            ),
            (
                "MYRX",
                "https://www.idnfinancials.com/id/announcement/index/116?sl=id",
            ),
            (
                "KRAH",
                "https://www.idnfinancials.com/id/announcement/13876/2025%E5%B9%B47%E6%9C%8821%E6%97%A5%E3%81%ABgrand-kartech%E3%81%AE%E4%B8%8A%E5%A0%B4%E5%BB%83%E6%AD%A2?sl=id",
            ),
            (
                "KPAS",
                "https://www.idnfinancials.com/id/announcement/13869/exchange-decided-delist-securities-listed-companies-in-bankrupt-effective-july?sl=id",
            ),
            (
                "KPAL",
                "https://www.idnfinancials.com/id/announcement/13873/penghapusan-pencatatan-efek-steadfast-marine-pada-21-juli-2025",
            ),
            (
                "PRAS",
                "https://www.idnfinancials.com/id/announcement/13875/%E5%B9%B4%E6%9C%88%E6%97%A5%E3%81%ABprima-alloy-steel-universal%E3%81%AE%E4%B8%8A%E5%A0%B4%E5%BB%83%E6%AD%A2?sl=id",
            ),
            (
                "NIPS",
                "https://www.idnfinancials.com/id/announcement/13872/penghapusan-pencatatan-efek-nipress-pada-21-juli-2025",
            ),
            (
                "HDTX",
                "https://www.idnfinancials.com/id/announcement/13874/delisting-panasia-indo-resource-july-21-2025",
            ),
            (
                "JKSW",
                "https://www.idnfinancials.com/id/announcement/13877/penghapusan-pencatatan-efek-jakarta-kyoei-steel-pada-juli",
            ),
        )
    ),
    AdjudicatedDelisting(
        symbol="MFIN",
        effective_date="2025-10-02",
        quality=QUALITY_WARNING,
        evidence=(
            evidence(
                "IDNFinancials",
                "https://www.idnfinancials.com/videos/watch/1813/mandala-multifinance-gabung-adira-finance-delisting-2-oktober?sl=en",
                "Reports merger into ADMF and delisting scheduled for 2 October 2025.",
            ),
        ),
    ),
    AdjudicatedDelisting(
        symbol="MASA",
        effective_date="2025-10-30",
        quality=QUALITY_WARNING,
        evidence=(
            evidence(
                "BCA Sekuritas / IQPlus",
                "https://bcasekuritas.co.id/en/latest-news/news/bei-resmi-delisting-saham-multistrada-arah-sarana-masa-efektif-30-oktober-2025",
                "Reports IDX delisting effective 30 October 2025.",
            ),
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a bounded 2023-2025 IDX lifecycle reconstruction "
            "using canonical IPO events, official relisting output, "
            "monthly Table of Stock Price presence, and adjudicated "
            "delisting dates."
        )
    )
    parser.add_argument("--ipo-snapshot", default=DEFAULT_IPO_SNAPSHOT)
    parser.add_argument("--lifecycle-snapshot", default=DEFAULT_LIFECYCLE_SNAPSHOT)
    parser.add_argument("--membership-snapshot", default=DEFAULT_MEMBERSHIP_SNAPSHOT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} root must be a JSON object.")
    return payload


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def in_window(value: str) -> bool:
    parsed = parse_iso_date(value)
    return WINDOW_START <= parsed <= WINDOW_END


def month_key(value: str) -> tuple[int, int]:
    parsed = parse_iso_date(value)
    return (parsed.year, parsed.month)


def load_ipo_events(payload: dict[str, Any]) -> list[LifecycleEvent]:
    events = []
    for year_data in payload.get("years", []):
        if not isinstance(year_data, dict):
            continue
        for record in year_data.get("records", []):
            if not isinstance(record, dict):
                continue
            symbol = record.get("symbol")
            listing_date = record.get("listing_date")
            if not isinstance(symbol, str) or not isinstance(listing_date, str):
                continue
            if not in_window(listing_date):
                continue
            evidence_status = record.get("evidence_status")
            quality = record.get("quality")
            events.append(
                LifecycleEvent(
                    symbol=symbol.strip().upper(),
                    effective_date=listing_date,
                    event_type=EVENT_LISTING,
                    quality=quality if isinstance(quality, str) else QUALITY_WARNING,
                    source_code="IDX_IPO_CANONICAL_SNAPSHOT",
                    evidence_status=(
                        evidence_status
                        if isinstance(evidence_status, str)
                        else "UNKNOWN"
                    ),
                )
            )
    return events


def load_relisting_events(payload: dict[str, Any]) -> list[LifecycleEvent]:
    events = []
    for record in payload.get("relisting_records", []):
        if not isinstance(record, dict):
            continue
        symbol = record.get("symbol")
        event_date = record.get("event_date")
        if not isinstance(symbol, str) or not isinstance(event_date, str):
            continue
        if not in_window(event_date):
            continue
        events.append(
            LifecycleEvent(
                symbol=symbol.strip().upper(),
                effective_date=event_date,
                event_type=EVENT_RELISTING,
                quality=QUALITY_VALID,
                source_code="IDX_LISTING_ACTIVITY_RELISTING",
                evidence_status="OFFICIAL_IDX_ENDPOINT",
            )
        )
    return events


def delisting_events() -> list[LifecycleEvent]:
    return [
        LifecycleEvent(
            symbol=record.symbol,
            effective_date=record.effective_date,
            event_type=EVENT_DELISTING,
            quality=record.quality,
            source_code="ADJUDICATED_DELISTING_REGISTRY",
            evidence_status="CORROBORATED_SECONDARY_EVIDENCE",
        )
        for record in DELISTING_REGISTRY
        if in_window(record.effective_date)
    ]


def load_membership_months(
    payload: dict[str, Any],
) -> dict[tuple[int, int], set[str]]:
    result: dict[tuple[int, int], set[str]] = {}
    for record in payload.get("months", []):
        if not isinstance(record, dict):
            continue
        year = record.get("year")
        month = record.get("month")
        status = record.get("status")
        symbols = record.get("symbols")
        if (
            not isinstance(year, int)
            or not isinstance(month, int)
            or status != "VALID"
            or not isinstance(symbols, list)
        ):
            continue
        if not (2023 <= year <= 2025):
            continue
        normalized = {
            str(symbol).strip().upper()
            for symbol in symbols
            if isinstance(symbol, str) and symbol.strip()
        }
        result[(year, month)] = normalized
    return result


def load_candidate_symbols(payload: dict[str, Any]) -> set[str]:
    symbols = set()
    for record in payload.get("removal_candidates", []):
        if not isinstance(record, dict):
            continue
        symbol = record.get("symbol")
        first_absent_year = record.get("first_absent_year")
        if (
            isinstance(symbol, str)
            and isinstance(first_absent_year, int)
            and 2023 <= first_absent_year <= 2025
        ):
            symbols.add(symbol.strip().upper())
    return symbols


def event_map(
    events: list[LifecycleEvent],
) -> dict[tuple[int, int], list[LifecycleEvent]]:
    result: dict[tuple[int, int], list[LifecycleEvent]] = {}
    for event in events:
        result.setdefault(month_key(event.effective_date), []).append(event)
    for values in result.values():
        values.sort(key=lambda item: (item.effective_date, item.symbol, item.event_type))
    return result


def replay_monthly_presence(
    observed: dict[tuple[int, int], set[str]],
    events: list[LifecycleEvent],
) -> tuple[int, tuple[MonthlyReplay, ...], set[str]]:
    january = observed.get((2023, 1))
    if january is None:
        raise ValueError("2023-01 VALID membership snapshot is required.")

    additions_january = {
        event.symbol
        for event in events
        if month_key(event.effective_date) == (2023, 1)
        and event.event_type in {EVENT_LISTING, EVENT_RELISTING}
    }

    baseline = set(january) - additions_january
    grouped = event_map(events)
    replay_rows = []
    active = set(baseline)

    for year in range(2023, 2026):
        for month in range(1, 13):
            observed_symbols = observed.get((year, month))
            if observed_symbols is None:
                replay_rows.append(
                    MonthlyReplay(
                        year=year,
                        month=month,
                        observed_symbols=0,
                        replayed_symbols=0,
                        missing_from_replay=(),
                        extra_in_replay=(),
                        tolerated_same_month_delisting=(),
                        passed=False,
                    )
                )
                continue

            presence = set(active)
            month_events = grouped.get((year, month), [])

            for event in month_events:
                if event.event_type in {EVENT_LISTING, EVENT_RELISTING}:
                    presence.add(event.symbol)
                    active.add(event.symbol)
                elif event.event_type == EVENT_DELISTING:
                    presence.add(event.symbol)
                    active.discard(event.symbol)

            missing = tuple(sorted(observed_symbols - presence))
            raw_extra = presence - observed_symbols
            same_month_delistings = {
                event.symbol
                for event in month_events
                if event.event_type == EVENT_DELISTING
            }
            tolerated = tuple(sorted(raw_extra & same_month_delistings))
            extra = tuple(sorted(raw_extra - same_month_delistings))

            replay_rows.append(
                MonthlyReplay(
                    year=year,
                    month=month,
                    observed_symbols=len(observed_symbols),
                    replayed_symbols=len(presence),
                    missing_from_replay=missing,
                    extra_in_replay=extra,
                    tolerated_same_month_delisting=tolerated,
                    passed=not missing and not extra,
                )
            )

    return (len(baseline), tuple(replay_rows), baseline)


def build_intervals(
    baseline: set[str],
    events: list[LifecycleEvent],
) -> tuple[UniverseInterval, ...]:
    starts: dict[str, tuple[str, str]] = {
        symbol: (WINDOW_START.isoformat(), "WINDOW_BASELINE")
        for symbol in baseline
    }
    intervals = []

    ordered = sorted(
        events,
        key=lambda item: (item.effective_date, item.event_type, item.symbol),
    )

    for event in ordered:
        if event.event_type in {EVENT_LISTING, EVENT_RELISTING}:
            starts[event.symbol] = (
                event.effective_date,
                event.event_type,
            )
            continue

        if event.event_type != EVENT_DELISTING:
            continue

        started = starts.pop(event.symbol, None)
        if started is None:
            continue

        intervals.append(
            UniverseInterval(
                symbol=event.symbol,
                valid_from=started[0],
                valid_to=event.effective_date,
                start_reason=started[1],
                end_reason=EVENT_DELISTING,
                point_in_time_safe=False,
                availability_status="UNKNOWN",
            )
        )

    for symbol, (valid_from, reason) in sorted(starts.items()):
        intervals.append(
            UniverseInterval(
                symbol=symbol,
                valid_from=valid_from,
                valid_to=None,
                start_reason=reason,
                end_reason=None,
                point_in_time_safe=False,
                availability_status="UNKNOWN",
            )
        )

    return tuple(
        sorted(
            intervals,
            key=lambda item: (item.symbol, item.valid_from),
        )
    )


def write_snapshot(snapshot: BoundedLifecycleSnapshot, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(snapshot), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()

    ipo_path = Path(args.ipo_snapshot)
    lifecycle_path = Path(args.lifecycle_snapshot)
    membership_path = Path(args.membership_snapshot)
    output_path = Path(args.output)

    for path in (ipo_path, lifecycle_path, membership_path):
        if not path.exists():
            raise FileNotFoundError(path)

    ipo_payload = load_json(ipo_path)
    lifecycle_payload = load_json(lifecycle_path)
    membership_payload = load_json(membership_path)

    listing = load_ipo_events(ipo_payload)
    relisting = load_relisting_events(lifecycle_payload)
    delisting = delisting_events()
    events = listing + relisting + delisting

    observed = load_membership_months(membership_payload)
    candidates = load_candidate_symbols(membership_payload)
    adjudicated = {record.symbol for record in DELISTING_REGISTRY}

    missing_candidate_evidence = tuple(sorted(candidates - adjudicated))
    extra_adjudication_symbols = tuple(sorted(adjudicated - candidates))

    baseline_count, replay_rows, baseline = replay_monthly_presence(
        observed=observed,
        events=events,
    )

    passed = sum(row.passed for row in replay_rows)
    replay_total = len(replay_rows)
    replay_ready = replay_total == 36 and passed == replay_total

    intervals = build_intervals(
        baseline=baseline,
        events=events,
    )

    event_date_ready = not missing_candidate_evidence
    bounded_ready = event_date_ready and replay_ready

    snapshot = BoundedLifecycleSnapshot(
        generated_at=datetime.now(UTC).isoformat(),
        snapshot_version="idx_bounded_lifecycle_2023_2025_v1",
        window_start=WINDOW_START.isoformat(),
        window_end=WINDOW_END.isoformat(),
        baseline_symbols=baseline_count,
        listing_events=len(listing),
        relisting_events=len(relisting),
        delisting_events=len(delisting),
        candidate_symbols=tuple(sorted(candidates)),
        adjudicated_candidate_symbols=tuple(sorted(adjudicated & candidates)),
        missing_candidate_evidence=missing_candidate_evidence,
        extra_adjudication_symbols=extra_adjudication_symbols,
        monthly_replay=replay_rows,
        monthly_replay_passed=passed,
        monthly_replay_total=replay_total,
        intervals=intervals,
        event_date_ready=event_date_ready,
        monthly_presence_replay_ready=replay_ready,
        bounded_universe_ready=bounded_ready,
        strict_pit_ready=False,
        events=tuple(
            sorted(
                events,
                key=lambda item: (item.effective_date, item.symbol, item.event_type),
            )
        ),
        adjudicated_delistings=DELISTING_REGISTRY,
    )

    write_snapshot(snapshot, output_path)

    print("Indonesia Market Intelligence")
    print("IDX Bounded Lifecycle Reconstruction V1")
    print("--------------------------------")
    print("Window         : 2023-01-01 -> 2025-12-31")
    print("Database write : DISABLED")
    print()

    print("1. CANDIDATE ADJUDICATION")
    print(f"  Membership candidates : {len(candidates)}")
    print(f"  Candidate adjudicated : {len(adjudicated & candidates)}")
    print(
        "  Missing evidence      : "
        + (", ".join(missing_candidate_evidence) or "-")
    )
    print(
        "  Registry outside candidates: "
        + (", ".join(extra_adjudication_symbols) or "-")
    )
    print()

    print("2. LIFECYCLE EVENTS")
    print(f"  Baseline symbols : {baseline_count}")
    print(f"  IPO/listing      : {len(listing)}")
    print(f"  Relisting        : {len(relisting)}")
    print(f"  Delisting        : {len(delisting)}")
    print()

    print("3. MONTHLY PRESENCE REPLAY")
    for row in replay_rows:
        if row.passed:
            continue
        print(
            f"  {row.year}-{row.month:02d} FAIL "
            f"observed={row.observed_symbols} "
            f"replayed={row.replayed_symbols}"
        )
        print(
            "    Missing from replay: "
            + (", ".join(row.missing_from_replay) or "-")
        )
        print(
            "    Extra in replay    : "
            + (", ".join(row.extra_in_replay) or "-")
        )
        print(
            "    Tolerated same-month delisting: "
            + (", ".join(row.tolerated_same_month_delisting) or "-")
        )

    if passed == replay_total:
        print("  All 36 months PASS")
    print()

    print("4. OUTPUT")
    print(f"  Universe intervals : {len(intervals)}")
    print(f"  Snapshot           : {output_path}")
    print()

    print("SUMMARY")
    print(f"Candidate evidence gate : {'PASS' if event_date_ready else 'FAIL'}")
    print(f"Monthly replay           : {passed}/{replay_total}")
    print(f"Bounded universe gate    : {'PASS' if bounded_ready else 'FAIL'}")
    print("Strict PIT gate          : FAIL")
    print()

    print("IMPORTANT")
    print(
        "Delisting dates in this batch are adjudicated from corroborated "
        "public reports or announcement mirrors, not yet primary-source "
        "historical publication timestamps."
    )
    print(
        "Monthly Table of Stock Price is treated as bounded monthly presence "
        "evidence; same-month delistings may be present or absent in the report."
    )
    print(
        "Intervals are window-bounded for 2023-2025 and retain "
        "availability_status=UNKNOWN and point_in_time_safe=False."
    )
    print()
    print("DATABASE WRITE:")
    print("ENABLED : NO")


if __name__ == "__main__":
    main()
