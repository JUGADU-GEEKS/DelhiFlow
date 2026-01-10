"""
Create grid index GeoJSON file from Delhi ward boundaries.

This script generates a grid overlay covering Delhi and saves it as grid_index.geojson.
The grid cells can be used for spatial lookups when Grid_IDs from the dataset need
to be matched to geographic locations.

Usage:
    python create_grid_index.py [--grid-size-m 500] [--output dataset/grid_index.geojson]
"""
import os
import argparse
from shapely.geometry import box
import geopandas as gpd
import numpy as np


def create_grid_index_from_wards(ward_gdf, grid_size_deg=0.005, output_path=None):
    """Create a grid index covering all ward boundaries.
    
    Args:
        ward_gdf: GeoDataFrame with ward boundaries
        grid_size_deg: Grid cell size in degrees (default ~500m)
        output_path: Output file path (default: dataset/grid_index.geojson)
    
    Returns:
        GeoDataFrame with grid cells and Grid_ID
    """
    # Get Delhi bounds from ward boundaries
    minx, miny, maxx, maxy = ward_gdf.total_bounds
    
    print(f"[INFO] Delhi bounds: ({minx:.4f}, {miny:.4f}) to ({maxx:.4f}, {maxy:.4f})")
    print(f"[INFO] Creating grid with cell size: {grid_size_deg:.6f} degrees (~{grid_size_deg * 111000:.0f} meters)")
    
    # Create grid cells
    x_coords = np.arange(minx, maxx + grid_size_deg, grid_size_deg)
    y_coords = np.arange(miny, maxy + grid_size_deg, grid_size_deg)
    
    polygons = []
    for x in x_coords:
        for y in y_coords:
            polygons.append(box(x, y, x + grid_size_deg, y + grid_size_deg))
    
    # Create GeoDataFrame
    grid_gdf = gpd.GeoDataFrame({'geometry': polygons}, crs=ward_gdf.crs)
    
    # Clip to ward boundaries (only keep grids that intersect with Delhi)
    print("[INFO] Clipping grid to Delhi boundaries...")
    # Use overlay to get intersection
    grid_clipped = gpd.overlay(grid_gdf, ward_gdf, how='intersection')
    
    # Remove duplicate geometries that might occur from overlay
    grid_clipped = grid_clipped.drop_duplicates(subset=['geometry'])
    
    # Reset index and assign Grid_ID
    grid_clipped = grid_clipped.reset_index(drop=True)
    grid_clipped['Grid_ID'] = range(len(grid_clipped))
    
    # Keep only essential columns for grid index
    grid_index = grid_clipped[['Grid_ID', 'geometry']].copy()
    
    print(f"[INFO] Created {len(grid_index)} grid cells")
    
    # Save to file
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        grid_index.to_file(output_path, driver='GeoJSON')
        print(f"[SUCCESS] Grid index saved to: {output_path}")
    
    return grid_index


def main():
    parser = argparse.ArgumentParser(
        description="Create grid index GeoJSON file for Delhi flood prediction system"
    )
    parser.add_argument(
        '--grid-size-m',
        type=int,
        default=500,
        help='Grid cell size in meters (default: 500)'
    )
    parser.add_argument(
        '--ward-file',
        type=str,
        default=None,
        help='Path to ward boundaries GeoJSON (default: auto-detect)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output file path (default: server/dataset/grid_index.geojson)'
    )
    
    args = parser.parse_args()
    
    # Set default output path relative to script location
    if args.output is None:
        base_dir = os.path.dirname(__file__)
        args.output = os.path.join(base_dir, 'dataset', 'grid_index.geojson')
    
    # Find ward boundaries file
    if args.ward_file and os.path.exists(args.ward_file):
        ward_path = args.ward_file
    else:
        # Auto-detect ward file
        base_dir = os.path.dirname(__file__)
        candidates = [
            os.path.join(base_dir, 'delhi_wards.geojson'),
            os.path.join(base_dir, 'dataset', 'ward_boundaries.geojson'),
        ]
        
        ward_path = None
        for candidate in candidates:
            if os.path.exists(candidate):
                ward_path = candidate
                break
        
        if not ward_path:
            print("[ERROR] Ward boundaries file not found. Please provide --ward-file path.")
            print(f"[INFO] Searched in: {candidates}")
            return 1
    
    print(f"[INFO] Loading ward boundaries from: {ward_path}")
    
    try:
        ward_gdf = gpd.read_file(ward_path)
        
        # Normalize Ward_ID column if needed
        if 'Ward_ID' not in ward_gdf.columns:
            if 'Ward_No' in ward_gdf.columns:
                ward_gdf = ward_gdf.rename(columns={'Ward_No': 'Ward_ID'})
        
        print(f"[INFO] Loaded {len(ward_gdf)} wards")
        
        # Convert grid size from meters to degrees (approximate)
        # 1 degree latitude ≈ 111,000 meters
        grid_size_deg = args.grid_size_m / 111000.0
        
        # Create grid index
        grid_index = create_grid_index_from_wards(
            ward_gdf,
            grid_size_deg=grid_size_deg,
            output_path=args.output
        )
        
        print(f"\n[SUCCESS] Grid index created successfully!")
        print(f"  - Total grid cells: {len(grid_index)}")
        print(f"  - Output file: {args.output}")
        print(f"  - You can now use grid-based predictions (no more fallback message)")
        
        return 0
        
    except Exception as e:
        print(f"[ERROR] Failed to create grid index: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

