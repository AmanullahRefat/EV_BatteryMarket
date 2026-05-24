import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pysal.explore as esda
from libpysal.weights import Queen
import requests
import re
import os

st.set_page_config(layout="wide", page_title="EV Battery Spatial Analytics")

st.title("Bangladesh EV Battery Market - Micro-Level Spatial Statistics")
st.write("Data source streaming directly from Google Drive GeoJSON.")

# Target File ID for the 151MB GeoJSON asset
FILE_ID = "1wdjRT8KbQoQ5ut-McL-NLvaOvWZ3KSBl"

@st.cache_data(show_spinner=False)
def load_and_optimize_data(file_id):
    local_geojson = "spatial_data.geojson"
    
    if not os.path.exists(local_geojson):
        with st.spinner("Streaming spatial GeoJSON from Google Drive (this may take a moment)..."):
            session = requests.Session()
            base_url = "https://docs.google.com/uc?export=download"
            
            # Dispatch primary handshake request
            response = session.get(base_url, params={'id': file_id}, stream=True)
            
            token = None
            # Method A: Extract validation key from response cookies
            for key, value in response.cookies.items():
                if key.startswith('download_warning'):
                    token = value
                    break
            
            # Method B: Scrape token from HTML body if intercepted by the warning layout
            if not token and 'text/html' in response.headers.get('Content-Type', ''):
                match = re.search(r'confirm=([0-9a-zA-Z_-]+)', response.text)
                if match:
                    token = match.group(1)
            
            # Execute secondary payload pull if token validation is required
            if token:
                response = session.get(base_url, params={'id': file_id, 'confirm': token}, stream=True)
                
            # Write data stream block to server storage
            with open(local_geojson, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB buffer chunks
                    if chunk:
                        f.write(chunk)
                        
    # Parse compiled binary stream via GeoPandas internal drivers
    try:
        gdf = gpd.read_file(local_geojson)
    except Exception as read_error:
        if os.path.exists(local_geojson) and os.path.getsize(local_geojson) < 150000:
            with open(local_geojson, "r", errors='ignore') as f:
                sample = f.read(1000)
            raise ValueError(f"Download pipeline broken. Google Drive responded with HTML page: {sample}")
        raise read_error
    
    # Prune null topological layers
    gdf = gdf[gdf.geometry.notnull() & ~gdf.geometry.is_empty]
    
    # Cast text metrics into functional floats for matrix calculation
    for col in ['F48V_Marke', 'F60V_Marke']:
        if col in gdf.columns:
            if gdf[col].dtype == 'object':
                gdf[col] = gdf[col].astype(str).str.replace('%', '').astype(float)
                
    # Server-side geometric simplification to protect smartphone browser viewport rendering
    if gdf.crs and gdf.crs.is_geographic:
        gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.0005, preserve_topology=True)
        
    return gdf

# Execute Data Integration Pipeline
try:
    gdf = load_and_optimize_data(FILE_ID)
    st.sidebar.success(f"Successfully vectorized {len(gdf)} records.")
except Exception as e:
    st.error(f"Pipeline error loading data engine: {e}")
    st.stop()

# Dashboard Graphic Layout Columns
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Spatial Econometrics Engine")
    
    metrics = [c for c in ['F48V_Marke', 'F60V_Marke', 'Quantity_E', 'PopDens', 'TOTAL_POP'] if c in gdf.columns]
    target_var = st.selectbox("Select Target Field", metrics if metrics else gdf.columns)
    
    st.markdown("---")
    
    if st.button("Compute Spatial Autocorrelation (Moran's I)"):
        with st.spinner("Constructing Queen Spatial Contiguity Matrix..."):
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
    
    centroid_lat = gdf.geometry.centroid.y.mean()
    centroid_lon = gdf.geometry.centroid.x.mean()
    
    m = folium.Map(location=[centroid_lat, centroid_lon], zoom_start=7, tiles="cartodbpositron")
    
    folium.Choropleth(
        geo_data=gdf.__geo_interface__,
        data=gdf,
        columns=[gdf.index.name or 'fid' if gdf.index.name else gdf.columns[0], target_var],
        key_on="feature.id",
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name=f"{target_var} Distribution Matrix"
    ).add_to(m)
    
    st_folium(m, width="100%", height=550, returned_objects=[])
