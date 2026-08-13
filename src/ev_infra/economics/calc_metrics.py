"""Calculate NPV, IRR, LCOE, and payback period for PV-based charging infrastructure
under different charging tariffs and discount rates, and filter/export results."""

import numpy as np
import pandas as pd
import geopandas as gpd
import numpy_financial as npf

from ev_infra.config import DATA_PROCESSED, USD_TO_INR
from ev_infra.utils import map_block_to_district

BLOCK_ECONOMICS_CSV = {
    '10%': DATA_PROCESSED / "west-bengal-pv-economics-subs-ra-10pct.csv",
    '30%': DATA_PROCESSED / "west-bengal-pv-economics-subs-ra-30pct.csv",
    '100%': DATA_PROCESSED / "west-bengal-pv-economics-subs-ra-100pct.csv",
}
BLOCK_LCOE_GEOJSON = {
    '10%': DATA_PROCESSED / "block-lcoe-wbevp-risk-10pct.geojson",
    '30%': DATA_PROCESSED / "block-lcoe-wbevp-risk-30pct.geojson",
    '100%': DATA_PROCESSED / "block-lcoe-wbevp-risk-100pct.geojson",
}


def calculate_economics(dict_pv_costs, df_pv_prod, tariffs, discount_rates, subsidy=True):
    # Ensure discount_rates is iterable
    if np.isscalar(discount_rates):
        discount_rates = np.array([discount_rates])
    else:
        discount_rates = np.array(discount_rates)

    # Define an empty dictionary to store the results
    economic_results = {}

    # Define an empty list to store all the new columns
    new_columns = []

    # Define the unique block names
    block_id = df_pv_prod.iloc[:,1:].columns

    # Perform economic calculations for each block
    for block in block_id:

        # Initialize an empty dictionary to store the results for each block
        block_results = {}

        # Obtain the dataframe containing the costs for the block
        df_pv_cost = dict_pv_costs[block]

        # For each tariff, calculate the charging revenue and cashflow for each year
        for tariff in tariffs:

            # Convert the USD tariff to INR
            tariff_inr = tariff * USD_TO_INR
            # Create a column name value to use for the charging revenue and cashflow
            col_name_inr = f"{tariff_inr:.2f}"

            # Calculate the charging revenue
            annual_energy = df_pv_prod[block].values
            revenue_usd = df_pv_prod[block] * tariff
            new_columns.append(revenue_usd.rename(f'revenue_Rs{col_name_inr}'))

            # Determine the cashflow components
            capital_cost_usd = df_pv_cost['investment_cost_$']
            o_and_m_usd = df_pv_cost['o&m_cost_$']
            subsidy_usd = df_pv_cost['subsidy_$'] if subsidy else 0

            # Compute cashflow
            cashflow_usd = revenue_usd + subsidy_usd - capital_cost_usd - o_and_m_usd
            new_columns.append(cashflow_usd.rename(f'cashflow_Rs{col_name_inr}'))

            # Convert values for LCOE calculation
            cashflows = cashflow_usd.values * USD_TO_INR
            capital_cost_inr = capital_cost_usd.values * USD_TO_INR
            o_and_m_inr = o_and_m_usd.values * USD_TO_INR
            subsidy_inr = subsidy_usd.values * USD_TO_INR if subsidy else 0

            # Pre-calculate common energy output for LCOE
            total_energy = annual_energy.sum()

            npv_per_rate = {}
            lcoe_per_rate = {}

            for discount in discount_rates:
                # Calculate the NPV
                npv_inr = npf.npv(discount, cashflows)
                npv_per_rate[discount] = npv_inr

                # Discount factors
                years = df_pv_prod['year'].values
                discount_factors = 1 / (1 + discount) ** years

                # Discounted costs and energy
                discounted_energy = annual_energy * discount_factors

                if discount == 0:
                    total_costs = capital_cost_inr.sum() + o_and_m_inr.sum() - (subsidy_inr.sum() if subsidy else 0)
                    lcoe = total_costs / total_energy
                else:
                    discounted_costs = (capital_cost_usd + o_and_m_usd - subsidy_usd) * USD_TO_INR * discount_factors
                    lcoe = discounted_costs.sum() / discounted_energy.sum()

                lcoe_per_rate[discount] = lcoe

            # Calculate the IRR
            try:
                irr = npf.irr(cashflow_usd.values)
            except Exception:
                irr = np.nan  # fallback in case IRR fails

            # Calculate the payback period for the specific tariff
            cumulative_cf = np.cumsum(cashflows)

            # Case 1: Never paid back
            if all(cumulative_cf < 0):
                payback = np.nan

            else:
                # Find first index where cumulative cashflow becomes positive
                payback_year_index = np.argmax(cumulative_cf >= 0)

                # If it's the first year:
                if payback_year_index == 0:
                    payback = 0

                else:
                    # Linear interpolation between the two years
                    C_prev = cumulative_cf[payback_year_index - 1]
                    C_curr = cumulative_cf[payback_year_index]

                    frac = abs(C_prev) / (C_curr - C_prev)

                    # Year numbering uses df_pv_prod['year']
                    year_prev = df_pv_prod['year'].values[payback_year_index - 1]

                    payback = year_prev + frac

            # Store results for this tariff rate for this block
            block_results[tariff] = {
                'npvs': npv_per_rate,
                'irr': irr,
                'lcoe': lcoe_per_rate,
                'payback_period': payback
            }

        # Store the economic results for all tariffs for this block
        economic_results[block] = block_results

    # After the loop ends, concatenate all the new columns at once
    df_new_columns = pd.concat(new_columns, axis=1)

    # Join the new columns to the original DataFrame
    df_compiled = pd.concat([df_pv_cost, df_pv_prod[block], df_new_columns], axis=1)

    return df_compiled, economic_results


