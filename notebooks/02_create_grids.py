# %% 
# # Grid Creation for Tanzania Rubeho Mapper
# Create hierarchical fishnet grid (500m parent, 100m children) for program + adjacent regions

# %%
# Setup and imports

import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from pathlib import Path
from shapely.geometry import Polygon
from shapely.prepared import prep

import sys

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import *

# Define data paths
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

print("Setup complete!")
print(f"Grid sizes: {GRID_SIZE_LARGE}m parent, {GRID_SIZE_SMALL}m children")
print(f"Target CRS: {TARGET_CRS}")


# %%
print("Loading processed data from district exploration")

# Load the region coverage plan
region_plan_file = PROCESSED_DATA_DIR / "region_coverage_plan.json"
with open(region_plan_file, 'r') as f:
    region_plan = json.load(f)

# Print treatment locations
if 'treatment_ward_names' in region_plan['program_locations']:
    treatment_wards = region_plan['program_locations']['treatment_ward_names']
    treatment_ward_districts = region_plan['program_locations']['treatment_ward_district_list']
    
    print(f"\nTREATMENT LOCATIONS ({len(treatment_wards)} wards):")
    for ward_district in treatment_ward_districts:
        print(f"  • {ward_district}")
        
    # Print treatment villages if available
    if 'treatment_villages' in region_plan['program_locations']:
        treatment_villages = region_plan['program_locations']['treatment_villages']
        print(f"\nTREATMENT VILLAGES ({len(treatment_villages)} villages):")
        for village in treatment_villages:
            print(f"  • {village}")
else:
    print(f"\nTREATMENT LOCATIONS ({region_plan['program_locations']['matched_treatment_wards']} wards):")
    print("  (Ward names not available in JSON - update previous script)")
# Print control locations  
if 'control_ward_names' in region_plan['program_locations']:
    control_wards = region_plan['program_locations']['control_ward_names']
    control_ward_districts = region_plan['program_locations']['control_ward_district_list']
    
    print(f"\nPROGRAM CONTROL LOCATIONS ({len(control_wards)} wards):")
    for ward_district in control_ward_districts:
        print(f"  • {ward_district}")
        
    # Print control villages if available
    if 'control_villages' in region_plan['program_locations']:
        control_villages = region_plan['program_locations']['control_villages']
        print(f"\nPROGRAM CONTROL VILLAGES ({len(control_villages)} villages):")
        for village in control_villages:
            print(f"  • {village}")
else:
    print(f"\nPROGRAM CONTROL LOCATIONS ({region_plan['program_locations']['matched_control_wards']} wards):")

# %%
##load in geojson 
# Load the relevant wards shapefile with flags
print("Loading relevant wards GeoJSON file...")
relevant_wards_file = PROCESSED_DATA_DIR / "relevant_wards_with_flags.geojson"

if relevant_wards_file.exists():
    gdf_relevant = gpd.read_file(relevant_wards_file)
    print(f"✅ Successfully loaded relevant wards: {len(gdf_relevant)} wards")
    print(f"  - Treatment wards: {gdf_relevant['is_treatment'].sum()}")
    print(f"  - Program control wards: {gdf_relevant['is_program_control'].sum()}")
    print(f"  - Program region wards: {gdf_relevant['is_program_region'].sum()}")
    print(f"  - Adjacent region wards: {gdf_relevant['is_adjacent_region'].sum()}")
else:
    print(f"❌ File not found: {relevant_wards_file}")
    print("Available files in processed directory:")
    for file in PROCESSED_DATA_DIR.iterdir():
        print(f"  📄 {file.name}")
    raise FileNotFoundError(f"Required file not found: {relevant_wards_file}")



# Convert to UTM for accurate grid creation
gdf_utm = gdf_relevant.to_crs(TARGET_CRS)

# Create overall study area
study_area_utm = gdf_utm.union_all()
study_bounds = study_area_utm.bounds

print(f"Study area bounds (UTM): {study_bounds}")
print(f"Study area dimensions: {(study_bounds[2]-study_bounds[0])/1000:.1f} x {(study_bounds[3]-study_bounds[1])/1000:.1f} km")

# Calculate grid dimensions
width_m = study_bounds[2] - study_bounds[0]
height_m = study_bounds[3] - study_bounds[1]
n_cols_500m = int(np.ceil(width_m / GRID_SIZE_LARGE))
n_rows_500m = int(np.ceil(height_m / GRID_SIZE_LARGE))

print(f"Master grid dimensions: {n_cols_500m} x {n_rows_500m} = {n_cols_500m * n_rows_500m:,} cells (500m)")

# %%
# Grid creation function
def create_fishnet_grid(bounds, cell_size, crs=TARGET_CRS):
    """Create a fishnet grid within given bounds."""
    minx, miny, maxx, maxy = bounds
    
    # Calculate number of cells
    cols = int(np.ceil((maxx - minx) / cell_size))
    rows = int(np.ceil((maxy - miny) / cell_size))
    
    print(f"Creating {cols} x {rows} = {cols*rows:,} grid cells")
    
    # Generate grid
    polygons = []
    grid_ids = []
    
    for i in range(cols):
        for j in range(rows):
            left = minx + i * cell_size
            right = minx + (i + 1) * cell_size
            bottom = miny + j * cell_size
            top = miny + (j + 1) * cell_size
            
            poly = Polygon([(left, bottom), (right, bottom), 
                          (right, top), (left, top)])
            polygons.append(poly)
            grid_ids.append(f"G_{i:04d}_{j:04d}")
    
    gdf = gpd.GeoDataFrame({
        'grid_id': grid_ids,
        'col': [i for i in range(cols) for j in range(rows)],
        'row': [j for i in range(cols) for j in range(rows)],
        'cell_size': cell_size,
        'geometry': polygons
    }, crs=crs)
    
    return gdf

