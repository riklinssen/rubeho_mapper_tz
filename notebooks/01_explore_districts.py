# %% 
# # Tanzania Districts Exploration
# Explore available districts and identify target areas for the Rubeho mapping project using existing ward shapefile

# %%
# Setup and imports
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import json
from pathlib import Path
import sys
# Add project root to Python path
project_root = Path(__file__).parent.parent

print(project_root)
sys.path.insert(0, str(project_root))

from config.settings import *


# %%
print(f"Target CRS: {TARGET_CRS}")
print(f"Web CRS: {WEB_CRS}")

# %%
#paths 
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
print(f"Data directory: {DATA_DIR}")
print(f"Raw data: {RAW_DATA_DIR}")
print(f"Processed data: {PROCESSED_DATA_DIR}")


# %%
#load the shapefile
shapefile_dir = RAW_DATA_DIR / "ALL WARDS TANZANIA"
shp_files = list(shapefile_dir.glob("*.shp"))
if shp_files:
    shp_file = shp_files[0]  # Take the first .shp file found
print(shapefile_dir)

# %%
if shp_files:
    print("Loading ward shapefile...")
    try:
        gdf_wards = gpd.read_file(shp_file)
        
        print(f"Shape: {gdf_wards.shape}")
        print(f"CRS: {gdf_wards.crs}")
        print(f"Columns: {list(gdf_wards.columns)}")
        print("\nFirst few rows:")
        print(gdf_wards.head())
        
        print(f"\nLoaded {len(gdf_wards)} wards successfully! ✅")
        
    except Exception as e:
        print(f"❌ Error loading shapefile: {e}")
        print("This might be due to encoding issues or corrupted files")
else:
    print("❌ Cannot load shapefile - no .shp file found")


# %%
#load data with relevant wards from programme. 
# this is an xls sheet with some ward and district names. 
# Load the program implementation Excel file
excel_file = RAW_DATA_DIR / "Rubeho Villages for HH survey - v2.xlsx"
if excel_file.exists():
    print(f"Loading program data from: {excel_file.name}")
    
    try:
        # Load the Excel file
        df_program = pd.read_excel(excel_file, sheet_name="Villages")
        
        print(f"Shape: {df_program.shape}")
        print(f"Columns: {list(df_program.columns)}")
        print("\nFirst few rows:")
        print(df_program.head())
        
        print(f"\nLoaded {len(df_program)} program locations successfully! ✅")
        
    except Exception as e:
        print(f"❌ Error loading Excel file: {e}")
        
else:
    print(f"❌ Excel file not found at: {excel_file}")
    print("Contents of raw data directory:")
    for item in RAW_DATA_DIR.iterdir():
        print(f"  📄 {item.name}")
programme_districts=df_program.District.unique()
#get lists of districts and wards
programme_districts
#one weird name tfs that is not a ward. 
programme_wards=[d for d in df_program.Ward.unique() if  not 'TFS' in d]


# %%
#check which regions I am in. 
district_region_mapping = gdf_wards.groupby('dist_name')['reg_name'].first().to_dict()
program_regions = set()

for district in programme_districts:
    if district in district_region_mapping:
        region = district_region_mapping[district]
        program_regions.add(region)
        print(f"  • {district} → {region}")
    else:
        print(f"  ❌ {district} → NOT FOUND in shapefile")

print(f"\nProgram covers these regions: {sorted(program_regions)}")


# %%
# %%
# Find adjacent regions for sufficient control area buffer
print("🗺️ Finding adjacent regions for control area matching...")

# Start with your program regions
print(f"Core program regions: {sorted(program_regions)}")

# Get all regions in Tanzania
all_regions = gdf_wards['reg_name'].unique()
print(f"Total regions in Tanzania: {len(all_regions)}")

# Create region polygons for adjacency analysis
all_regions_dissolved = gdf_wards.dissolve(by='reg_name').reset_index()