def economic_results_flatten(economic_results):
    """Flatten the nested economic_results dict into a long-format dataframe, one row
    per block x tariff x discount rate combination."""
    flatten_results = []

    for block, tariffs in economic_results.items():
        for tariff, metrics in tariffs.items():
            for discount, npv in metrics['npvs'].items():
                lcoe_value = metrics['lcoe'][discount]
                if isinstance(lcoe_value, np.ndarray):
                    lcoe_value = lcoe_value[-1]

                flatten_results.append({
                    'block': block,
                    'tariff_usd': tariff,
                    'tariff_inr': tariff * USD_TO_INR,
                    'discount_rate': discount,
                    'npv': npv,
                    'lcoe': lcoe_value,
                    'irr': metrics['irr'],
                    'payback_period': metrics.get('payback_period', np.nan)
                })

    # Convert flattened results into DataFrame
    df_flatten = pd.DataFrame(flatten_results)

    return df_flatten


def write_block_economics(pv_costs_by_scenario, pv_energy_by_scenario, wb_districts, tariffs, discount_rates, subsidy=True):
    """Run calculate_economics + flatten for each scenario, annotate with district and
    district code, and write results to CSV. Returns (compiled_by_scenario, annotated_by_scenario)."""
    district_code_map = wb_districts.set_index('district')['code'].to_dict()

    compiled = {}
    annotated = {}
    for scenario in pv_costs_by_scenario:
        df_compiled, economic_results = calculate_economics(
            dict_pv_costs=pv_costs_by_scenario[scenario],
            df_pv_prod=pv_energy_by_scenario[scenario],
            tariffs=tariffs,
            discount_rates=discount_rates,
            subsidy=subsidy,
        )
        compiled[scenario] = df_compiled

        df_flat = economic_results_flatten(economic_results)

        # Add district and district code, derived from block name
        df_flat['district'] = df_flat['block'].apply(map_block_to_district)
        df_flat['code'] = df_flat['district'].map(district_code_map)

        df_flat.to_csv(BLOCK_ECONOMICS_CSV[scenario], index=False)
        annotated[scenario] = df_flat

    return compiled, annotated


