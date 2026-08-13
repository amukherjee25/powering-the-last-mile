"""Process West Bengal RTO (Regional Transport Organization) vehicle registration data:
convert raw points to geometry, summarize registrations by district, and disaggregate
district-level fleet counts to blocks based on population share."""

import geopandas as gpd
import numpy as np
import pandas as pd
from geopandas import GeoDataFrame
from shapely.geometry import Point

from ev_infra.config import DATA_PROCESSED, RTO_3W_XLSX
from ev_infra.preprocess.population import WB_BLOCKS_POP_GEOJSON, WB_DISTRICTS_POP_GEOJSON

# Define the directory for storing the processed data
WB_RTO_3W_GEOJSON = DATA_PROCESSED / "west-bengal-rto-threewheeler.geojson"
WB_BLOCKS_3W_GEOJSON = DATA_PROCESSED / "west-bengal-blocks-3w.geojson"

# Define the three-wheeler fleet types
VEHICLE_COLS = ["e-rickshaw", "E3W_passenger", "E3W_goods", "ICE3W_passenger"]


def geometry_process(filepath):
    """Read an RTO Excel file and convert its Lat/Long columns into Point geometry."""
    data = pd.read_excel(filepath)

    points = data.apply(lambda row: Point(row.Long, row.Lat), axis=1)

    gdf = gpd.GeoDataFrame(data, geometry=points)
    gdf.crs = "epsg:4326"

    return gdf


def process_rto_registrations(threewheeler_path=RTO_3W_XLSX):
    """Convert both RTO three-wheeler registration files to GeoDataFrames and write them out as GeoJSON.
    """
    wb_rto_3w = geometry_process(threewheeler_path)
    wb_rto_3w.to_file(WB_RTO_3W_GEOJSON, driver="GeoJSON")

    return wb_rto_3w


def summarize_district_registrations(wb_rto_3w: gpd.GeoDataFrame) -> pd.DataFrame:
    """Sum RTO-level registrations up to district-level totals for each vehicle type."""

    wb_district_3w = wb_rto_3w.groupby("District")[VEHICLE_COLS].sum().reset_index()
    wb_district_3w = wb_district_3w.rename(columns={"District": "district"})

    return wb_district_3w


def apportion_all_vehicles(df_blocks, df_district_totals, group_col, share_col, vehicle_cols):
    """Allocate district-level vehicle totals to blocks using proportional shares, while
    preserving integer totals that exactly match district totals (largest-remainder method).

    Parameters
    ----------
    df_blocks : pd.DataFrame
        Block-level dataframe containing group_col and share_col.
    df_district_totals : pd.DataFrame
        District-level dataframe containing group_col and each column in vehicle_cols.
    group_col : str
        Column used for grouping (e.g. 'district').
    share_col : str
        Share column used for allocation (e.g. 'pop_share').
    vehicle_cols : list[str]
        Vehicle columns to allocate (e.g. ['e-rickshaw', 'E3W_passenger']).

    Returns
    -------
    pd.DataFrame
        Block-level dataframe with integer vehicle allocations for each vehicle_cols entry.
    """
    df_blocks = df_blocks.copy()
    df_district_totals = df_district_totals.copy()

    # Ensure grouping column is a column (not index)
    if group_col in df_blocks.index.names:
        df_blocks = df_blocks.reset_index()
    if group_col in df_district_totals.index.names:
        df_district_totals = df_district_totals.reset_index()

    # Remove duplicate columns, if any
    df_blocks = df_blocks.loc[:, ~df_blocks.columns.duplicated()]
    df_district_totals = df_district_totals.loc[:, ~df_district_totals.columns.duplicated()]

    # Merge all vehicle columns and prepare output dataframe
    out = df_blocks.merge(df_district_totals[[group_col] + vehicle_cols], on=group_col, how="left")

    # Allocate each vehicle column independently (vectorized)
    for vcol in vehicle_cols:
        alloc_col = f"{vcol}_block"

        # Step 1: raw allocation
        out[f"{vcol}_raw"] = out[vcol] * out[share_col]
        # Step 2: floor allocation
        out[alloc_col] = np.floor(out[f"{vcol}_raw"]).astype(int)
        # Step 3: remainder
        out[f"{vcol}_rem"] = out[f"{vcol}_raw"] - out[alloc_col]
        # Step 4: compute remaining per district
        district_total = out.groupby(group_col)[vcol].transform("first")
        allocated_total = out.groupby(group_col)[alloc_col].transform("sum")
        remaining = (district_total - allocated_total).astype(int)
        out["_remaining"] = out[group_col].map(remaining.groupby(out[group_col]).first())
        # Step 5: rank within district by remainder
        out["_rank"] = out.groupby(group_col)[f"{vcol}_rem"].rank(method="first", ascending=False)
        # Step 6: assign remaining units
        out.loc[out["_rank"] <= out["_remaining"], alloc_col] += 1
        # Cleanup intermediate columns for this vehicle
        out.drop(columns=[f"{vcol}_raw", f"{vcol}_rem"], inplace=True)

    # Final cleanup of output dataframe
    out.drop(columns=["_remaining", "_rank"], inplace=True, errors="ignore")

    # Rename outputs back to original names
    for vcol in vehicle_cols:
        alloc_col = f"{vcol}_block"
        # Remove original column if exists to avoid duplicates
        if vcol in out.columns:
            out.drop(columns=[vcol], inplace=True)
        out.rename(columns={alloc_col: vcol}, inplace=True)

    return out


