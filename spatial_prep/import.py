# Libraries
import pandas as pd
import glob
import os

# Merge all the embedding data to a single CSV file (all csv in ./exports_1
export_folder = './exports'

## EMBEDDINGS

# # Match all exported CSVs (adjust the pattern if needed)
# csv_files = sorted(glob.glob(os.path.join(export_folder, "polygon_embeddings_2025_columns_*.csv")))
# print(f"Found {len(csv_files)} CSV files to merge.")
#
# # Merge all of them
# df_list = []
# for f in csv_files:
#     print(f"Reading {os.path.basename(f)} ...")
#     df = pd.read_csv(f)
#     df_list.append(df)
#
# merged_df = pd.concat(df_list, ignore_index=True)
# merged_df = merged_df.drop_duplicates(subset=['grid_id'])
#
# # Save the merged CSV
# output_path = "./polygon_embeddings_2025_full.csv"
# merged_df.to_csv(output_path, index=False)
#
# print(f"✅ Merged CSV saved to: {output_path}")
# print(f"Final shape: {merged_df.shape}")

## DYNAMIC WORLD / LANDSAT

# Match all exported CSVs (adjust the pattern if needed)
csv_files = sorted(glob.glob(os.path.join(export_folder, "polygon_landsat_2025_columns_*.csv")))
print(f"Found {len(csv_files)} CSV files to merge.")

# Merge all of them
df_list = []
for f in csv_files:
    print(f"Reading {os.path.basename(f)} ...")
    df = pd.read_csv(f)
    df_list.append(df)

merged_df = pd.concat(df_list, ignore_index=True)
merged_df = merged_df.drop_duplicates(subset=['grid_id'])

# Save the merged CSV
output_path = "./polygon_dynamicworld_2025_full.csv"
merged_df.to_csv(output_path, index=False)

print(f"✅ Merged CSV saved to: {output_path}")
print(f"Final shape: {merged_df.shape}")


## NIGHT LIGHT

# # Match all exported CSVs (adjust the pattern if needed)
# csv_files = sorted(glob.glob(os.path.join(export_folder, "polygon_night_light_2025_columns_*.csv")))
# print(f"Found {len(csv_files)} CSV files to merge.")
#
# # Merge all of them
# df_list = []
# for f in csv_files:
#     print(f"Reading {os.path.basename(f)} ...")
#     df = pd.read_csv(f)
#     df_list.append(df)
#
# merged_df = pd.concat(df_list, ignore_index=True)
# merged_df = merged_df.drop_duplicates(subset=['grid_id'])
#
# # Save the merged CSV
# output_path = "./polygon_night_light_2025_full.csv"
# merged_df.to_csv(output_path, index=False)
#
# print(f"✅ Merged CSV saved to: {output_path}")
# print(f"Final shape: {merged_df.shape}")

## MERGE ALL THREE DATASETS

embeddings_df = pd.read_csv("./polygon_embeddings_2025_full.csv")
landsat_df = pd.read_csv("./polygon_dynamicworld_2025_full.csv")
night_light_df = pd.read_csv("./polygon_night_light_2025_full.csv")
print(f"Embeddings shape: {embeddings_df.shape}")
print(f"Landsat shape: {landsat_df.shape}")
print(f"Night Light shape: {night_light_df.shape}")

# Merge them on 'grid_id'
merged_df = embeddings_df.merge(landsat_df, on='grid_id', how='outer').merge(night_light_df, on='grid_id', how='outer')
print(f"Merged shape: {merged_df.shape}")
# Save the final merged CSV
output_path = "./polygon_all_2025_full.csv"
merged_df.to_csv(output_path, index=False)
print(f"✅ Final merged CSV saved to: {output_path}")


