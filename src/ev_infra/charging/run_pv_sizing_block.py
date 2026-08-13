# Import relevant packages
import numpy as np
import pandas as pd
import random
import os
import glob
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pv_sizing.log'),
        logging.StreamHandler()
    ]
)

# Read in solar and input data and run the function to calculate PV system required to serve fleet size
def main():

    # Use the sys function to extract system level information
    # sys.argv[0] is always the script name (run_pv_sizing.py).
    # sys.argv[1], sys.argv[2], etc., are any additional arguments provided on the command line.
    if len(sys.argv) < 3:
        raise ValueError("Please provide a district ID as a command-line argument.")
    
    # Get the block name from the command line argument
    block_id = sys.argv[1]

    # Get the district name from command-line argument
    district_id = sys.argv[2]

    # Get the current working directory
    cwd = os.getcwd()

    # Specify the folder with input data for solar GHI and fleet conversion for each district
    input_dir = 'district_data'
    district_data = os.path.join(cwd, input_dir)

    # Specify the folder to write out the results
    output_dir = '_Outputs'
    output_path = os.path.join(cwd, output_dir)
    os.makedirs(output_path, exist_ok=True)

    # Get the file path for the district-level solar data
    solar_file = os.path.join(district_data, f'{district_id}_solar.csv')
    # Get the file path for district-level 3W fleet size data
    fleet_file = os.path.join(district_data, f'{district_id}_fleet.csv')

    if not os.path.exists(solar_file) or not os.path.exists(fleet_file):
        raise FileNotFoundError(f"Missing input files for {district_id}")
    
    # Read the data into dataframes
    try:
        df_solar = pd.read_csv(solar_file)
    except Exception as e:
        logging.error(f"Failed to read PV file for {district_id}: {e}")
        return 1

    try:
        df_fleet = pd.read_csv(fleet_file)
        df_fleet_block = df_fleet[df_fleet['block'] == block_id]
    except Exception as e:
        logging.error(f"Failed to read 3W fleet file for {district_id}: {e}")
        return 1

    # Call the function to calculate the required PV size for each block in each district based on proposed fleet conversion
    results = pv_sizing_district(
        df_solar=df_solar,
        df_fleet=df_fleet_block,
        batt_size=8.9,
        daily_vmt=118,
        vehicle_range=178,
        district=district_id
        )

    # Write out the results
    write_pv_results(pv_results=results, district=district_id, block=block_id, output_dir=output_path)

    return 0


