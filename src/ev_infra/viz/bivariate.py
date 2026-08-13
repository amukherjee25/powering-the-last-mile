"""Distribution plots and bivariate choropleth mapping for combining two
variables (e.g. population size and 3W fleet demand) into a single composite map."""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
from geopandas import GeoDataFrame
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler, PowerTransformer

from ev_infra.viz.style import add_north_arrow, label_districts, style_map_axes


def data_distribution_transform(df, col_name):
    df = df.copy()
    col = col_name

    # Apply various scalers
    df['minmax'] = MinMaxScaler().fit_transform(df[[col]])
    df['standard'] = StandardScaler().fit_transform(df[[col]])
    df['robust'] = RobustScaler().fit_transform(df[[col]])
    df['power_yeojohnson'] = PowerTransformer(method='yeo-johnson').fit_transform(df[[col]])
    df['log'] = np.log1p(df[col])  # log1p handles zero

    # Set up plotting
    fig, axes = plt.subplots(3, 2, figsize=(14, 12))
    axes = axes.flatten()

    scalers = [col, 'minmax', 'standard', 'robust', 'power_yeojohnson', 'log']
    titles = [col, 'MinMaxScaler', 'StandardScaler', 'RobustScaler', 'PowerTransformer (Yeo-Johnson)', 'Log Transform']

    for ax, scaler, title in zip(axes, scalers, titles):
        sns.histplot(df[scaler], bins=30, kde=True, ax=ax, color='steelblue')
        ax.set_title(title)
        ax.set_xlabel('')
        ax.set_ylabel('Density')

    plt.tight_layout()
    plt.show()

    return fig, axes


