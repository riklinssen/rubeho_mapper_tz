import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
import geopandas as gpd
import json
from pathlib import Path
import sys
from folium import plugins
from streamlit_gsheets import GSheetsConnection
import json

# Initialize Google Sheets connection
@st.cache_resource
def init_gsheets():
    return st.connection("gsheets", type=GSheetsConnection)

try:
    conn = init_gsheets()
    
    # Load existing annotations from sheet
    @st.cache_data(ttl=10)
    def load_annotations_from_sheet():
        try:
            df = conn.read(worksheet="Sheet1", ttl=10)
            if df.empty or len(df) == 0:
                return []
            annotations = df.to_dict('records')
            for ann in annotations:
                if 'geometry' in ann and isinstance(ann['geometry'], str):
                    try:
                        ann['geometry'] = json.loads(ann['geometry'])
                    except:
                        pass
                if 'is_treatment' in ann:
                    ann['is_treatment'] = str(ann['is_treatment']).lower() == 'true'
            return annotations
        except Exception as e:
            st.sidebar.warning(f"Could not load from Google Sheets: {e}")
            return []
    
    def is_village_already_mapped(village_name, ward_name):
        try:
            df = conn.read(worksheet="Sheet1")
            if df.empty:
                return False
            existing = df[(df['village_name'] == village_name) & (df['ward_name'] == ward_name)]
            return not existing.empty
        except:
            return False
    
    def save_annotation_to_sheet(annotation):
        try:
            annotation_copy = annotation.copy()
            annotation_copy['geometry'] = json.dumps(annotation_copy['geometry'])
            df = conn.read(worksheet="Sheet1")
            new_row = pd.DataFrame([annotation_copy])
            if df.empty:
                df = new_row
            else:
                df = pd.concat([df, new_row], ignore_index=True)
            conn.update(worksheet="Sheet1", data=df)
            return True, "Saved"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def delete_annotation_from_sheet(village_name, ward_name):
        try:
            df = conn.read(worksheet="Sheet1")
            df = df[~((df['village_name'] == village_name) & (df['ward_name'] == ward_name))]
            conn.update(worksheet="Sheet1", data=df)
            return True
        except Exception as e:
            st.error(f"Error deleting: {e}")
            return False
    
    sheets_available = True
    
except Exception as e:
    st.sidebar.error(f"Google Sheets not available: {e}")
    sheets_available = False
    def load_annotations_from_sheet():
        return []
    def is_village_already_mapped(v, w):
        return False
    def save_annotation_to_sheet(a):
        return False, "Offline"
    def delete_annotation_from_sheet(v, w):
        return False


# Page config
st.set_page_config(page_title="Treatment area mapping RUbeho CCT", layout="wide")
st.title("🌳 Treatment area mapping tool")

# Initialize session state for annotations - MUST BE EARLY ###HERE
if 'annotations' not in st.session_state:
    if sheets_available:
        st.session_state.annotations = load_annotations_from_sheet()
    else:
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
        results['grid'] = None
       
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
    @st.cache_data
    def filter_villages_for_ward(selected_ward, ward_gdf_hash, village_data_hash):
        """Cache village filtering per ward to avoid reprocessing"""
        if selected_ward == 'All Target Areas' or not village_data:
            return [], []
        
        ward_info = ward_gdf[ward_gdf['ward_name'] == selected_ward]
        if ward_info.empty:
            return [], []
        
        ward_district = ward_info.iloc[0]['dist_name']
        
        treatment_villages = []
        if 'treatment_villages' in village_data:
            for village in village_data['treatment_villages']:
                if selected_ward in village and ward_district in village:
                    village_name = village.split(' village in')[0]
                    treatment_villages.append(village_name)
        
        control_villages = []
        if 'control_villages' in village_data:
            for village in village_data['control_villages']:
                if selected_ward in village and ward_district in village:
                    village_name = village.split(' village in')[0]
                    control_villages.append(village_name)
        
        return treatment_villages, control_villages

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


# Map settings
st.sidebar.header("Map Settings")


# Navigation controls if ward data is available
if ward_gdf is not None:
    st.sidebar.header("Navigation")
    
    # Get treatment and control wards
    treatment_wards = ward_gdf[ward_gdf['is_treatment'] == True]['ward_name'].unique()
    control_wards = ward_gdf[ward_gdf['is_program_control'] == True]['ward_name'].unique()
    
all_target_wards = list(treatment_wards) + list(control_wards)
ward_options = ['All Target Areas'] + sorted(all_target_wards)  # CHANGED: 'All Target Areas' instead of 'Custom Location'

