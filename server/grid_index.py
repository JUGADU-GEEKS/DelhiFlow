"""Grid and Ward index loader with spatial lookup.

This module provides spatial lookup functions for:
1. Grid_ID from lat/lon (grid-level lookups)
2. Ward_ID from lat/lon (ward-level lookups)
3. All grids within a ward

Supported input files (first one found will be used):
 - Grid: server/dataset/grid_index.geojson/parquet/shp
 - Wards: server/dataset/ward_boundaries.geojson/parquet/shp

If none are found, lookup functions will raise a descriptive error.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional, List

import shapely.geometry as geom


BASE_DIR = os.path.dirname(__file__)
DATASET_DIR = os.path.join(BASE_DIR, "dataset")


def _candidate_paths(prefix: str):
    """Get candidate file paths for a given data type (grid or ward)."""
    return [
        os.path.join(DATASET_DIR, f"{prefix}_index.geojson"),
        os.path.join(DATASET_DIR, f"{prefix}_index.parquet"),
        os.path.join(DATASET_DIR, f"{prefix}_index.shp"),
        os.path.join(DATASET_DIR, f"{prefix}_boundaries.geojson"),
        os.path.join(DATASET_DIR, f"{prefix}_boundaries.parquet"),
        os.path.join(DATASET_DIR, f"{prefix}_boundaries.shp"),
    ]


def _load_gdf(data_type: str = "grid", id_column: str = "Grid_ID"):
    """Attempt to load a GeoDataFrame with spatial index.
    
    Args:
        data_type: "grid" or "ward"
        id_column: Name of the ID column (Grid_ID, Ward_ID, etc.)
    """
    try:
        import geopandas as gpd  # type: ignore
    except Exception as ex:
        raise RuntimeError(
            "geopandas is required for spatial lookup but is not installed. "
            "Install dependencies from server/requirements.txt."
        ) from ex

    for p in _candidate_paths(data_type):
        if os.path.exists(p):
            gdf = gpd.read_file(p)
            # Normalize expected ID column
            if id_column not in gdf.columns:
                # try some common variants
                for alt in (id_column.lower(), id_column.replace("_", ""), f"id"):
                    if alt in gdf.columns:
                        gdf = gdf.rename(columns={alt: id_column})
                        break
            if id_column not in gdf.columns or gdf.geometry is None:
                raise RuntimeError(
                    f"Index file '{p}' missing required columns [{id_column}, geometry]"
                )
            # Ensure spatial index can be built
            _ = gdf.sindex  # builds/validates spatial index
            return gdf[[id_column, "geometry"]].copy()
    raise FileNotFoundError(
        f"No {data_type} geometry file found. Provide one of: "
        f"dataset/{data_type}_index.geojson, dataset/{data_type}_index.parquet, dataset/{data_type}_index.shp, "
        f"dataset/{data_type}_boundaries.geojson, dataset/{data_type}_boundaries.parquet, dataset/{data_type}_boundaries.shp"
    )


@lru_cache(maxsize=2)
def get_grid_gdf():
    """Load and cache grid geometry."""
    return _load_gdf("grid", "Grid_ID")


@lru_cache(maxsize=2)
def get_ward_gdf():
    """Load and cache ward geometry."""
    return _load_gdf("ward", "Ward_ID")


def is_available() -> bool:
    """Check if grid index is available."""
    try:
        get_grid_gdf()
        return True
    except Exception:
        return False


def is_ward_available() -> bool:
    """Check if ward index is available."""
    try:
        get_ward_gdf()
        return True
    except Exception:
        return False


def lookup_grid_id(latitude: float, longitude: float) -> Optional[int]:
    """Return Grid_ID containing the point (lat, lon), or None if not found.

    Requires a grid geometry file to be present.
    """
    gdf = get_grid_gdf()
    pt = geom.Point(float(longitude), float(latitude))  # note: (x,y) = (lon,lat)
    # fast bounding-box filter
    idxs = list(gdf.sindex.query(pt, predicate="intersects"))
    if not idxs:
        return None
    cand = gdf.iloc[idxs]
    # precise check
    mask = cand.contains(pt)
    if mask.any():
        row = cand[mask].iloc[0]
        return int(row["Grid_ID"])  # type: ignore
    return None

def lookup_ward_id(latitude: float, longitude: float) -> Optional[int]:
    """Return Ward_ID containing the point (lat, lon), or None if not found.

    Requires a ward geometry file to be present.
    """
    gdf = get_ward_gdf()
    pt = geom.Point(float(longitude), float(latitude))  # note: (x,y) = (lon,lat)
    # fast bounding-box filter
    idxs = list(gdf.sindex.query(pt, predicate="intersects"))
    if not idxs:
        return None
    cand = gdf.iloc[idxs]
    # precise check
    mask = cand.contains(pt)
    if mask.any():
        row = cand[mask].iloc[0]
        return int(row["Ward_ID"])  # type: ignore
    return None


def get_grids_in_ward(ward_id: int) -> List[int]:
    """Return list of all Grid_IDs that intersect with a ward.
    
    Args:
        ward_id: The Ward_ID to query
        
    Returns:
        List of Grid_IDs in the ward, or empty list if ward not found
    """
    try:
        ward_gdf = get_ward_gdf()
        grid_gdf = get_grid_gdf()
        
        # Get the ward geometry
        ward_rows = ward_gdf[ward_gdf['Ward_ID'] == ward_id]
        if ward_rows.empty:
            return []
        
        ward_geom = ward_rows.iloc[0].geometry
        
        # Find all grids that intersect with this ward
        intersecting = grid_gdf[grid_gdf.geometry.intersects(ward_geom)]
        
        return intersecting['Grid_ID'].astype(int).tolist()
    except Exception as e:
        print(f"[ERROR] Failed to get grids in ward {ward_id}: {e}")
        return []


def get_ward_info(ward_id: int) -> Optional[dict]:
    """Get ward information including geometry bounds and name if available.
    
    Args:
        ward_id: The Ward_ID to query
        
    Returns:
        Dict with Ward_ID, bounds, and optionally Ward_Name, or None if not found
    """
    try:
        ward_gdf = get_ward_gdf()
        ward_rows = ward_gdf[ward_gdf['Ward_ID'] == ward_id]
        
        if ward_rows.empty:
            return None
        
        row = ward_rows.iloc[0]
        geom = row.geometry
        bounds = geom.bounds  # (minx, miny, maxx, maxy)
        
        info = {
            'Ward_ID': int(ward_id),
            'bounds': {
                'min_lon': float(bounds[0]),
                'min_lat': float(bounds[1]),
                'max_lon': float(bounds[2]),
                'max_lat': float(bounds[3])
            }
        }
        
        # Add ward name if available
        if 'Ward_Name' in ward_gdf.columns:
            info['Ward_Name'] = row['Ward_Name']
        
        return info
    except Exception as e:
        print(f"[ERROR] Failed to get ward info for {ward_id}: {e}")
        return None