def economics_filter(dict_economics, tariff, discount):
    """
    Extract relevant data for a specified tariff and optional discount rate.

    Parameters
    ----------
    dict_economics : dict
        Dictionary with scenario names as keys and DataFrames as values.
    tariff : float
        Tariff value in INR to filter on.
    discount : float, optional
        Discount rate to filter on. If None, all rates or singular rate is considered.

    Returns
    -------
    tariff_filter : dict
        DataFrames filtered for the given tariff (and excluding Kolkata if discount is None).
    tariff_discount_filter : dict
        DataFrames filtered for both the given tariff and nearest discount (excluding Kolkata if discount is given).
    """
    # Initialize the dictionaries to store the results for each scenario
    tariff_economics = {}
    tariff_filter = {}
    tariff_discount = {}
    tariff_discount_filter = {}

    # Extract the data for each scenario
    for scenario, df in dict_economics.items():
        # Filter dataframe based on specified tariff
        df_tariff = df[np.isclose(df['tariff_inr'], tariff)]

        # Append the data into the new dictionary
        tariff_economics[scenario] = df_tariff

        # Skip if there is no matching tariff data
        if df_tariff.empty:
            print(f"No matching tariff data found for {scenario}.")
            continue

        if discount is not None:
            # Find the nearest available discount rate in this scenario
            nearest_rate = df_tariff['discount_rate'].iloc[
                (df_tariff['discount_rate'] - discount).abs().argsort()].iloc[0]
            print(f"Nearest available discount rate for {scenario}: {nearest_rate:.3f}")

            # Filter using the nearest available rate
            df_discount_filter = df_tariff[np.isclose(df_tariff['discount_rate'], nearest_rate)]

            # Append the data into the new dictionary
            tariff_discount[scenario] = df_discount_filter

            # Print the NPV, LCOE for Kolkata for the given scenario
            df_kol = df_discount_filter[df_discount_filter['district'] == 'Kolkata']
            if not df_kol.empty:
                npv_kol = df_kol['npv'].iloc[0]
                lcoe_kol = df_kol['lcoe'].iloc[0]
                print(f'Kolkata NPV for {scenario} conversion with discount rate {nearest_rate * 100:.3f}%: INR {(npv_kol / 1e5):.3f} Lakh')
                print(f'Kolkata LCOE for {scenario} conversion with discount rate {nearest_rate * 100:.3f}%: {lcoe_kol:.3f} INR/kWh')
            else:
                print(f"Kolkata not found for {scenario} at discount rate {nearest_rate:.3f}")

            # Remove Kolkata from each scenario and append it to new dictionary
            tariff_discount_filter[scenario] = df_discount_filter[df_discount_filter['district'] != 'Kolkata'].reset_index(drop=True)

        else:
            df_kol = df_tariff[df_tariff['district'] == 'Kolkata']
            if not df_kol.empty:
                npv_kol = df_kol['npv'].iloc[0]
                lcoe_kol = df_kol['lcoe'].iloc[0]
                print(f'Kolkata NPV for {scenario} conversion (all discount rates): INR {(npv_kol / 1e5):.3f}')
                print(f'Kolkata LCOE for {scenario} conversion (all discount rates): {lcoe_kol:.3f} INR/kWh')

            # Remove Kolkata and append it new dictionary
            tariff_filter[scenario] = df_tariff[df_tariff['district'] != 'Kolkata'].reset_index(drop=True)

    return tariff_filter, tariff_discount_filter, tariff_discount


def write_scenario_geojson(policy_tariff_by_scenario, wb_blocks):
    """Merge filtered economics results with block geometry and write out per-scenario
    GeoJSON files (e.g. for the WBEVP policy tariff at the risk-adjusted discount rate)."""
    written = {}

    for scenario, df in policy_tariff_by_scenario.items():
        # Merge only the needed columns to avoid duplicates
        gdf = df.merge(
            wb_blocks[['block', 'geometry']],
            on='block',
            how='left'
        )

        # Convert to GeoDataFrame with proper CRS
        gdf = gpd.GeoDataFrame(gdf, geometry='geometry', crs=wb_blocks.crs)

        # --- Quality check for duplicate column names ---
        dup_cols = [col for col in gdf.columns if col.endswith('_x') or col.endswith('_y')]
        if dup_cols:
            print(f"Warning: Duplicate suffix columns found in {scenario}: {dup_cols}")
            raise ValueError(f"Duplicate columns found: {dup_cols}")
        else:
            print(f"No duplicate columns in {scenario}")

        # Write GeoJSON
        gdf.to_file(BLOCK_LCOE_GEOJSON[scenario], driver="GeoJSON")
        print(f"Wrote {BLOCK_LCOE_GEOJSON[scenario]}")

        written[scenario] = gdf

    return written
