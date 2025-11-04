#imports
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
from pathlib import Path
import sys
from folium import plugins
from streamlit_gsheets import GSheetsConnection
import json

# ============================================================================
# PAGE CONFIG 
# ============================================================================

# Page config
st.set_page_config(page_title="Treatment area mapping Rubeho CCT", layout="wide")

# ============================================================================
# GOOGLE SHEETS SETUP - OPTIMIZED
# ============================================================================
@st.cache_resource
def init_gsheets():
    return st.connection("gsheets", type=GSheetsConnection)

def load_annotations_from_sheet():
    """Load from sheet and cache in session state"""
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        if df.empty or len(df) == 0:
            return []
        
        annotations = []
        for idx, row in df.iterrows():
            ann = row.to_dict()
            
            # Handle geometry parsing - it's already a dict-like string from your sheet
            if 'geometry' in ann and ann['geometry']:
                geometry_value = ann['geometry']
                
                # Skip if it's NaN, None, or empty
                if pd.isna(geometry_value) or str(geometry_value).strip() in ['', 'nan', 'None']:
                    st.sidebar.warning(f"Row {idx}: Skipping - empty geometry")
                    continue
                
                # If it's a string, try to parse it
                if isinstance(geometry_value, str):
                    try:
                        # Your data appears to be dict-like strings, try json.loads first
                        ann['geometry'] = json.loads(geometry_value)
                    except json.JSONDecodeError:
                        # If JSON fails, try ast.literal_eval for Python dict strings
                        try:
                            import ast
                            ann['geometry'] = ast.literal_eval(geometry_value)
                        except (ValueError, SyntaxError) as e:
                            st.sidebar.error(f"Row {idx} ({ann.get('village_name', 'Unknown')}): Could not parse geometry - {str(e)[:100]}")
                            continue
                elif isinstance(geometry_value, dict):
                    # Already a dict, use as-is
                    ann['geometry'] = geometry_value
                else:
                    st.sidebar.warning(f"Row {idx}: Unexpected geometry type: {type(geometry_value)}")
                    continue
            else:
                # Skip rows without geometry
                st.sidebar.warning(f"Row {idx}: No geometry column found")
                continue
            
            # Handle boolean conversion for is_treatment
            if 'is_treatment' in ann:
                ann['is_treatment'] = str(ann['is_treatment']).strip().upper() in ['TRUE', 'YES', '1', 'T']
            
            annotations.append(ann)
        
        st.sidebar.success(f"✅ Loaded {len(annotations)} annotations from Sheet1")
        return annotations
        
    except Exception as e:
        st.sidebar.error(f"Could not load from Google Sheets: {e}")
        import traceback
        st.sidebar.code(traceback.format_exc())
        return []

def load_reference_villages_from_sheet():
    """Load the reference list of treatment villages from Sheet2"""
    try:
        df = conn.read(worksheet="ReferenceVillages", ttl=0)
        if df.empty or len(df) == 0:
            return None
        # Normalize: strip whitespace and ensure consistent column names
        df.columns = df.columns.str.strip().str.lower()
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].str.strip()
        return df
    except Exception as e:
        st.sidebar.warning(f"Could not load reference villages from Google Sheets: {e}")
        return None

def is_village_already_mapped(village_name, ward_name):
    """Check in session state instead of reading from sheet - OPTIMIZED"""
    return any(
        ann.get('village_name') == village_name and 
        ann.get('ward_name') == ward_name 
        for ann in st.session_state.annotations
    )

def save_annotation_to_sheet(annotation):
    """Save to sheet - reads once, writes once - OPTIMIZED"""
    try:
        annotation_copy = annotation.copy()
        annotation_copy['geometry'] = json.dumps(annotation_copy['geometry'])
        
        # Read current data
        df = conn.read(worksheet="Sheet1", ttl=0)
        new_row = pd.DataFrame([annotation_copy])
        
        if df.empty:
            df = new_row
        else:
            df = pd.concat([df, new_row], ignore_index=True)
        
        # Write back
        conn.update(worksheet="Sheet1", data=df)
        
        # Update session state immediately without re-reading - SAVES 1 API CALL
        st.session_state.annotations.append(annotation)
        
        return True, "Saved successfully"
    except Exception as e:
        return False, f"Error: {str(e)}"

