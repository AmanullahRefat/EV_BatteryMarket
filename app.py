import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pysal.explore as esda
from libpysal.weights import Queen
import requests
import io
import os

st.set_page_config(layout="wide", page_title="EV Battery Spatial Analytics")

st.title("Bangladesh EV Battery Market - Micro-Level Spatial Statistics")
st.write("Data source streaming directly from Google Drive GeoJSON.")

# Extracted File ID from your shared Google Drive link
FILE_ID = "1wdjRT8KbQoQ5ut-McL-NLvaOvWZ3KSBl"

@st.cache_data(show_spinner=False)
def load_and_optimize_data(file_id):
    local_geojson = "spatial_data.geojson"
    
    # Download the geojson file from Google Drive if not locally cached on the server
    if not os.path.exists(local_geojson):
        with st.spinner("Streaming spatial GeoJSON from Google Drive (this may take a moment)..."):
            session = requests.Session()
            base_url = "https://docs.google.com/uc?export=download"
            
            response = session.get(base_url, params={'id': file_id}, stream=True)
            token = None
            
            # Extract confirmation token if Google Drive prompts a large-file warning screen
            for key, value in response.cookies.items():
                if key.startswith('download_warning'):
                    token = value
                    break
                    
            if token:
                response = session.get(base_url, params={'id': file_id, 'confirm': token}, stream=True)
                
            with open(local_geojson, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                    if chunk:
                        f.write(chunk)
                        
    # Read the downloaded local GeoJSON via GeoPandas
    try:
        gdf = gpd.read_file(local_geojson)
    except Exception as read_error:
        # Check if Google Drive sent an HTML error page instead of raw data
        if os.path.exists(local_geojson) and os.path.getsize(local_geojson) < 50000:
            with open(local_geojson, "r", errors='ignore') as f:
                sample = f.read(500)
            raise ValueError(f"Download failed or incomplete. Google Drive returned: {sample}")
        raise read_error
    
    # Clean up empty or corrupted topologies
    gdf = gdf[gdf.geometry.notnull() & ~gdf.geometry.is_empty]
    
    # Standardize string market share values (e.g., '60%') into numbers if necessary
    for col in ['F48V_Marke', 'F60V_Marke']:
        if col in gdf.columns:
            if gdf[col].dtype == 'object':
                gdf[col] = gdf[col].astype(str).str.replace('%', '').astype(float)
                
    # Server-side geometry simplification to optimize rendering performance
    if gdf.crs and gdf.crs.is_geographic:
        gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.0005, preserve_topology=True)
        
    return gdf

# Execute Data Pipeline
try:
    gdf = load_and_optimize_data(FILE_ID)
    st.sidebar.success(f"Loaded {len(gdf)} Administrative Polygons.")
except Exception as e:
    st.error(f"Pipeline error loading data engine: {e}")
    st.info("Double check that the Google Drive link permission remains set to 'Anyone with the link'.")
    st.stop()

# Layout Columns
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Spatial Econometrics Engine")
    
    # Isolate numeric fields suitable for spatial weights calculation
    metrics = [c for c in ['F48V_Marke', 'F60V_Marke', 'Quantity_E', 'PopDens', 'TOTAL_POP'] if c in gdf.columns]
    target_var = st.selectbox("Select Target Field", metrics if metrics else gdf.columns)
    
    st.markdown("---")
    
    # Run PySAL Spatial Autocorrelation Engine
    if st.button("Compute Spatial Autocorrelation (Moran's I)"):
        with st.spinner("Constructing Spatial Weights Matrix..."):
            # allow_islands=True handles any discontinuous island/coastal polygons cleanly
            w = Queen.from_dataframe(gdf, allow_islands=True)
            w.transform = 'r'
            
            valid_idx = gdf[target_var].notnull()
            y = gdf.loc[valid_idx, target_var].values
            
            if not valid_idx.all():
                w = Queen.from_dataframe(gdf[valid_idx], allow_islands=True)
                w.transform = 'r'
            
            moran = esda.moran.Moran(y, w)
            
            st.metric(label="Global Moran's I Index", value=f"{moran.I:.4f}")
            st.metric(label="Analytical p-value", value=f"{moran.p_sim:.4f}")
            
            if moran.p_sim < 0.05:
                st.success("Result: Statistically Significant Spatial Clustering Detected")
            else:
                st.warning("Result: Random Spatial Distribution (No Significant Clustering)")

with col2:
    st.subheader("Interactive Demarcation Map")
    
    # Calculate a stable spatial center point for rendering
    centroid_lat = gdf.geometry.centroid.y.mean()
    centroid_lon = gdf.geometry.centroid.x.mean()
    
    # Initialize Leaflet Map map canvas
    m = folium.Map(location=[centroid_lat, centroid_lon], zoom_start=7, tiles="cartodbpositron")
    
    # Create Choropleth thematic map overlay
    folium.Choropleth(
        geo_data=gdf.__geo_interface__,
        data=gdf,
        columns=[gdf.index.name or 'fid' if gdf.index.name else gdf.columns[0], target_var],
        key_on="feature.id",
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name=f"{target_var} Metric Distribution Map"
    ).add_to(m)
    
    st_folium(m, width="100%", height=550, returned_objects=[])
