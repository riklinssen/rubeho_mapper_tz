import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime


# Page config
st.set_page_config(page_title="Treatment area  Annotation Tool", layout="wide")
st.title("🌳 Deforestation Annotation Tool")

# Initialize session state for annotations
if 'annotations' not in st.session_state:
    st.session_state.annotations = []

# Sidebar controls
st.sidebar.header("Controls")

# File upload for continuing previous work
uploaded_file = st.sidebar.file_uploader("Upload previous annotations (optional)", type=['csv'])
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.session_state.annotations = df.to_dict('records')
    st.sidebar.success(f"Loaded {len(df)} previous annotations")

# Mode selection
mode = st.sidebar.radio("Annotation Mode:", ["Treatment Area", "Control Area"])
is_treatment = mode == "Treatment Area"

# Create the map
st.subheader("Click on the map to annotate areas")

# Initialize map - you can change these coordinates to your area of interest
m = folium.Map(location=[0, 0], zoom_start=5)

# Add existing annotations to map
for ann in st.session_state.annotations:
    color = 'red' if ann['is_treatment'] else 'blue'
    folium.CircleMarker(
        location=[ann['latitude'], ann['longitude']],
        radius=8,
        popup=f"{'Treatment' if ann['is_treatment'] else 'Control'} Area<br>Lat: {ann['latitude']:.6f}<br>Lng: {ann['longitude']:.6f}",
        color=color,
        fillColor=color,
        fillOpacity=0.7
    ).add_to(m)

# Display map and capture clicks
map_data = st_folium(m, width=700, height=500)

# Handle map clicks
if map_data['last_clicked']:
    lat = map_data['last_clicked']['lat']
    lng = map_data['last_clicked']['lng']
    
    # Add new annotation
    new_annotation = {
        'latitude': lat,
        'longitude': lng,
        'is_treatment': is_treatment,
        'timestamp': datetime.now().isoformat(),
        'type': 'Treatment' if is_treatment else 'Control'
    }
    
    st.session_state.annotations.append(new_annotation)
    st.success(f"Added {mode} at coordinates: {lat:.6f}, {lng:.6f}")
    st.rerun()

# Display current annotations
st.subheader(f"Current Annotations ({len(st.session_state.annotations)})")
if st.session_state.annotations:
    df = pd.DataFrame(st.session_state.annotations)
    st.dataframe(df)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV download
        csv = df.to_csv(index=False)
        st.download_button(
            label="📊 Download Coordinates (CSV)",
            data=csv,
            file_name=f"coordinates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # Map download
        map_html = m._repr_html_()
        st.download_button(
            label="🗺️ Download Map (HTML)",
            data=map_html,
            file_name=f"map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            mime="text/html"
        )
    
    # Clear all button
    if st.button("🗑️ Clear All Annotations"):
        st.session_state.annotations = []
        st.rerun()
else:
    st.info("No annotations yet. Click on the map to start annotating!")

# Instructions
with st.expander("📋 Instructions"):
    st.markdown("""
    1. **Select mode**: Choose between "Treatment Area" or "Control Area" in the sidebar
    2. **Click on map**: Click anywhere on the map to place an annotation
    3. **Download progress**: Use the download buttons to save your work
    4. **Resume work**: Upload your CSV file next time to continue where you left off
    5. **Export**: Download both the coordinates (CSV) and visual map (HTML)
    """)
