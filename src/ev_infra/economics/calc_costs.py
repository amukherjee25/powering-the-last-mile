"""Calculate lifetime CAPEX, OPEX, and subsidy cashflows for PV systems at each block."""

import pandas as pd

from ev_infra.config import USD_TO_INR, PV_CAPEX_PER_KW, PV_OPEX_PER_KW, WBEVP_SUBSIDY_PCT

SUBSIDY_CAP_USD = 40_000_000 / USD_TO_INR   # Subsidy capped at INR 40,000,000 (40 Crore)
PV_LIFESPAN_YEARS = 25


def block_annual_costs(df_pv, fleet_conversion='10%_conversion'):
    # Create a dictionary to store the CAPEX and OPEX costs for PV system for each block
    block_pv_economics = {}

    # Extract the individual block names
    block_id = df_pv['block'].unique()

    # Initialize the lifespan of the PV system (i.e. 25 years)
    years = list(range(PV_LIFESPAN_YEARS + 1))

    for block in block_id:
        block_pv_size = df_pv.loc[df_pv['block'] == block, f'{fleet_conversion}_pv_size'].values[0]

        # Initialize empty lists for storing the investment and O&M costs for each year of the PV system
        investment_cost = []
        o_and_m_cost = []
        subsidy = []

        # Loop over each year to calculate the costs
        for year in years:
            # Investment cost (only in year 0)
            if year == 0:
                investment_cost.append(PV_CAPEX_PER_KW * block_pv_size)
            else:
                investment_cost.append(0)

            # O&M costs (from year 1 through year 25)
            if year >= 1:
                o_and_m_cost.append(PV_OPEX_PER_KW * block_pv_size)
            else:
                o_and_m_cost.append(0)

            # Subsidy (only for years 1 through 5, distributed evenly)
            # Calculate the total subsidy given the PV size capital cost
            total_subsidy = WBEVP_SUBSIDY_PCT * PV_CAPEX_PER_KW * block_pv_size
            if 1 <= year <= 5:
                # If the total subsidy exceeds the subsidy cap, only subsidize the investment cost based on the threshold
                if total_subsidy > SUBSIDY_CAP_USD:
                    subsidy.append(SUBSIDY_CAP_USD / 5)
                elif total_subsidy <= SUBSIDY_CAP_USD:
                    subsidy.append(total_subsidy / 5)
            else:
                subsidy.append(0)

        # Create a DataFrame for each block with the calculated values
        block_economics_df = pd.DataFrame({
            'year': years,
            'investment_cost_$': investment_cost,
            'o&m_cost_$': o_and_m_cost,
            'subsidy_$': subsidy
        })

        # Store the DataFrame for each block in the dictionary
        block_pv_economics[block] = block_economics_df

    return block_pv_economics
