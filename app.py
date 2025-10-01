import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium import plugins
from utils.map_utils import DataLoader
import sys
from pathlib import Path
from datetime import datetime
import shapely.geometry as shp_geom
import traceback
import json
import time

# Page config
st.set_page_config(page_title="Treatment area mapping RUbeho CCT", layout="wide")
st.title("🌳 Treatment area mapping tool")

# Initialize session state for annotations - MUST BE EARLY
if 'annotations' not in st.session_state:
    st.session_state.annotations = []

# Add utils to path
sys.path.append(str(Path(__file__).parent / "utils"))

try:
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

# Performance & geometry detail (moved earlier so tolerance is defined before simplification)
with st.sidebar.expander("Performance & Detail", expanded=False):
    geom_detail = st.select_slider(
        "Ward boundary detail level",
        options=["Low", "Medium", "High"],
        value="Medium",
        help="Lower detail = faster map loading (geometry is simplified)."
    )

DETAIL_TOLERANCES_METERS = {"High": 10, "Medium": 50, "Low": 150}
selected_tolerance_m = DETAIL_TOLERANCES_METERS[geom_detail]

# Add lock view and recenter controls early
with st.sidebar.expander("View Controls", expanded=False):
    lock_view = st.checkbox("Lock map view (stop auto recenters)", value=st.session_state.get('lock_view', False))
    force_recenter = st.button("Recenter Now")
    st.session_state['lock_view'] = lock_view

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

def compute_map_view(ward_gdf, selected_ward, annotations):
    """Unified center computation"""
    try:
        if ward_gdf is not None and selected_ward not in ['All Target Areas']:
            subset = ward_gdf[ward_gdf['ward_name'] == selected_ward]
            if not subset.empty:
                b = subset.total_bounds  # minx, miny, maxx, maxy
                lat = (b[1] + b[3]) / 2
                lon = (b[0] + b[2]) / 2
                return [lat, lon], 13
            else:
                b = ward_gdf.total_bounds
                lat = (b[1] + b[3]) / 2
                lon = (b[0] + b[2]) / 2
                return [lat, lon], 9
        elif ward_gdf is not None and selected_ward == 'All Target Areas' and hasattr(ward_gdf, 'total_bounds'):
            b = ward_gdf.total_bounds
            lat = (b[1] + b[3]) / 2
            lon = (b[0] + b[2]) / 2
            return [lat, lon], 9
        # Fallback to annotations
        pts = _compute_annotation_centers(annotations)
        if pts:
            lat = sum(p[0] for p in pts) / len(pts)
            lon = sum(p[1] for p in pts) / len(pts)
            zoom = 10 if len(pts) < 20 else 9
            return [lat, lon], zoom
    except Exception as e:
        if st.session_state.get('debug'):
            st.sidebar.error(f"Center computation failed: {e}")
    return [-6.0, 35.0], 6

# Replace cached layer helpers with lightweight, non-cached builders
# (Caching folium layer objects can cause disappearance / stale references on rerun.)

@st.cache_data(show_spinner=False)
def get_simplified_ward_geojson(_ward_gdf, tolerance_m: int, max_vertices: int = 250_000):
    """Return a simplified, coordinate-rounded GeoJSON string for ward_gdf.
    _ward_gdf: input GeoDataFrame (EPSG:4326)
    tolerance_m: simplification tolerance in projected meters (Web Mercator)
    max_vertices: threshold over which simplification is applied regardless of detail level
    """
    if ward_gdf is None or len(ward_gdf) == 0:
        return None
    start_t = time.time()
    try:
        gdf = ward_gdf
        # Keep only required columns to shrink payload
        required_cols = [c for c in ['ward_name', 'dist_name', 'reg_name', 'geometry'] if c in gdf.columns]
        gdf = gdf[required_cols].copy()
        # Ensure CRS; assume data is already EPSG:4326 else attempt to set/convert gracefully
        try:
            if gdf.crs is None:
                gdf = gdf.set_crs(4326, allow_override=True)
        except Exception:
            pass
        try:
            gdf_proj = gdf.to_crs(3857)
        except Exception:
            gdf_proj = gdf
        def _geom_vertices(geom):
            if geom.is_empty:
                return 0
            if geom.geom_type == 'Polygon':
                return len(geom.exterior.coords)
            if geom.geom_type == 'MultiPolygon':
                return sum(len(p.exterior.coords) for p in geom.geoms)
            return 0
        total_vertices = int(gdf_proj.geometry.map(_geom_vertices).sum())
        apply_simplify = (tolerance_m > 0) and (geom_detail != 'High' or total_vertices > max_vertices)
        if apply_simplify:
            gdf_proj = gdf_proj.copy()
            gdf_proj['geometry'] = gdf_proj.geometry.simplify(tolerance=tolerance_m, preserve_topology=True)
        try:
            gdf_wgs = gdf_proj.to_crs(4326)
        except Exception:
            gdf_wgs = gdf_proj
        geojson_obj = json.loads(gdf_wgs.to_json())
        def _round_coords(obj, nd=5):
            if isinstance(obj, list):
                if len(obj) == 0:
                    return obj
                if isinstance(obj[0], (float, int)) and len(obj) >= 2:
                    return [round(obj[0], nd), round(obj[1], nd)] + ([round(obj[2], nd)] if len(obj) == 3 else [])
                else:
                    return [_round_coords(x, nd) for x in obj]
            elif isinstance(obj, dict):
                if 'coordinates' in obj:
                    obj['coordinates'] = _round_coords(obj['coordinates'], nd)
                elif 'geometries' in obj:
                    obj['geometries'] = [_round_coords(g, nd) for g in obj['geometries']]
                return obj
            else:
                return obj
        _round_coords(geojson_obj, nd=5 if geom_detail != 'High' else 6)
        for feat in geojson_obj.get('features', []):
            props = feat.get('properties', {})
            props['_simp_tol_m'] = tolerance_m if apply_simplify else 0
            props['_vertices_est'] = total_vertices
            props['_build_ms'] = int((time.time() - start_t) * 1000)
            feat['properties'] = props
        return json.dumps(geojson_obj, separators=(',', ':'))
    except Exception as e:
        if st.session_state.get('debug'):
            st.sidebar.error(f"Simplification failed: {e}")
        return None

