"""Faceted boxplot comparison across scenarios (fleet conversion, tariff, etc.), one
subplot per scenario, sharing a category-ordered y-axis. Reused for PV system size
comparisons (charging) and financial metric comparisons (economics)."""

import matplotlib.pyplot as plt
import seaborn as sns


def plot_scenario_boxplots(data_by_scenario, value_col, colors, x_label,
                            category_col='district', code_col='code',
                            order_scenario=None, title_suffix='Conversion',
                            showfliers=False, flierprops=None):
    """
    Parameters
    ----------
    data_by_scenario : dict[str, pd.DataFrame]
        Scenario name -> dataframe containing category_col, code_col, and value_col.
    value_col : str
        Column to plot on the x-axis (e.g. 'pv_size', 'npv').
    colors : dict[str, str]
        Scenario name -> hex color for that scenario's boxplot.
    x_label : str
        Shared x-axis label across all subplots.
    category_col : str
        Column to plot on the y-axis (default 'district').
    code_col : str
        Column used to build combined "category (code)" labels on the first subplot.
    order_scenario : str
        Which scenario's data to use for computing category order (by descending median
        value_col). Defaults to the first key in data_by_scenario.
    title_suffix : str
        Appended to each subplot's title as f'{scenario} {title_suffix}'.
    """
    scenarios = list(data_by_scenario.keys())
    n_scenarios = len(scenarios)

    order_scenario = order_scenario or scenarios[0]

    # Determine the order of categories (use one scenario or combined medians)
    category_order = (
        data_by_scenario[order_scenario].groupby(category_col)[value_col]
        .median()
        .sort_values(ascending=False)
        .index
    )

    # Create a single row of subplots
    fig, axes = plt.subplots(
        1, n_scenarios,
        figsize=(7 * n_scenarios, len(category_order) * 0.5),
        sharey=True,
        sharex=True
    )

    # If only one scenario, axes is not iterable
    if n_scenarios == 1:
        axes = [axes]

    # Loop through scenarios and plot each in its own subplot
    for ax, scenario in zip(axes, scenarios):
        df = data_by_scenario[scenario]

        # Color fliers to match this scenario's box color, if flier styling was requested
        scenario_flierprops = None
        if showfliers and flierprops is not None:
            scenario_flierprops = dict(flierprops, 
                                       markerfacecolor=colors[scenario], 
                                       markeredgecolor=colors[scenario])

        # Plot the box-and-whisker plot
        sns.boxplot(
            data=df,
            y=category_col,
            x=value_col,
            order=category_order,
            orient='h',
            width=0.5,
            showfliers=showfliers,
            color=colors[scenario],
            linewidth=0,
            boxprops=dict(facecolor=colors[scenario], alpha=1),
            whiskerprops=dict(color=colors[scenario], alpha=0.4, linewidth=16),
            capprops=dict(color=colors[scenario], linewidth=0),
            medianprops=dict(color='white', linewidth=2),
            flierprops=scenario_flierprops,
            ax=ax
        )

        ax.set_title(f'{scenario} {title_suffix}', fontsize=16, fontweight='bold')
        ax.set_xlabel('')
        ax.set_ylabel('')
        ax.tick_params(axis='both', which='major', labelsize=16)

        if ax == axes[0]:
            # Create a lookup table with both category and code
            df_labels = df[[category_col, code_col]].copy()

            # Create combined labels
            df_labels[f'{category_col}_label'] = df_labels[category_col] + ' (' + df_labels[code_col] + ')'

            # Use the category order to define label order
            label_map = df_labels.drop_duplicates(subset=[category_col]).set_index(category_col)[f'{category_col}_label']

            # Apply the labels in the correct order
            new_labels = [label_map.get(cat, cat) for cat in category_order]

            ax.set_yticklabels(new_labels)
        else:
            ax.tick_params(axis='y', which='both', left=False, labelleft=False)

        # Clean up borders
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(True)
        ax.spines['left'].set_visible(ax == axes[0])  # only show y-axis on first plot

    # Add a common x-axis label
    fig.supxlabel(x_label, fontsize=16, fontweight='bold')

    plt.tight_layout()
    plt.show()

    return fig, axes
