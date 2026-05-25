import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import gdown
import os

# 1. Page Configuration
st.set_page_config(layout="wide", page_title="EV Market Spatial Analytics Dashboard")

st.title("Bangladesh EV Battery Market - Micro-Level Spatial Statistics")
st.write("Analyzing Market Shares with High-Performance Performance Caching and Infographics.")

FILE_ID = "1wdjRT8KbQoQ5ut-McL-NLvaOvWZ3KSBl"

# 2. Optimized Spatial Data Loader (Cached)
@st.cache_data(show_spinner=False)
def load_and_simplify_spatial(file_id):
    local_geojson = "spatial_data.geojson"
    if not os.path.exists(local_geojson):
        with st.spinner("Downloading high-resolution spatial layer..."):
            url = f"https://drive.google.com/uc?id={file_id}"
            gdown.download(url, local_geojson, quiet=True)
                        
    gdf = gpd.read_file(local_geojson)
    gdf = gdf[gdf.geometry.notnull() & ~gdf.geometry.is_empty]
    
    # Process string metrics to clean numeric data types
    for col in ['F48V_Marke', 'F60V_Marke']:
        if col in gdf.columns and gdf[col].dtype == 'object':
            gdf[col] = gdf[col].astype(str).str.replace('%', '', regex=False).str.strip().astype(float)
    
    for numeric_col in ['Quantity_E', 'TOTAL_POP', 'Quantity_48V', 'Quantity_60V']:
        if numeric_col in gdf.columns:
            gdf[numeric_col] = pd.to_numeric(gdf[numeric_col], errors='coerce').fillna(0)
            
    # Bivariate cuts
    for col, target in [('F48V_Marke', 'bin_48v'), ('F60V_Marke', 'bin_60v')]:
        try:
            gdf[target] = pd.qcut(gdf[col], 3, labels=[1, 2, 3], duplicates='drop').astype(int)
        except Exception:
            gdf[target] = pd.cut(gdf[col], bins=[-1, 33, 66, 101], labels=[1, 2, 3]).astype(int)
            
    gdf['bivariate_class'] = gdf['bin_48v'].astype(str) + "-" + gdf['bin_60v'].astype(str)
    
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    elif gdf.crs.to_string() != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
        
    gdf = gdf.reset_index(drop=True)
    # Simplify geometry constraints significantly to minimize JSON footprint & optimize browser runtime
    gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.001, preserve_topology=True)
    return gdf

# 3. Fast Tabular and KPI Analytics Aggregator (Cached separately to avoid blocking layout loads)
@st.cache_data
def calculate_market_analytics(gdf_dataframe):
    # Strip spatial metadata completely for instantaneous attribute framework sorting
    flat_df = pd.DataFrame(gdf_dataframe.drop(columns=['geometry', 'bin_48v', 'bin_60v', 'bivariate_class'], errors='ignore'))
    
    summary_metrics = {
        "total_ev": int(flat_df['Quantity_E'].sum()),
        "total_pop": int(flat_df['TOTAL_POP'].sum()),
        "total_48v": int(flat_df['Quantity_48V'].sum()) if 'Quantity_48V' in flat_df.columns else int((flat_df['Quantity_E'] * (flat_df['F48V_Marke'] / 100)).sum()),
        "total_60v": int(flat_df['Quantity_60V'].sum()) if 'Quantity_60V' in flat_df.columns else int((flat_df['Quantity_E'] * (flat_df['F60V_Marke'] / 100)).sum())
    }
    
    core_order = ['DIVISION_N', 'DISTRICT_N', 'UPAZILA_NA', 'UNION_NAME', 'TOTAL_POP', 'Quantity_E', 'F48V_Marke', 'F60V_Marke']
    existing_core = [c for c in core_order if c in flat_df.columns]
    remaining_cols = [c for c in flat_df.columns if c not in existing_core]
    
    return flat_df[existing_core + remaining_cols], summary_metrics

try:
    gdf = load_and_simplify_spatial(FILE_ID)
    table_df, metrics = calculate_market_analytics(gdf)
except Exception as e:
    st.error(f"Initialization or file load breakdown occurred: {e}")
    st.stop()


# ==========================================
# INFOGRAPHIC INFRASTRUCTURE: KEY METRICS 
# ==========================================
st.markdown("### 📊 Executive Market Summary Infographics")
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.metric(label="Total Projected EV Volume", value=f"{metrics['total_ev']:,}")
with kpi2:
    st.metric(label="Total Population Catchment", value=f"{metrics['total_pop']:,}")
with kpi3:
    st.metric(label="Calculated 48V Fleet Units", value=f"{metrics['total_48v']:,}")
with kpi4:
    st.metric(label="Calculated 60V Fleet Units", value=f"{metrics['total_60v']:,}")

st.markdown("---")


# ==========================================
# GRAPHIC INFOGRAPHIC DESIGN: CHARTS & MAPS
# ==========================================
col1, col2 = st.columns([2, 3])

with col1:
    st.subheader("Fleet Distribution Profile")
    # Quick, fast distribution chart component serving as a dynamic dashboard infographic
    chart_data = table_df[['UPAZILA_NA', 'Quantity_E']].groupby('UPAZILA_NA').sum().sort_values(by='Quantity_E', ascending=False).head(15)
    st.bar_chart(chart_data, y="Quantity_E", use_container_width=True)
    st.caption("Top 15 Upazilas sorted by Total Volume distributions.")

with col2:
    st.subheader("Spatial Bivariate Grid Distribution")
    centroid_lat = gdf.geometry.centroid.y.mean()
    centroid_lon = gdf.geometry.centroid.x.mean()
    
    m = folium.Map(location=[centroid_lat, centroid_lon], zoom_start=7, tiles="cartodbpositron")
    bivariate_colors = {
        "1-1": "#e8e8e8", "1-2": "#b0d5df", "1-3": "#64acbe", 
        "2-1": "#e4acac", "2-2": "#ad9ea5", "2-3": "#627f8c", 
        "3-1": "#c85a5a", "3-2": "#985356", "3-3": "#574249"  
    }
    color_lookup = gdf['bivariate_class'].map(bivariate_colors).to_dict()
    
    def style_function(feature):
        return {
            'fillColor': color_lookup.get(str(feature.get('id')), "#ffffff"),
            'color': '#555555', 'weight': 0.3, 'fillOpacity': 0.7
        }
        
    folium.GeoJson(
        gdf.__geo_interface__,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=['UNION_NAME', 'F48V_Marke', 'F60V_Marke', 'Quantity_E'],
            aliases=['Union:', '48V Share:', '60V Share:', 'EV Volume:'],
            localize=True
        )
    ).add_to(m)
    
    st_folium(m, width="100%", height=400, returned_objects=[])

st.markdown("---")


# ==========================================
# INTERACTIVE FRAMEWORK: SORTABLE TABLE
# ==========================================
st.markdown("### 📋 Spatial Administrative Attribute Table")
st.write("Click any column header cell below to change sort direction dynamically across all records.")

# Native interactive DataFrame allows immediate spreadsheet interaction/sorting
st.dataframe(
    table_df,
    use_container_width=True,
    height=380
    )
