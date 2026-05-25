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
st.write("Analyzing Market Shares with High-Performance Caching and Infographics.")

FILE_ID = "1wdjRT8KbQoQ5ut-McL-NLvaOvWZ3KSBl"

# 2. Optimized Spatial Data Loader (Cached with Schema Mapping)
@st.cache_data(show_spinner=False)
def load_and_simplify_spatial(file_id):
    local_geojson = "spatial_data.geojson"
    if not os.path.exists(local_geojson):
        with st.spinner("Downloading high-resolution spatial layer..."):
            url = f"https://drive.google.com/uc?id={file_id}"
            gdown.download(url, local_geojson, quiet=True)
                        
    gdf = gpd.read_file(local_geojson)
    gdf = gdf[gdf.geometry.notnull() & ~gdf.geometry.is_empty]
    
    # --- Dynamic Column Mapping Engine ---
    cols = list(gdf.columns)
    def match_column(keywords, fallback):
        for c in cols:
            if all(kw.lower() in c.lower() for kw in keywords):
                return c
        for c in cols:
            if any(kw.lower() in c.lower() for kw in keywords):
                return c
        return fallback

    # Store resolved schema keys inside a session-portable dictionary attributes
    gdf.attrs['col_48v'] = match_column(['48v'], 'F48V_Marke')
    gdf.attrs['col_60v'] = match_column(['60v'], 'F60V_Marke')
    gdf.attrs['col_qty'] = match_column(['quant', 'qty', 'ev'], 'Quantity_E')
    gdf.attrs['col_pop'] = match_column(['pop'], 'TOTAL_POP')
    gdf.attrs['col_union'] = match_column(['union', 'uni'], 'UNION_NAME')
    gdf.attrs['col_upazila'] = match_column(['upazila', 'upz'], 'UPAZILA_NA')
    gdf.attrs['col_district'] = match_column(['dist'], 'DISTRICT_N')
    gdf.attrs['col_division'] = match_column(['div'], 'DIVISION_N')

    c48, c60 = gdf.attrs['col_48v'], gdf.attrs['col_60v']
    c_qty, c_pop = gdf.attrs['col_qty'], gdf.attrs['col_pop']

    # Clean text values (e.g., '60%') into floating points safely
    for col in [c48, c60]:
        if col in gdf.columns and gdf[col].dtype == 'object':
            gdf[col] = gdf[col].astype(str).str.replace('%', '', regex=False).str.strip().astype(float)
    
    # Cast standard fields to numerical elements for math calculations
    for numeric_col in [c_qty, c_pop]:
        if numeric_col in gdf.columns:
            gdf[numeric_col] = pd.to_numeric(gdf[numeric_col], errors='coerce').fillna(0)
            
    # Compute Bivariate Matrix Splits
    try:
        gdf['bin_48v'] = pd.qcut(gdf[c48], 3, labels=[1, 2, 3], duplicates='drop').astype(int)
    except Exception:
        gdf['bin_48v'] = pd.cut(gdf[c48], bins=[-1, 33, 66, 101], labels=[1, 2, 3]).astype(int)
        
    try:
        gdf['bin_60v'] = pd.qcut(gdf[c60], 3, labels=[1, 2, 3], duplicates='drop').astype(int)
    except Exception:
        gdf['bin_60v'] = pd.cut(gdf[c60], bins=[-1, 33, 66, 101], labels=[1, 2, 3]).astype(int)
    
    gdf['bivariate_class'] = gdf['bin_48v'].astype(str) + "-" + gdf['bin_60v'].astype(str)
    
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    elif gdf.crs.to_string() != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
        
    gdf = gdf.reset_index(drop=True)
    gdf.index = gdf.index.astype(str)
    
    # Compress complex geometry bounds down to improve viewport initialization speeds
    gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.001, preserve_topology=True)
    return gdf

# 3. Separate Analytics Caching Aggregator
@st.cache_data
def calculate_market_analytics(gdf_dataframe):
    # Keep metadata constraints local for processing inside calculation loop
    attrs = gdf_dataframe.attrs
    c48, c60, c_qty, c_pop = attrs['col_48v'], attrs['col_60v'], attrs['col_qty'], attrs['col_pop']
    
    flat_df = pd.DataFrame(gdf_dataframe.drop(columns=['geometry', 'bin_48v', 'bin_60v', 'bivariate_class'], errors='ignore'))
    
    summary_metrics = {
        "total_ev": int(flat_df[c_qty].sum()),
        "total_pop": int(flat_df[c_pop].sum()),
        "total_48v": int((flat_df[c_qty] * (flat_df[c48] / 100)).sum()) if flat_df[c48].max() > 1.0 else int((flat_df[c_qty] * flat_df[c48]).sum()),
        "total_60v": int((flat_df[c_qty] * (flat_df[c60] / 100)).sum()) if flat_df[c60].max() > 1.0 else int((flat_df[c_qty] * flat_df[c60]).sum())
    }
    
    core_order = [attrs['col_division'], attrs['col_district'], attrs['col_upazila'], attrs['col_union'], c_pop, c_qty, c48, c60]
    existing_core = [c for c in core_order if c in flat_df.columns]
    remaining_cols = [c for c in flat_df.columns if c not in existing_core]
    
    return flat_df[existing_core + remaining_cols], summary_metrics, attrs

try:
    gdf = load_and_simplify_spatial(FILE_ID)
    table_df, metrics, schema = calculate_market_analytics(gdf)
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
    # Dynamically track column values based on our mapped properties dictionary keys
    chart_data = table_df[[schema['col_upazila'], schema['col_qty']]].groupby(schema['col_upazila']).sum().sort_values(by=schema['col_qty'], ascending=False).head(15)
    st.bar_chart(chart_data, y=schema['col_qty'], use_container_width=True)
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
            fields=[schema['col_union'], schema['col_48v'], schema['col_60v'], schema['col_qty']],
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

st.dataframe(
    table_df,
    use_container_width=True,
    height=380
)
