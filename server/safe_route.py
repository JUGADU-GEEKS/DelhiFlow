"""Safe Route Finding System for Delhi Floods.

This module provides:
1. Road network data loading and segmentation
2. Risk scoring for road segments
3. Graph-based routing using Dijkstra's algorithm
4. Fallback route generation
5. Route visualization data
"""

import os
import json
import heapq
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime

import numpy as np


def convert_numpy_types(obj: Any) -> Any:
    """Recursively convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    else:
        return obj


# Try to import shapely, but continue if not available
try:
    from shapely.geometry import Point, LineString
    from shapely.ops import split
    HAS_SHAPELY = True
except ImportError:
    print("[SAFE_ROUTE] Warning: shapely not available, using simplified mode")
    HAS_SHAPELY = False
    Point = None
    LineString = None
    split = None

# Try to import geopandas, but continue if not available
try:
    import geopandas as gpd
    HAS_GEOPANDAS = True
except ImportError:
    print("[SAFE_ROUTE] Warning: geopandas not available, using simplified mode")
    HAS_GEOPANDAS = False

try:
    from grid_index import get_ward_info
except ImportError:
    get_ward_info = None


BASE_DIR = os.path.dirname(__file__)
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
WARD_BOUNDARIES_PATH = os.path.join(DATASET_DIR, "ward_boundaries.geojson")

# Default risk penalty (higher = more penalized)
RISK_PENALTY = 1000  # meters equivalent
SEGMENT_LENGTH = 75  # meters (50-100m range)


@dataclass
class RoadSegment:
    """Represents a single road segment with risk attributes."""
    segment_id: str
    geometry: Dict  # GeoJSON-like dict with coordinates
    ward_id: Optional[str]
    ward_name: Optional[str]
    flood_risk: float  # 0-1
    elevation: Optional[float]
    drain_distance: Optional[float]
    is_underpass: bool
    risk_score: float  # 0-1 normalized
    risk_level: str  # 'low', 'medium', 'high'
    length: float  # meters


@dataclass
class Route:
    """Represents a complete route with waypoints and risk assessment."""
    route_id: str
    source: Dict  # {lat, lon}
    destination: Dict  # {lat, lon}
    waypoints: List[Dict]  # [{lat, lon}, ...]
    segments_used: List[str]
    total_distance: float  # meters
    total_risk_score: float  # 0-1 average
    total_cost: float  # weighted cost
    risk_level: str  # overall risk level
    is_safe: bool  # True if avoids high-risk areas
    created_at: str


class SafeRouteManager:
    """Manages safe route finding for Delhi road network."""

    def __init__(self):
        """Initialize the manager and load data."""
        self.roads_gdf = None
        self.wards_gdf = None
        self.segments = {}  # segment_id -> RoadSegment
        self.graph = {}  # node_id -> [edge_node_id, ...]
        self.segment_graph = {}  # segment_id -> (from_node, to_node, cost)
        self.segment_counter = 0
        self._load_data()

    def _load_data(self):
        """Load ward boundaries for risk assignment."""
        try:
            if not HAS_GEOPANDAS:
                print("[SAFE_ROUTE] Skipping ward data load (geopandas not available)")
                return
                
            if os.path.exists(WARD_BOUNDARIES_PATH):
                self.wards_gdf = gpd.read_file(WARD_BOUNDARIES_PATH)
                print(f"[SAFE_ROUTE] Loaded {len(self.wards_gdf)} wards")
        except Exception as e:
            print(f"[SAFE_ROUTE] Warning: Could not load wards - {e}")

    def _get_ward_risk(self, point: Point) -> Tuple[Optional[str], Optional[str], float]:
        """Find ward containing point and return risk score.
        
        Returns:
            (ward_id, ward_name, risk_score)
        """
        if self.wards_gdf is None:
            return None, None, 0.5  # default to medium risk

        try:
            matching = self.wards_gdf[self.wards_gdf.geometry.contains(point)]
            if len(matching) > 0:
                ward = matching.iloc[0]
                ward_id = ward.get("Ward_ID", str(ward.name))
                ward_name = ward.get("Ward_Name", "Unknown")
                # Try to get flood risk if available
                risk = float(ward.get("Flood_Risk", 0.5))
                return ward_id, ward_name, risk
        except Exception:
            pass

        return None, None, 0.5

    def add_road_network(self, roads_geojson: Dict) -> int:
        """Load and segment road network from GeoJSON.
        
        Args:
            roads_geojson: GeoJSON-like dict with features
            
        Returns:
            Number of segments created
        """
        from shapely.geometry import shape
        
        self.segments = {}
        self.segment_counter = 0
        segment_count = 0

        features = roads_geojson.get("features", [])
        print(f"[SAFE_ROUTE] Processing {len(features)} road features")

        for feature in features:
            try:
                geom = shape(feature["geometry"])
                if geom.geom_type != "LineString":
                    continue

                # Segment the road
                segments = self._segment_linestring(geom)
                for seg_geom in segments:
                    segment_count += self._create_segment(seg_geom)

            except Exception as e:
                print(f"[SAFE_ROUTE] Error processing feature: {e}")
                continue

        print(f"[SAFE_ROUTE] Created {segment_count} road segments")
        self._build_graph()
        return segment_count

    def _segment_linestring(self, line: LineString) -> List[LineString]:
        """Split long roads into 50-100m segments.
        
        For short roads (< 150m), returns as-is to preserve intersection points.
        """
        total_length = line.length
        # Don't segment short roads - they're already optimized for grid connections
        if total_length <= 150:  # meters
            return [line]

        # Calculate number of segments for longer roads
        num_segments = max(2, int(np.ceil(total_length / SEGMENT_LENGTH)))
        
        segments = []
        cumulative_distance = 0
        current_line = line

        for i in range(num_segments - 1):
            target_distance = (i + 1) * (total_length / num_segments)
            point = current_line.interpolate(
                min(target_distance - cumulative_distance, current_line.length * 0.99)
            )
            
            try:
                split_lines = list(split(current_line, point))
                if len(split_lines) >= 2:
                    segments.append(split_lines[0])
                    current_line = split_lines[1]
                    cumulative_distance = target_distance
            except Exception:
                continue

        segments.append(current_line)
        return [s for s in segments if s.length > 0]

    def _create_segment(self, geometry: LineString) -> int:
        """Create a segment from LineString geometry."""
        try:
            # Get start and end points
            start_point = Point(geometry.coords[0])
            end_point = Point(geometry.coords[-1])

            # Assign ward and risk
            ward_id, ward_name, ward_risk = self._get_ward_risk(
                Point(geometry.centroid)
            )

            # Elevation (simulated - would use DEM in production)
            elevation = np.random.uniform(200, 250)

            # Drain distance (simulated - would use actual drainage network)
            drain_distance = np.random.uniform(50, 500)

            # Check for underpass (simplified - would check actual data)
            is_underpass = np.random.random() < 0.05  # 5% chance

            # Compute risk score
            risk_score = self._compute_risk_score(
                ward_risk, elevation, drain_distance, is_underpass
            )

            # Determine risk level
            if risk_score < 0.33:
                risk_level = "low"
            elif risk_score < 0.67:
                risk_level = "medium"
            else:
                risk_level = "high"

            segment_id = f"seg_{self.segment_counter}"
            self.segment_counter += 1

            segment = RoadSegment(
                segment_id=segment_id,
                geometry={
                    "type": "LineString",
                    "coordinates": list(geometry.coords),
                },
                ward_id=ward_id,
                ward_name=ward_name,
                flood_risk=ward_risk,
                elevation=elevation,
                drain_distance=drain_distance,
                is_underpass=is_underpass,
                risk_score=risk_score,
                risk_level=risk_level,
                length=geometry.length,
            )

            self.segments[segment_id] = segment
            return 1

        except Exception as e:
            print(f"[SAFE_ROUTE] Error creating segment: {e}")
            return 0

    def _compute_risk_score(
        self,
        ward_risk: float,
        elevation: float,
        drain_distance: float,
        is_underpass: bool,
    ) -> float:
        """Compute normalized risk score for a segment.
        
        Factors:
        - Ward flood risk (50%)
        - Low elevation (30%) - lower elevation = higher risk
        - Far from drain (15%) - farther = higher risk
        - Underpass (5%) - underpasses are risky
        """
        score = 0.0

        # Ward risk (50%)
        score += ward_risk * 0.5

        # Elevation risk (30%) - lower elevation = higher risk
        # Assuming range 200-250m, low risk at high elevation
        elevation_normalized = max(0, min(1, 1 - (elevation - 200) / 50))
        score += elevation_normalized * 0.3

        # Drain distance risk (15%) - farther = higher risk
        # Assuming 50-500m range
        drain_risk = min(1, (drain_distance - 50) / 450)
        score += drain_risk * 0.15

        # Underpass penalty (5%)
        if is_underpass:
            score += 0.05

        return min(1.0, score)

    def _build_graph(self):
        """Build spatial graph from segments."""
        self.graph = {}
        self.segment_graph = {}

        for segment_id, segment in self.segments.items():
            coords = segment.geometry["coordinates"]
            start = coords[0]
            end = coords[-1]

            start_key = f"node_{start[0]:.6f}_{start[1]:.6f}"
            end_key = f"node_{end[0]:.6f}_{end[1]:.6f}"

            # Build adjacency graph
            if start_key not in self.graph:
                self.graph[start_key] = []
            if end_key not in self.graph:
                self.graph[end_key] = []

            self.graph[start_key].append(end_key)
            self.graph[end_key].append(start_key)

            # Store segment cost
            cost = segment.length + (segment.risk_score * RISK_PENALTY)
            self.segment_graph[segment_id] = (start_key, end_key, cost)

        print(f"[SAFE_ROUTE] Built graph with {len(self.graph)} nodes")

    def find_multiple_routes(
        self, source: Tuple[float, float], destination: Tuple[float, float], num_routes: int = 3
    ) -> List[Optional[Route]]:
        """Find multiple alternative routes between source and destination.
        
        Returns:
            List of Route objects, ordered by safety (lowest risk first)
        """
        print(f"\n[MULTI_ROUTE] Finding {num_routes} alternative routes from {source} to {destination}")
        
        if not self.segments or not self.graph:
            print("[MULTI_ROUTE] No segments or graph available")
            return []

        src_node = self._find_nearest_node(Point(source[1], source[0]), max_distance=50000)
        dst_node = self._find_nearest_node(Point(destination[1], destination[0]), max_distance=50000)

        if not src_node or not dst_node:
            print("[MULTI_ROUTE] Could not find source or destination nodes")
            return []

        routes = []
        used_segments = set()
        
        # Find multiple routes by penalizing previously used segments
        for route_num in range(num_routes):
            print(f"[MULTI_ROUTE] Finding route {route_num + 1}/{num_routes}")
            
            # Run Dijkstra with penalties on used segments
            path_nodes, total_cost = self._dijkstra_with_penalties(src_node, dst_node, used_segments)

            if not path_nodes:
                print(f"[MULTI_ROUTE] No more routes found after {route_num} routes")
                break

            # Convert path to waypoints and segments
            waypoints, segments_used = self._path_to_waypoints(path_nodes)
            total_distance = sum(
                self.segments[seg].length for seg in segments_used if seg in self.segments
            )
            total_risk = np.mean([
                self.segments[seg].risk_score for seg in segments_used if seg in self.segments
            ]) if segments_used else 0.5

            # Determine risk level
            if total_risk < 0.33:
                risk_level = "low"
            elif total_risk < 0.67:
                risk_level = "medium"
            else:
                risk_level = "high"

            is_safe = risk_level in ["low", "medium"]

            route = Route(
                route_id=f"route_{int(datetime.now().timestamp() * 1000)}_{route_num}",
                source={"lat": source[1], "lon": source[0]},
                destination={"lat": destination[1], "lon": destination[0]},
                waypoints=waypoints,
                segments_used=segments_used,
                total_distance=total_distance,
                total_risk_score=total_risk,
                total_cost=total_cost,
                risk_level=risk_level,
                is_safe=is_safe,
                created_at=datetime.now().isoformat(),
            )
            
            routes.append(route)
            used_segments.update(segments_used)
            
            print(f"[MULTI_ROUTE] Route {route_num + 1}: Risk={risk_level}, Distance={total_distance:.0f}m")

        return routes

    def _dijkstra_with_penalties(
        self, start: str, end: str, penalized_segments: set
    ) -> Tuple[Optional[List[str]], float]:
        """Dijkstra's algorithm with penalties on previously used segments."""
        distances = {node: float("inf") for node in self.graph}
        distances[start] = 0
        predecessors = {node: None for node in self.graph}
        visited = set()
        pq = [(0, start)]

        while pq:
            current_dist, current_node = heapq.heappop(pq)

            if current_node in visited:
                continue

            visited.add(current_node)

            if current_node == end:
                path = []
                node = end
                while node is not None:
                    path.append(node)
                    node = predecessors[node]
                return list(reversed(path)), current_dist

            for neighbor in self.graph.get(current_node, []):
                if neighbor not in visited:
                    edge_cost = 1.0
                    penalty = 0.0
                    
                    for seg_id, (start_node, end_node, cost) in self.segment_graph.items():
                        if (start_node == current_node and end_node == neighbor) or \
                           (start_node == neighbor and end_node == current_node):
                            edge_cost = cost
                            # Add penalty if segment was used before
                            if seg_id in penalized_segments:
                                penalty = edge_cost * 2  # Double the cost for reused segments
                            break

                    new_dist = current_dist + edge_cost + penalty
                    if new_dist < distances[neighbor]:
                        distances[neighbor] = new_dist
                        predecessors[neighbor] = current_node
                        heapq.heappush(pq, (new_dist, neighbor))

        return None, float("inf")

    def find_safest_route(
        self, source: Tuple[float, float], destination: Tuple[float, float]
    ) -> Optional[Route]:
        """Find safest route using Dijkstra's algorithm.
        
        Args:
            source: (longitude, latitude)
            destination: (longitude, latitude)
            
        Returns:
            Route object or None if no route found
        """
        print(f"\n[DIJKSTRA] Finding route from {source} to {destination}")
        print(f"[DIJKSTRA] Segments available: {len(self.segments)}")
        print(f"[DIJKSTRA] Graph nodes: {len(self.graph)}")
        
        if not self.segments or not self.graph:
            print("[DIJKSTRA] No segments or graph available - returning None")
            return None

        # Find nearest segment nodes to source and destination
        src_node = self._find_nearest_node(Point(source[1], source[0]), max_distance=50000)
        dst_node = self._find_nearest_node(Point(destination[1], destination[0]), max_distance=50000)
        
        print(f"[DIJKSTRA] Source node: {src_node}, Destination node: {dst_node}")

        if not src_node or not dst_node:
            print("[DIJKSTRA] Could not find source or destination nodes")
            return None

        # Run Dijkstra
        path_nodes, total_cost = self._dijkstra(src_node, dst_node)

        if not path_nodes:
            return None

        # Convert path to waypoints and segments
        waypoints, segments_used = self._path_to_waypoints(path_nodes)
        total_distance = sum(
            self.segments[seg].length for seg in segments_used if seg in self.segments
        )
        total_risk = np.mean([
            self.segments[seg].risk_score for seg in segments_used if seg in self.segments
        ]) if segments_used else 0.5

        # Determine overall risk level
        if total_risk < 0.33:
            risk_level = "low"
        elif total_risk < 0.67:
            risk_level = "medium"
        else:
            risk_level = "high"

        is_safe = risk_level in ["low", "medium"]

        route = Route(
            route_id=f"route_{int(datetime.now().timestamp() * 1000)}",
            source={"lat": source[1], "lon": source[0]},
            destination={"lat": destination[1], "lon": destination[0]},
            waypoints=waypoints,
            segments_used=segments_used,
            total_distance=total_distance,
            total_risk_score=total_risk,
            total_cost=total_cost,
            risk_level=risk_level,
            is_safe=is_safe,
            created_at=datetime.now().isoformat(),
        )

        return route

    def _find_nearest_node(self, point: Point, max_distance: float = 10000) -> Optional[str]:
        """Find nearest graph node to given point within max_distance meters."""
        min_dist = float("inf")
        nearest_node = None
        
        print(f"[NODE_FIND] Searching for nearest node to {point}")
        print(f"[NODE_FIND] Graph has {len(self.graph)} nodes")

        for i, node_id in enumerate(self.graph.keys()):
            if i < 3:  # Debug first 3 nodes
                print(f"[NODE_FIND]   Sample node {i}: {node_id}")
            
            # Extract coordinates from node_id
            parts = node_id.split("_")
            if len(parts) >= 3:
                try:
                    lon, lat = float(parts[1]), float(parts[2])
                    node_point = Point(lat, lon)
                    dist = point.distance(node_point) * 111000  # approx meters
                    
                    if i < 3:
                        print(f"[NODE_FIND]     Parsed: lon={lon}, lat={lat}, dist={dist:.0f}m, within_limit={dist < max_distance}")
                    
                    if dist < min_dist and dist < max_distance:
                        min_dist = dist
                        nearest_node = node_id
                except ValueError as e:
                    print(f"[NODE_FIND] Parse error on {node_id}: {e}")
                    continue

        print(f"[NODE_FIND] Result: nearest_node={nearest_node}, min_dist={min_dist:.0f}m")
        return nearest_node
        return nearest_node

    def _dijkstra(
        self, start: str, end: str
    ) -> Tuple[Optional[List[str]], float]:
        """Dijkstra's algorithm for shortest-safest path."""
        print(f"[DIJKSTRA] Running Dijkstra from {start} to {end}")
        
        distances = {node: float("inf") for node in self.graph}
        distances[start] = 0
        predecessors = {node: None for node in self.graph}
        visited = set()
        pq = [(0, start)]

        while pq:
            current_dist, current_node = heapq.heappop(pq)

            if current_node in visited:
                continue

            visited.add(current_node)

            if current_node == end:
                # Reconstruct path
                path = []
                node = end
                while node is not None:
                    path.append(node)
                    node = predecessors[node]
                result_path = list(reversed(path))
                print(f"[DIJKSTRA] Path found! Nodes: {len(result_path)}, Cost: {current_dist}")
                return result_path, current_dist

            for neighbor in self.graph.get(current_node, []):
                if neighbor not in visited:
                    # Find segment connecting these nodes
                    edge_cost = 1.0  # default
                    for seg_id, (start_node, end_node, cost) in self.segment_graph.items():
                        if (start_node == current_node and end_node == neighbor) or \
                           (start_node == neighbor and end_node == current_node):
                            edge_cost = cost
                            break

                    new_dist = current_dist + edge_cost
                    if new_dist < distances[neighbor]:
                        distances[neighbor] = new_dist
                        predecessors[neighbor] = current_node
                        heapq.heappush(pq, (new_dist, neighbor))

        print(f"[DIJKSTRA] No path found! Visited {len(visited)} nodes out of {len(self.graph)}")
        return None, float("inf")


    def _path_to_waypoints(self, path_nodes: List[str]) -> Tuple[List[Dict], List[str]]:
        """Convert node path to waypoints and segments."""
        waypoints = []
        segments = []

        for i, node_id in enumerate(path_nodes):
            parts = node_id.split("_")
            if len(parts) >= 3:
                try:
                    lon, lat = float(parts[1]), float(parts[2])
                    waypoints.append({"lat": lat, "lon": lon})
                except ValueError:
                    continue

            # Find segment for this edge
            if i < len(path_nodes) - 1:
                next_node = path_nodes[i + 1]
                for seg_id, (start, end, _) in self.segment_graph.items():
                    if (start == node_id and end == next_node) or \
                       (start == next_node and end == node_id):
                        segments.append(seg_id)
                        break

        return waypoints, segments

    def get_segment_by_id(self, segment_id: str) -> Optional[Dict]:
        """Get segment data as dict."""
        if segment_id in self.segments:
            seg = self.segments[segment_id]
            return convert_numpy_types(asdict(seg))
        return None

    def get_all_segments(self) -> List[Dict]:
        """Get all segments for visualization."""
        return [convert_numpy_types(asdict(seg)) for seg in self.segments.values()]

    def get_route_visualization(self, route: Route) -> Dict:
        """Prepare route data for frontend visualization."""
        result = {
            "route": asdict(route),
            "segments": [
                self.get_segment_by_id(seg_id)
                for seg_id in route.segments_used
                if self.get_segment_by_id(seg_id)
            ],
            "statistics": {
                "total_distance_km": route.total_distance / 1000,
                "total_risk_score": float(route.total_risk_score),
                "segments_count": len(route.segments_used),
                "high_risk_segments": sum(
                    1 for seg_id in route.segments_used
                    if self.get_segment_by_id(seg_id) and
                    self.get_segment_by_id(seg_id).get("risk_level") == "high"
                ),
                "medium_risk_segments": sum(
                    1 for seg_id in route.segments_used
                    if self.get_segment_by_id(seg_id) and
                    self.get_segment_by_id(seg_id).get("risk_level") == "medium"
                ),
                "low_risk_segments": sum(
                    1 for seg_id in route.segments_used
                    if self.get_segment_by_id(seg_id) and
                    self.get_segment_by_id(seg_id).get("risk_level") == "low"
                ),
            },
        }
        # Convert all numpy types to Python types for JSON serialization
        return convert_numpy_types(result)