def delete_annotation_from_sheet(village_name, ward_name):
    """Delete from sheet - reads once, writes once - OPTIMIZED"""
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        df = df[~((df['village_name'] == village_name) & (df['ward_name'] == ward_name))]
        conn.update(worksheet="Sheet1", data=df)
        
        # Update session state immediately without re-reading - SAVES 1 API CALL
        st.session_state.annotations = [
            ann for ann in st.session_state.annotations 
            if not (ann.get('village_name') == village_name and ann.get('ward_name') == ward_name)
        ]
        
        return True
    except Exception as e:
        st.error(f"Error deleting: {e}")
        return False

try:
    conn = init_gsheets()
    sheets_available = True
except Exception as e:
    st.sidebar.error(f"Google Sheets not available: {e}")
    sheets_available = False
# ============================================================================
# GEOSPATIAL DATA SETUP
# ============================================================================

# Add utils to path
sys.path.append(str(Path(__file__).parent))

try:
    from utils.map_utils import DataLoader

    # Initialize data loader
    DATA_DIR = Path(__file__).parent.parent / "data"
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
    ward_gdf = geospatial_data['wards']
    village_data = geospatial_data['villages']
 
except ImportError as e:
    st.error(f"Could not import map utilities: {e}")
    st.info("Running in basic mode without geospatial features")
    grid_gdf = None
    ward_gdf = None
    village_data = {}

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
if 'annotations' not in st.session_state:
    if sheets_available:
        st.session_state.annotations = load_annotations_from_sheet()
    else:
        st.session_state.annotations = []

if 'reference_villages' not in st.session_state:
    if sheets_available:
        st.session_state.reference_villages = load_reference_villages_from_sheet()
    else:
        st.session_state.reference_villages = None
# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def filter_villages_for_ward(selected_ward):
    """Filter villages for the selected ward - TREATMENT ONLY"""
    if selected_ward == 'All Treatment Wards':
        return []
    
    if st.session_state.reference_villages is not None:
        # Use Google Sheet reference data
        df = st.session_state.reference_villages
        ward_villages = df[
            df['ward_name'].str.strip().str.upper() == selected_ward.strip().upper()
        ]
        return ward_villages['village_name'].tolist()
    elif village_data and 'treatment_villages' in village_data:
        # Fallback to JSON method
        ward_info = ward_gdf[ward_gdf['ward_name'] == selected_ward]
        if ward_info.empty:
            return []
        
        ward_district = ward_info.iloc[0]['dist_name']
        treatment_villages = []
        for village in village_data['treatment_villages']:
            if selected_ward in village and ward_district in village:
                village_name = village.split(' village in')[0]
                treatment_villages.append(village_name)
        return treatment_villages
    
    return []

