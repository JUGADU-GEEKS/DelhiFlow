"""Grid index loader and spatial lookup.

This module tries to load a vector grid geometry with Grid_ID polygons to map
lat/lon to the correct Grid_ID.

Supported input files (first one found will be used):
 - server/dataset/grid_index.geojson
 - server/dataset/grid_index.parquet (GeoParquet)
 - server/dataset/grid_index.shp (Shapefile)

If none are found, lookup functions will raise a descriptive error.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

import shapely.geometry as geom


BASE_DIR = os.path.dirname(__file__)
DATASET_DIR = os.path.join(BASE_DIR, "dataset")


def _candidate_paths():
    return [
        os.path.join(DATASET_DIR, "grid_index.geojson"),
        os.path.join(DATASET_DIR, "grid_index.parquet"),
        os.path.join(DATASET_DIR, "grid_index.shp"),
    ]


def _load_gdf():
    """Attempt to load a GeoDataFrame with columns [Grid_ID, geometry]."""
    try:
        import geopandas as gpd  # type: ignore
    except Exception as ex:
        raise RuntimeError(
            "geopandas is required for spatial lookup but is not installed. "
            "Install dependencies from server/requirements.txt."
        ) from ex

    for p in _candidate_paths():
        if os.path.exists(p):
            gdf = gpd.read_file(p)
            # Normalize expected columns
            if "Grid_ID" not in gdf.columns:
                # try some common variants
                for alt in ("grid_id", "gridId", "GRID_ID", "id"):
                    if alt in gdf.columns:
                        gdf = gdf.rename(columns={alt: "Grid_ID"})
                        break
            if "Grid_ID" not in gdf.columns or gdf.geometry is None:
                raise RuntimeError(
                    f"Grid index file '{p}' missing required columns [Grid_ID, geometry]"
                )
            # Ensure spatial index can be built
            _ = gdf.sindex  # builds/validates spatial index
            return gdf[["Grid_ID", "geometry"]]
    raise FileNotFoundError(
        "No grid geometry file found. Provide one of: "
        "dataset/grid_index.geojson, dataset/grid_index.parquet, dataset/grid_index.shp"
    )


@lru_cache(maxsize=1)
def get_grid_gdf():
    return _load_gdf()


def is_available() -> bool:
    try:
        get_grid_gdf()
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
