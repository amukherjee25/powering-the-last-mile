"""Siting solar-based charging infrastructure based on policy investment thresholds
for each three-wheeler fleet conversion scenario.
"""

import numpy as np
import pandas as pd
import geopandas as gpd

from ev_infra.config import WBEVP_SUBSIDY_PCT
from ev_infra.preprocess.boundaries import WB_BLOCKS_GEOJSON, WB_DISTRICTS_GEOJSON, WEST_BENGAL_GEOJSON
from ev_infra.preprocess.population import WB_BLOCKS_POP_GEOJSON
from ev_infra.preprocess.rwi import WB_BLOCKS_RWI_GEOJSON
from ev_infra.preprocess.fleet import WB_BLOCKS_3W_GEOJSON
from ev_infra.charging.compile_results import BLOCK_PV_VEHICLES_GEOJSON
from ev_infra.economics.pv_capex import BLOCK_PV_COST_CSV
from ev_infra.economics.calc_metrics import BLOCK_LCOE_GEOJSON
from ev_infra.viz.bivariate import bivariate_classification
from ev_infra.viz.sites_selected import plot_site_selection


def build_demand_composite(metric_df, metric_col, fleet_df, fleet_col, reverse_metric=False):
    """Log-normalize a metric column (population, RWI, or LCOE) and a fleet-demand column,
    then classify them into a bivariate composite score using bivariate_classification."""
    metric_norm = metric_df.copy()
    metric_norm[f'{metric_col}_norm'] = np.log1p(metric_norm[metric_col])

    fleet_norm = fleet_df.copy()
    fleet_norm[f'{fleet_col}_norm'] = np.log1p(fleet_norm[fleet_col])

    return bivariate_classification(
        metric_norm, fleet_norm,
        col1_name=f'{metric_col}_norm',
        col2_name=f'{fleet_col}_norm',
        merge_col='block',
        num_score_reverse=reverse_metric,
    )


def load_population_demand_composite(fleet_df, fleet_scenario='30%'):
    wb_block_pop = gpd.read_file(WB_BLOCKS_POP_GEOJSON)
    return build_demand_composite(
        wb_block_pop, 'total_pop', fleet_df, f'{fleet_scenario}_conversion', reverse_metric=False
    )


def load_rwi_demand_composite(fleet_df, fleet_scenario='30%'):
    wb_block_rwi = gpd.read_file(WB_BLOCKS_RWI_GEOJSON)
    return build_demand_composite(
        wb_block_rwi, 'avg_rwi', fleet_df, f'{fleet_scenario}_conversion', reverse_metric=True
    )


def load_lcoe_demand_composite(fleet_df, fleet_scenario='30%'):
    block_lcoe = gpd.read_file(BLOCK_LCOE_GEOJSON[fleet_scenario])
    return build_demand_composite(
        block_lcoe, 'lcoe', fleet_df, f'{fleet_scenario}_conversion', reverse_metric=True
    )


def load_block_pv_cost(scenario='30%'):
    # Read in relevant PV charging system size and costs for each fleet conversion scenario
    cost_df = pd.read_csv(BLOCK_PV_COST_CSV[scenario])

    # Add a column to calculate the capital cost subsidy for each block per WBEVP
    cost_df['capex_inr_sub'] = cost_df['pv_capex_inr_lakh'] * WBEVP_SUBSIDY_PCT

    return cost_df


def load_block_pv_vehicles(scenario='30%'):
    # Read in the relevant PV charging system size and vehicles served for each fleet conversion scenario
    return gpd.read_file(BLOCK_PV_VEHICLES_GEOJSON[scenario])


# Define a function to merge PV size, cost, and vehicles served for each block
def merge_pv_dfs(vehicles_df, cost_df, scenario):
    # Define the string for column names for dataframes
    scenario_string = f'{scenario}_conversion'

    # Define column names
    daily_vehicles_col = f"{scenario_string}_avg_vehicles_served_daily"
    yearly_vehicles_col = f"{scenario_string}_tot_vehicles_served_yearly"
    
    # Select only necessary columns from the dataframe containing vehicles served information
    selected_cols = ['block', 'district', daily_vehicles_col, yearly_vehicles_col]
    vehicles_subset = vehicles_df[selected_cols]

    # Drop redundant columns in cost_df
    cost_df_filter = cost_df.drop(columns=[daily_vehicles_col, yearly_vehicles_col], errors='ignore')

    # Merge vehicle data and cost dataframes
    merged_df = cost_df_filter.merge(vehicles_subset, on=['block', 'district'], how='left')
    
    return merged_df

