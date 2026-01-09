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
    paths = [
        os.path.join(DATASET_DIR, f"{prefix}_index.geojson"),
        os.path.join(DATASET_DIR, f"{prefix}_index.parquet"),
        os.path.join(DATASET_DIR, f"{prefix}_index.shp"),
        os.path.join(DATASET_DIR, f"{prefix}_boundaries.geojson"),
        os.path.join(DATASET_DIR, f"{prefix}_boundaries.parquet"),
        os.path.join(DATASET_DIR, f"{prefix}_boundaries.shp"),
    ]
    # For wards, also check original delhi_wards.geojson (if it exists in parent directory)
    if prefix == "ward":
        original_path = os.path.join(BASE_DIR, "delhi_wards.geojson")
        if os.path.exists(original_path):
            # Prepend to check first (original has better ward names)
            paths.insert(0, original_path)
    return paths


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
                # For wards, try Ward_No (from delhi_wards.geojson) as well
                if data_type == "ward" and id_column == "Ward_ID":
                    # Check for Ward_No first (original GeoJSON format)
                    if "Ward_No" in gdf.columns:
                        gdf = gdf.rename(columns={"Ward_No": id_column})
                    elif "ward_no" in gdf.columns:
                        gdf = gdf.rename(columns={"ward_no": id_column})
                    elif "WNo_SEC" in gdf.columns:
                        # Sometimes Ward_No might be in WNo_SEC
                        gdf = gdf.rename(columns={"WNo_SEC": id_column})
                # try common variants
                if id_column not in gdf.columns:
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
            # Keep all columns for ward data (preserves Ward_Name, etc.)
            if data_type == "ward":
                return gdf.copy()
            # For grids, keep only essential columns
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
    """Load and cache ward geometry.
    
    This function caches the GeoDataFrame. To reload with different files,
    call get_ward_gdf.cache_clear() first.
    """
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

def lookup_nearest_ward(latitude: float, longitude: float) -> Optional[int]:
    """Return the Ward_ID whose geometry is nearest to the point.

    This is used as a fallback when a point falls just outside polygons.
    """
    gdf = get_ward_gdf()
    pt = geom.Point(float(longitude), float(latitude))
    try:
        nearest_idx = list(gdf.sindex.nearest(pt, num_results=1))
        if nearest_idx:
            row = gdf.iloc[nearest_idx[0]]
            return int(row["Ward_ID"])  # type: ignore
    except Exception:
        # Fallback if spatial index nearest fails: use geometric distance
        try:
            distances = gdf.geometry.distance(pt)
            min_idx = distances.idxmin()
            row = gdf.loc[min_idx]
            return int(row["Ward_ID"])  # type: ignore
        except Exception:
            return None
    return None


def lookup_ward_id(latitude: float, longitude: float) -> Optional[int]:
    """Return Ward_ID containing the point (lat, lon), or nearest ward if not found.

    Requires a ward geometry file to be present.
    """
    gdf = get_ward_gdf()
    pt = geom.Point(float(longitude), float(latitude))  # note: (x,y) = (lon,lat)
    # fast bounding-box filter
    idxs = list(gdf.sindex.query(pt, predicate="intersects"))
    if idxs:
        cand = gdf.iloc[idxs]
        mask = cand.contains(pt)
        if mask.any():
            row = cand[mask].iloc[0]
            return int(row["Ward_ID"])  # type: ignore

    # Fallback: nearest ward (covers edge cases/out-of-extent)
    return lookup_nearest_ward(latitude, longitude)


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


def _extract_ward_name(row, ward_gdf) -> Optional[str]:
    """Extract ward name from GeoJSON properties dynamically.
    
    Checks for actual ward name properties, avoiding district-prefixed names
    from enhance_ward_names.py. Prioritizes genuine ward names like "FATEH NAGAR"
    over district-prefixed names like "South Delhi - Ward 1".
    
    Priority order:
    1. WardName (actual ward name from delhi_wards.geojson, e.g., "FATEH NAGAR")
    2. NW2022 (formatted name, extract ward name part after comma)
    3. Ward_Name (but strip district prefix if present, e.g., "South Delhi - Ward 1" -> "Ward 1")
    4. Other variations (ward_name, WARD_NAME, name)
    
    Args:
        row: The GeoDataFrame row for the ward
        ward_gdf: The full ward GeoDataFrame (for column checking)
        
    Returns:
        Ward name string if found (without district prefixes), None otherwise
    """
    # Priority 1: WardName - actual ward name from original GeoJSON
    if 'WardName' in ward_gdf.columns:
        value = row.get('WardName')
        if value is not None and str(value).strip():
            name = str(value).strip()
            # Avoid district names - if it contains "Delhi" and pattern like "X Delhi", skip it
            if 'Delhi' not in name or '-' not in name:
                return name
    
    # Priority 2: NW2022 - formatted name (e.g., "100, FATEH NAGAR")
    if 'NW2022' in ward_gdf.columns:
        value = row.get('NW2022')
        if value is not None and str(value).strip():
            if ',' in str(value):
                # Extract name part after comma (e.g., "100, FATEH NAGAR" -> "FATEH NAGAR")
                parts = str(value).split(',', 1)
                if len(parts) > 1:
                    name = parts[1].strip()
                    # Only return if it doesn't look like a district name
                    if 'Delhi' not in name or '-' not in name:
                        return name
    
    # Priority 3: Ward_Name - but strip district prefix if present
    if 'Ward_Name' in ward_gdf.columns:
        value = row.get('Ward_Name')
        if value is not None and str(value).strip():
            name = str(value).strip()
            # Check if it's a district-prefixed name (e.g., "South Delhi - Ward 1")
            if ' - ' in name or ' -' in name or '- ' in name:
                parts = name.split('-', 1)
                if len(parts) > 1:
                    # Extract the part after the dash (e.g., "Ward 1")
                    ward_part = parts[1].strip()
                    # If it starts with "Ward", use it; otherwise check if original is better
                    if ward_part.startswith('Ward'):
                        return ward_part
                    # If we have a ward number, use "Ward {number}" format
                    ward_id = row.get('Ward_ID') or row.get('Ward_No')
                    if ward_id is not None:
                        return f"Ward {ward_id}"
            else:
                # Not a district-prefixed name, use as-is
                # But avoid if it's just a district name
                if 'Delhi' not in name or ('Ward' in name or any(char.isdigit() for char in name)):
                    return name
    
    # Priority 4: Other variations
    for candidate in ['ward_name', 'WARD_NAME', 'name']:
        if candidate in ward_gdf.columns:
            value = row.get(candidate)
            if value is not None and str(value).strip():
                name = str(value).strip()
                # Avoid district-only names
                if 'Delhi' not in name or ('Ward' in name or '-' in name):
                    return name
    
    # Fallback: Use ward number if available
    ward_id = row.get('Ward_ID') or row.get('Ward_No')
    if ward_id is not None:
        return f"Ward {ward_id}"
    
    return None


def get_ward_info(ward_id: int) -> Optional[dict]:
    """Get ward information including geometry bounds and name if available.
    
    Ward names are extracted dynamically from GeoJSON properties, supporting
    various property name formats (WardName, Ward_Name, ward_name, etc.).
    
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
        
        # Extract ward name dynamically from GeoJSON properties
        ward_name = _extract_ward_name(row, ward_gdf)
        if ward_name:
            info['Ward_Name'] = ward_name
        
        return info
    except Exception as e:
        print(f"[ERROR] Failed to get ward info for {ward_id}: {e}")
        return None