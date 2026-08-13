"""Read raw per-district hourly solar data and compute district-level GHI (Global
Horizontal Irradiance) statistics for characterizing solar resource across West Bengal."""

import os
import pandas as pd

from ev_infra.config import DATA_RAW_DISTRICT_SOLAR

# Re-map raw file-name district IDs to the full district names used in the fleet dataframe
DISTRICT_ID_REMAP = {
    'south24': 'South Twenty Four Parganas',
    'north24': 'North Twenty Four Parganas',
    'kolkata': 'Kolkata',
    'haora': 'Haora',
    'hugli': 'Hugli',
    'nadia': 'Nadia',
    'barddhaman': 'Barddhaman',
    'purba-medinipur': 'Purba Medinipur',
    'paschim-medinipur': 'Paschim Medinipur',
    'jhargram': 'Jhargram',
    'bankura': 'Bankura',
    'puruliya': 'Puruliya',
    'paschim-barddhaman': 'Paschim Barddhaman',
    'birbhum': 'Birbhum',
    'murshidabad': 'Murshidabad',
    'maldah': 'Maldah',
    'dakshin-dinajpur': 'Dakshin Dinajpur',
    'uttar-dinajpur': 'Uttar Dinajpur',
    'koch-bihar': 'Koch Bihar',
    'jalpaiguri': 'Jalpaiguri',
    'darjiling': 'Darjiling',
    'alipurduar': 'Alipurduar',
    'kalimpong': 'Kalimpong'
}


def pv_output_process(df):
    # Rename the Time column and convert it to datetime format
    df['Time'] = pd.to_datetime(df['Time'], format='mixed', dayfirst=False)
    df = df.rename(columns={'Time': 'date_time'})

    # Extract the hour value for each time into a separate column
    df['date'] = df['date_time'].dt.date
    df['hour'] = df['date_time'].dt.hour
    df['month'] = df['date_time'].dt.month

    return df


def load_district_solar(solar_dir=DATA_RAW_DISTRICT_SOLAR):
    """Read raw per-district hourly solar CSVs, preprocess datetime columns, and remap
    district IDs to their full district names."""
    # List all CSV files in the folder
    csv_files = [f for f in os.listdir(solar_dir) if f.endswith('.csv')]

    # Create a dictionary to store the DataFrames for each district
    district_solar = {}

    # Loop through each file and read it into a DataFrame
    for csv_file in csv_files:
        district_id = csv_file.split('.')[0]  # Use the file name as the district ID
        district_df = pd.read_csv(solar_dir / csv_file)  # Read the CSV into a DataFrame

        # Pre-process the PV output data using pv_output_process function
        district_df = pv_output_process(district_df)

        # Store the processed DataFrame in the dictionary
        district_solar[district_id] = district_df

    # Re-map the keys for the solar dictionary to match the district names in the fleet dataframe
    district_solar_remap = {
        DISTRICT_ID_REMAP.get(district_id, district_id): df
        for district_id, df in district_solar.items()
    }

    return district_solar_remap