def create_map(selected_ward, annotations):
    """Create the folium map with all layers"""
    
    # Determine map center and zoom
    if ward_gdf is not None and selected_ward not in ['All Treatment Wards']:
        ward_subset = ward_gdf[ward_gdf['ward_name'] == selected_ward]
        if not ward_subset.empty:
            bounds = ward_subset.total_bounds
            center_lat = (bounds[1] + bounds[3]) / 2
            center_lon = (bounds[0] + bounds[2]) / 2
            zoom = 13
        else:
            bounds = ward_gdf.total_bounds
            center_lat = (bounds[1] + bounds[3]) / 2
            center_lon = (bounds[0] + bounds[2]) / 2
            zoom = 9
    elif ward_gdf is not None and selected_ward == 'All Treatment Wards':
        bounds = ward_gdf.total_bounds
        center_lat = (bounds[1] + bounds[3]) / 2
        center_lon = (bounds[0] + bounds[2]) / 2
        zoom = 10
    else:
        center_lat = -6.0
        center_lon = 35.0
        zoom = 6
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles=None
    )

    # Add tile layers
    folium.TileLayer(tiles='OpenStreetMap', name='OpenStreetMap', control=True).add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='ESRI', name='ESRI Satellite', control=True
    ).add_to(m)
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google', name='Google Satellite', control=True, show=True
    ).add_to(m)

    # Add ward boundaries
    if ward_gdf is not None:
        if selected_ward == 'All Treatment Wards':
            target_ward_gdf = ward_gdf[ward_gdf['is_treatment'] == True]
            if not target_ward_gdf.empty:
                folium.GeoJson(
                    target_ward_gdf,
                    style_function=lambda x: {'color': 'red', 'weight': 2, 'fillOpacity': 0.1, 'opacity': 0.7, 'dashArray': '5,5'},
                    tooltip=folium.GeoJsonTooltip(fields=['ward_name', 'dist_name', 'reg_name'], aliases=['Ward:', 'District:', 'Region:']),
                    name='Ward Boundaries'
                ).add_to(m)
        else:
            selected_ward_gdf = ward_gdf[ward_gdf['ward_name'] == selected_ward]
            if not selected_ward_gdf.empty:
                folium.GeoJson(
                    selected_ward_gdf,
                    style_function=lambda x: {'color': 'yellow', 'weight': 2, 'fillOpacity': 0, 'opacity': 0.7, 'dashArray': '5,5'},
                    tooltip=folium.GeoJsonTooltip(fields=['ward_name', 'dist_name', 'reg_name'], aliases=['Ward:', 'District:', 'Region:']),
                    name='Ward Boundary'
                ).add_to(m)
    
    # Add drawing tools
    draw = plugins.Draw(
        export=True,
        draw_options={'polyline': False, 'rectangle': True, 'polygon': True, 'circle': False, 'marker': False, 'circlemarker': False},
        edit_options={'edit': False}
    )
    draw.add_to(m)

    # Add existing annotations
    for ann in annotations:
        if 'geometry' in ann:
            color = 'red' if ann.get('is_treatment', False) else 'blue'
            folium.GeoJson(
                ann['geometry'],
                style_function=lambda x, color=color: {'fillColor': color, 'color': color, 'weight': 2, 'fillOpacity': 0.3},
                popup=folium.Popup(f"<b>{ann.get('village_name', 'Unknown')}</b><br>Type: {ann.get('village_type', 'Unknown')}<br>Ward: {ann.get('ward_name', 'Unknown')}"),
                tooltip=f"{ann.get('village_name', 'Unknown')} ({ann.get('village_type', 'Unknown')})"
            ).add_to(m)

    folium.LayerControl(position='topright', collapsed=False).add_to(m)
    return m



# ============================================================================
# MAIN APP LAYOUT
# ============================================================================
st.title("🌳 Treatment area mapping tool")

# Create tabs
tab1, tab2 = st.tabs(["🗺️ Mapping Interface", "📊 Progress Tracker"])