selected_ward = st.sidebar.selectbox("Jump to ward:", ward_options)
# Filter villages for the selected ward
treatment_villages_in_ward, control_villages_in_ward = filter_villages_for_ward(
    selected_ward, 
    id(ward_gdf),  # Hash for cache invalidation
    id(village_data)
)
# Show villages for selected ward only
if selected_ward not in ['All Target Areas']:
    st.sidebar.header(f"Villages in {selected_ward}")
    
    if treatment_villages_in_ward:
        with st.sidebar.expander("Treatment Villages to Map", expanded=True):
            st.write(f"**{len(treatment_villages_in_ward)} villages:**")
            for i, village in enumerate(treatment_villages_in_ward):
                st.write(f"{i+1}. {village}")
    
    if control_villages_in_ward:
        with st.sidebar.expander("Control Villages to Map", expanded=False):
            st.write(f"**{len(control_villages_in_ward)} villages:**")
            for i, village in enumerate(control_villages_in_ward):
                st.write(f"{i+1}. {village}")
    
    if not treatment_villages_in_ward and not control_villages_in_ward:
        st.sidebar.warning("No villages found for this ward in the database")

# Annotation mode selection
# Village selector for annotation
st.sidebar.header("Select Village to Map")

if selected_ward not in ['All Target Areas']:
    # Combine treatment and control villages for selection
    all_villages = []
    if treatment_villages_in_ward:
        all_villages.extend([(v, 'Treatment') for v in treatment_villages_in_ward])
    if control_villages_in_ward:
        all_villages.extend([(v, 'Control') for v in control_villages_in_ward])
    
    if all_villages:
        village_options = [f"{v[0]} ({v[1]})" for v in all_villages]
        selected_village_option = st.sidebar.selectbox("Choose village:", village_options)
        
        # Extract village name and type
        village_name = selected_village_option.split(' (')[0]
        village_type = 'Treatment' if '(Treatment)' in selected_village_option else 'Control'
        is_treatment = village_type == 'Treatment'
        
        st.sidebar.success(f"Now mapping: {village_name}")
        st.sidebar.info("Draw a polygon around this village settlement on the map")
    else:
        st.sidebar.warning("No villages to map in this ward")
        village_name = None
        village_type = None
        is_treatment = True
else:
    st.sidebar.info("Select a specific ward to see villages")
    village_name = None
    village_type = None
    is_treatment = True


# Create the map
def create_map():
    """Create the folium map with all layers"""
    
    # Determine map center and zoom
    if ward_gdf is not None and selected_ward not in ['All Target Areas']:
        # SPECIFIC WARD SELECTED - zoom to it and show grid
        ward_subset = ward_gdf[ward_gdf['ward_name'] == selected_ward]
        if not ward_subset.empty:
            bounds = ward_subset.total_bounds
            center_lat = (bounds[1] + bounds[3]) / 2
            center_lon = (bounds[0] + bounds[2]) / 2
            zoom = 13
            show_grid = True
        else:
            bounds = ward_gdf.total_bounds
            center_lat = (bounds[1] + bounds[3]) / 2
            center_lon = (bounds[0] + bounds[2]) / 2
            zoom = 9
            show_grid = False
    elif ward_gdf is not None and selected_ward == 'All Target Areas':
        bounds = ward_gdf.total_bounds
        center_lat = (bounds[1] + bounds[3]) / 2
        center_lon = (bounds[0] + bounds[2]) / 2
        zoom = 9
        show_grid = False
    else:
        if st.session_state.annotations:
            lats = [ann['latitude'] for ann in st.session_state.annotations]
            lngs = [ann['longitude'] for ann in st.session_state.annotations]
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lngs) / len(lngs)
            zoom = 10
        else:
            center_lat = -6.0
            center_lon = 35.0
            zoom = 6
        show_grid = False

    # Create base map with no default tiles
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles=None
    )

    # Add all imagery options as toggleable layers
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='OpenStreetMap',
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='ESRI',
        name='ESRI Satellite',
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Satellite',
        control=True,
        show=True  # Make this the default visible layer
    ).add_to(m)

    # Add ward boundaries if available - ONLY FOR SELECTED WARD
    if ward_gdf is not None and selected_ward not in ['All Target Areas']:
        # Filter to only the selected ward
        selected_ward_gdf = ward_gdf[ward_gdf['ward_name'] == selected_ward]
        
        if not selected_ward_gdf.empty:
            folium.GeoJson(
                selected_ward_gdf,
                style_function=lambda x: {
                    'color': 'yellow',
                    'weight': 2,
                    'fillOpacity': 0,
                    'opacity': 0.7,
                    'dashArray': '5,5'
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['ward_name', 'dist_name', 'reg_name'],
                    aliases=['Ward:', 'District:', 'Region:'],
                    localize=True
                ),
                name='Ward Boundary'
            ).add_to(m)

    # Add drawing tools for polygon annotation
    draw = plugins.Draw(
        export=True,
        draw_options={
            'polyline': False,
            'rectangle': True,
            'polygon': True,
            'circle': False,
            'marker': False,
            'circlemarker': False,
        },
        edit_options={'edit': False}
    )
    draw.add_to(m)

    # Add existing annotations as polygons
    for i, ann in enumerate(st.session_state.annotations):
        if 'geometry' in ann:
            # New polygon-based annotations
            color = 'red' if ann.get('is_treatment', False) else 'blue'
            
            folium.GeoJson(
                ann['geometry'],
                style_function=lambda x, color=color: {
                    'fillColor': color,
                    'color': color,
                    'weight': 2,
                    'fillOpacity': 0.3
                },
                popup=folium.Popup(f"<b>{ann.get('village_name', 'Unknown')}</b><br>Type: {ann.get('village_type', 'Unknown')}<br>Ward: {ann.get('ward_name', 'Unknown')}"),
                tooltip=f"{ann.get('village_name', 'Unknown')} ({ann.get('village_type', 'Unknown')})"
            ).add_to(m)

    # Add layer control
    folium.LayerControl(position='topright', collapsed=False).add_to(m)

    
    return m