# %%
# Find regions that share boundaries with program regions
def find_adjacent_regions(target_regions, all_regions_gdf, buffer_distance=1000):
    """
    Find regions adjacent to target regions.
    
    Args:
        target_regions: List of region names to find neighbors for
        all_regions_gdf: GeoDataFrame with all regions dissolved
        buffer_distance: Small buffer in meters to account for digitization gaps
    """
    # Get target region polygons
    target_gdf = all_regions_gdf[all_regions_gdf['reg_name'].isin(target_regions)].copy()
    
    # Convert to UTM for accurate distance calculations
    target_utm = target_gdf.to_crs(TARGET_CRS)
    all_regions_utm = all_regions_gdf.to_crs(TARGET_CRS)
    
    # Create small buffer around target regions to catch near-adjacent regions
    target_buffered = target_utm.geometry.buffer(buffer_distance).unary_union
    
    adjacent_regions = set()
    
    # Check each region for adjacency
    for idx, region_row in all_regions_utm.iterrows():
        region_name = region_row['reg_name']
        
        # Skip if it's already a program region
        if region_name in target_regions:
            continue
            
        # Check if region intersects with buffered program regions
        if region_row.geometry.intersects(target_buffered):
            adjacent_regions.add(region_name)
            
    return list(adjacent_regions)

# Find adjacent regions
adjacent_regions = find_adjacent_regions(program_regions, all_regions_dissolved)

print(f"\nAdjacent regions found: {sorted(adjacent_regions)}")

# %%
# Calculate distances and adjacency relationships
print("📏 Analyzing regional adjacency relationships...")

# Create adjacency matrix for better understanding
program_regions_gdf = all_regions_dissolved[all_regions_dissolved['reg_name'].isin(program_regions)]
adjacent_regions_gdf = all_regions_dissolved[all_regions_dissolved['reg_name'].isin(adjacent_regions)]

# Convert to UTM for distance calculations
program_utm = program_regions_gdf.to_crs(TARGET_CRS)
adjacent_utm = adjacent_regions_gdf.to_crs(TARGET_CRS)

adjacency_info = []
for _, prog_region in program_utm.iterrows():
    prog_name = prog_region['reg_name']
    
    for _, adj_region in adjacent_utm.iterrows():
        adj_name = adj_region['reg_name']
        
        # Calculate minimum distance between regions
        distance = prog_region.geometry.distance(adj_region.geometry)
        
        # Check if they actually touch (distance = 0)
        touches = prog_region.geometry.touches(adj_region.geometry)
        
        adjacency_info.append({
            'program_region': prog_name,
            'adjacent_region': adj_name,
            'distance_km': distance / 1000,
            'directly_adjacent': touches
        })

adjacency_df = pd.DataFrame(adjacency_info)

print("Regional adjacency summary:")
for prog_region in program_regions:
    adj_info = adjacency_df[adjacency_df['program_region'] == prog_region]
    touching = adj_info[adj_info['directly_adjacent'] == True]['adjacent_region'].tolist()
    near = adj_info[(adj_info['directly_adjacent'] == False) & 
                    (adj_info['distance_km'] < 10)]['adjacent_region'].tolist()
    
    print(f"\n{prog_region}:")
    print(f"  Directly adjacent: {touching}")
    if near:
        print(f"  Nearby (<10km): {near}")

# %%
# Create comprehensive region list for grid coverage
extended_regions = list(set(program_regions) | set(adjacent_regions))

print(f"\n🎯 Recommended regions for grid coverage:")
print(f"Program regions ({len(program_regions)}): {sorted(program_regions)}")
print(f"Adjacent regions ({len(adjacent_regions)}): {sorted(adjacent_regions)}")
print(f"Total extended regions ({len(extended_regions)}): {sorted(extended_regions)}")

# Calculate coverage statistics
extended_regions_gdf = all_regions_dissolved[all_regions_dissolved['reg_name'].isin(extended_regions)]

# Convert to UTM for area calculations
extended_utm = extended_regions_gdf.to_crs(TARGET_CRS)
program_only_utm = program_regions_gdf.to_crs(TARGET_CRS)

total_area = extended_utm.geometry.area.sum() / (1000**2)  # Convert to km²
program_area = program_only_utm.geometry.area.sum() / (1000**2)

print(f"\nArea analysis:")
print(f"  Program regions only: {program_area:,.0f} km²")
print(f"  Extended coverage: {total_area:,.0f} km²")
print(f"  Control buffer ratio: {total_area/program_area:.1f}x")

# %%
# Visualize the extended coverage area
print("📊 Visualizing extended coverage...")

fig, ax = plt.subplots(1, 1, figsize=(15, 12))

# Plot all Tanzania regions in light gray
all_regions_dissolved.plot(ax=ax, facecolor='lightgray', edgecolor='white', alpha=0.3)

# Plot extended coverage regions
extended_regions_gdf.plot(ax=ax, facecolor='lightblue', edgecolor='blue', alpha=0.4, linewidth=1)