# ============================================================================
# TAB 1: MAPPING INTERFACE
# ============================================================================
with tab1:
    # Handle navigation from Progress Tracker tab
    ward_from_params = None
    village_from_params = None
    
    if "ward" in st.query_params:
        ward_from_params = st.query_params["ward"]
    
    if "village" in st.query_params:
        village_from_params = st.query_params["village"]
    
    if "tab" in st.query_params and st.query_params["tab"] == "mapping":
        del st.query_params["tab"]
    
    # Initialize variables that will be used throughout the tab
    village_name = None
    village_type = None
    is_treatment = True
    selected_ward = 'All Treatment Wards'
    
    # Sidebar navigation
    if ward_gdf is not None:
        st.sidebar.header("Navigation")
        treatment_wards = ward_gdf[ward_gdf['is_treatment'] == True]['ward_name'].unique()
        ward_options = ['All Treatment Wards'] + sorted(list(treatment_wards))
        
        default_ward = 'All Treatment Wards'
        if ward_from_params and ward_from_params in ward_options:
            default_ward = ward_from_params
            # Clear the ward param after using it
            if "ward" in st.query_params:
                del st.query_params["ward"]
        
        selected_ward = st.sidebar.selectbox(
            "Jump to ward:", 
            ward_options,
            index=ward_options.index(default_ward) if default_ward in ward_options else 0
        )
        
        # Filter villages for selected ward
        treatment_villages_in_ward = filter_villages_for_ward(selected_ward)
        
        # Show villages in sidebar
        if selected_ward not in ['All Treatment Wards']:
            st.sidebar.header(f"Villages in {selected_ward}")
            if treatment_villages_in_ward:
                with st.sidebar.expander("Treatment Villages to Map", expanded=True):
                    st.write(f"**{len(treatment_villages_in_ward)} villages:**")
                    for i, village in enumerate(treatment_villages_in_ward):
                        st.write(f"{i+1}. {village}")
            else:
                st.sidebar.warning("No villages found for this ward in the database")
        
        # Village selector
        st.sidebar.header("Select Village to Map")
        if selected_ward not in ['All Treatment Wards'] and treatment_villages_in_ward:
            village_options = [f"{v} (Treatment)" for v in treatment_villages_in_ward]
            
            # Auto-select village if coming from progress tracker
            default_village_index = 0
            if village_from_params:
                matching_option = f"{village_from_params} (Treatment)"
                if matching_option in village_options:
                    default_village_index = village_options.index(matching_option)
                    # Clear the village param after using it
                    if "village" in st.query_params:
                        del st.query_params["village"]
            
            selected_village_option = st.sidebar.selectbox(
                "Choose village:", 
                village_options,
                index=default_village_index
            )
            
            # EXTRACT THE VILLAGE INFO FROM THE SELECTION
            village_name = selected_village_option.split(' (')[0]
            village_type = 'Treatment'
            is_treatment = True
            
            st.sidebar.success(f"Now mapping: {village_name}")
            st.sidebar.info("Draw a polygon around this village settlement on the map")
        else:
            if selected_ward == 'All Treatment Wards':
                st.sidebar.info("Select a specific ward to see villages")
            else:
                st.sidebar.warning("No villages to map in this ward")

    
    # Debug info
    if st.sidebar.checkbox("Show debug info"):
        st.sidebar.write("Available files:")
        for file in data_loader.get_available_files():
            st.sidebar.write(f"- {file.name}")
    
    # Main content area
    st.subheader("Click on the relevant ward to create village areas")
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        m = create_map(selected_ward, st.session_state.annotations)
        map_data = st_folium(
            m, 
            width=900,
            height=900,
            returned_objects=["all_drawings", "last_active_drawing"],
            key=f"map_{selected_ward}_{len(st.session_state.annotations)}"
        )
    
    with col2:
        st.subheader("Current Context")
        
        if ward_gdf is not None and selected_ward not in ['All Treatment Wards']:
            st.write(f"**Focus ward:** {selected_ward}")
            ward_info = ward_gdf[ward_gdf['ward_name'] == selected_ward]
            if not ward_info.empty:
                ward_row = ward_info.iloc[0]
                st.write(f"**District:** {ward_row['dist_name']}")
                st.write(f"**Region:** {ward_row['reg_name']}")
                if ward_row['is_treatment']:
                    st.success("Treatment Ward")
        
        if village_name:
            st.write(f"**Mapping village:** {village_name}")
            st.write(f"**Type:** {village_type} village")
        else:
            st.write("**Select a ward and village to start mapping**")
    
    # Handle drawn polygons
    if map_data and map_data.get('last_active_drawing') and village_name:
        drawing = map_data['last_active_drawing']
        st.session_state['pending_annotation'] = {
            'village_name': village_name,
            'village_type': village_type,
            'is_treatment': is_treatment,
            'ward_name': selected_ward,
            'geometry': drawing['geometry'],
            'timestamp': datetime.now().isoformat(),
        }
        st.info(f"✏️ Polygon drawn for **{village_name}** - Click 'Save to Database' below to confirm")
    
    # Pending annotation save/discard
    if 'pending_annotation' in st.session_state and st.session_state['pending_annotation']:
        st.markdown("---")
        st.subheader("💾 Pending Annotation")
        
        col_preview, col_actions = st.columns([2, 1])
        
        with col_preview:
            pending = st.session_state['pending_annotation']
            st.write(f"**Village:** {pending['village_name']}")
            st.write(f"**Ward:** {pending['ward_name']}")
            st.write(f"**Type:** {pending['village_type']}")
        
        with col_actions:
            already_mapped = any(
                ann.get('village_name') == pending['village_name'] and 
                ann.get('ward_name') == pending['ward_name'] 
                for ann in st.session_state.annotations
            )
            
            if already_mapped:
                st.warning("⚠️ Already mapped!")
                if st.button("🗑️ Clear Pending", type="secondary", use_container_width=True):
                    del st.session_state['pending_annotation']
                    st.rerun()
            else:
                if st.button("💾 Save to Database", type="primary", use_container_width=True):
                    if sheets_available:
                        success, message = save_annotation_to_sheet(pending)
                        if success:
                            st.success(f"✅ {pending['village_name']} saved successfully!")
                            del st.session_state['pending_annotation']
                            st.rerun()
                        else:
                            st.error(f"❌ Save failed: {message}")
                    else:
                        st.session_state.annotations.append(pending)
                        st.success("✅ Saved locally (offline mode)")
                        del st.session_state['pending_annotation']
                        st.rerun()
                
                if st.button("🗑️ Discard", type="secondary", use_container_width=True):
                    del st.session_state['pending_annotation']
                    st.rerun()
        
        st.markdown("---")
    
    # Refresh button
    col_refresh, col_spacer = st.columns([1, 3])
    with col_refresh:
        if st.button("🔄 Refresh from Database"):
            if sheets_available:
                st.session_state.annotations = load_annotations_from_sheet()
                st.success("✅ Refreshed from database")
                st.rerun()
    
    st.markdown("---")
    
    # Display annotations
    # st.subheader(f"Current Annotations ({len(st.session_state.annotations)})")
    
    # if st.session_state.annotations:
    #     st.write("### Mapped Villages")
    #     for idx, ann in enumerate(st.session_state.annotations):
    #         col_info, col_delete = st.columns([4, 1])
            
    #         with col_info:
    #             village_name_display = ann.get('village_name', 'Unknown')
    #             village_type_display = ann.get('village_type', 'Unknown')
    #             ward_name_display = ann.get('ward_name', 'Unknown')
    #             timestamp = ann.get('timestamp', 'Unknown')
                
    #             icon = "🔴" if village_type_display == 'Treatment' else "🔵"
    #             st.markdown(f"{icon} **{village_name_display}** ({village_type_display}) in {ward_name_display}")
    #             st.caption(f"Mapped at: {timestamp[:19] if len(timestamp) > 19 else timestamp}")
            
    #         with col_delete:
    #             if st.button("🗑️", key=f"delete_{idx}"):
    #                 if sheets_available:
    #                     if delete_annotation_from_sheet(ann['village_name'], ann['ward_name']):
    #                         st.rerun()
        
    #     st.write("---")
        
    #     # Export buttons
    #     col1, col2 = st.columns(2)
    #     with col1:
    #         df = pd.DataFrame(st.session_state.annotations)
    #         csv = df.to_csv(index=False)
    #         st.download_button(
    #             label="📊 Export Backup CSV",
    #             data=csv,
    #             file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    #             mime="text/csv"
    #         )
    #     with col2:
    #         map_html = m._repr_html_()
    #         st.download_button(
    #             label="🗺️ Download Map",
    #             data=map_html,
    #             file_name=f"village_map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
    #             mime="text/html"
    #         )
    # else:
    #     st.info("No villages mapped yet. Select a ward and village, then draw a polygon around the settlement!")
    
    # Instructions
    with st.expander("📋 Instructions", expanded=False):
        st.markdown("""
        ### Workflow:
        1. **Navigate to specific wards** using the dropdown menu on the left
        2. **Select a village to map** in the dropdown in the sidebar
        3. **Locate the village** on the map - use different basemaps for context
        4. **Click draw a polygon** on left side of the map
        5. **Draw lines around the village outline** - click first point to close
        6. **Check the pending annotation** appears correctly
        7. **Click save to database** to confirm
        """)


