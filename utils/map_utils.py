import folium
import geopandas as gpd
from shapely.prepared import prep

class SatelliteImageryManager:
    """Handles different satellite imagery sources"""
    
    @staticmethod
    def add_google_satellite(m):
        """Add Google Satellite imagery as base layer"""
        google_satellite = folium.raster_layers.WmsTileLayer(
            url='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
            layers='',
            name='Google Satellite',
            attr='Google',
            overlay=False,
            control=True
        )
        google_satellite.add_to(m)
    
    @staticmethod 
    def add_esri_satellite(m):
        """Add ESRI World Imagery as base layer"""
        esri_satellite = folium.raster_layers.WmsTileLayer(
            url='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            layers='',
            name='ESRI Satellite',
            attr='ESRI',
            overlay=False,
            control=True
        )
        esri_satellite.add_to(m)

class GridManager:
    """Handles grid overlay and styling"""
    
    @staticmethod
    def add_grid_overlay(m, grid_gdf):
        """Add grid cells as overlay with treatment/control styling"""
        
        # Style function for grid cells
        def style_function(feature):
            props = feature['properties']
            
            if props.get('is_treatment_ward', False):
                return {
                    'fillColor': 'red',
                    'color': 'darkred',
                    'weight': 1,
                    'fillOpacity': 0.1,
                    'opacity': 0.7
                }
            elif props.get('is_program_control', False):
                return {
                    'fillColor': 'blue', 
                    'color': 'darkblue',
                    'weight': 1,
                    'fillOpacity': 0.1,
                    'opacity': 0.7
                }
            else:
                return {
                    'fillColor': 'gray',
                    'color': 'gray',
                    'weight': 0.5,
                    'fillOpacity': 0.05,
                    'opacity': 0.3
                }
        
        # Add grid to map
        folium.GeoJson(
            grid_gdf,
            style_function=style_function,
            popup=folium.Popup('Click to annotate'),
            tooltip=folium.Tooltip(['grid_id', 'ward_name', 'district']),
            name='Grid Cells'
        ).add_to(m)

class DataLoader:
    """Handles loading and caching of geospatial data"""
    
    def __init__(self, data_dir):
        self.data_dir = data_dir
    
    def load_grid_data(self):
        """Load the 500m grid with treatment/control flags"""
        # Try multiple file formats
        potential_files = [
            ("grid_500m_parent.parquet", self._load_parquet_grid),
            ("grid_500m_parent.geojson", gpd.read_file),
            ("grid_500m_parent.shp", gpd.read_file)
        ]
        
        for filename, loader_func in potential_files:
            grid_file = self.data_dir / "processed" / filename
            if grid_file.exists():
                try:
                    gdf = loader_func(grid_file)
                    # Ensure correct CRS
                    if gdf.crs is None:
                        gdf.set_crs('EPSG:4326', inplace=True)
                    elif gdf.crs != 'EPSG:4326':
                        gdf = gdf.to_crs('EPSG:4326')
                    return gdf
                except Exception as e:
                    print(f"Failed to load {filename}: {e}")
                    continue
        
        raise FileNotFoundError(f"Could not find grid data in any supported format in {self.data_dir / 'processed'}")
    
    def _load_parquet_grid(self, grid_file):
        """Handle Parquet files which need special treatment for geometry"""
        import pandas as pd
        
        # Read as pandas DataFrame first
        df = pd.read_parquet(grid_file)
        
        # Convert back to GeoDataFrame
        gdf = gpd.GeoDataFrame(df, geometry='geometry')
        
        return gdf
    
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
