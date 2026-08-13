"""Generic choropleth plotting for West Bengal block/district maps: population size,
fleet size, RWI, and LCOE all share this same rendering logic, differing only in
which column is plotted, whether it's log-normalized, and how ticks are formatted."""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import LogNorm

from ev_infra.viz.style import add_north_arrow, label_districts, style_map_axes, round_whole


def plot_choropleth(
    df,
    column,
    wb_districts,
    west_bengal,
    cbar_label,
    cmap='Blues',
    boundary_gdf=None,
    log_normalize=False,
    n_ticks=6,
    tick_fmt='{:.0f}',
    tick_divisor=1,
    tick_scale_label=None,
    exclude_top_outliers=0,
    outlier_color='#022B1A',
    figsize=(15, 15),
):
    # Boundary layer defaults to the plotted dataframe itself, unless a separate
    # (e.g. unfiltered) boundary layer is passed in, as with the LCOE outlier map
    boundary_gdf = boundary_gdf if boundary_gdf is not None else df

    # Optionally exclude the top N outliers from the color scale and plot them separately
    if exclude_top_outliers > 0:
        plot_df = df.sort_values(column, ascending=True).iloc[:-exclude_top_outliers]
        outlier_df = df.nlargest(exclude_top_outliers, column)
    else:
        plot_df = df
        outlier_df = None

    # Optionally log-normalize the column for color mapping (colorbar ticks stay in raw units)
    if log_normalize:
        plot_df = plot_df.copy()
        plot_df[f'{column}_norm'] = np.log1p(plot_df[column])
        plot_column = f'{column}_norm'
        vmin_raw = plot_df[column][plot_df[column] > 0].min()
    else:
        plot_column = column
        vmin_raw = plot_df[column].min()

    vmax_raw = plot_df[column].max()

    fig, ax = plt.subplots(figsize=figsize)
    cmap_obj = plt.get_cmap(cmap)

    norm = LogNorm(vmin=vmin_raw, vmax=vmax_raw) if log_normalize else mcolors.Normalize(vmin=vmin_raw, vmax=vmax_raw)

    # Plot the boundaries
    plot_df.plot(ax=ax, column=plot_column, cmap=cmap_obj, alpha=0.75)
    if outlier_df is not None:
        outlier_df.plot(ax=ax, column=column, color=outlier_color)
    boundary_gdf.boundary.plot(ax=ax, color='black', alpha=0.5, linewidth=0.4)
    wb_districts.boundary.plot(ax=ax, color='black', alpha=0.7, linewidth=1.2)
    west_bengal.boundary.plot(ax=ax, color='black', linewidth=1.5)

    label_districts(ax, wb_districts)

    # Add a colorbar with the appropriate ticks and labels
    sm = plt.cm.ScalarMappable(cmap=cmap_obj, norm=norm)
    sm.set_array([])  # Only needed for older versions of Matplotlib

    # Create the colorbar
    # Manually position the colorbar (top left)
    cax = fig.add_axes([0.2, 0.95, 0.28, 0.025])  # [left, bottom, width, height]
    cbar = fig.colorbar(sm, cax=cax, orientation='horizontal', alpha=0.75)

    if log_normalize:
        # Log-space positions, rounded to nice values
        log_ticks = np.logspace(np.log10(vmin_raw), np.log10(vmax_raw), n_ticks)
        tick_vals = sorted(set(round_whole(val) for val in log_ticks))
    else:
        # Linear space ticks
        tick_vals = np.linspace(vmin_raw, vmax_raw, n_ticks)

    cbar.set_ticks(tick_vals)
    cbar.set_ticklabels([tick_fmt.format(val / tick_divisor) for val in tick_vals], fontsize=16)

    cbar.ax.set_xlabel(cbar_label, rotation=0, labelpad=10, fontsize=16, fontweight='bold')

    # Add a scale annotation (e.g. "×10³") at the end of the colorbar, if provided
    if tick_scale_label:
        cax.annotate(tick_scale_label, xy=(1.02, 0.5), xycoords='axes fraction',
                     fontsize=16, fontweight='bold', va='center', ha='left')

    add_north_arrow(ax)
    style_map_axes(ax)

    plt.tight_layout()
    plt.show()

    return fig, ax
