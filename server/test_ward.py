from grid_index import lookup_ward_id, get_grids_in_ward, get_ward_info, is_available, is_ward_available

# Test coordinates from the error
lat = 28.514714
lon = 77.309542

print(f"Testing coordinates: {lat}, {lon}")
print(f"Grid index available: {is_available()}")
print(f"Ward index available: {is_ward_available()}")

if is_ward_available():
    ward_id = lookup_ward_id(lat, lon)
    print(f"Ward ID: {ward_id}")
    
    if ward_id:
        ward_info = get_ward_info(ward_id)
        print(f"Ward info: {ward_info}")
        
        grid_ids = get_grids_in_ward(ward_id)
        print(f"Number of grids in ward: {len(grid_ids)}")
        if grid_ids:
            print(f"Grid IDs (first 10): {grid_ids[:10]}")
            print(f"Grid ID range in ward: {min(grid_ids)} - {max(grid_ids)}")
