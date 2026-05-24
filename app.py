import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pysal.explore as esda
from libpysal.weights import Queen
import requests
import os

st.set_page_config(layout="wide", page_title="EV Battery Spatial Analytics")

st.title("Bangladesh EV Battery Market - Micro-Level Spatial Statistics")
st.write("Data source streaming directly from Google Drive Feature Class export.")

# Extracted File ID from your shared Google Drive link
FILE_ID = "1wdjRT8KbQoQ5ut-McL-NLvaOvWZ3KSBl"

@st.cache_data(show_spinner=False)
def load_and_optimize_data(file_id):
    # Google Drive direct download URL stream
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    local_zip = "spatial_data.zip"
    
    # Download the archive to the cloud server memory if not present
    if not os.path.exists(local_zip):
        with st.spinner("Streaming spatial dataset from Google Drive (this may take a moment)..."):
            response = requests.get(url, stream=True)
            with open(local_zip, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
    # Read zipped shapefile directly via GeoPandas/Fiona engine
    gdf = gpd.read_file(local_zip)
    
    # Standardize and drop empty geometries
    gdf = gdf[gdf.geometry.notnull() & ~gdf.geometry.is_empty]
    
    # Clean text-based percentage attributes into numeric floats for PySAL computation
    for col in ['F48V_Marke', 'F60V_Marke']:
        if col in gdf.columns:
            if gdf[col].dtype == 'object':
                gdf[col] = gdf[col].astype(str).str.replace('%', '').astype(float)
                
    # Server-side geometry simplification to optimize mobile visualization rendering
    if gdf.crs and gdf.crs.is_geographic:
        # 0.0005 tolerance works optimally for WGS84 coordinates at Union level
        gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.0005, preserve_topology=True)
        
    return gdf

# Execute Data Pipeline
try:
    gdf = load_and_optimize_data(FILE_ID)
    st.sidebar.success(f"Loaded {len(gdf)} Administrative Polygons.")
except Exception as e:
    st.error(f"Pipeline error loading data engine: {e}")
    st.info("Ensure the Google Drive link permission remains set to 'Anyone with the link'.")
    st.stop()

# Layout Columns
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Spatial Econometrics Engine")
    
    # Expose valid analytical metrics dynamically
    metrics = [c for c in ['F48V_Marke', 'F60V_Marke', 'Quantity_E', 'PopDens', 'TOTAL_POP'] if c in gdf.columns]
    target_var = st.selectbox("Select Target Field", metrics if metrics else gdf.columns)
    
    st.markdown("---")
    
    # Run PySAL Spatial Autocorrelation Engine
    if st.button("Compute Spatial Autocorrelation (Moran's I)"):
        with st.spinner("Constructing Queen Contiguity Weights Matrix..."):
            # allow_islands=True handles any disjoint coastal/offshore polygons seamlessly
            w = Queen.from_dataframe(gdf, allow_islands=True)
            w.transform = 'r'
            
            # Isolate values and mask potential NaN coordinates
            valid_idx = gdf[target_var].notnull()
            y = gdf.loc[valid_idx, target_var].values
            
            # Reconstruct weights for matching valid records if gaps exist
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
    
    # Calculate a stable dynamic bounding spatial centroid
    centroid_lat = gdf.geometry.centroid.y.mean()
    centroid_lon = gdf.geometry.centroid.x.mean()
    
    # Render map
    m = folium.Map(location=[centroid_lat, centroid_lon], zoom_start=7, tiles="cartodbpositron")
    
    folium.Choropleth(
        geo_data=gdf.__geo_interface__,
        data=gdf,
        columns=[gdf.index.name or 'fid' if gdf.index.name else gdf.columns[0], target_var],
        key_on="feature.id",
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name=f"{target_var} Metric Density Map"
    ).add_to(m)
    
    st_folium(m, width="100%", height=550, returned_objects=[])
