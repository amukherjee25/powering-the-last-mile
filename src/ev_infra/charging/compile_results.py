"""Aggregate block-level PV sizing results from the compute cluster (run_pv_sizing_block.py)
into consolidated GeoJSON files, one per fleet conversion scenario."""

import os

import pandas as pd
import geopandas as gpd

from ev_infra.config import DATA_OUTPUT, DATA_PROCESSED

FLEET_CONVERSION_SCENARIOS = ['10%', '30%', '100%']

BLOCK_PV_VEHICLES_GEOJSON = {
    '10%': DATA_PROCESSED / "west-bengal-block-pv-10pct.geojson",
    '30%': DATA_PROCESSED / "west-bengal-block-pv-30pct.geojson",
    '100%': DATA_PROCESSED / "west-bengal-block-pv-100pct.geojson",
}

def compile_block_pv_results(block_fleet, output_dir=DATA_OUTPUT):
    # Read in the csv files and create a compiled dataframe
    pv_size_files = [f for f in os.listdir(output_dir) if f.endswith('.csv')]

    # Create a list to store the dataframes
    district_pv_sizes = []

    # Loop through each file and read into a dataframe
    for file in pv_size_files:
        # Read the CSV file into dataframe
        file_path = output_dir / file
        pv_df = pd.read_csv(file_path)

        # Append the dataframe to a list
        district_pv_sizes.append(pv_df)

    # Create a new dataframe from the concatenated list
    district_pv_df = pd.concat(district_pv_sizes, ignore_index=True)

    # Merge the compiled block level PV sizes with the block geometry
    merged_df = pd.merge(district_pv_df, block_fleet[['block', 'district', 'geometry']],
                         on=['block', 'district'], how='left')

    # Convert the dataframe into GeoDataFrame
    block_pv = gpd.GeoDataFrame(merged_df, geometry='geometry', crs=block_fleet.crs)

    return block_pv


def write_block_pv_by_scenario(block_pv, output_dir=DATA_PROCESSED):
    # Save the PV sizes for each block based on each fleet conversion scenario
    block_pv_by_scenario = {}

    for scenario in FLEET_CONVERSION_SCENARIOS:
        prefix = f'{scenario}_conversion'
        scenario_df = block_pv[['block', 'district', 'geometry'] + [col for col in block_pv.columns if col.startswith(prefix)]]

        scenario_df.to_file(BLOCK_PV_VEHICLES_GEOJSON, driver='GeoJSON')

        block_pv_by_scenario[scenario] = scenario_df

    return block_pv_by_scenario


def prepare_pv_size_for_plotting(block_pv_by_scenario, wb_districts):
    """Strip the scenario prefix from column names, tag each row with its scenario,
    add district codes, and drop Kolkata, for boxplot comparison across scenarios."""
    pv_sizes_filter = {}

    for scenario, df in block_pv_by_scenario.items():
        # Define the prefix to eliminate in column headers for all dataframes
        prefix = f"{scenario}_conversion_"

        # Remove the prefix from column headers in dataframe
        df_clean = df.copy()      # Create a copy of the original dataframe
        df_clean = df_clean.rename(
            columns=lambda col_name: col_name.replace(prefix, "") if prefix in col_name else col_name)

        # Add a column for the scenario column in the dataframe
        df_clean['scenario'] = f"{scenario} conversion"

        # Add district codes for all block
        df_clean = df_clean.merge(
            wb_districts[['district', 'code']],
            on='district',
            how='left')

        # Drop Kolkata from the dataframe
        df_clean = df_clean[df_clean['district'] != 'Kolkata']

        # Add cleaned dataframe to new dictionary
        pv_sizes_filter[scenario] = df_clean

    return pv_sizes_filter
