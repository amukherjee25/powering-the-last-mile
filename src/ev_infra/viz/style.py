"""Shared plotting helpers reused across the West Bengal choropleth maps:
north arrow annotation, district code labels, axis styling, and colorbar tick rounding."""

import numpy as np
import matplotlib.patheffects as path_effects


def round_whole(x):
    """Round x to nearest 1, 2, 5 × 10^n for clean ticks"""
    exponent = np.floor(np.log10(x))
    fraction = x / 10**exponent
    if fraction < 1.5:
        nice_fraction = 1
    elif fraction < 3.5:
        nice_fraction = 2
    elif fraction < 7.5:
        nice_fraction = 5
    else:
        nice_fraction = 10
    return int(nice_fraction * 10**exponent)


def add_north_arrow(ax):
    # Add a north arrow
    x, y, arrow_length = 0.95, 0.99, 0.05        # adjust arrow position and arrow length
    ax.annotate('N', xy=(x, y), xytext=(x, y - arrow_length),
                arrowprops=dict(facecolor='black', width=5, headwidth=15),
                ha='center', va='center', fontsize=16, xycoords=ax.transAxes)


def label_districts(ax, wb_districts):
    # Add district code labels
    for idx, row in wb_districts.iterrows():
        txt = ax.text(row.geometry.centroid.x, row.geometry.centroid.y, s=row['code'],
                fontsize=16, fontweight='bold', ha='center', color='black')

        # Add a black outline around the text
        txt.set_path_effects([
            path_effects.Stroke(linewidth=2.5, foreground='white'),  # outline
            path_effects.Normal()  # normal text on top
        ])


def style_map_axes(ax):
    # Remove latitude and longitude ticks
    ax.set_xticks([])   # Remove x-axis (longitude) ticks
    ax.set_yticks([])   # Remove y-axis (latitude) ticks
    ax.axis('off')      # Remove all borders of plot
