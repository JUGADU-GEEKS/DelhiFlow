"""
Script to create Delhi ward boundaries (GeoJSON format).
Fetches REAL administrative ward boundaries from OpenStreetMap.
Run this once to generate ward_boundaries.geojson in dataset/ folder.

⚠️  WARNING: This may take 20-45 minutes due to OSM API limitations.
"""

import os
import json
import time
import geopandas as gpd
import osmnx as ox
from shapely.geometry import box, Polygon
import numpy as np


def create_delhi_ward_boundaries():
    """Fetch real Delhi ward boundaries from OpenStreetMap and save as GeoJSON.
    
    This attempts to fetch actual administrative ward boundaries from OSM.
    Expected time: 20-45 minutes (OSM API is slow for large queries).
    
    Fallback: If OSM fails, creates synthetic wards based on grid division.
    """
    
    BASE_DIR = os.path.dirname(__file__)
    DATASET_DIR = os.path.join(BASE_DIR, "dataset")
    os.makedirs(DATASET_DIR, exist_ok=True)
    OUTPUT_PATH = os.path.join(DATASET_DIR, "ward_boundaries.geojson")
    
    print("=" * 70)
    print("FETCHING REAL DELHI WARD BOUNDARIES FROM OPENSTREETMAP")
    print("=" * 70)
    print("⚠️  This may take 20-45 minutes due to OSM API rate limits")
    print("⚠️  Please be patient and do not interrupt the process")
    print("=" * 70)
    print()
    
    start_time = time.time()
    
    try:
        # Step 1: Fetch Delhi boundary
        print("[Step 1/5] Fetching Delhi boundary from OSM...")
        print("   → This usually takes 30-90 seconds...")
        step_start = time.time()
        
        delhi_boundary = ox.geocode_to_gdf("Delhi, India")
        bounds = delhi_boundary.geometry.iloc[0].bounds
        
        elapsed = time.time() - step_start
        print(f"   ✓ Delhi boundary fetched in {elapsed:.1f}s")
        print(f"   → Bounds: {bounds}")
        print()
        
        # Step 2: Try to fetch ward-level boundaries (admin_level=10)
        print("[Step 2/5] Fetching ward boundaries (admin_level=10)...")
        print("   → This is the slowest step, may take 15-30 minutes...")
        print("   → Querying OpenStreetMap Overpass API...")
        step_start = time.time()
        
        try:
            wards_gdf = ox.features_from_bbox(
                north=bounds[3],
                south=bounds[1],
                east=bounds[2],
                west=bounds[0],
                tags={'boundary': 'administrative', 'admin_level': '10'}
            )
            
            elapsed = time.time() - step_start
            print(f"   ✓ OSM query completed in {elapsed:.1f}s")
            print(f"   → Found {len(wards_gdf)} potential ward features")
            print()
            
            # Step 3: Filter and clean ward data
            print("[Step 3/5] Cleaning ward data...")
            
            # Keep only Polygon/MultiPolygon geometries
            wards_gdf = wards_gdf[wards_gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
            print(f"   → {len(wards_gdf)} valid polygon wards")
            
            # Ensure CRS is WGS84
            wards_gdf = wards_gdf.to_crs(epsg=4326)
            
            if len(wards_gdf) == 0:
                print("   ⚠️  No valid wards found, falling back to synthetic wards")
                raise ValueError("No valid wards")
            
            # Add Ward_ID and Ward_Name
            wards_gdf = wards_gdf.reset_index(drop=True)
            wards_gdf['Ward_ID'] = range(1, len(wards_gdf) + 1)
            
            if 'name' in wards_gdf.columns:
                wards_gdf['Ward_Name'] = wards_gdf['name'].fillna('').apply(
                    lambda x: x if x else f"Ward_{wards_gdf[wards_gdf['name']==x].index[0] + 1 if x in wards_gdf['name'].values else 'Unknown'}"
                )
            else:
                wards_gdf['Ward_Name'] = [f"Ward_{i}" for i in range(1, len(wards_gdf) + 1)]
            
            wards_gdf_out = wards_gdf[['Ward_ID', 'Ward_Name', 'geometry']].copy()
            
            print(f"   ✓ {len(wards_gdf_out)} wards ready for export")
            print()
            
        except Exception as e:
            elapsed = time.time() - step_start
            print(f"   ✗ OSM ward fetch failed after {elapsed:.1f}s: {e}")
            print("   → Falling back to synthetic ward creation...")
            print()
            
            print("[Step 3/5] Creating synthetic wards...")
            wards_gdf_out = create_synthetic_wards(delhi_boundary)
        
        # Step 4: Save to GeoJSON
        print(f"[Step 4/5] Saving {len(wards_gdf_out)} wards to GeoJSON...")
        print("   → This may take 5-15 minutes for large ward datasets...")
        step_start = time.time()
        
        wards_gdf_out.to_file(OUTPUT_PATH, driver='GeoJSON')
        
        elapsed = time.time() - step_start
        print(f"   ✓ File saved in {elapsed:.1f}s")
        print()
        
        # Step 5: Summary
        total_time = time.time() - start_time
        print("[Step 5/5] Complete!")
        print("=" * 70)
        print(f"✓ Successfully created {len(wards_gdf_out)} wards")
        print(f"✓ Total time: {total_time/60:.1f} minutes")
        print(f"✓ Saved to: {OUTPUT_PATH}")
        print("=" * 70)
        
        return OUTPUT_PATH
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n✗ Critical error after {elapsed:.1f}s: {e}")
        print("→ Creating synthetic wards as complete fallback...")
        print()
        
        # Complete fallback with hardcoded bounds
        delhi_bounds_polygon = Polygon([
            (76.8, 28.4),
            (77.35, 28.4),
            (77.35, 28.9),
            (76.8, 28.9),
            (76.8, 28.4)
        ])
        
        delhi_boundary = gpd.GeoDataFrame(
            {'geometry': [delhi_bounds_polygon]},
            crs='EPSG:4326'
        )
        
        wards_gdf_out = create_synthetic_wards(delhi_boundary)
        wards_gdf_out.to_file(OUTPUT_PATH, driver='GeoJSON')
        
        total_time = time.time() - start_time
        print(f"✓ Created {len(wards_gdf_out)} synthetic wards in {total_time:.1f}s")
        print(f"✓ Saved to: {OUTPUT_PATH}")
        
        return OUTPUT_PATH


def create_synthetic_wards(delhi_boundary):
    """Create synthetic wards by dividing Delhi into a grid of zones.
    
    This is used as a fallback when OSM data is unavailable.
    Creates approximately 50-60 wards based on spatial grid division.
    """
    
    minx, miny, maxx, maxy = delhi_boundary.total_bounds
    
    # Create synthetic wards with grid division
    WARD_GRID_DIVISIONS = 8  # Creates 8x8 = 64 potential wards
    
    print(f"   → Creating {WARD_GRID_DIVISIONS}x{WARD_GRID_DIVISIONS} grid...")
    
    x_coords = np.linspace(minx, maxx, WARD_GRID_DIVISIONS + 1)
    y_coords = np.linspace(miny, maxy, WARD_GRID_DIVISIONS + 1)
    
    polygons = []
    ward_ids = []
    ward_names = []
    
    ward_id = 1
    
    for i in range(len(x_coords) - 1):
        for j in range(len(y_coords) - 1):
            x1, x2 = x_coords[i], x_coords[i + 1]
            y1, y2 = y_coords[j], y_coords[j + 1]
            
            ward_poly = box(x1, y1, x2, y2)
            
            # Only keep wards that intersect with Delhi boundary
            if ward_poly.intersects(delhi_boundary.geometry.iloc[0]):
                intersected = ward_poly.intersection(delhi_boundary.geometry.iloc[0])
                if intersected.area > 0:
                    polygons.append(intersected)
                    ward_ids.append(ward_id)
                    ward_names.append(f"Ward_{ward_id}")
                    ward_id += 1
    
    print(f"   ✓ Created {len(polygons)} synthetic wards")
    
    wards_gdf = gpd.GeoDataFrame(
        {
            'Ward_ID': ward_ids,
            'Ward_Name': ward_names,
            'geometry': polygons
        },
        crs='EPSG:4326'
    )
    
    return wards_gdf


if __name__ == "__main__":
    create_delhi_ward_boundaries()
