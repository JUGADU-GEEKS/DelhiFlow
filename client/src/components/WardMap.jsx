import React, { useEffect, useRef, useState } from 'react';

/**
 * WardMap component displays Delhi wards on a map and highlights the detected ward.
 * Uses Leaflet library loaded via CDN.
 */
function WardMap({ latitude, longitude, detectedWardId, wardName, floodRiskClass, API_BASE, showHeatmap = true }) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const layersRef = useRef({});
  const [isMapReady, setIsMapReady] = useState(false);
  const [error, setError] = useState(null);
  const [heatmapData, setHeatmapData] = useState(null);
  const [isHeatmapLoading, setIsHeatmapLoading] = useState(false);

  // Helper function to get risk color
  const getRiskColor = (risk) => {
    if (!risk) return '#9333EA'; // default purple
    switch (risk.toLowerCase()) {
      case 'high':
        return '#EF4444'; // red
      case 'medium':
        return '#F59E0B'; // yellow/orange
      case 'low':
        return '#10B981'; // green
      default:
        return '#9333EA'; // purple
    }
  };

  // Load Leaflet CSS and JS, and Leaflet.heat plugin
  useEffect(() => {
    // Check if already loaded
    if (window.L && document.querySelector('link[href*="leaflet"]')) {
      setIsMapReady(true);
      return;
    }

    // Load Leaflet CSS
    if (!document.querySelector('link[href*="leaflet"]')) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      link.integrity = 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=';
      link.crossOrigin = '';
      document.head.appendChild(link);
    }

    // Load Leaflet JS
    if (!window.L) {
      const script = document.createElement('script');
      script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      script.integrity = 'sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=';
      script.crossOrigin = '';
      script.onload = () => {
        // Load Leaflet.heat plugin after Leaflet is loaded
        const heatScript = document.createElement('script');
        heatScript.src = 'https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js';
        heatScript.crossOrigin = '';
        heatScript.onload = () => {
          setIsMapReady(true);
        };
        heatScript.onerror = () => {
          console.warn('Leaflet.heat plugin failed to load, heatmap will be disabled');
          setIsMapReady(true); // Still allow map to work without heatmap
        };
        document.body.appendChild(heatScript);
      };
      script.onerror = () => {
        setError('Failed to load Leaflet map library');
      };
      document.body.appendChild(script);
    } else {
      // Leaflet already loaded, check for heat plugin
      if (!window.L.heatLayer) {
        const heatScript = document.createElement('script');
        heatScript.src = 'https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js';
        heatScript.crossOrigin = '';
        heatScript.onload = () => {
          setIsMapReady(true);
        };
        heatScript.onerror = () => {
          console.warn('Leaflet.heat plugin failed to load, heatmap will be disabled');
          setIsMapReady(true);
        };
        document.body.appendChild(heatScript);
      } else {
        setIsMapReady(true);
      }
    }

    // Cleanup function - be careful not to remove if other components use it
    return () => {
      // Don't remove if other components might be using Leaflet
      // The cleanup is minimal to avoid breaking other potential uses
    };
  }, []);

  // Initialize map and load wards
  useEffect(() => {
    if (!isMapReady || !mapRef.current || mapInstanceRef.current) return;

    const L = window.L;
    if (!L) return;

    try {
      // Clean up any existing map instance
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }

      // Initialize map centered on Delhi
      const delhiCenter = [28.6139, 77.2090];
      const map = L.map(mapRef.current).setView(delhiCenter, 11);

      // Add tile layer
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
      }).addTo(map);

      mapInstanceRef.current = map;

      // Load ward GeoJSON
      const base = API_BASE?.replace(/\/$/, '') || 'http://127.0.0.1:8000';
      fetch(`${base}/wards/geojson`)
        .then(response => {
          if (!response.ok) {
            return response.text().then(text => {
              let errorDetail = text;
              try {
                const jsonError = JSON.parse(text);
                errorDetail = jsonError.detail?.error || jsonError.detail || text;
              } catch (e) {
                // Keep original text if not JSON
              }
              throw new Error(`Failed to load wards: ${response.status} - ${errorDetail}`);
            });
          }
          return response.json();
        })
        .then(geojson => {
          if (!geojson || !geojson.features || geojson.features.length === 0) {
            throw new Error('No ward features found in GeoJSON');
          }
          // Add all wards to map
          const wardLayer = L.geoJSON(geojson, {
            style: (feature) => {
              const props = feature.properties || {};
              const wardId = props.Ward_ID !== undefined ? props.Ward_ID : props.Ward_No;
              const isDetectedWard = wardId !== undefined && wardId === detectedWardId;
              return {
                fillColor: isDetectedWard 
                  ? getRiskColor(floodRiskClass)
                  : '#6B7280', // gray for non-detected wards
                color: isDetectedWard 
                  ? '#FFFFFF' // white border for detected ward
                  : '#374151', // darker gray border
                weight: isDetectedWard ? 3 : 1,
                opacity: isDetectedWard ? 1 : 0.6,
                fillOpacity: isDetectedWard ? 0.7 : 0.3
              };
            },
            onEachFeature: (feature, layer) => {
              const props = feature.properties || {};
              const wardId = props.Ward_ID !== undefined ? props.Ward_ID : props.Ward_No;
              const name = props.Ward_Name || `Ward ${wardId || 'Unknown'}`;
              const popupContent = `
                <div style="font-family: 'Poppins', sans-serif;">
                  <strong>${name}</strong><br/>
                  Ward ID: ${wardId || 'Unknown'}
                  ${detectedWardId !== null && detectedWardId !== undefined && wardId === detectedWardId && floodRiskClass ? 
                    `<br/><strong>Flood Risk: ${floodRiskClass}</strong>` : ''}
                </div>
              `;
              layer.bindPopup(popupContent);
            }
          }).addTo(map);

          layersRef.current.wards = wardLayer;

          // If we have a detected ward, zoom to it and highlight it
          if (detectedWardId !== null && detectedWardId !== undefined) {
            const detectedFeature = geojson.features.find(f => {
              const props = f.properties || {};
              const wardId = props.Ward_ID !== undefined ? props.Ward_ID : props.Ward_No;
              return wardId === detectedWardId;
            });
            if (detectedFeature) {
              const bounds = L.geoJSON(detectedFeature).getBounds();
              map.fitBounds(bounds, { padding: [50, 50] });
            }
          }

          // If we have user location, add a marker
          if (latitude && longitude) {
            const userMarker = L.marker([latitude, longitude], {
              icon: L.divIcon({
                className: 'user-location-marker',
                html: '<div style="background: #EF4444; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 10px rgba(0,0,0,0.5);"></div>',
                iconSize: [16, 16],
                iconAnchor: [8, 8]
              })
            }).addTo(map);
            userMarker.bindPopup('<strong>Your Location</strong>').openPopup();
            layersRef.current.userMarker = userMarker;
          }
        })
        .catch(err => {
          console.error('Error loading wards:', err);
          setError(`Failed to load ward data: ${err.message}`);
        });
    } catch (err) {
      console.error('Error initializing map:', err);
      setError(`Map initialization failed: ${err.message}`);
    }

    return () => {
      // Only cleanup if component is unmounting
      // Don't cleanup on prop changes to avoid re-rendering
      if (mapInstanceRef.current) {
        try {
          mapInstanceRef.current.remove();
        } catch (e) {
          console.warn('Error removing map:', e);
        }
        mapInstanceRef.current = null;
      }
      layersRef.current = {};
    };
  }, [isMapReady, API_BASE]); // Only re-run when map becomes ready or API_BASE changes

  // Load heatmap data
  useEffect(() => {
    if (!showHeatmap || !isMapReady) return;

    const base = API_BASE?.replace(/\/$/, '') || 'http://127.0.0.1:8000';
    setIsHeatmapLoading(true);
    
    fetch(`${base}/heatmap/ward_risk`)
      .then(response => {
        if (!response.ok) {
          throw new Error(`Failed to load heatmap data: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        if (data && data.heatmap_data && Array.isArray(data.heatmap_data)) {
          setHeatmapData(data.heatmap_data);
        }
      })
      .catch(err => {
        console.error('Error loading heatmap data:', err);
        // Don't set error state - heatmap is optional
      })
      .finally(() => {
        setIsHeatmapLoading(false);
      });
  }, [isMapReady, showHeatmap, API_BASE]);

  // Add heatmap layer to map
  useEffect(() => {
    if (!mapInstanceRef.current || !heatmapData || !window.L || !window.L.heatLayer) return;

    const L = window.L;

    // Remove existing heatmap layer if present
    if (layersRef.current.heatmap) {
      try {
        mapInstanceRef.current.removeLayer(layersRef.current.heatmap);
      } catch (e) {
        console.warn('Error removing existing heatmap:', e);
      }
    }

    // Convert heatmap data to format expected by leaflet.heat
    // Format: [[lat, lng, intensity], ...]
    const heatmapPoints = heatmapData.map(point => [point[0], point[1], point[2]]);

    // Find intensity range for gradient
    const intensities = heatmapData.map(p => p[2]);
    const minIntensity = Math.min(...intensities);
    const maxIntensity = Math.max(...intensities);

    // Create heatmap layer with gradient based on risk intensity
    // Higher intensity = higher risk = red/orange colors
    // Lower intensity = lower risk = yellow/green colors
    try {
      const heatmapLayer = L.heatLayer(heatmapPoints, {
        radius: 35, // Radius of heat point (adjust based on zoom)
        blur: 30,   // Blur factor for smooth gradient
        maxZoom: 17,
        max: maxIntensity, // Normalize to max intensity
        gradient: {
          // Color gradient: blue/green (low) -> yellow -> orange -> red (high)
          0.0: 'blue',      // Very low risk
          0.25: 'cyan',     // Low risk
          0.5: 'lime',      // Medium-low risk
          0.65: 'yellow',   // Medium risk
          0.8: 'orange',    // Medium-high risk
          1.0: 'red'        // High risk
        },
        minOpacity: 0.4,    // Minimum opacity (semi-transparent)
        maxOpacity: 0.8     // Maximum opacity (more visible for high risk)
      });

      // Add to map (as overlay, on top of ward polygons)
      heatmapLayer.addTo(mapInstanceRef.current);
      layersRef.current.heatmap = heatmapLayer;
    } catch (e) {
      console.error('Error creating heatmap layer:', e);
    }
  }, [heatmapData, isMapReady]); // Re-run when heatmap data changes or map becomes ready

  // Update map when ward detection changes
  useEffect(() => {
    if (!mapInstanceRef.current || !layersRef.current.wards) return;

    const L = window.L;
    if (!L) return;

    // Update ward styling based on detected ward
    const wardLayer = layersRef.current.wards;
    wardLayer.eachLayer((layer) => {
      const feature = layer.feature;
      if (feature) {
        const props = feature.properties || {};
        const wardId = props.Ward_ID !== undefined ? props.Ward_ID : props.Ward_No;
        const isDetectedWard = wardId !== undefined && wardId === detectedWardId;

        layer.setStyle({
          fillColor: isDetectedWard 
            ? getRiskColor(floodRiskClass)
            : '#6B7280',
          color: isDetectedWard 
            ? '#FFFFFF'
            : '#374151',
          weight: isDetectedWard ? 3 : 1,
          opacity: isDetectedWard ? 1 : 0.6,
          fillOpacity: isDetectedWard ? 0.7 : 0.3
        });
      }
    });

    // Zoom to detected ward if available
    if (detectedWardId !== null && detectedWardId !== undefined && wardLayer) {
      wardLayer.eachLayer((layer) => {
        const feature = layer.feature;
        if (feature) {
          const props = feature.properties || {};
          const wardId = props.Ward_ID !== undefined ? props.Ward_ID : props.Ward_No;
          if (wardId === detectedWardId) {
            const bounds = layer.getBounds();
            mapInstanceRef.current.fitBounds(bounds, { padding: [50, 50] });
          }
        }
      });
    }
  }, [detectedWardId, floodRiskClass]);

  if (error) {
    return (
      <div className="w-full h-full bg-black/30 border border-red-400/30 rounded-2xl flex items-center justify-center p-8">
        <div className="text-center">
          <p className="text-red-300 text-sm mb-2">Map Error</p>
          <p className="text-red-300/70 text-xs">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      <div
        ref={mapRef}
        style={{
          width: '100%',
          height: '100%',
          minHeight: '500px',
          borderRadius: '1rem',
          zIndex: 1
        }}
        className="border border-purple-400/30"
      />
      {!isMapReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-2xl z-10">
          <div className="text-center">
            <div className="animate-spin h-8 w-8 border-4 border-purple-400 border-t-transparent rounded-full mx-auto mb-2"></div>
            <p className="text-white/60 text-sm">Loading map...</p>
          </div>
        </div>
      )}
      {isHeatmapLoading && isMapReady && (
        <div className="absolute top-4 right-4 bg-purple-900/90 backdrop-blur-sm border border-purple-400/30 rounded-lg px-3 py-2 z-20 shadow-lg">
          <p className="text-white/80 text-xs flex items-center gap-2">
            <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Generating heatmap...
          </p>
        </div>
      )}
    </div>
  );
}

export default WardMap;