# Plot program regions (core areas)
program_regions_gdf.plot(ax=ax, facecolor='red', edgecolor='black', alpha=0.7, linewidth=2)

# Add labels
for idx, row in extended_regions_gdf.iterrows():
    centroid = row.geometry.centroid
    color = 'red' if row['reg_name'] in program_regions else 'blue'
    weight = 'bold' if row['reg_name'] in program_regions else 'normal'
    
    ax.annotate(row['reg_name'], 
               xy=(centroid.x, centroid.y),
               ha='center', va='center', fontsize=10, fontweight=weight,
               color='white',
               bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.8))

ax.set_title("Extended Grid Coverage: Program Regions (Red) + Adjacent Regions (Blue)", fontsize=16)
plt.tight_layout()
plt.show()

# %%
# Update your target regions for grid creation
YOUR_FINAL_TARGET_REGIONS = extended_regions

print(f"🎯 Final recommendation for grid creation:")
print(f"Include these {len(YOUR_FINAL_TARGET_REGIONS)} regions: {sorted(YOUR_FINAL_TARGET_REGIONS)}")

# Calculate estimated grid size
extended_wards = gdf_wards[gdf_wards['reg_name'].isin(YOUR_FINAL_TARGET_REGIONS)]
extended_area_utm = extended_wards.dissolve(by='reg_name').to_crs(TARGET_CRS)
extended_bounds = extended_area_utm.total_bounds

estimated_cells_500m = ((extended_bounds[2] - extended_bounds[0]) / 500) * ((extended_bounds[3] - extended_bounds[1]) / 500)

print(f"\nEstimated grid impact:")
print(f"  Bounding box: {(extended_bounds[2] - extended_bounds[0])/1000:.0f} x {(extended_bounds[3] - extended_bounds[1])/1000:.0f} km")
print(f"  Estimated 500m cells: ~{estimated_cells_500m:,.0f}")
print(f"  Estimated 100m cells: ~{estimated_cells_500m * 25:,.0f}")

# Check if this is computationally feasible
if estimated_cells_500m > 100000:
    print(f"⚠️  Large grid detected! Consider:")
    print(f"   • Processing in smaller chunks")
    print(f"   • Starting with 500m cells only")
    print(f"   • Using only directly adjacent regions")
else:
    print(f"✅ Grid size looks manageable for processing")

# %%
# Save the extended region list for grid generation
region_info = {
    'program_regions': program_regions,
    'adjacent_regions': adjacent_regions,
    'all_target_regions': YOUR_FINAL_TARGET_REGIONS,
    'coverage_stats': {
        'program_area_km2': float(program_area),
        'total_area_km2': float(total_area),
        'control_buffer_ratio': float(total_area/program_area)
    }
}

# with open(PROCESSED_DATA_DIR / "region_coverage_plan.json", "w") as f:
#     json.dump(region_info, f, indent=2, default=str)

# print(f"✅ Saved region coverage plan to region_coverage_plan.json")
# %%
#collecting treatment wards from the excel. 
treatment_locations = df_program[
    (df_program['ARR'] == 1) | (df_program['REDD'] == 1)
][['Ward', 'District']].drop_duplicates()

print(f"I have {len(treatment_locations)} treatment ward-district combinations")
print("\nTreatment locations:")
for _, row in treatment_locations.iterrows():
    print(f"  • {row['Ward']} in {row['District']}")

# %%
#finding matches in the shapefile.
programme_wards_gdf = gdf_wards[
    (gdf_wards['reg_name'].isin(program_regions)) &
    (gdf_wards['dist_name'].isin(treatment_locations['District'].unique()))
].copy()

# confining to programme regions only. 

# Get ward names from programme regions only
programme_wards_gdf = gdf_wards[
    (gdf_wards['reg_name'].isin(program_regions)) &
    (gdf_wards['dist_name'].isin(treatment_locations['District'].unique()))
].copy()

print(f"Filtered to programme regions AND treatment districts: {len(programme_wards_gdf)} wards")
print(f"Treatment districts: {treatment_locations['District'].unique().tolist()}")


# **ADAPTATION 3: Create ward-district pairs for precise matching**
# Create ward-district combinations from shapefile
shapefile_ward_district = set()
for _, row in programme_wards_gdf.iterrows():
    ward_district_key = f"{str(row['ward_name']).strip().upper()}||{str(row['dist_name']).strip().upper()}"
    shapefile_ward_district.add(ward_district_key)

