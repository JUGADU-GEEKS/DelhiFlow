#!/usr/bin/env python3
"""Diagnostic script to test safe route system."""

import sys
sys.path.insert(0, '.')

from safe_route import SafeRouteManager, load_sample_roads

print("\n=== DIAGNOSING SAFE ROUTE SYSTEM ===\n")

# Create manager
manager = SafeRouteManager()
print(f"1. Manager created")
print(f"   - Segments: {len(manager.segments)}")
print(f"   - Graph nodes: {len(manager.graph)}")

# Load roads
roads = load_sample_roads()
print(f"\n2. Sample roads loaded")
print(f"   - Features: {len(roads['features'])}")
if roads['features']:
    print(f"   - First feature: {roads['features'][0]['properties']['name']}")

# Add roads to manager
count = manager.add_road_network(roads)
print(f"\n3. Roads added to manager")
print(f"   - Segments created: {count}")
print(f"   - Manager segments now: {len(manager.segments)}")
print(f"   - Manager graph nodes now: {len(manager.graph)}")
print(f"   - Segment graph edges: {len(manager.segment_graph)}")

# Check if graph is connected
if manager.graph:
    sample_node = list(manager.graph.keys())[0]
    print(f"\n4. Sample graph connectivity")
    print(f"   - Sample node: {sample_node}")
    print(f"   - Neighbors: {manager.graph[sample_node]}")
    print(f"   - Total nodes: {len(manager.graph)}")
    
    # Check if all nodes have neighbors
    isolated = [n for n in manager.graph if len(manager.graph[n]) == 0]
    print(f"   - Isolated nodes: {len(isolated)}")

# Try to find a route
print(f"\n5. Testing route finding...")
source = (77.0, 28.5)  # lon, lat (middle of bounds)
destination = (77.3, 28.8)
print(f"   - Source: {source}")
print(f"   - Destination: {destination}")

route = manager.find_safest_route(source, destination)
if route:
    print(f"   - SUCCESS! Found route with {len(route.waypoints)} waypoints")
    print(f"   - Distance: {route.total_distance:.0f}m")
    print(f"   - Risk: {route.risk_level}")
else:
    print(f"   - FAILED! No route found")

print("\n=== END DIAGNOSTICS ===\n")
