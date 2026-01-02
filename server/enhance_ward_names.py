"""
Enhance synthetic ward boundaries with real Delhi area names.
Maps ward centroids to actual Delhi localities/areas.
"""

import json
import geopandas as gpd
from shapely.geometry import Point

# Real Delhi areas mapped to approximate coordinate ranges
DELHI_AREAS = {
    # Central Delhi
    "Connaught Place": {"lat": (28.625, 28.635), "lon": (77.210, 77.225)},
    "Karol Bagh": {"lat": (28.645, 28.660), "lon": (77.185, 77.200)},
    "Paharganj": {"lat": (28.640, 28.650), "lon": (77.205, 77.220)},
    "Chandni Chowk": {"lat": (28.650, 28.665), "lon": (77.225, 77.240)},
    
    # South Delhi
    "Hauz Khas": {"lat": (28.545, 28.560), "lon": (77.190, 77.210)},
    "Saket": {"lat": (28.520, 28.535), "lon": (77.200, 77.220)},
    "Greater Kailash": {"lat": (28.540, 28.555), "lon": (77.235, 77.255)},
    "Nehru Place": {"lat": (28.545, 28.555), "lon": (77.245, 77.260)},
    "Vasant Kunj": {"lat": (28.510, 28.530), "lon": (77.150, 77.170)},
    "Mehrauli": {"lat": (28.510, 28.530), "lon": (77.175, 77.195)},
    "Defence Colony": {"lat": (28.565, 28.575), "lon": (77.230, 77.245)},
    "Lajpat Nagar": {"lat": (28.565, 28.575), "lon": (77.240, 77.255)},
    "Green Park": {"lat": (28.555, 28.565), "lon": (77.200, 77.215)},
    
    # North Delhi
    "Rohini": {"lat": (28.730, 28.760), "lon": (77.065, 77.120)},
    "Pitampura": {"lat": (28.685, 28.710), "lon": (77.120, 77.145)},
    "Model Town": {"lat": (28.700, 28.720), "lon": (77.185, 77.205)},
    "Civil Lines": {"lat": (28.675, 28.690), "lon": (77.215, 77.230)},
    "Burari": {"lat": (28.720, 28.755), "lon": (77.180, 77.210)},
    
    # East Delhi
    "Preet Vihar": {"lat": (28.640, 28.655), "lon": (77.285, 77.305)},
    "Laxmi Nagar": {"lat": (28.630, 28.645), "lon": (77.270, 77.290)},
    "Mayur Vihar": {"lat": (28.605, 28.620), "lon": (77.290, 77.310)},
    "Shahdara": {"lat": (28.675, 28.695), "lon": (77.275, 77.300)},
    "Gandhi Nagar": {"lat": (28.660, 28.670), "lon": (77.245, 77.260)},
    
    # West Delhi
    "Janakpuri": {"lat": (28.615, 28.630), "lon": (77.075, 77.095)},
    "Rajouri Garden": {"lat": (28.635, 28.650), "lon": (77.115, 77.130)},
    "Tilak Nagar": {"lat": (28.630, 28.645), "lon": (77.090, 77.110)},
    "Punjabi Bagh": {"lat": (28.665, 28.680), "lon": (77.120, 77.140)},
    "Dwarka": {"lat": (28.580, 28.610), "lon": (77.030, 77.070)},
    "Vikaspuri": {"lat": (28.640, 28.655), "lon": (77.055, 77.075)},
    "Uttam Nagar": {"lat": (28.610, 28.625), "lon": (77.050, 77.075)},
    
    # South-West Delhi
    "Vasant Vihar": {"lat": (28.555, 28.570), "lon": (77.155, 77.170)},
    "RK Puram": {"lat": (28.560, 28.575), "lon": (77.165, 77.185)},
    "Munirka": {"lat": (28.555, 28.565), "lon": (77.170, 77.185)},
    
    # New Delhi
    "Diplomatic Enclave": {"lat": (28.590, 28.605), "lon": (77.180, 77.200)},
    "Chanakyapuri": {"lat": (28.595, 28.605), "lon": (77.185, 77.200)},
    "India Gate": {"lat": (28.610, 28.620), "lon": (77.225, 77.235)},
    
    # North-West Delhi
    "Narela": {"lat": (28.840, 28.880), "lon": (77.075, 77.110)},
    "Bawana": {"lat": (28.790, 28.820), "lon": (77.020, 77.055)},
    "Shalimar Bagh": {"lat": (28.705, 28.725), "lon": (77.140, 77.165)},
    "Adarsh Nagar": {"lat": (28.715, 28.730), "lon": (77.160, 77.180)},
}

def get_area_name_from_coords(lat, lon):
    """Get Delhi area name based on lat/lon coordinates."""
    for area_name, bounds in DELHI_AREAS.items():
        if (bounds["lat"][0] <= lat <= bounds["lat"][1] and 
            bounds["lon"][0] <= lon <= bounds["lon"][1]):
            return area_name
    
    # If no exact match, return general region
    if lat > 28.70:
        return "North Delhi"
    elif lat < 28.55:
        return "South Delhi"
    elif lon < 77.15:
        return "West Delhi"
    elif lon > 77.25:
        return "East Delhi"
    else:
        return "Central Delhi"

def enhance_ward_names():
    """Update ward names in ward_boundaries.geojson with real area names."""
    
    import os
    BASE_DIR = os.path.dirname(__file__)
    GEOJSON_PATH = os.path.join(BASE_DIR, "dataset", "ward_boundaries.geojson")
    
    if not os.path.exists(GEOJSON_PATH):
        print(f"❌ File not found: {GEOJSON_PATH}")
        return
    
    print("=" * 70)
    print("ENHANCING WARD NAMES WITH REAL DELHI AREAS")
    print("=" * 70)
    
    # Read the GeoJSON
    gdf = gpd.read_file(GEOJSON_PATH)
    print(f"✓ Loaded {len(gdf)} wards")
    
    # Calculate centroids and update names
    updated_count = 0
    for idx, row in gdf.iterrows():
        centroid = row.geometry.centroid
        lat, lon = centroid.y, centroid.x
        
        area_name = get_area_name_from_coords(lat, lon)
        
        # Update Ward_Name with area name and ward ID
        new_name = f"{area_name} - Ward {row['Ward_ID']}"
        gdf.at[idx, 'Ward_Name'] = new_name
        
        print(f"  Ward {row['Ward_ID']:2d}: {area_name:25s} ({lat:.4f}, {lon:.4f})")
        updated_count += 1
    
    # Save back to GeoJSON
    gdf.to_file(GEOJSON_PATH, driver='GeoJSON')
    
    print("=" * 70)
    print(f"✓ Updated {updated_count} ward names")
    print(f"✓ Saved to: {GEOJSON_PATH}")
    print("=" * 70)

if __name__ == "__main__":
    enhance_ward_names()
