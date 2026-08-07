import argparse
import time
from collections import Counter
from datetime import date, timedelta

import httpx

from imi.collectors.yahoo_equity_history import (
    fetch_yahoo_equity_history,
)
from imi.db import engine
from imi.repositories.equity_eod import (
    get_latest_idx_session,
    get_source_id,
    load_work_queue,
    mark_complete,
    mark_failed,
    mark_progress,
    mark_running,
    rebuild_previous_close,
    seed_ingestion_states,
    upsert_equity_bars,
)
from imi.validators.equity_eod import (
    validate_equity_daily_bar,
)

DEFAULT_CHUNK_DAYS = 3000
DEFAULT_DELAY_SECONDS = 0.35


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help=(
            "Comma-separated IDX symbols. "
            "Example: BBCA,TLKM,ASII"
        ),
    )

    parser.add_argument(
        "--max-symbols",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--chunk-days",
        type=int,
        default=DEFAULT_CHUNK_DAYS,
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
    )

    return parser.parse_args()


def chunk_end(
    start_date: date,
    target_end_date: date,
    *,
    chunk_days: int,
) -> date:
    if chunk_days <= 0:
        raise ValueError(
            "chunk_days must be greater than zero."
        )

    candidate = (
        start_date
        + timedelta(
            days=chunk_days - 1
        )
    )

    return min(
        candidate,
        target_end_date,
    )


