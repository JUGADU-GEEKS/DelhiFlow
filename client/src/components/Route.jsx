import React, { useState, useEffect } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './Route.css';

// Fix Leaflet icon issue
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

function Route() {
  const [map, setMap] = useState(null);
  const [source, setSource] = useState({ lat: 28.6139, lon: 77.2090 });
  const [destination, setDestination] = useState({ lat: 28.5500, lon: 77.1500 });
  const [route, setRoute] = useState(null);
  const [loading, setLoading] = useState(false);
  const [mapLayers, setMapLayers] = useState({ route: null });

  // Initialize map
  useEffect(() => {
    const mapInstance = L.map('map').setView([28.6139, 77.2090], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(mapInstance);
    setMap(mapInstance);

    return () => {
      mapInstance.remove();
    };
  }, []);

  // Fetch real road route from OSRM (Open Route Service Machine)
  const fetchRealRouteFromOSRM = async (srcLat, srcLon, destLat, destLon) => {
    try {
      console.log(`Fetching route from OSRM: (${srcLat},${srcLon}) → (${destLat},${destLon})`);
      
      // OSRM API uses lon,lat order
      const url = `https://router.project-osrm.org/route/v1/driving/${srcLon},${srcLat};${destLon},${destLat}?overview=full&geometries=geojson&steps=true`;
      
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`OSRM HTTP ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.code !== 'Ok' || !data.routes || data.routes.length === 0) {
        console.error('OSRM error:', data);
        throw new Error(`OSRM error: ${data.code}`);
      }
      
      const route = data.routes[0];
      console.log('✓ OSRM route received:', {
        distance_m: route.distance,
        duration_s: route.duration,
        coordinates: route.geometry.coordinates.length
      });
      
      // Convert coordinates to waypoints [lat,lon]
      const waypoints = route.geometry.coordinates.map(coord => ({
        lat: coord[1],
        lon: coord[0]
      }));
      
      return {
        waypoints,
        distance: route.distance,  // meters
        duration: route.duration   // seconds
      };
      
    } catch (error) {
      console.error('OSRM Error:', error.message);
      throw new Error(`Failed to fetch route: ${error.message}`);
    }
  };

  // Calculate flood risk for route waypoints
  const calculateFloodRiskForRoute = async (waypoints) => {
    try {
      if (!waypoints || waypoints.length === 0) {
        return { risk_score: 0.5, risk_level: 'medium' };
      }
      
      // Sample waypoints to check (every nth point)
      const step = Math.max(1, Math.floor(waypoints.length / 10));
      const samplePoints = [];
      for (let i = 0; i < waypoints.length; i += step) {
        samplePoints.push(waypoints[i]);
      }
      
      console.log(`Checking flood risk for ${samplePoints.length} sample points...`);
      
      let totalRisk = 0;
      let successCount = 0;
      
      // Get flood risk for each point from backend
      for (const point of samplePoints) {
        try {
          const response = await fetch('/api/location/risk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              latitude: point.lat,
              longitude: point.lon
            })
          });
          
          if (response.ok) {
            const data = await response.json();
            const risk = data.flood_risk !== undefined ? data.flood_risk : 0.5;
            totalRisk += risk;
            successCount++;
          } else {
            // Fallback to medium risk if API fails
            totalRisk += 0.5;
            successCount++;
          }
        } catch (e) {
          console.warn('Could not get risk for point:', point, e);
          totalRisk += 0.5;  // Default to medium risk
          successCount++;
        }
      }
      
      const avgRisk = successCount > 0 ? totalRisk / successCount : 0.5;
      const riskLevel = avgRisk > 0.67 ? 'high' : avgRisk > 0.33 ? 'medium' : 'low';
      
      console.log('✓ Flood risk calculated:', { risk_score: avgRisk, risk_level });
      
      return {
        risk_score: Math.min(1, avgRisk),
        risk_level: riskLevel
      };
    } catch (error) {
      console.error('Error calculating flood risk:', error);
      return { risk_score: 0.5, risk_level: 'medium' };
    }
  };

  // Get color for risk level
  const getColorForRiskLevel = (riskLevel) => {
    switch (riskLevel) {
      case 'high':
        return '#FF0000';  // Red
      case 'medium':
        return '#FFFF00';  // Yellow
      case 'low':
        return '#00FF00';  // Green
      default:
        return '#808080';  // Gray
    }
  };

  // Visualize route on map
  const visualizeRoute = (routeData, mapInstance) => {
    if (!mapInstance || !routeData.waypoints) {
      console.warn('Cannot visualize route - invalid data');
      return;
    }

    // Remove old route layer
    if (mapLayers.route) {
      mapInstance.removeLayer(mapLayers.route);
    }

    const featureGroup = L.featureGroup();
    
    // Extract data
    const waypoints = routeData.waypoints.map((wp) => [wp.lat, wp.lon]);
    const routeColor = getColorForRiskLevel(routeData.risk_level);
    const routeWeight = routeData.risk_level === 'high' ? 6 : 4;
    const dashArray = routeData.risk_level === 'high' ? '5, 5' : '';
    
    // Draw main route polyline
    const routePolyline = L.polyline(waypoints, {
      color: routeColor,
      weight: routeWeight,
      opacity: 0.85,
      dashArray: dashArray,
    });
    
    // Add popup with route info
    const distanceKm = (routeData.total_distance / 1000).toFixed(1);
    const riskPercent = (routeData.risk_score * 100).toFixed(1);
    routePolyline.bindPopup(
      `<strong>${routeData.risk_level.toUpperCase()} RISK Route</strong><br/>
       Distance: ${distanceKm} km<br/>
       Risk Score: ${riskPercent}%<br/>
       Waypoints: ${routeData.waypoints.length}`
    );
    featureGroup.addLayer(routePolyline);

    // Add source marker (GREEN)
    const sourceMarker = L.circleMarker([routeData.source.lat, routeData.source.lon], {
      radius: 10,
      fillColor: '#00AA00',
      color: '#000',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.9,
    });
    sourceMarker.bindPopup(
      `<strong>SOURCE</strong><br/>
       Lat: ${routeData.source.lat.toFixed(4)}<br/>
       Lon: ${routeData.source.lon.toFixed(4)}`
    );
    featureGroup.addLayer(sourceMarker);

    // Add destination marker (RED)
    const destMarker = L.circleMarker([routeData.destination.lat, routeData.destination.lon], {
      radius: 10,
      fillColor: '#FF0000',
      color: '#000',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.9,
    });
    destMarker.bindPopup(
      `<strong>DESTINATION</strong><br/>
       Lat: ${routeData.destination.lat.toFixed(4)}<br/>
       Lon: ${routeData.destination.lon.toFixed(4)}`
    );
    featureGroup.addLayer(destMarker);

    // Add intermediate waypoints (sample)
    if (waypoints.length > 20) {
      const step = Math.floor(waypoints.length / 10);
      for (let i = step; i < waypoints.length - step; i += step) {
        L.circleMarker(waypoints[i], {
          radius: 3,
          fillColor: routeColor,
          color: '#000',
          weight: 1,
          opacity: 0.6,
        }).addTo(featureGroup);
      }
    }

    featureGroup.addTo(mapInstance);
    setMapLayers({ ...mapLayers, route: featureGroup });
    
    console.log('✓ Route visualized on map');
  };

  // Main function to find and display route
  const handleFindRoute = async () => {
    try {
      setLoading(true);
      console.log('\n' + '='.repeat(60));
      console.log('FINDING ROUTE WITH REAL ROADS');
      console.log('='.repeat(60));
      console.log(`From: [${source.lat}, ${source.lon}]`);
      console.log(`To: [${destination.lat}, ${destination.lon}]`);
      
      // Step 1: Fetch real road route from OSRM
      console.log('\n[1] Fetching real road route from OSRM...');
      const osmRoute = await fetchRealRouteFromOSRM(
        source.lat, source.lon,
        destination.lat, destination.lon
      );
      
      // Step 2: Calculate flood risk
      console.log('\n[2] Calculating flood risk for route...');
      const riskData = await calculateFloodRiskForRoute(osmRoute.waypoints);
      
      // Step 3: Build complete route object
      const routeObject = {
        source: source,
        destination: destination,
        waypoints: osmRoute.waypoints,
        total_distance: osmRoute.distance,
        total_risk_score: riskData.risk_score,
        risk_level: riskData.risk_level,
        is_safe: riskData.risk_level !== 'high'
      };
      
      setRoute(routeObject);
      visualizeRoute(routeObject, map);
      
      // Fit map to route
      if (osmRoute.waypoints.length > 0) {
        const bounds = L.latLngBounds(
          osmRoute.waypoints.map((wp) => [wp.lat, wp.lon])
        );
        map.fitBounds(bounds, { padding: [50, 50] });
      }
      
      // Show summary
      const distKm = (osmRoute.distance / 1000).toFixed(1);
      const riskPct = (riskData.risk_score * 100).toFixed(1);
      const durationMin = Math.round(osmRoute.duration / 60);
      
      console.log('\n' + '='.repeat(60));
      console.log('ROUTE FOUND!');
      console.log('='.repeat(60));
      console.log(`Distance: ${distKm} km`);
      console.log(`Duration: ~${durationMin} minutes`);
      console.log(`Risk Level: ${riskData.risk_level.toUpperCase()} (${riskPct}%)`);
      console.log(`Waypoints: ${osmRoute.waypoints.length}`);
      console.log(`Route Color: ${getColorForRiskLevel(riskData.risk_level)}`);
      
      const colorEmoji = riskData.risk_level === 'high' ? '🔴' : 
                        riskData.risk_level === 'medium' ? '🟡' : '🟢';
      
      alert(`✓ ROUTE FOUND!\n\n` +
            `Distance: ${distKm} km\n` +
            `Duration: ~${durationMin} minutes\n` +
            `Risk Level: ${riskData.risk_level.toUpperCase()} (${riskPct}%)\n\n` +
            `${colorEmoji} Route displayed in ${riskData.risk_level === 'high' ? 'RED' : 
                                               riskData.risk_level === 'medium' ? 'YELLOW' : 
                                               'GREEN'} on map`);
      
    } catch (error) {
      console.error('\n❌ ERROR:', error);
      alert(`Error finding route:\n\n${error.message}\n\n` +
            `Make sure:\n` +
            `• Coordinates are within Delhi area\n` +
            `• Backend is running on port 8000\n` +
            `• OSRM service is accessible`);
    } finally {
      setLoading(false);
    }
  };

  const handleUseCurrentLocation = async () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setSource({
            lat: position.coords.latitude,
            lon: position.coords.longitude,
          });
        },
        (error) => {
          console.error('Geolocation error:', error);
          alert('Could not get your location');
        }
      );
    } else {
      alert('Geolocation not supported');
    }
  };

  return (
    <div className="route-container" style={{ paddingTop: '100px' }}>
      <div className="route-sidebar">
        <div className="route-header">
          <h1>🚗 Safe Route Finder</h1>
          <p>Real roads with flood risk awareness</p>
        </div>

        <div className="route-controls">
          <div className="control-section">
            <h3>📍 Source Location</h3>
            <div className="input-group">
              <input
                type="number"
                placeholder="Latitude"
                value={source.lat}
                onChange={(e) => setSource({ ...source, lat: parseFloat(e.target.value) })}
                step="0.0001"
              />
              <input
                type="number"
                placeholder="Longitude"
                value={source.lon}
                onChange={(e) => setSource({ ...source, lon: parseFloat(e.target.value) })}
                step="0.0001"
              />
              <button onClick={handleUseCurrentLocation} className="location-btn">
                📍 Current Location
              </button>
            </div>
          </div>

          <div className="control-section">
            <h3>📍 Destination Location</h3>
            <div className="input-group">
              <input
                type="number"
                placeholder="Latitude"
                value={destination.lat}
                onChange={(e) =>
                  setDestination({ ...destination, lat: parseFloat(e.target.value) })
                }
                step="0.0001"
              />
              <input
                type="number"
                placeholder="Longitude"
                value={destination.lon}
                onChange={(e) =>
                  setDestination({ ...destination, lon: parseFloat(e.target.value) })
                }
                step="0.0001"
              />
            </div>
          </div>

          {route && (
            <div className="route-info">
              <h3>✓ Route Information</h3>
              <div className="info-item">
                <strong>📏 Distance:</strong> <span>{(route.total_distance / 1000).toFixed(1)} km</span>
              </div>
              <div className="info-item">
                <strong>⚠️ Risk Level:</strong>
                <span className={`risk-badge risk-${route.risk_level}`}>
                  {route.risk_level.toUpperCase()}
                </span>
              </div>
              <div className="info-item">
                <strong>️ Waypoints:</strong> <span>{route.waypoints.length}</span>
              </div>
              <p className="safety-note">
                {route.is_safe
                  ? '✓ This is a safe route'
                  : '⚠ Warning: Route passes through flood-prone areas'}
              </p>
            </div>
          )}
        </div>

        <button
          onClick={handleFindRoute}
          disabled={loading}
          className="find-route-btn"
        >
          {loading ? '⏳ Finding Route...' : '🔍 Find Safe Route'}
        </button>
      </div>

      <div className="route-map" id="map">
        {/* Route Risk Indicator */}
        {route && (
          <div className={`risk-indicator risk-${route.risk_level}`}>
            <div style={{ fontSize: '12px', marginBottom: '4px', opacity: 0.9 }}>
              {route.risk_level === 'high' ? '⚠ HIGH FLOOD RISK' : 
               route.risk_level === 'medium' ? '⚠ MEDIUM FLOOD RISK' : 
               '✓ LOW RISK - SAFE ROUTE'}
            </div>
            <div style={{ fontSize: '11px', marginTop: '4px', borderTop: '1px solid rgba(255,255,255,0.3)', paddingTop: '4px' }}>
              Distance: {(route.total_distance / 1000).toFixed(1)} km<br/>
              Risk Score: {(route.risk_score * 100).toFixed(1)}%<br/>
              Waypoints: {route.waypoints.length}
            </div>
          </div>
        )}
      </div>

      <div className="route-legend">
        <div className="legend-title">🎯 Risk Level Legend</div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#00FF00' }}></div>
          <span>🟢 Low Risk - Safe</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#FFFF00' }}></div>
          <span>🟡 Medium Risk</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#FF0000' }}></div>
          <span>🔴 High Risk - Avoid</span>
        </div>
        <div className="legend-note">
          Route follows real roads from OpenStreetMap OSRM
        </div>
      </div>
    </div>
  );
}

export default Route;