# %%
# Create 500m parent grid
print("Creating 500m parent grid...")
parent_grid_utm = create_fishnet_grid(study_bounds, GRID_SIZE_LARGE, TARGET_CRS)
print(f"Parent grid created with {len(parent_grid_utm)} cells")
# More efficient filtering using spatial index
print("Creating spatial index for faster intersection...")

# Prepare the study area geometry for faster intersection
study_area_prepared = prep(study_area_utm)

# Use the prepared geometry for faster intersection
print("Filtering grid to study area (optimized)...")
intersecting_mask = parent_grid_utm.geometry.apply(lambda geom: study_area_prepared.intersects(geom))
parent_grid_filtered = parent_grid_utm[intersecting_mask].copy()

print(f"Filtered from {len(parent_grid_utm)} to {len(parent_grid_filtered)} cells")

# %%
# Add administrative information to grid cells
print("Adding administrative information to grid cells...")

# Spatial join with ward data (using centroids for performance)
grid_centroids = parent_grid_filtered.geometry.centroid
centroids_gdf = gpd.GeoDataFrame(geometry=grid_centroids, crs=TARGET_CRS)

# Spatial join to get ward, district, region for each grid cell
grid_with_admin = gpd.sjoin(
    centroids_gdf.reset_index(), 
    gdf_utm[['ward_name', 'dist_name', 'reg_name', 'is_treatment', 'is_program_region', 'is_adjacent_region', 'geometry']], 
    how='left', 
    predicate='within'
)

# Add administrative info back to main grid
parent_grid_filtered['ward_name'] = grid_with_admin['ward_name']
parent_grid_filtered['district'] = grid_with_admin['dist_name']
parent_grid_filtered['region'] = grid_with_admin['reg_name']
parent_grid_filtered['is_treatment_ward'] = grid_with_admin['is_treatment'].fillna(False)
parent_grid_filtered['is_program_region'] = grid_with_admin['is_program_region'].fillna(False)
parent_grid_filtered['is_adjacent_region'] = grid_with_admin['is_adjacent_region'].fillna(False)

print(f"Administrative info added to {len(parent_grid_filtered)} grid cells")
# %%
# %%
# Convert to WGS84 and save
print("Converting to WGS84 and saving...")

print("Saving as Parquet for speed...")

# Convert to WGS84
parent_grid_web = parent_grid_filtered.to_crs(WEB_CRS)

# Save as Parquet (much faster than GeoJSON)
parquet_file = PROCESSED_DATA_DIR / "grid_500m_parent.parquet"
parent_grid_web.to_parquet(parquet_file)

print(f"Saved {len(parent_grid_web)} cells as Parquet")

# %%
# Create and save grid metadata
grid_metadata = {
    'grid_info': {
        'cell_size_meters': GRID_SIZE_LARGE,
        'total_cells': len(parent_grid_web),
        'crs_utm': TARGET_CRS,
        'crs_web': WEB_CRS,
        'creation_date': pd.Timestamp.now().isoformat()
    },
    'coverage': {
        'cells_in_treatment_wards': int(parent_grid_web['is_treatment_ward'].sum()),
        'cells_in_program_regions': int(parent_grid_web['is_program_region'].sum()),
        'cells_in_adjacent_regions': int(parent_grid_web['is_adjacent_region'].sum())
    },
    'bounds': {
        'min_longitude': float(parent_grid_web.total_bounds[0]),
        'min_latitude': float(parent_grid_web.total_bounds[1]), 
        'max_longitude': float(parent_grid_web.total_bounds[2]),
        'max_latitude': float(parent_grid_web.total_bounds[3])
    }
}

# Save metadata
metadata_file = PROCESSED_DATA_DIR / "grid_metadata.json"
with open(metadata_file, 'w') as f:
    json.dump(grid_metadata, f, indent=2)

print(f"Saved grid metadata to {metadata_file.name}")

# %%
# Create summary statistics
print("\nGrid Summary:")
print(f"  Total 500m cells: {len(parent_grid_web):,}")
print(f"  Cells in treatment wards: {parent_grid_web['is_treatment_ward'].sum():,}")
print(f"  Cells in program regions: {parent_grid_web['is_program_region'].sum():,}")
print(f"  Potential 100m cells: {len(parent_grid_web) * 25:,}")

# Summary by region
region_summary = parent_grid_web.groupby('region').agg({
    'grid_id': 'count',
    'is_treatment_ward': 'sum'
}).rename(columns={'grid_id': 'total_cells', 'is_treatment_ward': 'treatment_cells'})

print("\nCells by region:")
for region, row in region_summary.iterrows():
    if pd.notna(region):
        print(f"  {region}: {row['total_cells']:,} cells ({row['treatment_cells']} in treatment wards)")

# %%
