"""Shared paths and constants for the ev_infra pipeline."""

from pathlib import Path

# Anchored to the installed package location, not the notebook's cwd —
# so paths resolve correctly regardless of which directory a notebook runs from.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW = DATA_DIR / "raw"
DATA_PROCESSED = DATA_DIR / "processed"
DATA_OUTPUT = DATA_DIR / "output"

# Raw data file paths
BLOCKS_DISTRICTS_CSV = DATA_RAW / "wb-districts-blocks.csv"
RTO_3W_XLSX = DATA_RAW / "wb-rto-3w.xlsx"
RAW_POPULATION_TIF = DATA_RAW / "ind_ppp_2020.tif"
RAW_RWI_CSV = DATA_RAW / "ind_pak_relative_wealth_index.csv"
DATA_RAW_DISTRICT_SOLAR = DATA_RAW / "district_solar"
RAW_DISCOUNT_RATE_CSV = DATA_RAW / "INTDSRINM193N.csv"

# Economic constants
USD_TO_INR = 85.57
PV_CAPEX_PER_KW = 1040           # $1,040/kW
PV_OPEX_PER_KW = 3.80            # $3.80/kW/year
WBEVP_SUBSIDY_PCT = 0.35         # WBEVP capital subsidy: 35% of PV system CAPEX
