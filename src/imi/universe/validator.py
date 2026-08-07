import re
from dataclasses import dataclass
from datetime import date

from imi.universe.models import (
    InstrumentProfile,
)

SYMBOL_PATTERN = re.compile(
    r"^[A-Z0-9]{1,12}$"
)


@dataclass(frozen=True, slots=True)
class InstrumentValidation:
    profile: InstrumentProfile
    valid: bool
    reasons: tuple[str, ...]


def validate_instrument_profile(
    profile: InstrumentProfile,
    *,
    snapshot_date: date,
) -> InstrumentValidation:
    reasons = []

    if not SYMBOL_PATTERN.fullmatch(
        profile.symbol
    ):
        reasons.append(
            "Invalid symbol format."
        )

    if not profile.name.strip():
        reasons.append(
            "Company name is empty."
        )

    if (
        profile.listed_date
        is not None
        and profile.listed_date
        > snapshot_date
    ):
        reasons.append(
            "Listing date is after "
            "snapshot date."
        )

    return InstrumentValidation(
        profile=profile,
        valid=not reasons,
        reasons=tuple(reasons),
    )