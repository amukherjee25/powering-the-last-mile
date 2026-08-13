"""Read raw India administrative boundaries (HDX) and derive processed West Bengal
state, district, sub-district, and block boundary files."""

import geopandas as gpd

from ev_infra.config import DATA_PROCESSED, DATA_RAW, BLOCKS_DISTRICTS_CSV
from ev_infra.utils import map_block_to_district

import pandas as pd

# Define the directory for the administrative boundaries
ADM_DIR = DATA_RAW / "adm"

# Define the directory for storing the processed files
WEST_BENGAL_GEOJSON = DATA_PROCESSED / "west-bengal.geojson"
WB_DISTRICTS_GEOJSON = DATA_PROCESSED / "west-bengal-districts.geojson"
WB_SUBDISTRICTS_GEOJSON = DATA_PROCESSED / "west-bengal-subdistricts.geojson"
WB_BLOCKS_GEOJSON = DATA_PROCESSED / "west-bengal-blocks.geojson"
WB_BLOCKS_DISTRICTS_GEOJSON = DATA_PROCESSED / "west-bengal-blocks-districts.geojson"

# District name -> two-letter code, used to label districts on maps.
DISTRICT_CODES = {
    "Alipurduar": "AD",
    "Bankura": "BN",
    "Paschim Barddhaman": "BR",
    "Barddhaman": "BR",
    "Birbhum": "BI",
    "Koch Bihar": "KB",
    "Dakshin Dinajpur": "DD",
    "Darjiling": "DA",
    "Hugli": "HG",
    "Haora": "HR",
    "Jalpaiguri": "JP",
    "Jhargram": "JH",
    "Kolkata": "KO",
    "Kalimpong": "KA",
    "Maldah": "MA",
    "Paschim Medinipur": "ME",
    "Purba Medinipur": "ME",
    "Murshidabad": "MU",
    "Nadia": "NA",
    "North Twenty Four Parganas": "PN",
    "South Twenty Four Parganas": "PS",
    "Puruliya": "PU",
    "Uttar Dinajpur": "UD",
}

def read_geojson_file(filepath):
    """Read a boundary GeoJSON, set its CRS to EPSG:4326, and drop HDX-specific ID columns."""
    gdf = gpd.read_file(filepath)
    gdf.crs = "epsg:4326"

    drop_cols = ["shapeISO", "shapeID", "shapeGroup"]
    if gdf.columns.isin(drop_cols).any():
        gdf = gdf.drop(columns=drop_cols, errors="ignore")

    return gdf


def load_india_admin_boundaries(adm_dir=ADM_DIR):
    """Read India ADM1-4 boundaries and rename each level's name column to its West Bengal label."""
    ind_adm1 = read_geojson_file(f"{adm_dir}/IND-ADM1.geojson").rename(columns={"shapeName": "state"})
    ind_adm2 = read_geojson_file(f"{adm_dir}/IND-ADM2.geojson").rename(columns={"shapeName": "district"})
    ind_adm3 = read_geojson_file(f"{adm_dir}/IND-ADM3.geojson").rename(columns={"shapeName": "sub_district"})
    ind_adm4 = read_geojson_file(f"{adm_dir}/IND-ADM4.geojson").rename(columns={"shapeName": "block"})

    return {
        "state": ind_adm1, 
        "district": ind_adm2, 
        "sub_district": ind_adm3, 
        "block": ind_adm4
    }


def _fix_duplicate_sankrail_blocks(wb_blocks: gpd.GeoDataFrame):
    """Disambiguate the two same-named 'Sankrail' blocks (Jhargram vs. Haora districts).

    NOTE: row indices are positional and specific to the IND-ADM4.geojson row order as
    inspected during preprocessing. If the upstream HDX file is re-downloaded or changes,
    re-verify these indices (e.g. by re-plotting the two Sankrail geometries) before trusting them.
    """
    wb_blocks = wb_blocks.copy()
    wb_blocks.at[5689, "block"] = "Sankrail-J"  # Sankrail in Jhargram
    wb_blocks.at[5825, "block"] = "Sankrail-H"  # Sankrail in Haora
    return wb_blocks


def extract_west_bengal_boundaries(admin_boundaries: dict) -> dict:
    """Clip India ADM2-4 boundaries to West Bengal and label districts with their code."""
    ind_adm1 = admin_boundaries["state"]
    ind_adm2 = admin_boundaries["district"]
    ind_adm3 = admin_boundaries["sub_district"]
    ind_adm4 = admin_boundaries["block"]

    west_bengal = ind_adm1[ind_adm1["state"] == "West Bengal"].to_crs(ind_adm2.crs)

    wb_districts = gpd.clip(ind_adm2, mask=west_bengal)
    wb_districts["code"] = wb_districts["district"].map(DISTRICT_CODES)

    wb_subdistricts = gpd.clip(ind_adm3, mask=west_bengal)

    wb_blocks = gpd.clip(ind_adm4, mask=west_bengal)
    wb_blocks = _fix_duplicate_sankrail_blocks(wb_blocks)

    return {
        "west_bengal": west_bengal,
        "districts": wb_districts,
        "sub_districts": wb_subdistricts,
        "blocks": wb_blocks,
    }


def filter_known_districts(wb_districts: gpd.GeoDataFrame, csv_path=BLOCKS_DISTRICTS_CSV) -> gpd.GeoDataFrame:
    """Keep only districts that appear in the canonical blocks-districts CSV."""
    known_districts = pd.read_csv(csv_path)["district"]
    return wb_districts[wb_districts["district"].isin(known_districts)].reset_index(drop=True)


def assign_block_districts(wb_blocks: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Map each block to its district and drop blocks that don't match a known district."""
    wb_blocks_districts = wb_blocks.copy()
    wb_blocks_districts["district"] = wb_blocks_districts["block"].apply(map_block_to_district)
    return (
        wb_blocks_districts
        .dropna(subset=["district"])
        .drop(columns=["shapeType"], errors="ignore")
        .reset_index(drop=True)
    )


def write_boundaries(west_bengal, wb_districts, wb_subdistricts, wb_blocks, wb_blocks_districts):
    """Write processed West Bengal boundary GeoDataFrames to GeoJSON."""
    west_bengal.to_file(WEST_BENGAL_GEOJSON, driver="GeoJSON")
    wb_districts.to_file(WB_DISTRICTS_GEOJSON, driver="GeoJSON")
    wb_subdistricts.to_file(WB_SUBDISTRICTS_GEOJSON, driver="GeoJSON")
    wb_blocks.to_file(WB_BLOCKS_GEOJSON, driver="GeoJSON")
    wb_blocks_districts.to_file(WB_BLOCKS_DISTRICTS_GEOJSON, driver="GeoJSON")
