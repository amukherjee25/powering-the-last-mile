"""Plot NPV/LCOE sensitivit for the economics analysis of PV-based charging infrastructure."""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter

def plot_npv_sensitivity(block_economics):
    """Plot how average NPV (and its 2nd-98th percentile band) varies across charging tariffs."""
    # Aggregate and determine the average NPV across all blocks based on different charging tariffs
    avg_npv_per_tariff = block_economics.groupby('tariff_inr')['npv'].agg(['mean', 'std']).reset_index()

    # Compute the quantile bounds (2% and 98%) to exclude the bottom 2% and top 2% of NPV outliers
    q05 = block_economics.groupby('tariff_inr')['npv'].quantile(0.02)
    q95 = block_economics.groupby('tariff_inr')['npv'].quantile(0.98)

    # Compute the tariff where mean NPV crosses zero (interpolated)
    zero_npv_tariff = np.interp(
        0,                                                  # target mean NPV
        avg_npv_per_tariff['mean'].values / 1e5,                   # y-values (npv)
        avg_npv_per_tariff['tariff_inr'].values             # x-values (tariff)
    )

    # Plot sensitivity results
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot the variation in NPV with respect to altering charging tariff
    ax.plot(avg_npv_per_tariff['tariff_inr'],
            avg_npv_per_tariff['mean'] / 1e5,
            linewidth=2,
            color='darkgreen',
            label='Average Net Present Value')
    ax.fill_between(
        avg_npv_per_tariff['tariff_inr'],
        q05 / 1e5,
        q95 / 1e5,
        alpha=0.3,
        color='lightgreen',
        label='98% Sensitivity'
    )

    # Move axes (spines) to the middle
    ax.spines['bottom'].set_position(('data', 0))
    ax.spines['left'].set_position(('data', zero_npv_tariff))

    # Hide the top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Set custom tick formatting (2 decimal places for tariff)
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.2f'))

    # Get the default y-ticks
    yticks = ax.get_yticks()

    # Exclude 0
    yticks = [y for y in yticks if y != 0]

    # Apply the new ticks
    ax.set_yticks(yticks)

    # Remove built-in labels
    ax.set_xlabel('')
    ax.set_ylabel('')

    # Add custom label at specific data coordinates
    ax.text(0.63, 0.2, 'Charging Tariff (INR/kWh)',
            transform=ax.transAxes,
            ha='left', va='top', fontsize=16, fontweight='bold')

    ax.text(zero_npv_tariff + 1.9, max(yticks),
            'Net Present Value (INR Lakh)', ha='center', va='bottom',
            fontsize=16, fontweight='bold', rotation=0)

    # Increase font size of tick labels
    ax.tick_params(axis='both', which='major', labelsize=14)

    # Customize the plot
    plt.legend(fontsize=14, loc='upper right', frameon=False)
    plt.tight_layout()
    plt.show()

    return fig, ax