import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
import geopandas as gpd
import json
from pathlib import Path
import sys

# Page config
st.set_page_config(page_title="Treatment area mapping RUbeho CCT", layout="wide")
st.title("🌳 Treatment area mapping tool")

# Initialize session state for annotations - MUST BE EARLY
if 'annotations' not in st.session_state:
    st.session_state.annotations = []

# Add utils to path
sys.path.append(str(Path(__file__).parent / "utils"))

try:
    from map_utils import DataLoader
    # Initialize data loader
    DATA_DIR = Path(__file__).parent / "data"
    data_loader = DataLoader(DATA_DIR)
    
    # Load geospatial data with better error handling
    @st.cache_data
    def load_all_geospatial_data():
        """Load all geospatial data with proper error handling"""
        results = {'grid': None, 'wards': None, 'villages': {}}
        
        try:
            results['grid'] = data_loader.load_grid_data()
        except Exception as e:
            st.sidebar.warning(f"Grid data not available: {e}")
        
        try:
            results['wards'] = data_loader.load_ward_data()
        except Exception as e:
            st.sidebar.warning(f"Ward data not available: {e}")
        
        try:
            results['villages'] = data_loader.load_village_lists()
        except Exception as e:
            st.sidebar.warning(f"Village data not available: {e}")
        
        return results
    
    # Load all data
    geospatial_data = load_all_geospatial_data()
    grid_gdf = geospatial_data['grid']
    ward_gdf = geospatial_data['wards']
    village_data = geospatial_data['villages']
    
    # Debug info
    if st.sidebar.checkbox("Show debug info"):
        st.sidebar.write("Available files:")
        for file in data_loader.get_available_files():
            st.sidebar.write(f"- {file.name}")

except ImportError as e:
    st.error(f"Could not import map utilities: {e}")
    st.info("Running in basic mode without geospatial features")
    grid_gdf = None
    ward_gdf = None
    village_data = {}

# Sidebar controls
st.sidebar.header("Controls")

# File upload for continuing previous work
uploaded_file = st.sidebar.file_uploader("Upload previous annotations (optional)", type=['csv'])
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.session_state.annotations = df.to_dict('records')
    st.sidebar.success(f"Loaded {len(df)} previous annotations")

# Map settings
st.sidebar.header("Map Settings")

# Imagery selection
imagery_options = {
    'ESRI Satellite (Free)': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    'Google Satellite (Best Quality)': 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
    'OpenStreetMap (Reference)': None  # Will use default OSM
}

selected_imagery = st.sidebar.selectbox(
    "Choose satellite imagery:",
    list(imagery_options.keys()),
    index=0
)

# Navigation controls if ward data is available
if ward_gdf is not None:
    st.sidebar.header("Navigation")
    
    # Get treatment and control wards
    treatment_wards = ward_gdf[ward_gdf['is_treatment'] == True]['ward_name'].unique()
    control_wards = ward_gdf[ward_gdf['is_program_control'] == True]['ward_name'].unique()
    
    all_target_wards = list(treatment_wards) + list(control_wards)
    ward_options = ['Custom Location'] + sorted(all_target_wards)
    
    selected_ward = st.sidebar.selectbox("Jump to ward:", ward_options)
    
    # Village reference if available
    if village_data:
        with st.sidebar.expander("Treatment Villages", expanded=True):
            if 'treatment_villages' in village_data:
                st.write(f"**{len(village_data['treatment_villages'])} villages to locate:**")
                for i, village in enumerate(village_data['treatment_villages'][:6]):
                    st.write(f"{i+1}. {village}")
                if len(village_data['treatment_villages']) > 6:
                    st.write(f"... and {len(village_data['treatment_villages'])-6} more")
        
        with st.sidebar.expander("Control Villages"):
            if 'control_villages' in village_data:
                st.write(f"**{len(village_data['control_villages'])} villages:**")
                for i, village in enumerate(village_data['control_villages'][:6]):
                    st.write(f"{i+1}. {village}")
                if len(village_data['control_villages']) > 6:
                    st.write(f"... and {len(village_data['control_villages'])-6} more")

# Annotation mode selection
st.sidebar.header("Annotation Mode")
annotation_options = [
    "Treatment Village Location",
    "Control Village Location",
    "Treatment Ward (Other Areas)",
    "Control Ward (Other Areas)"
]