# Create and display map (THIS IS OUTSIDE THE FUNCTION)
st.subheader("Click on the map to annotate areas")

# Layout: map and info panel
col1, col2 = st.columns([3, 1])

with col1:
    m = create_map()  # Call the function here
    map_data = st_folium(
        m, 
        width=900, 
        height=600, 
        returned_objects=["all_drawings", "last_active_drawing"],
        key=f"map_{selected_ward}_{len(st.session_state.annotations)}"
    )


with col2:
    st.subheader("Current Context")
    
    # Show current ward if selected
    if ward_gdf is not None and selected_ward not in ['All Target Areas']:  # CHANGED: updated condition
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
    
    if village_name:
        st.write(f"**Mapping:** {village_name}")
        st.write(f"**Type:** {village_type}")
    else:
        st.write("**Select a ward and village to start mapping**")
    
    # Show statistics
    st.subheader("Progress")
    total_annotations = len(st.session_state.annotations)
    treatment_count = sum(1 for ann in st.session_state.annotations if ann['is_treatment'])
    control_count = total_annotations - treatment_count
    
    st.metric("Total Annotations", total_annotations)
    st.metric("Treatment Areas", treatment_count)
    st.metric("Control Areas", control_count)

# Handle map clicks
# Capture drawn polygons
if map_data and map_data.get('last_active_drawing') and village_name:
    drawing = map_data['last_active_drawing']
    
    if sheets_available and is_village_already_mapped(village_name, selected_ward):
        st.warning(f"⚠️ {village_name} in {selected_ward} already mapped!")
    else:
        new_annotation = {
            'village_name': village_name,
            'village_type': village_type,
            'is_treatment': is_treatment,
            'ward_name': selected_ward,
            'geometry': drawing['geometry'],
            'timestamp': datetime.now().isoformat(),
        }
        
        if sheets_available:
            success, message = save_annotation_to_sheet(new_annotation)
            if success:
                st.session_state.annotations.append(new_annotation)
                st.cache_data.clear()
                st.success(f"✓ {village_name} saved to database")
            else:
                st.error(f"❌ {message}")
        else:
            st.session_state.annotations.append(new_annotation)
            st.warning("⚠️ Offline - not saved")

# Display current annotations
st.subheader(f"Current Annotations ({len(st.session_state.annotations)})")

if st.session_state.annotations:
    # Display mapped villages with delete buttons
    st.write("### Mapped Villages")
    for idx, ann in enumerate(st.session_state.annotations):
        col_info, col_delete = st.columns([4, 1])
        
        with col_info:
            village_name = ann.get('village_name', 'Unknown')
            village_type = ann.get('village_type', 'Unknown')
            ward_name = ann.get('ward_name', 'Unknown')
            timestamp = ann.get('timestamp', 'Unknown')
            
            # Color code based on type
            if village_type == 'Treatment':
                st.markdown(f"🔴 **{village_name}** ({village_type}) in {ward_name}")
            else:
                st.markdown(f"🔵 **{village_name}** ({village_type}) in {ward_name}")
            st.caption(f"Mapped at: {timestamp[:19] if len(timestamp) > 19 else timestamp}")
        
        with col_delete:
            if st.button("🗑️", key=f"delete_{idx}", help="Delete this annotation"):
                ann = st.session_state.annotations[idx]
            if sheets_available:
                if delete_annotation_from_sheet(ann['village_name'], ann['ward_name']):
                    st.session_state.annotations.pop(idx)
                    st.cache_data.clear()
                    st.rerun()
            else:
                st.session_state.annotations.pop(idx)
                st.rerun()
    st.write("---")
    
    # Export buttons
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV download
        df = pd.DataFrame(st.session_state.annotations)
        csv = df.to_csv(index=False)
        st.download_button(
            label="📊 Export Backup CSV",
            data=csv,
            file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            help="Backup only - auto-saved to Google Sheets"
        )

    with col2:
        # Map download
        map_html = m._repr_html_()
        st.download_button(
            label="🗺️ Download Map",
            data=map_html,
            file_name=f"village_map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            mime="text/html"
        )

else:
    st.info("No villages mapped yet. Select a ward and village, then draw a polygon around the settlement!")
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