def pv_sizing_district(df_solar, df_fleet, batt_size, daily_vmt, vehicle_range, district):

    # Create an empty list to store the results for each block and each scenario
    pv_results = []

    # Define the maximum PV sytem size
    max_size = 100000

    # Define the constants for calculating PV output
    f_pv = 0.80             # Derate factor (80%)
    g_t_STC = 1             # Standard irradiance (kW/m²)

    # Obtain the fleet conversion scenarios
    fleet_scenarios = df_fleet.iloc[:,2:5].columns.tolist()

    # Extract the fleet data for the blocks within the district
    district_blocks = df_fleet

    if district_blocks.empty:
        logging.warning(f"No blocks found for district: {district}")

    logging.info(f'Begin processing {district} district')

    for _, block_row in district_blocks.iterrows():

        # Obtain the block name
        block_id = block_row['block']

        logging.info(f'Begin processing {block_id} block in {district}')

        # Check if all fleet sizes across all scenarios are zero or NaN
        scenario_fleets = block_row[fleet_scenarios]
        if scenario_fleets.fillna(0).sum() == 0:
            logging.warning(f"All conversion scenarios have 0 vehicles for block {block_id} in {district}. Writing 0 for PV system size.")
            for scenario in fleet_scenarios:
                pv_results.append({
                    'block': block_id,
                    'district': district,
                    'scenario': scenario,
                    'system_size_kW': 0,
                    'annual_pv_energy_kWh': 0,
                    'days_met': 0,
                    'fraction_of_year': 0,
                    'hourly_pv_output': 0,
                    'daily_batteries': 0,
                    'avg_vehicles_served_daily': 0,
                    'tot_vehicles_served_yearly': 0
                })
            continue  # Skip PV sizing

        # Initialize the PV system system at 1 kW for each block at the top of the loop for going into the fleet conversion scenarios
        initial_size = 1
        
        for idx, scenario in enumerate(fleet_scenarios):

            # Obtain the fleet size for the fleet conversion scenario for the block
            fleet_size = block_row[scenario]

            # Skip a scenario if there are no vehicles in that block
            if fleet_size == 0 or np.isnan(fleet_size):
                continue            

            # Calculate the initial annual energy required for battery swapping based on battery size
            annual_mileage = daily_vmt * 365       # km
            annual_batt_swaps = np.ceil(annual_mileage / vehicle_range).astype(int)
            annual_batt_energy = (fleet_size * annual_batt_swaps * batt_size) * 1.1      # Accounting for 10% overall system losses

            # Initialize the PV system size
            system_size = 1 if idx == 0 else initial_size + 1 

            # print(f'Begin calculating optimal PV system size for {block_id} for {scenario} scenario')

            # Add a safety flag
            found_optimal_size = False

            while system_size <= max_size:

                # Calculate the annual hourly PV output
                df_pv_output = df_solar.copy()

                # Create a case-insensitive check and fallback
                col_name = next((col for col in df_solar.columns if col.lower() == 'incident_solar_kw/m2'), None)
                if col_name is None:
                    raise ValueError(f"'incident_solar_kw/m2' column not found in solar data for {district}")

                df_pv_output['PV_power_output_kW'] = f_pv * system_size * (df_pv_output[col_name] / g_t_STC)
                df_pv_output['PV_energy_kWh'] = df_pv_output['PV_power_output_kW']  # Assuming 1-hour intervals

                # Calculate the annual energy output of the PV system    
                annual_pv_energy = df_pv_output['PV_energy_kWh'].sum()

                # Call the battery charging algorithm for this PV system size
                try:
                    _, _, daily_batteries = battery_charging(
                        df_pv_output, capacity=185, voltage=48, c_rate=0.2,
                        arrival_soc=0.1, charged_soc=0.99, type='lithium-ion', vehicle='eauto'
                    )
                except Exception as e:
                    logging.error(f"Error during battery charging for block {block_id}: {e}")
                    break

                if 'total_eauto_batteries' not in daily_batteries.columns:
                    raise ValueError(f"'total_eauto_batteries' column missing in daily battery data for block {block_id}")

                # Check whether PV size meets required threshold (serve 50% of the fleet for 50% percent of year)
                fleet_served = fleet_size * 0.5
                num_days_met = (daily_batteries['total_eauto_batteries'] >= fleet_served).sum()
                fraction_of_year = num_days_met / 365

                # Store the results for the fleet conversion scenario for that block
                if annual_pv_energy >= annual_batt_energy and fraction_of_year >= 0.5:
                    pv_results.append({
                        'block': block_id,
                        'district': district,
                        'scenario': scenario,
                        'system_size_kW': system_size,
                        'annual_pv_energy_kWh': annual_pv_energy,
                        'days_met': num_days_met,
                        'fraction_of_year': fraction_of_year,
                        'hourly_pv_output': df_pv_output,
                        'daily_batteries': daily_batteries,
                        'avg_vehicles_served_daily': int(np.floor(daily_batteries['total_eauto_batteries'].mean())),
                        'tot_vehicles_served_yearly': int(np.floor(daily_batteries['total_eauto_batteries'].sum()))
                    })

                    # Store this scenario's system size for next scenario's initialization
                    initial_size = system_size
                    found_optimal_size = True
                    logging.info(f'Optimal PV Size found for {block_id} for {scenario} scenario')
                    
                    break
                else:
                    system_size += 1
            
            if not found_optimal_size:
                logging.warning(f"Block {block_id} in {district} ({scenario}) unmet with max size {max_size} kW")

    return pv_results


# Write out the results of the required PV system size for each block in each district
def write_pv_results(pv_results, district, block, output_dir):

    if pv_results:
        results_df = pd.DataFrame(pv_results)

        # Pivot for system sizes
        size_pivot = results_df.pivot(index='block', columns='scenario', values='system_size_kW')
        size_pivot.columns = [f"{col}_pv_size" for col in size_pivot.columns]
        size_pivot.reset_index(inplace=True)

        # Pivot for PV energy
        energy_pivot = results_df.pivot(index='block', columns='scenario', values='annual_pv_energy_kWh')
        energy_pivot.columns = [f"{col}_annual_pv_energy" for col in energy_pivot.columns]
        energy_pivot.reset_index(inplace=True)

        # Pivot for annual average vehicles served
        daily_ave_vehicles_pivot = results_df.pivot(index='block', columns='scenario', values='avg_vehicles_served_daily')
        daily_ave_vehicles_pivot.columns = [f"{col}_avg_vehicles_served_daily" for col in daily_ave_vehicles_pivot.columns]
        daily_ave_vehicles_pivot.reset_index(inplace=True)

        annual_tot_vehicles_pivot = results_df.pivot(index='block', columns='scenario', values='tot_vehicles_served_yearly')
        annual_tot_vehicles_pivot.columns = [f"{col}_tot_vehicles_served_yearly" for col in annual_tot_vehicles_pivot.columns]
        annual_tot_vehicles_pivot.reset_index(inplace=True)

        # Merge the the dataframes on block
        final_df = pd.merge(size_pivot, energy_pivot, on='block', how='outer')
        final_df = pd.merge(final_df, daily_ave_vehicles_pivot, on='block', how='outer')
        final_df = pd.merge(final_df, annual_tot_vehicles_pivot, on='block', how='outer')

        # Insert district column
        final_df.insert(1, 'district', district)
        
        # Save to CSV
        csv_path = os.path.join(output_dir, f"{block}_{district}_pv_system.csv")
        final_df.to_csv(csv_path, index=False)
        logging.info(f"Saved PV sizing results for {block} in {district}")
    else:
        logging.info(f"No results to save for {block}.")

    return


