"""Configuration settings for the Tanzania Rubeho mapper."""

# Tanzania districts you want to work with (update after exploration)
TARGET_DISTRICTS = [
    "Kilosa",
    "Mvomero", 
    "Morogoro Rural",
    # Add your specific districts here after running 01_explore_districts.py
]

# Target regions for grid coverage (use full regions instead of buffer)
TARGET_REGIONS = [
    "Morogoro",
    # Add neighboring regions if needed for complete grid coverage
    # "Dodoma", "Iringa", etc.
]

# Grid settings
GRID_SIZE_LARGE = 500  # meters
GRID_SIZE_SMALL = 100  # meters
# BUFFER_DISTANCE = 2000  # Remove buffer - use full regions instead

# Coordinate system settings
TARGET_CRS = "EPSG:32736"  # UTM Zone 36S (good for Tanzania)
WEB_CRS = "EPSG:4326"      # WGS84 for web maps

# GEE settings
GEE_SCALE = 10  # Sentinel-2 resolution
START_DATE = '2023-01-01'
END_DATE = '2024-12-31'


# App settings
DEFAULT_MAP_CENTER = [-6.8, 37.5]  # Approximate center of Tanzania
DEFAULT_ZOOM = 7