# Create ward-district combinations from treatment data
treatment_ward_district = set()
for _, row in treatment_locations.iterrows():
    ward_district_key = f"{str(row['Ward']).strip().upper()}||{str(row['District']).strip().upper()}"
    treatment_ward_district.add(ward_district_key)


# Find exact matches using ward-district pairs
treatment_exact_matches_pairs = treatment_ward_district.intersection(shapefile_ward_district)
treatment_missing_pairs = treatment_ward_district - shapefile_ward_district

# Extract just the ward names from successful matches for later use
treatment_exact_matches = set()
for pair in treatment_exact_matches_pairs:
    ward_name = pair.split('||')[0]
    treatment_exact_matches.add(ward_name)

if treatment_missing_pairs:
    print("These ward-district combinations are not in the shapefile:")
    for pair in treatment_missing_pairs:
        ward, district = pair.split('||')
        print(f"  • {ward} in {district}")
else:
    print(f"✅ All {len(treatment_locations)} treatment locations matched!")
    print(f"Matched ward-district pairs: {len(treatment_exact_matches_pairs)}")

relevant_regions = list(program_regions) + adjacent_regions
print(f"Relevant regions: {relevant_regions}")

# Filter shapefile to only relevant regions
gdf_relevant = gdf_wards[gdf_wards['reg_name'].isin(relevant_regions)].copy()
print(f"Filtered shapefile from {len(gdf_wards)} to {len(gdf_relevant)} wards in relevant regions")

# **ADAPTATION 5: Create precise treatment flagging using ward-district combinations**
gdf_relevant['is_treatment'] = False

# Create ward-district key for each row in relevant shapefile
gdf_relevant['ward_district_key'] = (
    gdf_relevant['ward_name'].astype(str).str.strip().str.upper() + '||' + 
    gdf_relevant['dist_name'].astype(str).str.strip().str.upper()
)

# Flag treatment wards using exact ward-district matches
gdf_relevant.loc[
    gdf_relevant['ward_district_key'].isin(treatment_exact_matches_pairs),
    'is_treatment'
] = True

# Summary of treatment flagging
treatment_count = gdf_relevant['is_treatment'].sum()
print(f"\nTreatment ward flagging (using ward-district pairs):")
print(f"  • Total wards in relevant regions: {len(gdf_relevant)}")
print(f"  • Treatment wards flagged: {treatment_count}")
print(f"  • Expected treatment wards: {len(treatment_exact_matches_pairs)}")
print(f"  • Match success: {'✅' if treatment_count == len(treatment_exact_matches_pairs) else '❌'}")

# Show treatment wards by region
treatment_summary = gdf_relevant[gdf_relevant['is_treatment'] == True].groupby('reg_name').size()
print(f"\nTreatment wards by region:")
for region, count in treatment_summary.items():
    print(f"  • {region}: {count} treatment wards")

# **ADAPTATION 6: Verification - no more duplicate issues**
print(f"\n📋 Treatment ward verification:")
treatment_wards_flagged = gdf_relevant[gdf_relevant['is_treatment'] == True].copy()

for region in sorted(treatment_wards_flagged['reg_name'].unique()):
    region_wards = treatment_wards_flagged[treatment_wards_flagged['reg_name'] == region]
    print(f"\n{region} ({len(region_wards)} wards):")
    for _, row in region_wards.iterrows():
        print(f"  • {row['ward_name']} in {row['dist_name']} district")

# Clean up the temporary column
gdf_relevant = gdf_relevant.drop('ward_district_key', axis=1)



# %%
gdf_relevant['is_program_region'] = gdf_relevant['reg_name'].isin(program_regions)
gdf_relevant['is_adjacent_region'] = gdf_relevant['reg_name'].isin(adjacent_regions)

# %%
#check if the programme and adjacent regions are within gdf relevant. 
print("I have", len(gdf_relevant), " wards in total")
print("and I have",(sum(gdf_relevant['is_program_region'])+ sum(gdf_relevant['is_adjacent_region'])),"wards in relevant regions (program + adjacent)")
# %%
##exporting relevant regions for grid generation
output_file = PROCESSED_DATA_DIR / "relevant_wards_with_flags.geojson"
gdf_relevant.to_file(output_file)

if output_file.exists():
    file_size = output_file.stat().st_size / (1024*1024)  # Convert to MB
    print(f"✅ Successfully saved relevant wards shapefile:")
    print(f"   File: {output_file.name}")
    print(f"   Size: {file_size:.1f} MB")
    print(f"   Records: {len(gdf_relevant)} wards")
