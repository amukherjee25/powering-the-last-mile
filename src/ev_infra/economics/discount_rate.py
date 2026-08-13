"""Estimate a risk-adjusted discount rate from historical rates using a Gaussian Mixture
Model and Monte Carlo simulation."""

import pandas as pd
from sklearn.mixture import GaussianMixture

from ev_infra.config import RAW_DISCOUNT_RATE_CSV


def fix_year(date_str):
    """Convert two-digit years: assume 1900s for >= 68, else 2000s."""
    parts = date_str.split('/')
    if len(parts) == 3:
        month, day, year = parts
        year = int(year)
        if year >= 68:
            year += 1900
        else:
            year += 2000
        return f"{month}/{day}/{year}"
    return date_str


def load_historical_discount_rates(csv_path=RAW_DISCOUNT_RATE_CSV):
    # Read in the historical discount rate
    historical_discount_rates = pd.read_csv(csv_path)

    # Apply the fix_year function
    historical_discount_rates['observation_date'] = historical_discount_rates['observation_date'].apply(fix_year)

    # Convert date column to datetime format
    historical_discount_rates['observation_date'] = pd.to_datetime(
        historical_discount_rates['observation_date'], format='%m/%d/%Y')

    # Rename the column
    historical_discount_rates = historical_discount_rates.rename(
        columns={'INTDSRINM193N': 'discount_rate'})

    return historical_discount_rates


def estimate_risk_adjusted_discount_rate(historical_discount_rates, n_components=2, n_samples=10000, random_state=42):
    """Fit a Gaussian Mixture Model to historical discount rates and estimate a risk-adjusted
    rate via Monte Carlo simulation."""
    # Obtain the data for applying for Gaussian Mixture Model
    # Drop any NaN values and reshape into column vector (infer the number of rows automatically (-1), and make it 1 column)
    model = historical_discount_rates['discount_rate'].dropna().values.reshape(-1, 1)

    # Fit Gaussian Mixture Model
    gmm = GaussianMixture(n_components=n_components, random_state=random_state).fit(model)

    print('Gaussian Model Mixture Results:')
    print('')
    for i in range(gmm.n_components):
        mean = gmm.means_[i]
        cov = gmm.covariances_[i]
        print(f"Component {i+1}:")
        print(f"  Mean vector: {mean}")
        print(f"  Covariance matrix:\n{cov}")
        print(f"  Weight: {gmm.weights_[i]:.2f}")
        print('')

    # Run a Monte Carlo Simulation on the GMM model to randomly obtain a set of discount rates
    monte_carlo_discount_rates = gmm.sample(n_samples)[0].flatten()

    # Compute the average discount rate from Monte Carlo simulations
    discount_rate_risk_adj = monte_carlo_discount_rates.mean()
    print(f'Risk Adjusted Discount Rate:  {discount_rate_risk_adj:.2f}%')

    return discount_rate_risk_adj
