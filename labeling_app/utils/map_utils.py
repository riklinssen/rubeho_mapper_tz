import folium
import geopandas as gpd



class DataLoader:
    """Handles loading and caching of geospatial data"""
    
    def __init__(self, data_dir):
        self.data_dir = data_dir
    
    def load_grid_data(self):
        """Load the 500m grid with treatment/control flags"""
        # Try multiple file formats, prioritizing the pre-filtered version
        potential_files = [
            ("grid_program_regions_only.geojson", gpd.read_file),  # Pre-filtered - fastest
            ("grid_500m_parent.geojson", gpd.read_file),
            ("grid_500m_parent.parquet", self._load_parquet_grid),
            ("grid_500m_parent.shp", gpd.read_file)
        ]
        
        for filename, loader_func in potential_files:
            grid_file = self.data_dir / "processed" / filename
            if grid_file.exists():
                try:
                    print(f"Attempting to load: {filename}")
                    gdf = loader_func(grid_file)
                    # Ensure correct CRS
                    if gdf.crs is None:
                        gdf.set_crs('EPSG:4326', inplace=True)
                    elif gdf.crs != 'EPSG:4326':
                        gdf = gdf.to_crs('EPSG:4326')
                    print(f"Successfully loaded {len(gdf)} grid cells from {filename}")
                    return gdf
                except Exception as e:
                    print(f"Failed to load {filename}: {e}")
                    continue
        
        raise FileNotFoundError(f"Could not find grid data in any supported format in {self.data_dir / 'processed'}")
    
    def load_ward_data(self):
        """Load ward boundaries with flags"""
        ward_file = self.data_dir / "processed" / "relevant_wards_with_flags.geojson"
        
        if not ward_file.exists():
            raise FileNotFoundError(f"Ward data file not found: {ward_file}")
        
        try:
            gdf = gpd.read_file(ward_file)
            # Ensure correct CRS
            if gdf.crs is None:
                gdf.set_crs('EPSG:4326', inplace=True)
            elif gdf.crs != 'EPSG:4326':
                gdf = gdf.to_crs('EPSG:4326')
            return gdf
        except Exception as e:
            raise Exception(f"Failed to load ward data: {e}")
    
    def load_village_lists(self):
        """Load treatment and control village lists"""
        import json
        
        village_file = self.data_dir / "processed" / "region_coverage_plan.json"
        
        if not village_file.exists():
            raise FileNotFoundError(f"Village data file not found: {village_file}")
        
        try:
            with open(village_file, 'r') as f:
                region_plan = json.load(f)
            return region_plan['program_locations']
        except Exception as e:
            raise Exception(f"Failed to load village data: {e}")
    
    def get_available_files(self):
        """Debug helper to see what files are actually available"""
        processed_dir = self.data_dir / "processed"
        if processed_dir.exists():
            return list(processed_dir.iterdir())
        else:
            return []