def bivariate_classification(df1, df2, col1_name, col2_name, merge_col='block', num_score_reverse=False, custom_score=None):
    """
    Classify and merge two dataframes on a common key, creating a composite classification and numeric mapping.

    Parameters:
        df1 (pd.DataFrame): First dataframe containing col1_name to classify.
        df2 (pd.DataFrame): Second dataframe containing col2_name to classify.
        col1_name (str): Column name in df1 to classify (e.g., 'total_pop').
        col2_name (str): Column name in df2 to classify (e.g., '100%_conversion').
        on (str): Column name to merge on (default is 'block').

    Returns:
        pd.DataFrame: Composite dataframe with bivariate classifications and numeric class.
    """

    # Define boundaries for classificatiin
    def define_bins(series):
        min_val = series.min()
        max_val = series.max()
        return np.linspace(min_val, max_val, 3)

    bins_var1 = define_bins(df1[col1_name])
    bins_var2 = define_bins(df2[col2_name])

    # Define first variable boundaries based on min and max values
    # Low = 1, Medium = 2, High = 3
    low_var1 = bins_var1[0]
    medium_var1 = bins_var1[1]
    high_var1 = bins_var1[2]

    # Define second variable boundaries based on min and max values
    # Low = A, Medium = B, High = C
    low_var2 = bins_var2[0]
    medium_var2 = bins_var2[1]
    high_var2 = bins_var2[2]

    # Function to classify a value in variable 1 dataframe
    def classify_var1(value):
        if pd.isna(value):
            return '0'  # Low if NaN
        elif value >= medium_var1 and value <= high_var1:
            return '2'  # High
        elif value > low_var1 and value <= medium_var1:
            return '1'  # Medium
        elif value >= low_var1 and value < medium_var1:
            return '0'  # Low

    # Function to classify a value in variable 2 dataframe
    def classify_var2(value):
        if pd.isna(value):
            return 'A'  # Low if NaN
        elif value >= medium_var2 and value <= high_var2:
            return 'C'  # High
        elif value > low_var2 and value <= medium_var2:
            return 'B'  # Medium
        elif value >= low_var2 and value < medium_var2:
            return 'A'  # Low

    # Apply classification function to both dataframes
    df1[f'class_{col1_name}'] = df1[col1_name].apply(classify_var1)
    df2[f'class_{col2_name}'] = df2[col2_name].apply(classify_var2)

    # Merge the two dataframes to create a composite classification dataframe
    df_composite = df1.merge(df2, on=merge_col)
    # Geometry fix if exists
    if 'geometry_x' in df_composite.columns:
        df_composite = df_composite.rename(columns={'geometry_x': 'geometry'})
        df_composite = GeoDataFrame(df_composite, geometry='geometry')
    # Rename relevant columns
    df_composite = df_composite.rename(columns={f'{merge_col}_x': merge_col, 'district_x': 'district'})
    # Drop irrelevant columns and rename columns
    df_composite = df_composite.drop(columns=[col for col in df_composite.columns if col.endswith('_y')])
    # Drop duplicates
    df_composite = df_composite[~df_composite.duplicated(subset=[merge_col, 'district', 'geometry'], keep='first')]

    # Create composite classification
    df_composite['comp_class'] = (
        df_composite[f'class_{col1_name}'].astype(str) +
        df_composite[f'class_{col2_name}'].astype(str)
    )

    # Map to numeric values
    if custom_score is not None:
        # Ensure that score rank array is of the correct shape
        if not isinstance(custom_score, np.ndarray) or custom_score.shape != (3, 3):
            raise ValueError('custom score array must be shape 3x3.')

        # Map layout (rows: A (low) to C (high), columns: 0 (low) to 2 (high))
        class_grid = np.array([
            ['0C', '1C', '2C'],
            ['0B', '1B', '2B'],
            ['0A', '1A', '2A']
        ])

        # Flatten the arrays and create custom dictionary for composite classification
        flat_class = class_grid.flatten()
        flat_score = custom_score.flatten()
        bivar_class_num = dict(zip(flat_class, flat_score))
    else:
        # Default scoring if no custom score is provided
        if num_score_reverse:
            # When num_score_reverse = True → reverse the pattern
            # High–High (2C) gets LOW score (3)
            # Values increase going top→bottom, right→left
            bivar_class_num = {
                '0C': 9, '1C': 6, '2C': 3,
                '0B': 8, '1B': 5, '2B': 2,
                '0A': 7, '1A': 4, '2A': 1
            }
        else:
            # When num_score_reverse = False → default pattern
            # High–High (2C) gets HIGH score (9)
            # Values decrease top→bottom, right→left
            bivar_class_num = {
                '0C': 3, '1C': 6, '2C': 9,
                '0B': 2, '1B': 5, '2B': 8,
                '0A': 1, '1A': 4, '2A': 7
            }

    df_composite['comp_num'] = df_composite['comp_class'].map(bivar_class_num)

    # Ensure categorical columns are strings
    cat_cols = df_composite.select_dtypes(include='category').columns
    df_composite[cat_cols] = df_composite[cat_cols].astype(str)

    # Ensure categorical columns are converted to strings
    for col in df_composite.columns:
        if isinstance(df_composite[col].dtype, pd.CategoricalDtype):
            df_composite[col] = df_composite[col].astype(str)

    # Convert to GeoDataFrame if geometry is present
    if 'geometry' in df_composite.columns:
        df_composite = GeoDataFrame(df_composite, geometry='geometry')

    return df_composite