# Define a function to determine priority blocks for siting PV-based charging infrastructure
def charging_station_siting(df_metric, df_pv_cost, subsidy_cap=4000, col_name='comp_num', scenario = '10%_conversion', metric_ascending=False):

    """
    Determine priority blocks for PV-based charging infrastructure siting
    Sort first by composite score ranking (9 scores highest, 1 scores lowest)
    For blocks with the same score, further sort by least cost PV system capital costs
    """

    # --- Merge the df_metric column and df_pv_cost dataframes ---
    # Select the columns to keep from df_pv_cost
    pv_columns = ['block',
                  f'{scenario}_pv_size', 
                  'pv_capex_usd', 
                  'pv_capex_inr_lakh',
                  'capex_inr_sub',
                  f'{scenario}_avg_vehicles_served_daily',
                  f'{scenario}_tot_vehicles_served_yearly']
    
    # Obtain the filtered new dataframe containing pv sizes and costs
    df_pv_cost_new = df_pv_cost[pv_columns]

    # Merge the dataframes
    df_combined = df_metric.merge(df_pv_cost_new, on='block', how='left')

    # --- Sort the combined dataframe first by selected column and then PV system capital costs ---
    df_sorted = df_combined.sort_values(
        by=[col_name, 'pv_capex_usd'],
        ascending=[metric_ascending, True]      # first based on user definition, then by lowest cost
    ).reset_index(drop=True)

    # --- Initialize the selection logic ---
    # Define the initial cumulative cost for deploying charging infrastructure
    cumulative_cost = 0  

    # Create an empty list to store the blocks which will get selected for siting
    blocks_selected =[]

    # Check which blocks can be selected based on investment cap
    for _, row in df_sorted.iterrows():
        # Identify the block
        block = row['block']

        # Look up the PV cost for corresponding block
        block_pv = df_pv_cost[df_pv_cost['block'] == block]
        if block_pv.empty:
            print(f"No PV cost found for {block}")
            continue
        
        # Identify the subsizied cost of the PV system for that block
        block_cost = block_pv['capex_inr_sub'].values[0]

        # Determine if investment subsidy cap can financially support building required PV size
        if cumulative_cost + block_cost <= subsidy_cap:
            # Add this cost to the cumulative cost
            cumulative_cost += block_cost
            # Append the block name to the list
            blocks_selected.append(block)
        else:
            break

    # --- Obtain the filtered dataframe with the selected blocks ---
    # Subset selected block geometries and their corresponding PV cost data
    df_blocks_selected = df_sorted[df_sorted['block'].isin(blocks_selected)].reset_index(drop=True)

    # --- Print summary metrics ---
    # Calculate the number of blocks selected for the scenario
    num_blocks_selected = len(df_blocks_selected)
    print(f'Number of blocks selected: {num_blocks_selected}')

    # Calculate the aggregate PV system size, CAPEX, subsidy amount for the selected blocks
    pv_size_col = f'{scenario}_pv_size'
    cumulative_pv = df_blocks_selected[pv_size_col].sum()
    print(f'Cumulative PV size for selected blocks: {cumulative_pv} kW')

    cumulative_capex = df_blocks_selected['pv_capex_inr_lakh'].sum()
    print(f'Cumulative PV CAPEX cost for selected blocks: {cumulative_capex:.2f} INR Lakh')

    cumulative_subsidy = df_blocks_selected['capex_inr_sub'].sum()
    print(f'Total WBEVP Subsidy used: {cumulative_subsidy:.2f} INR Lakh')

    # Print the number of vehicles served based on the blocks selected
    tot_avg_daily_vehicles = df_blocks_selected[f'{scenario}_avg_vehicles_served_daily'].sum()
    tot_annual_vehicles = df_blocks_selected[f'{scenario}_tot_vehicles_served_yearly'].sum()
    print(f'Total average vehicles served daily for selected blocks: {tot_avg_daily_vehicles}')
    print(f'Total vehicles served annually for selected blocks: {tot_annual_vehicles}')
    print(f'')
    print("")

    return df_blocks_selected


def select_priority_blocks(metric, scenario='30%', subsidy_cap=4000):
    """Run the full siting pipeline for one demand metric ('population', 'rwi', or 'lcoe')
    and one fleet conversion scenario: build the bivariate composite score, merge in PV
    cost/vehicles-served data, and select priority blocks under the subsidy investment cap."""
    fleet_df = gpd.read_file(WB_BLOCKS_3W_GEOJSON)

    composite_builders = {
        'population': load_population_demand_composite,
        'rwi': load_rwi_demand_composite,
        'lcoe': load_lcoe_demand_composite,
    }
    if metric not in composite_builders:
        raise ValueError(f"metric must be one of {list(composite_builders)}, got {metric!r}")

    df_metric = composite_builders[metric](fleet_df, scenario)

    vehicles_df = load_block_pv_vehicles(scenario)
    cost_df = load_block_pv_cost(scenario)
    df_pv_cost = merge_pv_dfs(vehicles_df, cost_df, scenario=scenario)

    wb_blocks = gpd.read_file(WB_BLOCKS_GEOJSON)
    wb_districts = gpd.read_file(WB_DISTRICTS_GEOJSON)
    west_bengal = gpd.read_file(WEST_BENGAL_GEOJSON)

    df_blocks_selected = charging_station_siting(
        df_metric, df_pv_cost, subsidy_cap=subsidy_cap, scenario=f'{scenario}_conversion'
    )

    plot_site_selection(df_blocks_selected, wb_blocks, wb_districts, west_bengal)

    return df_blocks_selected
