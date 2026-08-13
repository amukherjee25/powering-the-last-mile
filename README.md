# Solar-Based Charging Infrastructure Planning for Electric Autorickshaws
This is the data and code repository for the paper "Powering the Last Mile: Distributed, Solar-based Charging Infrastructure Planning for Electric Autorickshaws in West Bengal, India"

Additional Data
1. [India Administrative Boundaries](https://data.humdata.org/dataset/geoboundaries-admin-boundaries-for-india)
2. [India Population](https://hub.worldpop.org/geodata/summary?id=49804)

## Repository Structure  
<!-- TREE_START -->
```text
.
├── LICENSE
├── README.md
├── notebooks
│   ├── charging.ipynb
│   ├── economics.ipynb
│   ├── preprocess.ipynb
│   ├── siting.ipynb
│   └── spatial_wb.ipynb
├── pyproject.toml
├── src
│   ├── ev_infra
│      ├── __init__.py
│      ├── charging
│      │   ├── __init__.py
│      │   ├── calc_pv_degradation.py
│      │   ├── compile_results.py
│      │   ├── process_solar.py
│      │   ├── run_pv_sizing_block.py
│      │   └── run_pv_sizing_block.sh
│      ├── config.py
│      ├── economics
│      │   ├── __init__.py
│      │   ├── calc_costs.py
│      │   ├── calc_metrics.py
│      │   ├── discount_rate.py
│      │   ├── pv_capex.py
│      │   └── run_sensitivity.py
│      ├── preprocess
│      │   ├── __init__.py
│      │   ├── boundaries.py
│      │   ├── fleet.py
│      │   ├── population.py
│      │   └── rwi.py
│      ├── siting
│      │   ├── __init__.py
│      │   └── selection.py
│      ├── utils.py
│      └── viz
│          ├── __init__.py
│          ├── bivariate.py
│          ├── boxplot.py
│          ├── choropleth.py
│          ├── sensitivity.py
│          ├── sites_selected.py
│          ├── solar.py
│          └── style.py
```
<!-- TREE_END -->
```
