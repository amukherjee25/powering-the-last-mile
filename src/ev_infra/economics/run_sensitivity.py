"""Sensitivity analysis: how NPV and LCOE change as charging tariff or discount rate
are varied around a base case."""

import numpy as np
import pandas as pd


def compute_sensitivity(block_economics, base_tariff=6.00, base_discount=0.070):
    """For each block, compute % change in NPV/LCOE vs. a base tariff/discount case,
    separately varying tariff (at fixed discount) and discount (at fixed tariff)."""
    # Create an empty list to store the results of the sensitivity analysis
    results_tariff = []
    results_discount = []

    for block, group in block_economics.groupby('block'):
        # Extract the data for the base tariff
        base_case = group[(np.isclose(group['tariff_inr'], base_tariff)) &
                               (np.isclose(group['discount_rate'], base_discount))]
        if base_case.empty:
            continue        # skip the block if base case values are missing or not available

        # Obtain the values for base case NPV and LCOE values
        base_case_npv = base_case['npv'].values[0]
        base_case_lcoe = base_case['lcoe'].values[0]

        # --- Fixed Discount Rate, Vary Charging Tariff ---
        # Create copy of dataframe subset with discount rate set at base discount rate
        sensitivity_tariff = group[np.isclose(group['discount_rate'], base_discount)].copy()

        # Compute the percentage change in NPV & LCOE for each block
        sensitivity_tariff['npv_pct_change'] = (sensitivity_tariff['npv'] - base_case_npv) / base_case_npv * 100
        sensitivity_tariff['lcoe_pct_change'] = (sensitivity_tariff['lcoe'] - base_case_lcoe) / base_case_lcoe * 100

        # Append the results to initialized list
        results_tariff.append(sensitivity_tariff[['block', 'tariff_inr', 'discount_rate', 'npv_pct_change', 'lcoe_pct_change']])

        # --- Fixed Charging Tariff, Vary Discount Rate ---
        # Create copy of dataframe subset with discount rate set at base discount rate
        sensitivity_discount = group[np.isclose(group['tariff_inr'], base_tariff)].copy()

        # Compute the percentage change in NPV & LCOE for each block
        sensitivity_discount['npv_pct_change'] = (sensitivity_discount['npv'] - base_case_npv) / base_case_npv * 100
        sensitivity_discount['lcoe_pct_change'] = (sensitivity_discount['lcoe'] - base_case_lcoe) / base_case_lcoe * 100

        # Append the results to initialized list
        results_discount.append(sensitivity_discount[['block', 'tariff_inr', 'discount_rate', 'npv_pct_change', 'lcoe_pct_change']])

    # Create a dataframe for the final results
    sensitivity_tariff_df = pd.concat(results_tariff)
    sensitivity_discount_df = pd.concat(results_discount)

    return sensitivity_tariff_df, sensitivity_discount_df


def aggregate_sensitivity(sensitivity_tariff_df, sensitivity_discount_df):
    """Aggregate percent-change sensitivity results across all blocks, by tariff and by discount rate."""
    avg_tariff = sensitivity_tariff_df.groupby('tariff_inr')[
        ['npv_pct_change', 'lcoe_pct_change']].agg(['mean', 'std']).reset_index()
    avg_discount = sensitivity_discount_df.groupby('discount_rate')[
        ['npv_pct_change', 'lcoe_pct_change']].agg(['mean', 'std']).reset_index()

    return avg_tariff, avg_discount