# Define a function to calculate the number of batteries charged based on solar availability
def battery_charging(df, capacity, voltage, c_rate, arrival_soc, charged_soc, type, vehicle):

    # Define the battery specifications
    batt_capacity = capacity        # Ah
    batt_voltage = voltage          # V
    batt_energy = batt_voltage * batt_capacity / 1000    # kWh
    
    # Calculate the hourly charging energy delivered to charge the battery for 1 hour at CC mode
    charging_current = batt_capacity / (1 / c_rate)               # A
    charging_power = batt_voltage * charging_current / 1000       # kW
    charging_energy = charging_power * 1                          # kWh
    
    # For each hour, calculate the maximum number of batteries that can be charged given the PV energy output
    df['max_batt_charged'] = np.floor(df['PV_energy_kWh'] / charging_energy).astype(int)

    # Create an empty list for storing the number of batteries that were being charged during each hour of each day
    num_charging_hourly = []
    
    # Create an empty list for storing the batteries charged each hour of each day
    num_batteries_charged_hourly = []
    
    # Create an empty list for storing the batteries charged each day of each year
    num_batteries_charged_daily = []

    # Create an empty list for storing the total amount of energy used to fully charge a battery
    energy_for_full_charge = []

    # Create an empty list for storing the day number
    day_num = []

    # Create an empty list for storing SoC for partially charged batteries from previous day
    carryover_soc = []

    # Create an empty list for storing energy for partially charged batteries from previous day
    carryover_energy = []

    # Create an array for the unique dates (i.e. each day of each year) and the hours in each day
    days = df['date'].unique()
    hours = np.arange(0, 24, 1)

    for day in days:
        # Obtain the day of the year
        day_data = df[df['date'] == day]

        # Initialize the total number of batteries that are fully charged for that day
        daily_batteries_charged = 0

        # Define a theoretical maximum number of batteries to be charged based on max batteries that can be charged by solar in 1 day of the year
        max_daily_batteries = max(df.groupby('date')['max_batt_charged'].sum())

        # Obtain the number of partially charged batteries from previous day
        prev_day_num_battery = len(carryover_soc)

        # Calculate the number of new discharged batteries that can be be charged
        new_daily_batteries = max_daily_batteries - prev_day_num_battery

        # Create a random set of battery SoC's from a normal distribution
        soc_random = np.random.normal(loc=arrival_soc, scale=0.01, size=max_daily_batteries)
        soc_random = soc_random[soc_random >= 0]

        # Create a list of randomized SoC for the new batteries that can be charged for the day
        new_battery_soc = list(np.random.choice(soc_random, size=new_daily_batteries, replace=True))    # True means random sample can be selected multiple times

        # Create a list for the energy of each the new batteries that can be charged for the day
        new_battery_energy = np.array(new_battery_soc) * batt_energy

        # Create a compiled array for storing the SoCs and corresponding battery energy from previous day's partially charged batteries along with new randomized SoCs
        soc = np.concatenate([np.array(carryover_soc), np.array(new_battery_soc)], axis=0)
        energy = np.concatenate([np.array(carryover_energy), np.array(new_battery_energy)], axis=0)

        # # Initialize the battery SOC and energy arrays
        # soc = np.zeros(max_daily_batteries)       # Create this array to keep track of battery soc's for each hour
        # energy = np.zeros(max_daily_batteries)

        # Track the number of hours each battery takes to reach full charge
        hours_for_charging = np.zeros(max_daily_batteries)

        # Cycle through each hour of the day to determine how many batteries can be charged that day
        for hour in hours:
            # Obtain the maximum PV output for the given hour in the day
            pv_output = day_data.loc[day_data['hour'] == hour, 'PV_energy_kWh'].values[0]

            # Define the energy that can be supplied to each battery from charging for each hour
            charge_energy = charging_energy

            # Initialize the total energy used for charging batteries for that hour
            hourly_energy_used = 0

            # Initialize the number of batteries to which PV energy is delivered to for the hour
            batteries_charging = 0
            
            # Initialize the number of batteries charged for the hour
            hourly_batteries_charged = 0

            if pv_output > 0:
                # Obtain the maximum number of batteries that can be charged for that hour given solar output
                max_batt_hour = day_data.loc[day_data['hour'] == hour, 'max_batt_charged'].values[0]

                # Cycle through each battery based on SOC and PV power output
                for battery in range(max_batt_hour):
                    # Calculate the total energy that would be used to charge 1 more battery
                    total_energy_used = hourly_energy_used + charge_energy
                    # Check if you can charge one more unit without exhausting PV supply
                    if total_energy_used <= pv_output:
                        # If battery SoC >= user defined final SoC, skip this battery and move onto the next one (battery is considered fully charged)
                        if soc[battery] >= charged_soc:
                            continue
                        # If battery SoC = 0, assign random SoC to battery from soc random array
                        # This portion of code should technically not be executed since all batteries should have a randomized SoC assigned to them
                        if soc[battery] == 0:
                            initial_soc = random.choice(soc_random)
                            soc[battery] = initial_soc
                        # Otherwise, maintain the previous SoC from previous hourly iteration
                        else:
                            initial_soc = soc[battery]
                        # Define the energy within the battery based on the SoC
                        initial_energy = initial_soc * batt_energy
                        energy[battery] = initial_energy
                        # Charge the battery if there is enough energy
                        if soc[battery] < 1:
                            # Charge the battery with the allocated energy per hour and update the battery energy
                            battery_charge = energy[battery] + charge_energy
                            energy[battery] = battery_charge
                            batteries_charging += 1

                            # Calculate the battery SOC and update
                            battery_soc = battery_charge / batt_energy
                            if battery_soc > 1:
                                soc[battery] = 1        # If SoC exceeds 100% due to delivery of hourly energy, set the SoC to 100%
                            else:
                                soc[battery] = battery_soc

                            # Track the total energy used for charging
                            hourly_energy_used += charge_energy

                            # Track the number of hours for fully charging this battery
                            hours_for_charging[battery] += 1
                            
                            # If the SOC of the battery is within the specified threshold, stop charging the battery for the next hour
                            if soc[battery] >= charged_soc:
                                # Count towards the total number of batteries charged for that hour
                                hourly_batteries_charged +=1
                                # Count towards the total number of batteries charged
                                daily_batteries_charged += 1
                                # Append to the total energy required to charge that battery
                                energy_for_full_charge.append(hours_for_charging[battery] * charging_energy)
                            else:
                                pass
                    else:
                        break       # Stop charging once there is no more available solar energy

            # Store the number of batteries to which PV energy was delivered to during the hour in a list
            num_charging_hourly.append((day, hour, batteries_charging))
            
            # Store the number of batteries that were charged during the hour in a list
            num_batteries_charged_hourly.append((day, hour, hourly_batteries_charged))
        
        # Retain a list of the battery SoCs and corresponding energy for batteries that were not fully charged that day
        partial_charge_mask = soc < charged_soc                  # Create a boolean array mask where True means a battery is NOT fully charged
        carryover_soc = soc[partial_charge_mask].tolist()        # Creates a list for batteries where SoC is less than fully charged
        carryover_energy = energy[partial_charge_mask].tolist()

        # Store the number of batteries that were fully charged during the day in a list
        num_batteries_charged_daily.append(daily_batteries_charged)
        # Store the day number in a list
        day_num.append(day)

    # Create a dataframe for the number of batteries that were being charged on the hour
    batteries_charging_hourly = pd.DataFrame(num_charging_hourly, 
                                       columns=['date', 'hour', f'{vehicle}_batteries_charging'])
    
    # Create a dataframe for the hourly number of batteries charged
    charged_batteries_hourly = pd.DataFrame(num_batteries_charged_hourly, 
                                       columns=['date', 'hour', f'total_{vehicle}_batteries'])

    # Create a dataframe for the daily number of batteries charged
    charged_batteries_daily = pd.DataFrame(list(zip(day_num, num_batteries_charged_daily)),
               columns =['date', f'total_{vehicle}_batteries'])

    # Calculate statistics & print statements
    if num_batteries_charged_daily:
        total_annual_charged = sum(num_batteries_charged_daily)
        max_daily_charged = max(num_batteries_charged_daily)
        avg_daily_charged = np.floor(np.mean(num_batteries_charged_daily))

        if type.lower() == 'lead-acid':
            num_3w_served = np.floor(avg_daily_charged / 4)
        else:
            num_3w_served = avg_daily_charged
    else:
        total_annual_charged = 0
        max_daily_charged = 0
        avg_daily_charged = 0
        num_3w_served = 0 

    if energy_for_full_charge:
        average_energy_full_charge = np.mean(energy_for_full_charge)
    else:
        average_energy_full_charge = np.nan  # Or 0, or skip calculation

    return batteries_charging_hourly, charged_batteries_hourly, charged_batteries_daily


if __name__ == "__main__":
    main()