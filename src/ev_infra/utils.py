"""Shared helpers used across the spatial, charging, economics, and siting pipeline stages."""

from functools import lru_cache
from pathlib import Path

import pandas as pd

from ev_infra.config import BLOCKS_DISTRICTS_CSV


@lru_cache(maxsize=None)
def _block_district_map(csv_path: Path = BLOCKS_DISTRICTS_CSV) -> dict:
    """Build a {district: [blocks]} lookup from the blocks-districts CSV. Cached per csv_path."""
    blocks_in_districts = pd.read_csv(csv_path)
    return blocks_in_districts.groupby("district")["block"].apply(list).to_dict()


def map_block_to_district(block_name: str, csv_path: Path = BLOCKS_DISTRICTS_CSV) -> str | None:
    """Return the district containing block_name, or None if not found."""
    blocks_in_districts_dict = _block_district_map(csv_path)
    for district, blocks in blocks_in_districts_dict.items():
        if block_name in blocks:
            return district
    return None
