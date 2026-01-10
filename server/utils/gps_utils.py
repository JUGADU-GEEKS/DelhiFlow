"""GPS utility functions for distance and grid calculations."""

import math


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points in meters.
    
    Args:
        lat1, lon1: First point coordinates in decimal degrees
        lat2, lon2: Second point coordinates in decimal degrees
    
    Returns:
        Distance in meters
    """
    # Radius of Earth in meters
    R = 6371000
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance


def grid_bucket(lat: float, lon: float, grid_size_meters: float = 50.0):
    """Bucket a GPS coordinate into a grid cell ID.
    
    Creates a grid system where each cell is approximately grid_size_meters x grid_size_meters.
    Returns the grid ID and the base coordinates of the grid cell.
    
    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        grid_size_meters: Size of each grid cell in meters (default 50m)
    
    Returns:
        Tuple of (gridId, base_lat, base_lon, grid_lat_index, grid_lon_index)
    """
    # Approximate degrees per meter at this latitude
    # 1 degree latitude ≈ 111,320 meters
    # 1 degree longitude ≈ 111,320 * cos(latitude) meters
    meters_per_degree_lat = 111320.0
    meters_per_degree_lon = 111320.0 * math.cos(math.radians(lat))
    
    # Calculate grid size in degrees
    grid_degrees_lat = grid_size_meters / meters_per_degree_lat
    grid_degrees_lon = grid_size_meters / meters_per_degree_lon
    
    # Calculate grid indices
    grid_lat_index = int(math.floor(lat / grid_degrees_lat))
    grid_lon_index = int(math.floor(lon / grid_degrees_lon))
    
    # Calculate base coordinates (southwest corner of grid cell)
    base_lat = grid_lat_index * grid_degrees_lat
    base_lon = grid_lon_index * grid_degrees_lon
    
    # Create unique grid ID
    gridId = f"{grid_lat_index}_{grid_lon_index}"
    
    return gridId, base_lat, base_lon, grid_lat_index, grid_lon_index