mode = st.sidebar.radio("Select annotation type:", annotation_options)
is_treatment = mode.startswith("Treatment")

# Create the map
def create_map():
    """Create the folium map with all layers"""
    
    # Determine map center and zoom
    if ward_gdf is not None and selected_ward != 'Custom Location':
        # Zoom to specific ward
        ward_subset = ward_gdf[ward_gdf['ward_name'] == selected_ward]
        if not ward_subset.empty:
            bounds = ward_subset.total_bounds
            center_lat = (bounds[1] + bounds[3]) / 2
            center_lon = (bounds[0] + bounds[2]) / 2
            zoom = 12
        else:
            # Fallback to program areas
            bounds = ward_gdf.total_bounds
            center_lat = (bounds[1] + bounds[3]) / 2
            center_lon = (bounds[0] + bounds[2]) / 2
            zoom = 9
    else:
        # Default to Tanzania or user's previous location
        if st.session_state.annotations:
            # Center on existing annotations
            lats = [ann['latitude'] for ann in st.session_state.annotations]
            lngs = [ann['longitude'] for ann in st.session_state.annotations]
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lngs) / len(lngs)
            zoom = 10
        else:
            # Default to central Tanzania
            center_lat = -6.0
            center_lon = 35.0
            zoom = 6

    # Create base map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles=None if imagery_options[selected_imagery] else 'OpenStreetMap'
    )
    
    # Add selected satellite imagery
    if imagery_options[selected_imagery]:
        folium.TileLayer(
            tiles=imagery_options[selected_imagery],
            attr='Satellite Imagery',
            name=selected_imagery.split(' (')[0],
            control=False
        ).add_to(m)
    
    # Add grid overlay if available
    if grid_gdf is not None:
        def grid_style_function(feature):
            props = feature['properties']
            if props.get('is_treatment_ward', False):
                return {
                    'fillColor': 'red',
                    'color': 'darkred',
                    'weight': 1,
                    'fillOpacity': 0.1,
                    'opacity': 0.6
                }
            elif props.get('is_program_control', False):
                return {
                    'fillColor': 'blue',
                    'color': 'darkblue',
                    'weight': 1,
                    'fillOpacity': 0.1,
                    'opacity': 0.6
                }
            else:
                return {
                    'fillColor': 'gray',
                    'color': 'gray',
                    'weight': 0.5,
                    'fillOpacity': 0.02,
                    'opacity': 0.2
                }

        folium.GeoJson(
            grid_gdf,
            style_function=grid_style_function,
            popup=folium.Popup('Grid Cell'),
            tooltip=folium.Tooltip(['grid_id', 'ward_name', 'district']),
            name='Grid ells'
        ).add_to(m)
    
    # Add ward boundaries if available
    if ward_gdf is not None:
        folium.GeoJson(
            ward_gdf,
            style_function=lambda x: {
                'color': 'yellow',
                'weight': 2,
                'fillOpacity': 0,
                'opacity': 0.7,
                'dashArray': '5,5'
            },
            popup=folium.Popup('Ward Boundary'),
            tooltip=folium.Tooltip(['ward_name', 'dist_name', 'reg_name']),
            name='Ward Boundaries'
        ).add_to(m)
    
    # Add existing annotations
    for i, ann in enumerate(st.session_state.annotations):
        color = 'red' if ann['is_treatment'] else 'blue'
        icon_symbol = 'home' if 'Village' in ann.get('annotation_type', '') else 'circle'
        
        folium.Marker(
            location=[ann['latitude'], ann['longitude']],
            popup=f"""
            <b>{ann.get('annotation_type', ann.get('type', 'Annotation'))}</b><br>
            Lat: {ann['latitude']:.6f}<br>
            Lng: {ann['longitude']:.6f}<br>
            Time: {ann.get('timestamp', 'Unknown')}
            """,
            icon=folium.Icon(color='red' if ann['is_treatment'] else 'blue', icon=icon_symbol),
            tooltip=f"Annotation {i+1}: {ann.get('annotation_type', ann.get('type', 'Unknown'))}"
        ).add_to(m)
    
    # Add layer control if we have multiple layers
    if grid_gdf is not None or ward_gdf is not None:
        folium.LayerControl().add_to(m)
    
    return m

# Create and display map
st.subheader("Click on the map to annotate areas")

# Layout: map and info panel
col1, col2 = st.columns([3, 1])

