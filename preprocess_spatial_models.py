import logging
import warnings
warnings.filterwarnings('ignore')
import gc
from datetime import datetime
import os
import psutil

import pandas as pd
import numpy as np
from dask.distributed import Client, LocalCluster
cluster = LocalCluster(n_workers=10, memory_limit="2GB", 
                       processes=True)
client = Client(cluster)
import dask.dataframe as dd

# Memory monitoring function
def print_memory_usage():
    process = psutil.Process(os.getpid())
    mem_gb = process.memory_info().rss / 1024 / 1024 / 1024
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Current memory usage: {mem_gb:.2f} GB")
    return mem_gb

if __name__ == "__main__":

    file_path = r"D:\Work\ADB\SAR\datasets\SAR_SVN_rice_KienGiang_28Feb2025.csv"
    output_path = r"D:\Work\ADB\SAR\datasets\KienGiang_rice_processed.parquet"

    # Define necessary columns
    needed_cols = ['lon', 'lat', 'ndvi', 'pm25_mean', 'temp_av', 'rain_cum', 
                'hum_av', 'lag_lumen', 'reprod', 'veg', 'year', 'mon']

    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Starting distributed data loading from {file_path}")
    start_time = datetime.now()

    # Read CSV with Dask - automatically chunks the data
    # Adjust blocksize as needed for your machine's memory
    ddf = dd.read_csv(file_path, usecols=needed_cols, blocksize="50MB")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Created Dask DataFrame with {len(ddf.divisions)-1} partitions")

    # Filter data to keep only reproductive or vegetative phase
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Filtering data for reproductive or vegetative phase")
    ddf = ddf[(ddf['reprod'] == 1) | (ddf['veg'] == 1)]

    # Handle missing values
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Handling missing values")
    # First, compute statistics about missing values
    missing_stats = ddf.isnull().sum().compute()
    for col in ddf.columns:
        missing = missing_stats[col]
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Column {col}: {missing:,} missing values")

    # Drop rows with missing values in critical columns
    ddf = ddf.dropna(subset=['lon', 'lat', 'ndvi'])

    # For other columns, fill with appropriate values
    # We need to compute means first
    numeric_cols = ['pm25_mean', 'temp_av', 'rain_cum', 'hum_av', 'lag_lumen']
    means = ddf[numeric_cols].mean().compute()

    for col in numeric_cols:
        fill_value = means[col]
        ddf[col] = ddf[col].fillna(fill_value)
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Filled {col} missing values with mean: {fill_value:.4f}")

    # Create log transformations efficiently
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Creating log transformations of numeric variables")
    for col in numeric_cols[:-1]:  # Excluding lag_lumen
        # Get min, max, and count of zeros
        stats = ddf[col].describe().compute()
        min_val = stats['min']
        max_val = stats['max']
        n_zeros = (ddf[col] == 0).sum().compute()
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {col} range: {min_val:.4f} to {max_val:.4f}, Zero values: {n_zeros:,}")
        
        # Add small constant to avoid log(0)
        ddf[f'ln_{col}'] = ddf[col].clip(lower=0.0001).map_partitions(np.log)

    # Handle lag_lumen separately
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Processing lag_lumen")
    lag_lumen_stats = ddf['lag_lumen'].describe().compute()
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - lag_lumen range before adjustment: {lag_lumen_stats['min']:.4f} to {lag_lumen_stats['max']:.4f}")
    ddf['lag_lumen'] = ddf['lag_lumen'] + 0.01
    ddf['ln_lag_lumen'] = ddf['lag_lumen'].map_partitions(np.log)

    # Create squared term for log PM2.5
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Creating squared term for log PM2.5")
    ddf['ln_pm25_mean_sq'] = ddf['ln_pm25_mean'] ** 2

    # Create time identifier
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Creating time identifiers")
    ddf['time_id'] = ddf['year'].astype(str) + '-' + ddf['mon'].astype(str).map_partitions(lambda s: s.str.zfill(2))

    # We need to compute time_periods for later use
    time_periods = ddf['time_id'].unique().compute()
    time_periods = sorted(time_periods)
    n_periods = len(time_periods)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Found {n_periods} unique time periods")

    # Create plot ID from coordinates for fixed effects
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Creating plot ID from coordinates")
    ddf['plot_id'] = ddf['lon'].round(3).astype(str) + '_' + ddf['lat'].round(3).astype(str)

    # For time period dummies, we can create them directly
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Creating time period dummy variables")
    for period in time_periods[1:]:  # Skip first period to avoid perfect multicollinearity
        ddf[f'time_{period}'] = (ddf['time_id'] == period).astype(int)

    # For plot dummies, we need a different approach due to potential memory issues
    # First, let's find the most frequent plots
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Identifying most frequent plots for dummy variables")
    plot_counts = ddf['plot_id'].value_counts().compute()
    n_plots = len(plot_counts)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Found {n_plots} unique plot IDs")

    # If there are too many plots, use only the most frequent ones
    if n_plots > 1000:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Too many plot IDs ({n_plots}) for dummy variables. Using top 1000 most frequent plots.")
        top_plots = set(plot_counts.nlargest(1000).index)
        
        # Create a function to mark if a plot is in top plots
        def mark_top_plot(plot_id):
            return plot_id if plot_id in top_plots else 'other'
        
        # Apply the function and create dummies
        ddf['plot_category'] = ddf['plot_id'].map(mark_top_plot, meta=('plot_category', 'object'))
        
        # Get unique categories after mapping
        plot_categories = ddf['plot_category'].unique().compute()
        plot_categories = sorted(plot_categories)
        # Skip first category or 'other' to avoid perfect multicollinearity
        skip_category = 'other' if 'other' in plot_categories else plot_categories[0]
        
        for category in plot_categories:
            if category != skip_category:
                ddf[f'plot_{category}'] = (ddf['plot_category'] == category).astype(int)
    else:
        # If number of plots is manageable, create dummies for all
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Creating dummy variables for all plots")
        plot_categories = plot_counts.index.tolist()
        skip_category = plot_categories[0]  # Skip first category to avoid perfect multicollinearity
        
        for category in plot_categories:
            if category != skip_category:
                ddf[f'plot_{category}'] = (ddf['plot_id'] == category).astype(int)

    # Verify data quality for each period
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Verifying data quality for each period")
    for period in time_periods:
        period_data = ddf[ddf['time_id'] == period]
        n_obs = len(period_data)
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Period {period}: approximately {n_obs:,} observations")

    # Execute computation and write to parquet
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Writing processed data to {output_path}")
    ddf.to_parquet(output_path, compression="snappy", write_index=False)

    end_time = datetime.now()
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Processing completed in {end_time - start_time}")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Data saved to {output_path}")

    # Optionally, load a sample to verify
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Loading a sample of the saved data to verify")
    sample = dd.read_parquet(output_path).head()
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Sample data shape: {sample.shape}")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Sample columns: {list(sample.columns)}")