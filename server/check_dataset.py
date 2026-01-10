import pandas as pd

df = pd.read_parquet('dataset/delhi_flood_dataset_demo.parquet')
print(f'Dataset shape: {df.shape}')
print(f'Columns: {list(df.columns)}')
print(f'Grid_ID range: {df["Grid_ID"].min()} - {df["Grid_ID"].max()}')
print(f'Unique grids: {df["Grid_ID"].nunique()}')
print(f'\nFirst few rows:')
print(df.head())
