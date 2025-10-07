import pandas as pd

# Load Parquet
df = pd.read_parquet("dataset/delhi_flood_dataset_demo.parquet")

# Save as CSV
df.to_csv("dataset/delhi_flood_dataset_demo.csv", index=False)

print("✅ Converted to CSV successfully!")
