"""Calculate PV system capital costs (CAPEX) for each block, per fleet conversion scenario."""

from ev_infra.config import DATA_PROCESSED, USD_TO_INR, PV_CAPEX_PER_KW

BLOCK_PV_COST_CSV = {
    '10%': DATA_PROCESSED / "block-pv-cost-10pct.csv",
    '30%': DATA_PROCESSED / "block-pv-cost-30pct.csv",
    '100%': DATA_PROCESSED / "block-pv-cost-100pct.csv",
}

def calc_pv_capex(pv_sizes, fleet_conversion='10%_conversion'):
    # Create a copy of the dataframe and drop irrelevant columns
    block_pv_cost = pv_sizes.copy().drop(columns=[f'{fleet_conversion}_annual_pv_energy', 'geometry'])

    # Add a new column calculating the capital costs for each system for each block
    block_pv_cost['pv_capex_usd'] = block_pv_cost[f'{fleet_conversion}_pv_size'] * PV_CAPEX_PER_KW
    block_pv_cost['pv_capex_inr_lakh'] = block_pv_cost['pv_capex_usd'] * USD_TO_INR / 100000       # Convert to INR Lakh

    return block_pv_cost


def write_block_pv_cost(pv_sizes_by_scenario):
    """Calculate and write PV CAPEX for each fleet conversion scenario."""
    block_pv_cost_by_scenario = {}

    for scenario, pv_sizes in pv_sizes_by_scenario.items():
        block_pv_cost = calc_pv_capex(pv_sizes, fleet_conversion=f'{scenario}_conversion')
        block_pv_cost.to_csv(BLOCK_PV_COST_CSV[scenario], index=False)
        block_pv_cost_by_scenario[scenario] = block_pv_cost

    return block_pv_cost_by_scenario