def compile_district_ghi(district_solar, wb_districts):
    """Compile daily and monthly global solar irradiance (GHI) for each district from
    per-district hourly solar dataframes."""
    # Create a compiled dataframe with the daily and monthly global solar irradiance for each district
    compiled_daily_ghi = []
    monthly_ghi_sum = []
    monthly_ghi_avg = []

    for district_name, df in district_solar.items():
        # Make sure the data is preprocessed
        if 'date' not in df.columns:
            df = pv_output_process(df)

        # Group by date and calculate the total daily irradiation (sum of hourly values)
        daily_irradiation = df.groupby('date')['global_solar_kw/m2'].sum().reset_index()

        # Group by month and calculate the average monthly irradiation (mean of daily values)
        monthly_irradiation_sum = df.groupby('month')['global_solar_kw/m2'].sum().reset_index()
        monthly_irradiation_avg = df.groupby('month')['global_solar_kw/m2'].mean().reset_index()

        # Add district name
        daily_irradiation['district'] = district_name
        monthly_irradiation_sum['district'] = district_name
        monthly_irradiation_avg['district'] = district_name

        # Append to compiled list
        compiled_daily_ghi.append(daily_irradiation)
        monthly_ghi_sum.append(monthly_irradiation_sum)
        monthly_ghi_avg.append(monthly_irradiation_avg)

    # Combine all district daily GHI into one dataframe
    district_daily_ghi = pd.concat(compiled_daily_ghi, ignore_index=True)
    district_monthly_ghi_sum = pd.concat(monthly_ghi_sum, ignore_index=True)
    district_monthly_ghi_avg = pd.concat(monthly_ghi_avg, ignore_index=True)

    # Rename the column for the daily GHI
    district_daily_ghi = district_daily_ghi.rename(columns={
        'global_solar_kw/m2': 'daily_ghi_kwh/m2/day'
    })
    district_monthly_ghi_sum = district_monthly_ghi_sum.rename(columns={
        'global_solar_kw/m2': 'monthly_tot_ghi_kwh/m2/day'
    })
    district_monthly_ghi_avg = district_monthly_ghi_avg.rename(columns={
        'global_solar_kw/m2': 'monthly_avg_ghi_kwh/m2/day'
    })

    # Determine the average daily GHI for each district
    district_avg_daily_ghi = district_daily_ghi.groupby('district')['daily_ghi_kwh/m2/day'].mean()
    district_avg_daily_ghi.columns = ['district', 'avg_ghi_kwh/m2/day']

    # Merge GHI data with spatial boundary data of districts
    wb_districts_avg_ghi = wb_districts.merge(district_avg_daily_ghi, on='district')
    wb_districts_avg_ghi = wb_districts_avg_ghi.rename(columns={
        'daily_ghi_kwh/m2/day': 'avg_ghi_kwh/m2/day'})

    return {
        'daily': district_daily_ghi,
        'monthly_sum': district_monthly_ghi_sum,
        'monthly_avg': district_monthly_ghi_avg,
        'district_avg_ghi': wb_districts_avg_ghi,
    }


def min_max_avg_annual_ghi(df):
    # Calculate the annual GHI per district
    annual_ghi = df.groupby('district')['daily_ghi_kwh/m2/day'].sum()

    # Best solar day (max output)
    max_ghi_district = annual_ghi.idxmax()
    max_ghi = annual_ghi.max()
    print(f"District with max annual GHI: {max_ghi_district} with output: {max_ghi:.2f} kWh/m2")

    # Worst solar day (min output)
    min_ghi_district = annual_ghi.idxmin()
    min_ghi = annual_ghi.min()
    print(f"District with min annual GHI: {min_ghi_district} with output: {min_ghi:.2f} kWh/m2")

    # Average solar day (day closest to the mean daily output)
    average_ghi = annual_ghi.mean()
    closest_idx = (annual_ghi - average_ghi).abs().idxmin()
    average_ghi_district = closest_idx
    average_ghi = annual_ghi.loc[closest_idx]
    print(f"District with average annual GHI: {average_ghi_district} with output: {average_ghi:.2f} kWh/m2")

    return max_ghi_district, min_ghi_district, average_ghi_district


def best_worst_avg_solar_days(df_daily_ghi, district):
    # Extract the rows for specified district
    df = df_daily_ghi[df_daily_ghi['district'] == district]

    # Best solar day (max output)
    best_solar_idx = df['daily_ghi_kwh/m2/day'].idxmax()
    peak_day = df.loc[best_solar_idx, 'date']
    max_solar_output = df.loc[best_solar_idx, 'daily_ghi_kwh/m2/day']
    print(f"Best solar day: {peak_day} with output: {max_solar_output:.2f} kWh/m2")

    # Worst solar day (min output)
    worst_solar_idx = df['daily_ghi_kwh/m2/day'].idxmin()
    min_day = df.loc[worst_solar_idx, 'date']
    min_solar_output = df.loc[worst_solar_idx, 'daily_ghi_kwh/m2/day']
    print(f"Worst solar day: {min_day} with output: {min_solar_output:.2f} kWh/m2")

    # Average solar day (day closest to the mean daily output)
    average_pv = df['daily_ghi_kwh/m2/day'].mean()
    closest_idx = (df['daily_ghi_kwh/m2/day'] - average_pv).abs().idxmin()
    average_day = df.loc[closest_idx, 'date']
    average_solar_output = df.loc[closest_idx, 'daily_ghi_kwh/m2/day']
    print(f"Average solar day: {average_day} with output: {average_solar_output:.2f} kWh/m2")

    return peak_day, min_day, average_day