else:
    print(f"❌ Failed to save {output_file}")


# %%
#saving some helpful stats and metadata for grid generation. 
region_info = {
    'program_regions': list(program_regions),  # Convert set to list for JSON serialization
    'adjacent_regions': adjacent_regions,
    'all_target_regions': YOUR_FINAL_TARGET_REGIONS,
    'coverage_stats': {
        'program_area_km2': float(program_area),
        'total_area_km2': float(total_area),
        'control_buffer_ratio': float(total_area/program_area)
    },
    'treatment_wards': {
        'total_treatment_locations': len(treatment_locations),
        'matched_treatment_wards': len(treatment_exact_matches),
        'treatment_ward_list': list(treatment_exact_matches),
        'missing_treatment_wards': list(treatment_missing_pairs) if treatment_missing_pairs else [],
        'match_rate': len(treatment_exact_matches) / len(treatment_locations) if len(treatment_locations) > 0 else 0


    },
    'treatment_by_region': {},
    'spatial_bounds': {}
}

# Add treatment ward counts by region
treatment_summary_dict = gdf_relevant[gdf_relevant['is_treatment'] == True].groupby('reg_name').size().to_dict()
region_info['treatment_by_region'] = treatment_summary_dict

# Add spatial bounds for treatment areas
treatment_wards_gdf = gdf_relevant[gdf_relevant['is_treatment'] == True]
if len(treatment_wards_gdf) > 0:
    bounds = treatment_wards_gdf.total_bounds
    region_info['spatial_bounds']['treatment_areas'] = {
        'min_longitude': float(bounds[0]),
        'min_latitude': float(bounds[1]),
        'max_longitude': float(bounds[2]),
        'max_latitude': float(bounds[3])
    }

# Add spatial bounds for program regions
program_regions_gdf = gdf_relevant[gdf_relevant['is_program_region'] == True]
if len(program_regions_gdf) > 0:
    bounds = program_regions_gdf.total_bounds
    region_info['spatial_bounds']['program_regions'] = {
        'min_longitude': float(bounds[0]),
        'min_latitude': float(bounds[1]),
        'max_longitude': float(bounds[2]),
        'max_latitude': float(bounds[3])
    }

# Add spatial bounds for adjacent regions
adjacent_regions_gdf = gdf_relevant[gdf_relevant['is_adjacent_region'] == True]
if len(adjacent_regions_gdf) > 0:
    bounds = adjacent_regions_gdf.total_bounds
    region_info['spatial_bounds']['adjacent_regions'] = {
        'min_longitude': float(bounds[0]),
        'min_latitude': float(bounds[1]),
        'max_longitude': float(bounds[2]),
        'max_latitude': float(bounds[3])
    }

# Add spatial bounds for all relevant regions combined
all_bounds = gdf_relevant.total_bounds
region_info['spatial_bounds']['all_regions'] = {
    'min_longitude': float(all_bounds[0]),
    'min_latitude': float(all_bounds[1]),
    'max_longitude': float(all_bounds[2]),
    'max_latitude': float(all_bounds[3])
}

# Save the comprehensive plan
json_file = PROCESSED_DATA_DIR / "region_coverage_plan.json"
with open(json_file, "w") as f:
    json.dump(region_info, f, indent=2, default=str)

if json_file.exists():
    file_size = json_file.stat().st_size / 1024  # Convert to KB
    print(f"✅ Successfully saved region coverage plan:")
    print(f"   File: {json_file.name}")
    print(f"   Size: {file_size:.1f} KB")
    print(f"   Contains: {len(region_info)} top-level sections")
    print(f"   Treatment wards: {region_info['treatment_wards']['matched_treatment_wards']}")
    print(f"   Target regions: {len(region_info['all_target_regions'])}")
else:
    print(f"❌ Failed to save {json_file}")
# %%
# Check if filtering actually worked
print(f"Original shapefile: {len(gdf_wards)} wards")
print(f"Relevant regions: {len(gdf_relevant)} wards") 
print(f"Unique regions in gdf_relevant: {sorted(gdf_relevant['reg_name'].unique())}")
print(f"Expected regions: {sorted(relevant_regions)}")

# Are they the same?
if len(gdf_wards) == len(gdf_relevant):
    print("WARNING: No filtering occurred!")
