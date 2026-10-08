from dataclasses import dataclass


@dataclass(frozen=True)
class CrossSuffixLetter:
    """Row from cross_suffix_letters; code is VARCHAR(2) primary key."""

    code: str