def disaggregate_vehicles_to_blocks(
    wb_district_3w,
    block_pop_path=WB_BLOCKS_POP_GEOJSON,
    district_pop_path=WB_DISTRICTS_POP_GEOJSON):

    """Disaggregate district-level vehicle registrations to blocks by population share."""

    # Read in block and district population files 
    wb_block_pop = gpd.read_file(block_pop_path).drop(columns=["pop_den"])
    wb_district_pop = gpd.read_file(district_pop_path)

    # Extract the relevant columns from the district population dataframe
    wb_district_cols = wb_district_pop[["district", "total_pop"]].rename(
        columns={"total_pop": "total_pop_district"}
    )

    # Merge the district population into the block dataframe based on district name
    wb_block_3w = wb_block_pop.merge(wb_district_cols, on="district", how="left")

    # Calculate the population share within each block (ensure that population share sums to 1 across all blocks for each district)
    district_block_pop = wb_block_3w.groupby("district", as_index=False)["total_pop"].sum()
    district_block_pop = district_block_pop.rename(columns={"total_pop": "total_district_pop_across_blocks"})

    # Merge this back into the block-level dataframe
    wb_block_3w = wb_block_3w.merge(district_block_pop, on="district", how="left")

    # Calculate the population share per block
    wb_block_3w["pop_share"] = wb_block_3w["total_pop"] / wb_block_3w["total_district_pop_across_blocks"]

    return apportion_all_vehicles(
        df_blocks=wb_block_3w,
        df_district_totals=wb_district_3w,
        group_col="district",
        share_col="pop_share",
        vehicle_cols=VEHICLE_COLS,
    )


def add_conversion_scenarios(wb_block_3w):
    """Add fleet-conversion-scenario columns: number of autorickshaws to serve under
    10%, 30%, and 100% ICE-to-electric conversion."""

    wb_block_3w = wb_block_3w.copy()

    # Add fleet population for each conversion scenario
    wb_block_3w["10%_conversion"] = np.ceil(wb_block_3w["E3W_passenger"] + 0.1 * wb_block_3w["ICE3W_passenger"]).astype(int)
    wb_block_3w["30%_conversion"] = np.ceil(wb_block_3w["E3W_passenger"] + 0.3 * wb_block_3w["ICE3W_passenger"]).astype(int)
    wb_block_3w["100%_conversion"] = wb_block_3w["E3W_passenger"] + 1.0 * wb_block_3w["ICE3W_passenger"]

    return wb_block_3w


def process_block_fleet(
    rto_threewheeler_path=WB_RTO_3W_GEOJSON,
    block_pop_path=WB_BLOCKS_POP_GEOJSON,
    district_pop_path=WB_DISTRICTS_POP_GEOJSON):
    """Run the full block-level fleet pipeline: summarize district registrations,
    disaggregate to blocks by population share, add conversion scenarios, write out."""
    wb_rto_3w = gpd.read_file(rto_threewheeler_path)

    wb_district_3w = summarize_district_registrations(wb_rto_3w)
    wb_block_3w = disaggregate_vehicles_to_blocks(wb_district_3w, block_pop_path, district_pop_path)
    wb_block_3w = add_conversion_scenarios(wb_block_3w)

    wb_block_3w = GeoDataFrame(wb_block_3w, geometry="geometry")
    wb_block_3w.to_file(WB_BLOCKS_3W_GEOJSON, driver="GeoJSON")

    return wb_block_3w