with col1:
    m = create_map()
    map_data = st_folium(m, width=900, height=600, returned_objects=["last_clicked"])

with col2:
    st.subheader("Current Context")
    
    # Show current ward if selected
    if ward_gdf is not None and selected_ward != 'Custom Location':
        st.write(f"**Focus:** {selected_ward}")
        ward_info = ward_gdf[ward_gdf['ward_name'] == selected_ward]
        if not ward_info.empty:
            ward_row = ward_info.iloc[0]
            st.write(f"**District:** {ward_row['dist_name']}")
            st.write(f"**Region:** {ward_row['reg_name']}")
            
            if ward_row['is_treatment']:
                st.success("Treatment Ward")
            elif ward_row['is_program_control']:
                st.info("Control Ward")
    
    st.write(f"**Mode:** {mode}")
    
    # Show statistics
    st.subheader("Progress")
    total_annotations = len(st.session_state.annotations)
    treatment_count = sum(1 for ann in st.session_state.annotations if ann['is_treatment'])
    control_count = total_annotations - treatment_count
    
    st.metric("Total Annotations", total_annotations)
    st.metric("Treatment Areas", treatment_count)
    st.metric("Control Areas", control_count)

# Handle map clicks
if map_data['last_clicked']:
    lat = map_data['last_clicked']['lat']
    lng = map_data['last_clicked']['lng']
    
    # Create new annotation with enhanced information
    new_annotation = {
        'latitude': lat,
        'longitude': lng,
        'is_treatment': is_treatment,
        'annotation_type': mode,
        'type': mode,  # Keep for backwards compatibility
        'timestamp': datetime.now().isoformat(),
    }
    
    # Add grid/ward context if available
    if grid_gdf is not None:
        # Find which grid cell this point falls in
        from shapely.geometry import Point
        point = Point(lng, lat)
        containing_cells = grid_gdf[grid_gdf.geometry.contains(point)]
        if not containing_cells.empty:
            cell_info = containing_cells.iloc[0]
            new_annotation['grid_id'] = cell_info.get('grid_id', 'Unknown')
            new_annotation['ward_name'] = cell_info.get('ward_name', 'Unknown')
            new_annotation['district'] = cell_info.get('district', 'Unknown')
    
    st.session_state.annotations.append(new_annotation)
    st.success(f"Added {mode} at coordinates: {lat:.6f}, {lng:.6f}")
    st.rerun()

# Display current annotations
st.subheader(f"Current Annotations ({len(st.session_state.annotations)})")

if st.session_state.annotations:
    df = pd.DataFrame(st.session_state.annotations)
    
    # Show most recent annotations first
    df_display = df.sort_values('timestamp', ascending=False) if 'timestamp' in df.columns else df
    st.dataframe(df_display)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # CSV download
        csv = df.to_csv(index=False)
        st.download_button(
            label="📊 Download CSV",
            data=csv,
            file_name=f"annotations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # Map download
        map_html = m._repr_html_()
        st.download_button(
            label="🗺️ Download Map",
            data=map_html,
            file_name=f"map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            mime="text/html"
        )
    
    with col3:
        # Clear all button
        if st.button("🗑️ Clear All"):
            st.session_state.annotations = []
            st.rerun()

else:
    st.info("No annotations yet. Click on the map to start annotating!")

# Instructions
with st.expander("📋 Instructions", expanded=False):
    st.markdown("""
    ### Enhanced Annotation Workflow:
    
    1. **Choose satellite imagery** from the sidebar for best village visibility
    2. **Navigate to specific wards** using the dropdown to focus on target areas  
    3. **Reference village lists** in the sidebar to know which settlements to locate
    4. **Select annotation type** to specify what you're marking:
       - **Treatment Village Location**: Actual village settlements receiving intervention
       - **Control Village Location**: Control village settlements
       - **Treatment Ward (Other Areas)**: Other areas within treatment wards
       - **Control Ward (Other Areas)**: Other areas within control wards
    5. **Click on the map** to place annotations
    6. **Download your work** regularly using the CSV/Map buttons
    7. **Resume work** by uploading your CSV file
    
    ### Visual Guide:
    - **Red grid cells/markers**: Treatment areas
    - **Blue grid cells/markers**: Control areas  
    - **Yellow dashed lines**: Ward boundaries
    - **Satellite imagery**: Use for identifying actual village settlements
    """)