def bivariate_plotting(df_composite, var1_legend, var2_legend, wb_districts, west_bengal, reverse_var1=False, reverse_var2=False):
    # Define the composite classes and their associated colors
    comp_classes = ['0A', '0B', '0C', '1A', '1B', '1C', '2A', '2B', '2C']
    colors = [
        "#e8e8e8", "#ecbbe3", "#da6fc4",
        "#ace4e4", "#a5add3", "#8c62aa",
        "#53b6b6", "#457c97", "#1e2550"
    ]
    cmap = mcolors.ListedColormap(colors)

    # Apply mirroring if necessary
    def mirror_class(c, reverse_x=False, reverse_y=False):
        """Mirror a single comp_class string along reversed axes"""
        # c is like '0A', '2C', etc.
        col, row = c[0], c[1]
        if reverse_x:
            col = str(2 - int(col))  # 0↔2, 1 stays
        if reverse_y:
            row = chr(ord('A') + 2 - (ord(row) - ord('A')))  # A↔C, B stays
        return col + row

    df_composite = df_composite.copy()
    if reverse_var1 or reverse_var2:
        df_composite['comp_class'] = df_composite['comp_class'].apply(
            lambda x: mirror_class(x, reverse_var1, reverse_var2)
        )

    # Create a categorical mapping of 'comp_class' to the corresponding color
    df_composite['comp_class'] = pd.Categorical(df_composite['comp_class'], categories=comp_classes)

    alpha = 0.9  # alpha argument to make it more/less transperent

    # Plot the results
    fig, ax = plt.subplots(figsize=(12, 12))
    df_composite.plot(ax=ax, column='comp_class', cmap=cmap, alpha=alpha, legend=False)
    df_composite.boundary.plot(ax=ax, color='black', alpha=0.5, linewidth=0.4)

    # Plot the boundaries
    wb_districts.boundary.plot(ax=ax, color='black', alpha=0.7, linewidth=1.2)
    west_bengal.boundary.plot(ax=ax, color='black', linewidth=1.5)

    label_districts(ax, wb_districts)

    # Draw a bivariate chloropleth legend (3x3 "box" as 3 columns)
    # The xmin and xmax arguments axvspan are defined to create equally sized small boxes
    ax2 = fig.add_axes([0.2, 0.85, 0.1, 0.1])  # add new axes to place the legend there
                                                # and specify its location

    # Column 1
    ax2.axvspan(xmin=0, xmax=0.33, ymin=0, ymax=0.33, alpha=alpha, color=colors[0])
    ax2.axvspan(xmin=0, xmax=0.33, ymin=0.33, ymax=0.66, alpha=alpha, color=colors[1])
    ax2.axvspan(xmin=0, xmax=0.33, ymin=0.66, ymax=1, alpha=alpha, color=colors[2])

    # Column 2
    ax2.axvspan(xmin=0.33, xmax=0.66, ymin=0, ymax=0.33, alpha=alpha, color=colors[3])
    ax2.axvspan(xmin=0.33, xmax=0.66, ymin=0.33, ymax=0.66, alpha=alpha, color=colors[4])
    ax2.axvspan(xmin=0.33, xmax=0.66, ymin=0.66, ymax=1, alpha=alpha, color=colors[5])

    # Column 3
    ax2.axvspan(xmin=0.66, xmax=1, ymin=0, ymax=0.33, alpha=alpha, color=colors[6])
    ax2.axvspan(xmin=0.66, xmax=1, ymin=0.33, ymax=0.66, alpha=alpha, color=colors[7])
    ax2.axvspan(xmin=0.66, xmax=1, ymin=0.66, ymax=1, alpha=alpha, color=colors[8])

    # Annoate the bivariate legend
    ax2.tick_params(axis='both', which='both', length=0)  # remove ticks from the big box
    ax2.axis('off')  # turn off its axis

    # Draw axis arrows
    # x-axis arrow
    if reverse_var1:
        ax2.annotate("", xy=(0, 0), xytext=(1, 0), arrowprops=dict(arrowstyle="->", lw=2))
    else:
        ax2.annotate("", xy=(1, 0), xytext=(0, 0), arrowprops=dict(arrowstyle="->", lw=2))

    # y-axis arrow
    if reverse_var2:
        ax2.annotate("", xy=(0, 0), xytext=(0, 1), arrowprops=dict(arrowstyle="->", lw=2))
    else:
        ax2.annotate("", xy=(0, 1), xytext=(0, 0), arrowprops=dict(arrowstyle="->", lw=2))

    ax2.text(s=var1_legend, x=0.05, y=-0.18, fontweight='bold', fontsize=10)  # annotate x axis
    ax2.text(s=var2_legend, x=-0.18, y=0.1, rotation=90, fontweight='bold', fontsize=10)  # annotate y axis

    # Enable ticks (default length should work)
    ax2.tick_params(axis='both', which='major', length=3)
    # Define the border around legend
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.spines['bottom'].set_visible(True)
    ax2.spines['left'].set_visible(True)

    add_north_arrow(ax)
    style_map_axes(ax)

    plt.tight_layout()
    plt.show()

    return fig, ax
