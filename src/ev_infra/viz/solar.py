"""Plot solar resource (GHI) comparisons across West Bengal districts."""

from datetime import timedelta

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


def plot_ghi_annual_trend(district_daily_ghi, max_district, min_district):
    # Convert the day column to datetime format
    district_daily_ghi = district_daily_ghi.copy()
    district_daily_ghi['date'] = pd.to_datetime(district_daily_ghi['date'], format='mixed', dayfirst=False)

    # Extract the GHI data for min, max districts
    max_daily_ghi = district_daily_ghi[district_daily_ghi['district'] == max_district].copy()
    min_daily_ghi = district_daily_ghi[district_daily_ghi['district'] == min_district].copy()

    # Calculate the rolling average for daily GHI over the course of the year
    max_daily_ghi['ghi_rollavg'] = max_daily_ghi['daily_ghi_kwh/m2/day'].rolling(window=7).mean()
    min_daily_ghi['ghi_rollavg'] = min_daily_ghi['daily_ghi_kwh/m2/day'].rolling(window=7).mean()

    # Create a figure for each system size and axes for plotting all lines
    fig, ax = plt.subplots(figsize=(12, 5.5))

    # Plot the 7 day rolling average
    ax.plot(max_daily_ghi['date'], max_daily_ghi['ghi_rollavg'],
            color='darkred', alpha=0.7, linewidth=2, label='Maximum Annual GHI')
    ax.plot(min_daily_ghi['date'], min_daily_ghi['ghi_rollavg'],
            color='darkorange', alpha=0.7, linewidth=2, label='Minimum Annual GHI')

    # Format the x-axis to show only months
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))  # Show numeric month (01 to 12)

    # Set labels, title, and y limit
    ax.set_xlabel('Month', fontsize=16, fontweight='bold')
    ax.set_ylabel('Average Daily GHI (kWh/m\u00b2/day)', fontsize=16, fontweight='bold')

    # Increase font size of tick labels
    ax.tick_params(axis='both', which='major', labelsize=14)

    # Set limits on the start and end of the year
    start_date = pd.to_datetime(max_daily_ghi['date'].dt.to_period('Y').min().start_time)
    end_date = pd.to_datetime(max_daily_ghi['date'].dt.to_period('Y').max().end_time) - pd.Timedelta(days=1)
    # Add padding of ~6 days on each side (adjust as desired)
    padding = timedelta(days=10)
    ax.set_xlim([start_date - padding, end_date])
    ax.set_ylim(1, round(max_daily_ghi['ghi_rollavg'].max() + 0.5))

    # Define the border around the plot
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(True)
    ax.spines['left'].set_visible(True)

    ax.spines['left'].set_bounds(ax.get_yticks()[0], ax.get_yticks()[-1])

    # Add a legend
    plt.legend(fontsize=13, loc='upper right', frameon=False)
    plt.show()

    return fig, ax
