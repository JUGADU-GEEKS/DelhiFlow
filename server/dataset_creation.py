# main.py
"""
Final pipeline for preparing flood dataset grids with robust DEM handling.

Behavior:
 - If --dem is provided (or DEM_PATH env var), uses that GeoTIFF via rasterio.
 - Else, if --opentopo-key is provided (or OPENTOPO_API_KEY env var), attempts to
   download a GeoTIFF for Delhi from OpenTopography and use it.
 - Else tries OpenTopoData (public) to fetch centroid elevations for each grid.
 - Else falls back to simulated elevations.

Notes:
 - This script defaults to demo_mode (one week) to avoid huge memory usage.
 - To run full 5-year dataset you must set demo_mode=False and ensure you have
   enough disk/memory and preferably use Dask or chunked writes.
"""
import os
import sys
import time
import argparse
import datetime
import math
from shapely.geometry import box
import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
from rasterio.mask import mask
import osmnx as ox
import requests

# -------------------------
# Utilities
# -------------------------
from dotenv import load_dotenv
load_dotenv()

def create_grid(boundary_gdf, grid_size_deg=0.005):
    minx, miny, maxx, maxy = boundary_gdf.total_bounds
    x_coords = np.arange(minx, maxx, grid_size_deg)
    y_coords = np.arange(miny, maxy, grid_size_deg)
    polygons = []
    for x in x_coords:
        for y in y_coords:
            polygons.append(box(x, y, x+grid_size_deg, y+grid_size_deg))
    grid = gpd.GeoDataFrame({'geometry': polygons}, crs=boundary_gdf.crs)
    grid = gpd.overlay(grid, boundary_gdf, how='intersection')
    grid['Grid_ID'] = range(len(grid))
    return grid

def open_dem(dem_path):
    if not os.path.isfile(dem_path):
        return None
    try:
        ds = rasterio.open(dem_path)
        return ds
    except Exception as e:
        print(f"[DEM] Failed to open '{dem_path}': {e}", file=sys.stderr)
        return None

def sample_dem_average(dem_ds, geom):
    try:
        out_image, out_transform = mask(dem_ds, [geom], crop=True)
        band = out_image[0]
        nodata = dem_ds.nodata
        if nodata is None:
            data = band[~np.isnan(band)]
        else:
            data = band[band != nodata]
        if data.size == 0:
            return np.nan
        return float(np.mean(data))
    except Exception:
        return np.nan

def download_opentopo_dem(bbox, out_path="opentopo_delhi_dem.tif", demtype="SRTMGL1", api_key=None, timeout=180):
    """
    Download a GeoTIFF DEM from OpenTopography globalDEM endpoint (requires an API key).
    bbox: (west, south, east, north)
    demtype examples: 'SRTMGL1' (1 arc-second / ~30m), or 'SRTMGL3' (~90m)
    Returns rasterio dataset or None on failure.
    """
    if api_key is None:
        print("[OpenTopography] No API key provided.")
        return None

    base = "https://portal.opentopography.org/API/globaldem"
    params = {
        "demtype": demtype,
        "west": float(bbox[0]),
        "east": float(bbox[2]),
        "south": float(bbox[1]),
        "north": float(bbox[3]),
        "outputFormat": "GTiff",
        "API_Key": api_key
    }
    try:
        print("[OpenTopography] Requesting DEM (this can take some time)...")
        r = requests.get(base, params=params, stream=True, timeout=timeout)
        if r.status_code == 200:
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"[OpenTopography] DEM saved to {out_path}")
            ds = rasterio.open(out_path)
            return ds
        else:
            print(f"[OpenTopography] HTTP {r.status_code} - {r.text[:200]}")
            return None
    except Exception as e:
        print(f"[OpenTopography] Request failed: {e}")
        return None

def fetch_elevations_opentopodata(points, batch_size=200, delay_s=0.5, provider='srtm90m'):
    """
    points: list of (lat, lon) tuples
    Uses OpenTopoData public API (no key) to fetch elevations in batches.
    Returns list of elevations or None on failure.
    """
    base = f"https://api.opentopodata.org/v1/{provider}"
    elevations = []
    try:
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            locs = "|".join(f"{lat},{lon}" for lat,lon in batch)
            resp = requests.get(base, params={'locations': locs}, timeout=60)
            if resp.status_code != 200:
                print(f"[OpenTopoData] HTTP {resp.status_code}: {resp.text[:200]}")
                return None
            data = resp.json()
            results = data.get('results', [])
            for r in results:
                elevations.append(r.get('elevation', None))
            time.sleep(delay_s)
        if len(elevations) != len(points):
            print("[OpenTopoData] returned different number of elevations than requested.")
            return None
        return elevations
    except Exception as e:
        print(f"[OpenTopoData] Fetch error: {e}")
        return None

