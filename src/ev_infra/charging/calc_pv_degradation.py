"""Calculate the decrease in PV system energy production over its operational lifetime
due to panel efficiency degradation."""

import pandas as pd

from ev_infra.config import DATA_PROCESSED


def calc_pv_annual_energy_lifetime(df_pv, fleet_conversion='10%_conversion'):
    # Initialize the lifespan of the PV system (i.e. 25 years)
    years = list(range(26))

    # Create a dictionary to store the results of the decrease in annual PV production over lifespan of system
    lifetime_energy_prod = {'year': years}

    # Obtain a list of the block names
    block_id = df_pv['block'].unique()

    # Create a list storing the decrease in PV efficiency for each year of PV lifespan (based on SovaSolar module specifications, linear power percentage)
    efficiency = []
    for year in years:
        if year == 0:
            efficiency.append(1)
        elif year == 1:
            efficiency.append(0.975)
        else:
            efficiency.append(efficiency[-1] * (1 - 0.68/100))      # 0.68% efficiency decrease for every subsequent year

    # Loop through each file and read it into a DataFrame
    for block in block_id:
        # Extract the annual energy production for each block for Year 0 from previous sizing calculation
        annual_base_production = df_pv.loc[df_pv['block'] == block, f'{fleet_conversion}_annual_pv_energy'].values[0]

        # Calculate energy production over lifetime of PV with decreasing efficiency
        block_energy_prod = [annual_base_production * year_efficiency for year_efficiency in efficiency]

        # Store the results in a dictionary
        lifetime_energy_prod[block] = block_energy_prod

    # Create a new dataframe for the annual energy production at each district
    block_lifetime_energy = pd.DataFrame(lifetime_energy_prod)

    return block_lifetime_energy


def write_pv_energy_lifetime(block_pv_by_scenario, output_dir=DATA_PROCESSED):
    """Compute and write PV lifetime energy degradation for each fleet conversion scenario."""
    results = {}

    for scenario, df in block_pv_by_scenario.items():
        fleet_conversion = f'{scenario}_conversion'
        block_pv_energy = calc_pv_annual_energy_lifetime(df, fleet_conversion=fleet_conversion)

        block_pv_energy.to_csv(output_dir / f"block-pv-energy-lifetime-{scenario.rstrip('%')}pct.csv", index=False)

        results[scenario] = block_pv_energy

    return results