# ============================================================================
# TAB 2: PROGRESS TRACKER
# ============================================================================
with tab2:
    st.header("📊 Progress Tracker - Treatment Villages")
    
    # Refresh button
    col_refresh_top, col_spacer_top = st.columns([1, 3])
    with col_refresh_top:
        if st.button("🔄 Refresh from Database", key="refresh_progress"):
            if sheets_available:
                st.session_state.annotations = load_annotations_from_sheet()
                st.session_state.reference_villages = load_reference_villages_from_sheet()
                st.success("✅ Refreshed!")
                st.rerun()
    
    if st.session_state.reference_villages is None:
        st.error("Could not load reference village list from Google Sheets 'ReferenceVillages' tab.")
        st.info("Make sure you have a 'ReferenceVillages' worksheet with columns: village_name, ward_name, district_name, region_name")
    else:
        # Use the reference villages from Google Sheet
        df_treatment = st.session_state.reference_villages.copy()
        df_treatment = df_treatment.rename(columns={
            'village_name': 'village',
            'ward_name': 'ward',
            'district_name': 'district',
            'region_name': 'region'
        })
        
        # Get mapped villages FROM DATABASE (Sheet1)
        mapped_villages = []
        for ann in st.session_state.annotations:
            mapped_villages.append({
                'village': str(ann.get('village_name', '')).strip().upper(),
                'ward': str(ann.get('ward_name', '')).strip().upper()
            })

        
        df_mapped = pd.DataFrame(mapped_villages) if mapped_villages else pd.DataFrame(columns=['village', 'ward'])
        
        # Mark mapped status with case-insensitive matching
        def is_mapped(row):
            if df_mapped.empty:
                return False
            village_upper = str(row['village']).strip().upper()
            ward_upper = str(row['ward']).strip().upper()
            return ((df_mapped['village'] == village_upper) & (df_mapped['ward'] == ward_upper)).any()
        
        df_treatment['mapped'] = df_treatment.apply(is_mapped, axis=1)
        
        # Overall statistics
        total_treatment = len(df_treatment)
        total_mapped = df_treatment['mapped'].sum()
        completion_pct = (total_mapped / total_treatment * 100) if total_treatment > 0 else 0
        
        st.subheader("Overall Progress")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Treatment Villages", total_treatment)
        col2.metric("In Database (Sheet1)", len(st.session_state.annotations))
        col3.metric("Matched & Mapped", int(total_mapped))
        col4.metric("Completion", f"{completion_pct:.1f}%")
        st.progress(completion_pct / 100)
        
        st.markdown("---")
        
        # Progress by ward
        st.subheader("Progress by Ward")
        ward_progress = df_treatment.groupby('ward').agg({
            'village': 'count',
            'mapped': 'sum'
        }).rename(columns={'village': 'total', 'mapped': 'mapped'})
        ward_progress['remaining'] = ward_progress['total'] - ward_progress['mapped']
        ward_progress['completion_pct'] = (ward_progress['mapped'] / ward_progress['total'] * 100).round(1)
        ward_progress = ward_progress.sort_values('completion_pct', ascending=False)
        
        for ward, row in ward_progress.iterrows():
            with st.expander(f"**{ward}** - {int(row['mapped'])}/{int(row['total'])} villages ({row['completion_pct']}%)", 
               expanded=False):

                col1, col2 = st.columns([4, 1])
                
                with col1:
                    st.progress(row['completion_pct'] / 100)
                    
                    unmapped = df_treatment[(df_treatment['ward'] == ward) & (~df_treatment['mapped'])]
                    if len(unmapped) > 0:
                        st.write(f"**🔴 Unmapped villages ({len(unmapped)}):**")
                        for idx, village_row in unmapped.iterrows():
                            col_village, col_btn = st.columns([3, 1])
                            with col_village:
                                st.write(f"  • {village_row['village']}")
                            with col_btn:
                                if st.button("📍 Map", key=f"map_{ward}_{village_row['village']}", use_container_width=True):
                                    st.query_params["ward"] = ward
                                    st.query_params["village"] = village_row['village']
                                    st.query_params["tab"] = "mapping"
                                    st.rerun()
                    else:
                        st.success("✅ All villages mapped!")
                    
                    mapped = df_treatment[(df_treatment['ward'] == ward) & (df_treatment['mapped'])]
                    if len(mapped) > 0:
                        with st.expander(f"✅ Mapped villages ({len(mapped)})", expanded=False):
                            for _, village_row in mapped.iterrows():
                                st.write(f"  • {village_row['village']}")
                
                with col2:
                    if row['remaining'] > 0:
                        st.write("")
                        st.write("")
                        if st.button(f"Go to Ward", key=f"jump_ward_{ward}", use_container_width=True):
                            st.query_params["ward"] = ward
                            st.query_params["tab"] = "mapping"
                            st.rerun()
        
        st.markdown("---")
        
        # Progress by district
        st.subheader("Progress by District")
        district_progress = df_treatment.groupby('district').agg({
            'village': 'count',
            'mapped': 'sum'
        }).rename(columns={'village': 'total', 'mapped': 'mapped'})
        district_progress['remaining'] = district_progress['total'] - district_progress['mapped']
        district_progress['completion_pct'] = (district_progress['mapped'] / district_progress['total'] * 100).round(1)
        
        # Format the dataframe for display
        district_progress_display = district_progress.copy()
        district_progress_display['completion_pct'] = district_progress_display['completion_pct'].apply(lambda x: f"{x:.1f}%")

        st.dataframe(
            district_progress_display,
            use_container_width=True
        )
        # Detailed village list
        st.subheader("Detailed Village List")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filter_status = st.selectbox(
                "Filter by status:",
                ["All", "Mapped", "Unmapped"]
            )
        
        with col2:
            filter_ward = st.selectbox(
                "Filter by ward:",
                ["All"] + sorted(df_treatment['ward'].unique().tolist())
            )
        
        with col3:
            filter_district = st.selectbox(
                "Filter by district:",
                ["All"] + sorted(df_treatment['district'].unique().tolist())
            )
        
        # Apply filters
        df_filtered = df_treatment.copy()
        
        if filter_status == "Mapped":
            df_filtered = df_filtered[df_filtered['mapped'] == True]
        elif filter_status == "Unmapped":
            df_filtered = df_filtered[df_filtered['mapped'] == False]
        
        if filter_ward != "All":
            df_filtered = df_filtered[df_filtered['ward'] == filter_ward]
        
        if filter_district != "All":
            df_filtered = df_filtered[df_filtered['district'] == filter_district]
        
        st.write(f"Showing {len(df_filtered)} of {len(df_treatment)} villages")
        
        # # Display without action buttons
        for idx, row in df_filtered.iterrows():
            status_icon = '✅' if row['mapped'] else '🔴'
            status_text = 'Mapped' if row['mapped'] else 'Unmapped'
            st.write(f"{status_icon} **{row['village']}** - {row['ward']} ward, {row['district']} district ({status_text})")
                
        st.markdown("---")
                
        # Export progress report
        st.subheader("Export Progress Report")
        
        col1, col2 = st.columns(2)
        
        with col1:
            csv_detailed = df_treatment.to_csv(index=False)
            st.download_button(
                label="📊 Download Detailed List (CSV)",
                data=csv_detailed,
                file_name=f"treatment_villages_progress_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        with col2:
            summary_data = {
                'Metric': ['Total Villages', 'Mapped', 'Unmapped', 'Completion %'],
                'Value': [total_treatment, total_mapped, total_treatment - total_mapped, f"{completion_pct:.1f}%"]
            }
            df_summary = pd.DataFrame(summary_data)
            csv_summary = df_summary.to_csv(index=False)
            
            st.download_button(
                label="📈 Download Summary Report (CSV)",
                data=csv_summary,
                file_name=f"mapping_progress_summary_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )