import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pysal.explore as esda
from libpysal.weights import Queen
import gdown
import os

st.set_page_config(layout="wide", page_title="EV Battery Spatial Analytics")

st.title("Bangladesh EV Battery Market - Micro-Level Spatial Statistics")
st.write("Data source streaming directly from Google Drive GeoJSON via gdown engine.")

# Target Google Drive File ID
FILE_ID = "1wdjRT8KbQoQ5ut-McL-NLvaOvWZ3KSBl"

@st.cache_data(show_spinner=False)
def load_and_optimize_data(file_id):
    local_geojson = "spatial_data.geojson"
    
    # Securely acquire the 151MB file using the gdown automated wrapper
    if not os.path.exists(local_geojson):
        with st.spinner("Downloading high-resolution spatial GeoJSON from Google Drive..."):
            url = f"https://drive.google.com/uc?id={file_id}"
            gdown.download(url, local_geojson, quiet=True)
                        
    # Load and clean the spatial data layers
    try:
        gdf = gpd.read_file(local_geojson)
    except Exception as read_error:
        if os.path.exists(local_geojson):
            size = os.path.getsize(local_geojson)
            if size < 150000:
                with open(local_geojson, "r", errors='ignore') as f:
                    sample = f.read(500)
                raise ValueError(f"Download payload corrupted or restricted. File content: {sample}")
        raise read_error
    
    # Ensure spatial coordinate reference consistency
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    elif gdf.crs.to_string() != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
        
    # Prune null topological records
    gdf = gdf[gdf.geometry.notnull() & ~gdf.geometry.is_empty]
    
    # Reset indices to produce clean, sequential string match points for folium choropleth
    gdf = gdf.reset_index(drop=True)
    gdf['geojson_id'] = gdf.index.astype(str)
    
    # Standardize textual percentage fields into floats for pySAL computation
    for col in ['F48V_Marke', 'F60V_Marke']:
        if col in gdf.columns:
            if gdf[col].dtype == 'object':
                gdf[col] = gdf[col].astype(str).str.replace('%', '').astype(float)
                
    # Server-side spatial optimization to avoid overloading smartphone viewports
    gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.0005, preserve_topology=True)
        
    return gdf

# Execute Data Integration Pipeline
try:
    gdf = load_and_optimize_data(FILE_ID)
    st.sidebar.success(f"Successfully vectorized {len(gdf)} administrative polygons.")
except Exception as e:
    st.error(f"Pipeline error loading data engine: {e}")
    st.stop()

# Layout Design
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Spatial Econometrics Engine")
    
    # Filter for explicit target metrics matching the analytical schema
    metrics = [c for c in ['F48V_Marke', 'F60V_Marke', 'Quantity_E', 'PopDens', 'TOTAL_POP'] if c in gdf.columns]
    target_var = st.selectbox("Select Target Field", metrics if metrics else gdf.columns)
    
    st.markdown("---")
    
    if st.button("Compute Spatial Autocorrelation (Moran's I)"):
        with st.spinner("Constructing Queen Contiguity Weights..."):
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
        columns=['geojson_id', target_var],
        key_on="feature.id",  # Map row alignment keys directly against sequential dataframe tracking indices
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name=f"{target_var} Distribution Metric"
    ).add_to(m)
    
    st_folium(m, width="100%", height=550, returned_objects=[])