def main() -> None:
    args = parse_args()

    requested_symbols: set[str] | None = None

    if args.symbols:
        requested_symbols = {
            value.strip().upper()
            for value
            in args.symbols.split(",")
            if value.strip()
        }

    with engine.begin() as connection:
        source_id = get_source_id(
            connection,
            code="YAHOO_FINANCE",
        )

        target_end_date = (
            get_latest_idx_session(
                connection
            )
        )

        seeded = seed_ingestion_states(
            connection,
            source_id=source_id,
            target_end_date=(
                target_end_date
            ),
        )

    print(
        "Indonesia Market Intelligence"
    )
    print(
        "IDX Equity Historical EOD"
    )
    print(
        "--------------------------"
    )
    print(
        f"Target end date : "
        f"{target_end_date}"
    )
    print(
        f"States seeded   : "
        f"{seeded}"
    )

    with engine.connect() as connection:
        queue = load_work_queue(
            connection,
            source_id=source_id,
        )

    if requested_symbols is not None:
        queue = [
            row
            for row in queue
            if row.symbol
            in requested_symbols
        ]

    if args.max_symbols is not None:
        queue = queue[
            : args.max_symbols
        ]

    print(
        f"Work queue      : "
        f"{len(queue)}"
    )
    print()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36"
        ),
    }

    with httpx.Client(
        headers=headers,
        timeout=30.0,
        follow_redirects=True,
    ) as client:
        for position, item in enumerate(
            queue,
            start=1,
        ):
            print(
                f"[{position}/{len(queue)}] "
                f"{item.symbol}"
            )

            current_start = (
                item.next_start_date
                or item.start_date
            )

            last_success_date = None

            total_valid_rows = int(
                item.rows_loaded or 0
            )

            try:
                with engine.begin() as connection:
                    mark_running(
                        connection,
                        instrument_id=(
                            item.instrument_id
                        ),
                        source_id=source_id,
                    )

                while (
                    current_start
                    <= item.target_end_date
                ):
                    current_end = chunk_end(
                        current_start,
                        item.target_end_date,
                        chunk_days=(
                            args.chunk_days
                        ),
                    )

                    print(
                        "  "
                        f"{current_start} "
                        "-> "
                        f"{current_end}"
                    )

                    result = (
                        fetch_yahoo_equity_history(
                            idx_symbol=(
                                item.symbol
                            ),
                            start_date=(
                                current_start
                            ),
                            end_date=(
                                current_end
                            ),
                            client=client,
                        )
                    )

                    valid_bars = []
                    rejected_count = 0

                    rejection_reasons: Counter[
                        str
                    ] = Counter()

                    seen_dates: set[date] = set()

                    for bar in result.bars:
                        if (
                            bar.trading_date
                            in seen_dates
                        ):
                            rejected_count += 1

                            rejection_reasons[
                                "DUPLICATE_DATE"
                            ] += 1

                            continue

                        seen_dates.add(
                            bar.trading_date
                        )

                        validation = (
                            validate_equity_daily_bar(
                                bar,
                                listed_date=(
                                    item.listed_date
                                ),
                                target_end_date=(
                                    item.target_end_date
                                ),
                            )
                        )

                        if not validation.valid:
                            rejected_count += 1

                            rejection_reasons.update(
                                validation.reasons
                            )

                            continue

                        valid_bars.append(
                            bar
                        )

                    if valid_bars:
                        last_success_date = max(
                            bar.trading_date
                            for bar
                            in valid_bars
                        )

                    next_start = (
                        current_end
                        + timedelta(days=1)
                    )

                    if (
                        next_start
                        <= current_start
                    ):
                        raise RuntimeError(
                            "Historical ingestion "
                            "made no date progress "
                            f"for {item.symbol}: "
                            f"{current_start} -> "
                            f"{current_end}"
                        )

                    with engine.begin() as connection:
                        loaded = (
                            upsert_equity_bars(
                                connection,
                                instrument_id=(
                                    item.instrument_id
                                ),
                                source_id=source_id,
                                yahoo_symbol=(
                                    result.yahoo_symbol
                                ),
                                bars=valid_bars,
                            )
                        )

                        mark_progress(
                            connection,
                            instrument_id=(
                                item.instrument_id
                            ),
                            source_id=source_id,
                            next_start_date=(
                                next_start
                            ),
                            last_attempted_date=(
                                current_end
                            ),
                            last_success_date=(
                                last_success_date
                            ),
                            rows_loaded=loaded,
                        )

                    total_valid_rows += loaded

                    print(
                        "    raw="
                        f"{result.raw_count} "
                        "parsed="
                        f"{result.parsed_count} "
                        "valid="
                        f"{len(valid_bars)} "
                        "rejected="
                        f"{rejected_count} "
                        "incomplete="
                        f"{result.incomplete_count}"
                    )

                    if rejection_reasons:
                        reason_text = ", ".join(
                            (
                                f"{reason}="
                                f"{count}"
                            )
                            for reason, count
                            in sorted(
                                rejection_reasons.items()
                            )
                        )

                        print(
                            "    rejection reasons: "
                            f"{reason_text}"
                        )

                    # CRITICAL:
                    # Date progress must happen
                    # on every completed chunk,
                    # including raw=0 chunks.
                    current_start = next_start

                    time.sleep(
                        args.delay
                    )

                if total_valid_rows <= 0:
                    raise RuntimeError(
                        "No valid historical EOD "
                        "bars were found for "
                        f"{item.symbol}. "
                        "Instrument will not be "
                        "marked COMPLETE."
                    )

                with engine.begin() as connection:
                    rebuild_previous_close(
                        connection,
                        instrument_id=(
                            item.instrument_id
                        ),
                        source_id=source_id,
                    )

                    mark_complete(
                        connection,
                        instrument_id=(
                            item.instrument_id
                        ),
                        source_id=source_id,
                        last_attempted_date=(
                            item.target_end_date
                        ),
                        last_success_date=(
                            last_success_date
                        ),
                    )

                print(
                    "  COMPLETE"
                )

            except (
                httpx.HTTPError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as exc:
                with engine.begin() as connection:
                    mark_failed(
                        connection,
                        instrument_id=(
                            item.instrument_id
                        ),
                        source_id=source_id,
                        error=str(exc),
                    )

                print(
                    "  FAILED: "
                    f"{exc}"
                )

            print()

    print(
        "Historical ingestion run "
        "finished."
    )


if __name__ == "__main__":
    main()