# Global instance
_route_manager = None


def get_route_manager() -> SafeRouteManager:
    """Get or create global route manager."""
    global _route_manager
    if _route_manager is None:
        _route_manager = SafeRouteManager()
    return _route_manager


def load_sample_roads() -> Dict:
    """Load realistic road network covering Delhi grid.
    
    Creates a connected grid of roads with explicit intersections.
    """
    min_lon, max_lon = 76.8, 77.4
    min_lat, max_lat = 28.4, 28.9
    
    lons = [i * 0.05 + min_lon for i in range(int((max_lon - min_lon) / 0.05) + 1)]
    lats = [i * 0.05 + min_lat for i in range(int((max_lat - min_lat) / 0.05) + 1)]
    
    features = []
    
    # Create grid roads - each road segment connects two intersections
    # Horizontal roads (East-West)
    for i, lat in enumerate(lats):
        for j in range(len(lons) - 1):
            lon1, lon2 = lons[j], lons[j + 1]
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon1, lat], [lon2, lat]],
                },
                "properties": {"name": f"E-W {i}-{j}"},
            })
    
    # Vertical roads (North-South)
    for j, lon in enumerate(lons):
        for i in range(len(lats) - 1):
            lat1, lat2 = lats[i], lats[i + 1]
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon, lat1], [lon, lat2]],
                },
                "properties": {"name": f"N-S {i}-{j}"},
            })
    
    return {
        "type": "FeatureCollection",
        "features": features,
    }



if __name__ == "__main__":
    # Test the system
    manager = SafeRouteManager()
    roads = load_sample_roads()
    manager.add_road_network(roads)

    # Test routing
    source = (77.1, 28.5)  # lon, lat
    destination = (77.2, 28.7)
    route = manager.find_safest_route(source, destination)

    if route:
        print(f"\nRoute found!")
        print(f"Distance: {route.total_distance:.2f}m")
        print(f"Risk Level: {route.risk_level}")
        print(f"Waypoints: {len(route.waypoints)}")
    else:
        print("No route found")
