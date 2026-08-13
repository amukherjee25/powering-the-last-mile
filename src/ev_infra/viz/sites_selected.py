"""Plot the priority blocks selected for PV-based charging infrastructure siting."""

import matplotlib.pyplot as plt
import matplotlib.lines as mlines

from ev_infra.viz.style import add_north_arrow, label_districts, style_map_axes


def plot_site_selection(df_blocks_selected, wb_blocks, wb_districts, west_bengal):
    # --- Plot the spatial map to visualize the results ---
    # Plot the results
    fig, ax = plt.subplots(figsize=(15, 15))

    # Plot the relevant boundaries
    wb_blocks.plot(ax=ax, color='whitesmoke')
    df_blocks_selected.plot(ax=ax, color='crimson', alpha=0.7)
    wb_blocks.boundary.plot(ax=ax, color='black', alpha=0.5, linewidth=0.4)
    wb_districts.boundary.plot(ax=ax, color='black', alpha=0.7, linewidth=1.2)
    west_bengal.boundary.plot(ax=ax, color='black', linewidth=1.5)

    label_districts(ax, wb_districts)

    # Plot selected blocks only if the dataframe is not empty
    if not df_blocks_selected.empty:
        centroids = df_blocks_selected.geometry.centroid
        centroids.plot(ax=ax, marker='^', ec='black', fc='black', markersize=30, zorder=4, label='Selected Blocks')
    else:
        print('No blocks were selected for siting due to financial limiations.')

    # Add a custom handle for village centroids that are >5 km away from nearest metro and train station
    site_handle = mlines.Line2D([0], [0], marker='^', markeredgecolor='black', markerfacecolor='black', lw=0, markersize=14, label='Selected Blocks')

    # Add a general legend for bare land and colorbar
    ax.legend(handles=[site_handle], loc='upper left', frameon=False, fontsize=16)

    add_north_arrow(ax)
    style_map_axes(ax)

    # Customize the plot
    plt.tight_layout()
    plt.show()

    return fig, ax