# -------------------------
# Main
# -------------------------
def main():
    parser = argparse.ArgumentParser(description="Prepare Delhi flood dataset (grids + features).")
    parser.add_argument('--dem', help='Path to DEM GeoTIFF (optional)')
    parser.add_argument('--opentopo-key', help='OpenTopography API key (optional)')
    parser.add_argument('--grid-size-m', type=int, default=500, help='Grid size in meters (default 500)')
    parser.add_argument('--use-api', action='store_true', help='Allow using OpenTopoData for centroid elevations if DEM missing')
    parser.add_argument('--preview-only', action='store_true', help='Create grids & static features only (quicker)')
    args = parser.parse_args()

    # Step 1: Delhi boundary via OSM
    print("[Step] Downloading Delhi boundary (OSM)...")
    delhi_boundary = ox.geocode_to_gdf("Delhi, India")
    delhi_boundary = delhi_boundary.to_crs(epsg=4326)  # ensure lon/lat
    grid_size_deg = args.grid_size_m / 111000.0  # approx conversion meters -> degrees
    print(f"[Step] Creating grids of ~{args.grid_size_m} m ({grid_size_deg:.6f} deg) ...")
    grids = create_grid(delhi_boundary, grid_size_deg)
    print(f"[Step] Number of grids: {len(grids)}")

    # Step 2: DEM handling
    dem_path = args.dem or os.environ.get('DEM_PATH', None)
    dem_ds = open_dem(dem_path) if dem_path else None

    if dem_ds is not None:
        print(f"[DEM] Using provided DEM file: {dem_path}")
        grids['Elevation'] = grids['geometry'].apply(lambda g: sample_dem_average(dem_ds, g))
        grids['Elevation'].fillna(grids['Elevation'].mean(), inplace=True)
    else:
        print("[DEM] No local DEM file found.")
        # Try OpenTopography GeoTIFF download if user provided key
        opentopo_key = args.opentopo_key or os.environ.get('OPENTOPO_API_KEY')
        if opentopo_key:
            minx, miny, maxx, maxy = delhi_boundary.total_bounds
            bbox = (minx, miny, maxx, maxy)
            dem_ds = download_opentopo_dem(bbox, out_path="delhi_opentopo_dem.tif", demtype="SRTMGL1", api_key=opentopo_key)
            if dem_ds is not None:
                print("[DEM] OpenTopography DEM downloaded and opened.")
                grids['Elevation'] = grids['geometry'].apply(lambda g: sample_dem_average(dem_ds, g))
                grids['Elevation'].fillna(grids['Elevation'].mean(), inplace=True)
            else:
                print("[DEM] OpenTopography DEM download failed or returned no data.")
                dem_ds = None

        if dem_ds is None:
            # Try OpenTopoData centroid approach if allowed
            if args.use_api:
                print("[DEM] Attempting centroid elevation fetch via OpenTopoData (public API)...")
                centroids = grids['geometry'].centroid
                points = [(pt.y, pt.x) for pt in centroids]  # (lat, lon)
                elevations = fetch_elevations_opentopodata(points, batch_size=200, delay_s=0.5, provider='srtm90m')
                if elevations is not None:
                    print("[DEM] OpenTopoData returned centroid elevations.")
                    grids['Elevation'] = elevations
                    grids['Elevation'].fillna(np.nan, inplace=True)
                    grids['Elevation'].fillna(grids['Elevation'].mean(), inplace=True)
                else:
                    print("[DEM] OpenTopoData failed. Falling back to simulated elevation values.")
                    grids['Elevation'] = np.random.uniform(150, 300, len(grids))
            else:
                print("[DEM] API centroid fetching disabled. Using simulated elevations.")
                grids['Elevation'] = np.random.uniform(150, 300, len(grids))

    # Ensure reasonable values
    grids['Elevation'] = pd.to_numeric(grids['Elevation'], errors='coerce')
    grids['Elevation'].fillna(grids['Elevation'].median(), inplace=True)
    grids.loc[grids['Elevation'] <= 0, 'Elevation'] = grids['Elevation'].median()

    # Step 3: static features (roads)
    print("[Step] Downloading road network from OSM (may take a minute)...")
    G = ox.graph_from_place("Delhi, India", network_type='drive')
    edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
    # spatial join
    roads_with_grid = gpd.sjoin(edges, grids, how='inner', predicate='intersects')
    road_density = roads_with_grid.groupby('Grid_ID')['length'].sum().reset_index().rename(columns={'length':'Road_Density'})
    grids = grids.merge(road_density, on='Grid_ID', how='left')
    grids['Road_Density'] = grids['Road_Density'].fillna(0)

    # placeholders - replace with actual data sources for production
    grids['Drain_Density'] = np.nan
    grids['Pop_Density'] = np.nan
    grids['Historical_Flood_Score'] = np.nan

    print("[Step] Static features ready. Sample:")
    print(grids[['Grid_ID','Elevation','Road_Density']].head())

    if args.preview_only:
        os.makedirs("dataset", exist_ok=True)
        grids.to_parquet("dataset/grids_static_preview.parquet", index=False)
        print("[Saved] grids_static_preview.parquet")
        return

    # Step 4: Build hourly skeleton (demo: 1 week). Full 5-year requires chunking / Dask.
    demo_mode = True  # keep True for safety; set to False to run full 5-year (requires chunking and lots of disk)
    if demo_mode:
        start = datetime.datetime(2025, 7, 1, 0)
        end   = datetime.datetime(2025, 7, 7, 23)
        print("[Mode] DEMO mode: creating 1-week hourly dataset. To build full 5-year set, set demo_mode=False and implement chunked writes.")
    else:
        start = datetime.datetime(2021, 1, 1, 0)
        end   = datetime.datetime(2025, 12, 31, 23)

    timestamps = pd.date_range(start, end, freq='H')
    total_rows = len(grids) * len(timestamps)
    print(f"[Step] Creating grid x hour skeleton: {len(grids)} grids x {len(timestamps)} hours = {total_rows} rows")

    # caution: large memory if full; this demo fits in memory for reasonable grid counts
    grid_hours = pd.MultiIndex.from_product([grids['Grid_ID'], timestamps], names=['Grid_ID','Hour']).to_frame(index=False)
    grid_hours = grid_hours.merge(grids[['Grid_ID','Elevation','Road_Density','Drain_Density','Pop_Density','Historical_Flood_Score']], on='Grid_ID', how='left')

    # Dynamic features (replace with actual datasets for production)
    np.random.seed(42)
    grid_hours['Rain_mm'] = np.random.uniform(0, 50, len(grid_hours))
    grid_hours['Rain_Past3h'] = grid_hours.groupby('Grid_ID')['Rain_mm'].rolling(3, min_periods=1).sum().reset_index(0,drop=True)
    grid_hours['Drain_Water_Level'] = np.random.uniform(0, 2, len(grid_hours))
    grid_hours['Soil_Moisture'] = np.random.uniform(0, 1, len(grid_hours))

    # Flood risk using dynamic percentile thresholds
    print("[Step] Calculating flood risk (dynamic percentile thresholds)...")
    hist_score_series = grid_hours['Historical_Flood_Score'].fillna(0.0)
    safe_elevation = grid_hours['Elevation'].where(grid_hours['Elevation'] > 0, 1.0)
    grid_hours['Score'] = (
        (0.4 * grid_hours['Rain_mm'] / 50.0) +
        (0.2 * grid_hours['Rain_Past3h'] / 150.0) +
        (0.15 * (1.0 / safe_elevation)) +
        (0.15 * (grid_hours['Drain_Water_Level'] / 2.0)) +
        (0.1 * hist_score_series)
    )

    low_th = grid_hours['Score'].quantile(0.33)
    high_th = grid_hours['Score'].quantile(0.66)

    grid_hours['Flood_Risk'] = np.where(
        grid_hours['Score'] > high_th, "High",
        np.where(grid_hours['Score'] > low_th, "Medium", "Low")
    )

    os.makedirs("dataset", exist_ok=True)
    out_path = "dataset/delhi_flood_dataset_demo.parquet"
    grid_hours.to_parquet(out_path, index=False)
    print(f"[Saved] demo dataset: {out_path}")
    print("Finished successfully.")

if __name__ == "__main__":
    main()


#  b48513cebae4065bef5e60c87cde8b48