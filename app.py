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
# GOOGLE SHEETS SETUP
# ============================================================================

# Initialize Google Sheets connection
@st.cache_resource
def init_gsheets():
    return st.connection("gsheets", type=GSheetsConnection)

try:
    conn = init_gsheets()
    
    # Load existing annotations from sheet - NO CACHING
    def load_annotations_from_sheet():
        try:
            df = conn.read(worksheet="Sheet1", ttl=0)  # ttl=0 = no cache
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
            df = conn.read(worksheet="Sheet1", ttl=0)  # ttl=0 = no cache
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
            df = conn.read(worksheet="Sheet1", ttl=0)  # ttl=0 = no cache
            new_row = pd.DataFrame([annotation_copy])
            if df.empty:
                df = new_row
            else:
                df = pd.concat([df, new_row], ignore_index=True)
            conn.update(worksheet="Sheet1", data=df)
            return True, "Saved successfully"
        except Exception as e:
            return False, f"Error: {str(e)}"

    
    def delete_annotation_from_sheet(village_name, ward_name):
        try:
            df = conn.read(worksheet="Sheet1", ttl=0)  # ttl=0 = no cache
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





# ============================================================================
# GEOSPATIAL DATA SETUP
# ============================================================================

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
    
    
    #
    
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

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def filter_villages_for_ward(selected_ward):
        """Filter villages for the selected ward - TREATMENT ONLY"""
        if selected_ward == 'All Treatment Wards' or not village_data:
            return []
        
        ward_info = ward_gdf[ward_gdf['ward_name'] == selected_ward]
        if ward_info.empty:
            return []
        
        ward_district = ward_info.iloc[0]['dist_name']
        
        treatment_villages = []
        if 'treatment_villages' in village_data:
            for village in village_data['treatment_villages']:
                if selected_ward in village and ward_district in village:
                    village_name = village.split(' village in')[0]
                    treatment_villages.append(village_name)
        return treatment_villages


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
    # Sidebar navigation
    if ward_gdf is not None:
        st.sidebar.header("Navigation")
        treatment_wards = ward_gdf[ward_gdf['is_treatment'] == True]['ward_name'].unique()
        ward_options = ['All Treatment Wards'] + sorted(list(treatment_wards))
        
        default_ward = 'All Treatment Wards'
        if "ward" in st.query_params:
            requested_ward = st.query_params["ward"]
            if requested_ward in ward_options:
                default_ward = requested_ward
            st.query_params.clear()
        
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
            selected_village_option = st.sidebar.selectbox("Choose village:", village_options)
            
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
            village_name = None
            village_type = None
            is_treatment = True
    
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
            st.write(f"**Focus:** {selected_ward}")
            ward_info = ward_gdf[ward_gdf['ward_name'] == selected_ward]
            if not ward_info.empty:
                ward_row = ward_info.iloc[0]
                st.write(f"**District:** {ward_row['dist_name']}")
                st.write(f"**Region:** {ward_row['reg_name']}")
                if ward_row['is_treatment']:
                    st.success("Treatment Ward")
        
        if village_name:
            st.write(f"**Mapping:** {village_name}")
            st.write(f"**Type:** {village_type}")
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
                            st.session_state.annotations = load_annotations_from_sheet()
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
    st.subheader(f"Current Annotations ({len(st.session_state.annotations)})")
    
    if st.session_state.annotations:
        st.write("### Mapped Villages")
        for idx, ann in enumerate(st.session_state.annotations):
            col_info, col_delete = st.columns([4, 1])
            
            with col_info:
                village_name_display = ann.get('village_name', 'Unknown')
                village_type_display = ann.get('village_type', 'Unknown')
                ward_name_display = ann.get('ward_name', 'Unknown')
                timestamp = ann.get('timestamp', 'Unknown')
                
                icon = "🔴" if village_type_display == 'Treatment' else "🔵"
                st.markdown(f"{icon} **{village_name_display}** ({village_type_display}) in {ward_name_display}")
                st.caption(f"Mapped at: {timestamp[:19] if len(timestamp) > 19 else timestamp}")
            
            with col_delete:
                if st.button("🗑️", key=f"delete_{idx}"):
                    if sheets_available:
                        if delete_annotation_from_sheet(ann['village_name'], ann['ward_name']):
                            st.session_state.annotations = load_annotations_from_sheet()
                            st.rerun()
        
        st.write("---")
        
        # Export buttons
        col1, col2 = st.columns(2)
        with col1:
            df = pd.DataFrame(st.session_state.annotations)
            csv = df.to_csv(index=False)
            st.download_button(
                label="📊 Export Backup CSV",
                data=csv,
                file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        with col2:
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


# # Create and display map (THIS IS OUTSIDE THE FUNCTION)
# st.subheader("Click on the relevant ward to create village areas")

# # Layout: map and info panel
# col1, col2 = st.columns([4, 1])
# with col1:
#     m = create_map()  # Call the function here
#     map_data = st_folium(
#         m, 
#         width=900,  # Increased from 900
#         height=900,  # Increased from 600 for better visibility
#         returned_objects=["all_drawings", "last_active_drawing"],
#         key=f"map_{selected_ward}_{len(st.session_state.annotations)}"
#     )


# with col2:
#     st.subheader("Current Context")
    
#     # Show current ward if selected
#     if ward_gdf is not None and selected_ward not in ['All Treatment Wards']:  # CHANGED: updated condition
#         st.write(f"**Focus:** {selected_ward}")
#         ward_info = ward_gdf[ward_gdf['ward_name'] == selected_ward]
#         if not ward_info.empty:
#             ward_row = ward_info.iloc[0]
#             st.write(f"**District:** {ward_row['dist_name']}")
#             st.write(f"**Region:** {ward_row['reg_name']}")
            
#             if ward_row['is_treatment']:
#                 st.success("Treatment Ward")
                
#     if village_name:
#         st.write(f"**Mapping:** {village_name}")
#         st.write(f"**Type:** {village_type}")
#     else:
#         st.write("**Select a ward and village to start mapping**")
    


# # Handle map clicks
# # Capture drawn polygons
# if map_data and map_data.get('last_active_drawing') and village_name:
#     drawing = map_data['last_active_drawing']
    
#     # Store the pending annotation in session state (don't save yet)
#     st.session_state['pending_annotation'] = {
#         'village_name': village_name,
#         'village_type': village_type,
#         'is_treatment': is_treatment,
#         'ward_name': selected_ward,
#         'geometry': drawing['geometry'],
#         'timestamp': datetime.now().isoformat(),
#     }
    
#     st.info(f"✏️ Polygon drawn for **{village_name}** - Click 'Save to Database' below to confirm")

# # Show save button if there's a pending annotation
# if 'pending_annotation' in st.session_state and st.session_state['pending_annotation']:
#     st.markdown("---")
#     st.subheader("💾 Pending Annotation")
    
#     col_preview, col_actions = st.columns([2, 1])
    
#     with col_preview:
#         pending = st.session_state['pending_annotation']
#         st.write(f"**Village:** {pending['village_name']}")
#         st.write(f"**Ward:** {pending['ward_name']}")
#         st.write(f"**Type:** {pending['village_type']}")
    
#     with col_actions:
#         # Check if already mapped (only when user tries to save)
#         already_mapped = False
#         if sheets_available:
#             # Check in current session state first (no API call)
#             already_mapped = any(
#                 ann.get('village_name') == pending['village_name'] and 
#                 ann.get('ward_name') == pending['ward_name'] 
#                 for ann in st.session_state.annotations
#             )
        
#         if already_mapped:
#             st.warning("⚠️ Already mapped!")
#             if st.button("🗑️ Clear Pending", type="secondary", use_container_width=True):
#                 del st.session_state['pending_annotation']
#                 st.rerun()
#         else:
#             if st.button("💾 Save to Database", type="primary", use_container_width=True):
#                 if sheets_available:
#                     success, message = save_annotation_to_sheet(pending)
#                     if success:
#                         # Reload from sheet to ensure sync
#                         st.session_state.annotations = load_annotations_from_sheet()
#                         st.success(f"✅ {pending['village_name']} saved successfully!")
#                         del st.session_state['pending_annotation']
#                         st.rerun()
#                     else:
#                         st.error(f"❌ Save failed: {message}")
#                 else:
#                     st.session_state.annotations.append(pending)
#                     st.success("✅ Saved locally (offline mode)")
#                     del st.session_state['pending_annotation']
#                     st.rerun()
            
#             if st.button("🗑️ Discard", type="secondary", use_container_width=True):
#                 del st.session_state['pending_annotation']
#                 st.rerun()
    
#     st.markdown("---")

# # Manual refresh option
# col_refresh, col_spacer = st.columns([1, 3])
# with col_refresh:
#     if st.button("🔄 Refresh from Database", help="Reload annotations from Google Sheets"):
#         if sheets_available:
#             st.session_state.annotations = load_annotations_from_sheet()
#             st.success("✅ Refreshed from database")
#             st.rerun()
#         else:
#             st.warning("⚠️ Offline mode - no database to refresh from")

# st.markdown("---")


# # Display current annotations
# st.subheader(f"Current Annotations ({len(st.session_state.annotations)})")

# if st.session_state.annotations:
#     # Display mapped villages with delete buttons
#     st.write("### Mapped Villages")
#     for idx, ann in enumerate(st.session_state.annotations):
#         col_info, col_delete = st.columns([4, 1])
        
#         with col_info:
#             village_name = ann.get('village_name', 'Unknown')
#             village_type = ann.get('village_type', 'Unknown')
#             ward_name = ann.get('ward_name', 'Unknown')
#             timestamp = ann.get('timestamp', 'Unknown')
            
#             # Color code based on type
#             if village_type == 'Treatment':
#                 st.markdown(f"🔴 **{village_name}** ({village_type}) in {ward_name}")
#             else:
#                 st.markdown(f"🔵 **{village_name}** ({village_type}) in {ward_name}")
#             st.caption(f"Mapped at: {timestamp[:19] if len(timestamp) > 19 else timestamp}")
        
#         with col_delete:
#             if st.button("🗑️", key=f"delete_{idx}", help="Delete this annotation"):
#                 ann = st.session_state.annotations[idx]
#                 if sheets_available:
#                     if delete_annotation_from_sheet(ann['village_name'], ann['ward_name']):
#                         # Reload from sheet to ensure sync
#                         st.session_state.annotations = load_annotations_from_sheet()
#                         st.rerun()
#     st.write("---")
    
#     # Export buttons
#     col1, col2 = st.columns(2)
    
#     with col1:
#         # CSV download
#         df = pd.DataFrame(st.session_state.annotations)
#         csv = df.to_csv(index=False)
#         st.download_button(
#             label="📊 Export Backup CSV",
#             data=csv,
#             file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
#             mime="text/csv",
#             help="Backup only - auto-saved to Google Sheets"
#         )

#     with col2:
#         # Map download
#         map_html = m._repr_html_()
#         st.download_button(
#             label="🗺️ Download Map",
#             data=map_html,
#             file_name=f"village_map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
#             mime="text/html"
#         )

# else:
#     st.info("No villages mapped yet. Select a ward and village, then draw a polygon around the settlement!")
# # Instructions
# with st.expander("📋 Instructions", expanded=False):
#     st.markdown("""
#     ### Workflow:
    
    
#     1. **Navigate to specific wards** using the dropdown menu on the left to focus on relevant wards  
#     2. **Select a village to map** in the dropdown in the sidebar to know which settlements/village to locate
#     3. **Locate the village** On the map on the right-hand side select the basemap. 
#         Start with openstreetmap to see if the village is available and to get more context of the location.
#         Then select  either ESRI or google maps to see the imagery in which you can see the settlements/villages. 
#     4. **Click on draw a polygon** on left hand side of the map.
#     5. **Draw lines around the outline of the village/settlement.***
#         - Once done, click the first point. 
#     6. **If a village outline is mapped**, this will show-up as 'pending'. 
#                 Check if you have highlighted the outline correcctly. 
#     7.  IF the outline is annotated correctly **click save to the database**
     
#     """)