# Multi-detail cache in session_state to avoid re-generation when switching detail levels
if 'ward_geojson_cache' not in st.session_state:
    st.session_state['ward_geojson_cache'] = {}
cache_key = f"{ward_gdf}-{selected_tolerance_m}"
if cache_key in st.session_state['ward_geojson_cache']:
    simplified_ward_geojson = st.session_state['ward_geojson_cache'][cache_key]
else:
    simplified_ward_geojson = get_simplified_ward_geojson(ward_gdf, selected_tolerance_m)
    st.session_state['ward_geojson_cache'][cache_key] = simplified_ward_geojson

def build_ward_layer(ward_gdf):
    # Prefer simplified serialized JSON if available
    if simplified_ward_geojson:
        try:
            return folium.GeoJson(
                data=simplified_ward_geojson,
                name='Ward Boundaries',
                style_function=lambda x: {
                    'color': 'yellow',
                    'weight': 1.5 if geom_detail != 'Low' else 1,
                    'fillOpacity': 0,
                    'opacity': 0.7,
                    'dashArray': '5,5'
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['ward_name', 'dist_name', 'reg_name'],
                    aliases=['Ward:', 'District:', 'Region:'],
                    localize=True
                )
            )
        except Exception as e:
            if st.session_state.get('debug'):
                st.write(f"Failed to use simplified JSON: {e}")
    # Fallback original path
    if ward_gdf is not None and hasattr(ward_gdf, 'empty') and not ward_gdf.empty:
        return folium.GeoJson(
            ward_gdf,
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
            name='Ward Boundaries'
        )
    return None

def build_annotation_layers(annotations):
    layers = []
    for ann in annotations:
        geom = ann.get('geometry')
        if not geom:
            continue
        color = 'red' if ann.get('is_treatment', False) else 'blue'
        try:
            layers.append(
                folium.GeoJson(
                    geom,
                    style_function=lambda x, color=color: {
                        'fillColor': color,
                        'color': color,
                        'weight': 2,
                        'fillOpacity': 0.3
                    },
                    tooltip=f"{ann.get('village_name','Unknown')} ({ann.get('village_type','?')})",
                    name=f"{ann.get('village_name','Ann')}"
                )
            )
        except Exception as e:
            if st.session_state.get('debug'):
                st.write(f"Annotation layer error: {e}")
    return layers

# Annotation layers caching (restore logic)
import hashlib as _hashlib

def _annotations_sig(annotations):
    if not annotations:
        return 'empty'
    # Use subset + length for stable lightweight signature
    sample = annotations[-15:]  # last 15 shapes
    raw = json.dumps(sample, sort_keys=True, default=str) + str(len(annotations))
    return _hashlib.md5(raw.encode('utf-8')).hexdigest()

if 'annotation_layers_sig' not in st.session_state:
    st.session_state.annotation_layers_sig = ''
if 'cached_annotation_layers' not in st.session_state:
    st.session_state.cached_annotation_layers = []

_current_sig = _annotations_sig(st.session_state.annotations)
if _current_sig != st.session_state.annotation_layers_sig:
    st.session_state.cached_annotation_layers = build_annotation_layers(st.session_state.annotations)
    st.session_state.annotation_layers_sig = _current_sig
    if st.session_state.get('debug'):
        st.sidebar.info(f"Rebuilt annotation layers ({len(st.session_state.cached_annotation_layers)})")

# Helper: compute annotation center points (lat, lon)
def _compute_annotation_centers(annotations):
    pts = []
    for ann in annotations:
        try:
            if 'latitude' in ann and 'longitude' in ann:
                pts.append((ann['latitude'], ann['longitude']))
                continue
            geom_dict = ann.get('geometry')
            if isinstance(geom_dict, dict):
                gtype = geom_dict.get('type')
                if gtype in ('Polygon', 'MultiPolygon', 'Point', 'GeometryCollection'):
                    try:
                        geom = shp_geom.shape(geom_dict)
                        c = geom.centroid
                        pts.append((c.y, c.x))
                    except Exception:
                        pass
                elif gtype == 'LineString':
                    coords = geom_dict.get('coordinates')
                    if coords:
                        mid = coords[len(coords)//2]
                        pts.append((mid[1], mid[0]))
        except Exception:
            continue
    return pts

# Store map center/zoom in session state
if 'map_center' not in st.session_state:
    st.session_state['map_center'] = [-6.0, 35.0]
    st.session_state['map_zoom'] = 6

# REMOVE old duplicated center calculation block and use unified function only
# (Previously there was logic here computing center_lat/center_lon/zoom directly.)
# We now rely exclusively on compute_map_view for clarity and to avoid race conditions.

# Build base map fresh each rerun (avoid caching folium objects)
def build_base_map(center, zoom, selected_imagery):
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles=None if imagery_options[selected_imagery] else 'OpenStreetMap'
    )
    if imagery_options[selected_imagery]:
        folium.TileLayer(
            tiles=imagery_options[selected_imagery],
            attr='Satellite Imagery',
            name=selected_imagery.split(' (')[0],
            control=False
        ).add_to(m)
    return m



# Compute and store center AFTER functions are defined
center, zoom = compute_map_view(ward_gdf, selected_ward, st.session_state.annotations)
st.session_state['map_center'] = center
st.session_state['map_zoom'] = zoom

# Remove any earlier premature center computation (if present)
# (No action needed; this comment documents intentional ordering.)

DETAIL_TOLERANCES_METERS = {"High": 10, "Medium": 50, "Low": 150}
selected_tolerance_m = DETAIL_TOLERANCES_METERS[geom_detail]

# Center computation adjustment: only recompute if not locked or forced or ward changed
if 'last_selected_ward_for_center' not in st.session_state:
    st.session_state['last_selected_ward_for_center'] = None

recompute_center = force_recenter or (not lock_view) or (st.session_state['last_selected_ward_for_center'] != selected_ward)
if recompute_center:
    center, zoom = compute_map_view(ward_gdf, selected_ward, st.session_state.annotations)
    st.session_state['map_center'] = center
    st.session_state['map_zoom'] = zoom
    st.session_state['last_selected_ward_for_center'] = selected_ward

# Proceed to map rendering
st.subheader("Click on the map to annotate areas")

# Layout: map and info panel
col1, col2 = st.columns([3, 1])

with col1:
    try:
        m = build_base_map(st.session_state.get('map_center', [-6.0, 35.0]), st.session_state.get('map_zoom', 6), selected_imagery)
        ward_layer = build_ward_layer(ward_gdf)
        if ward_layer:
            ward_layer.add_to(m)
        plugins.Draw(
            export=True,
            draw_options={'polyline': False,'rectangle': True,'polygon': True,'circle': False,'marker': False,'circlemarker': False},
            edit_options={'edit': False}
        ).add_to(m)
        for layer in st.session_state.cached_annotation_layers:
            layer.add_to(m)
        if ward_layer or grid_gdf is not None:
            folium.LayerControl().add_to(m)
        map_data = st_folium(m, width=900, height=600, returned_objects=["all_drawings","last_active_drawing"], key="main_map")
    except Exception as e:
        if st.session_state.get('debug'):
            st.exception(e)
            st.code(traceback.format_exc())
        st.error("Map rendering failed. Enable Debug mode for details.")
        map_data = None


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

            if getattr(ward_row, 'is_treatment', False):
                st.success("Treatment Ward")
            elif getattr(ward_row, 'is_program_control', False):
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
        
        new_annotation = {
            'village_name': village_name,
            'village_type': village_type,
            'is_treatment': is_treatment,
            'ward_name': selected_ward,
            'geometry': drawing['geometry'],
            'timestamp': datetime.now().isoformat(),
        }
        
        st.session_state.annotations.append(new_annotation)
        st.success(f"✓ Mapped {village_name} as {village_type} village in {selected_ward}")
        st.rerun()
    elif map_data and map_data.get('last_active_drawing') and not village_name:
        st.warning("⚠️ Please select a village from the sidebar before drawing")

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
            label="📊 Download CSV",
            data=csv,
            file_name=f"village_annotations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
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