"""
Update dataset/ward_boundaries.geojson with all 251 wards from delhi_wards.geojson.

This ensures the system uses the complete ward dataset everywhere.
"""
import os
import geopandas as gpd

def update_ward_boundaries():
    base_dir = os.path.dirname(__file__)
    source_file = os.path.join(base_dir, 'delhi_wards.geojson')
    target_file = os.path.join(base_dir, 'dataset', 'ward_boundaries.geojson')
    
    print(f"[INFO] Loading wards from: {source_file}")
    gdf = gpd.read_file(source_file)
    print(f"[INFO] Found {len(gdf)} wards")
    
    # Normalize Ward_ID column
    if 'Ward_No' in gdf.columns and 'Ward_ID' not in gdf.columns:
        gdf = gdf.rename(columns={'Ward_No': 'Ward_ID'})
        print("[INFO] Renamed 'Ward_No' to 'Ward_ID'")
    
    # Ensure Ward_ID exists
    if 'Ward_ID' not in gdf.columns:
        print("[WARNING] Ward_ID column not found, creating from index")
        gdf['Ward_ID'] = range(1, len(gdf) + 1)
    
    # Keep essential columns
    if 'Ward_Name' in gdf.columns:
        output_gdf = gdf[['Ward_ID', 'Ward_Name', 'geometry']].copy()
    else:
        # Create Ward_Name if missing
        gdf['Ward_Name'] = gdf.apply(
            lambda row: row.get('WardName', f"Ward {row['Ward_ID']}"),
            axis=1
        )
        output_gdf = gdf[['Ward_ID', 'Ward_Name', 'geometry']].copy()
    
    # Save to dataset folder
    os.makedirs(os.path.dirname(target_file), exist_ok=True)
    output_gdf.to_file(target_file, driver='GeoJSON')
    
    print(f"[SUCCESS] Updated {target_file} with {len(output_gdf)} wards")
    print(f"[INFO] Ward_ID range: {output_gdf['Ward_ID'].min()} - {output_gdf['Ward_ID'].max()}")

if __name__ == "__main__":
    update_ward_boundaries()

