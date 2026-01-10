import React, { useEffect, useRef, useState } from 'react';
import Squares from './Squares';
import Dock from './Dock';
import ShinyText from './ShinyText';
import { VscHome, VscSearch, VscRefresh, VscGithubInverted } from 'react-icons/vsc';
import { useNavigate } from 'react-router-dom';

function HeatmapView() {
  const navigate = useNavigate();
  const API_BASE = import.meta.env.VITE_API_BASE || window.__API_BASE__ || 'http://127.0.0.1:8000';
  
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const heatLayerRef = useRef(null);
  const selectedLayerRef = useRef(null);

  const [isMapReady, setIsMapReady] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [geojson, setGeojson] = useState(null);
  const [batchResults, setBatchResults] = useState(null);

  const [searchText, setSearchText] = useState('');
  const [selectedWard, setSelectedWard] = useState(null);

  const dockItems = [
    { icon: <VscHome size={24} />, label: 'Home', onClick: () => navigate('/') },
    { icon: <VscSearch size={24} />, label: 'Search', onClick: () => document.getElementById('ward-search-input')?.focus() },
    { icon: <VscRefresh size={24} />, label: 'Refresh', onClick: () => window.location.reload() },
    { icon: <VscGithubInverted size={24} />, label: 'GitHub', onClick: () => window.open('https://github.com/JUGADU-GEEKS/DelhiFlow', '_blank') },
  ];

  /* ---------------- LOAD LEAFLET ---------------- */
  useEffect(() => {
    if (window.L) {
      setIsMapReady(true);
      return;
    }

    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    document.head.appendChild(css);

    const script = document.createElement('script');
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    script.onload = () => {
      const heat = document.createElement('script');
      heat.src = 'https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js';
      heat.onload = () => setIsMapReady(true);
      document.body.appendChild(heat);
    };
    script.onerror = () => setError('Leaflet failed to load');
    document.body.appendChild(script);
  }, []);

  /* ---------------- INIT MAP ---------------- */
  useEffect(() => {
    if (!isMapReady || mapInstanceRef.current) return;

    const L = window.L;
    const map = L.map(mapRef.current).setView([28.6139, 77.2090], 11);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, [isMapReady]);

  /* ---------------- LOAD GEOJSON + HEATMAP ---------------- */
  useEffect(() => {
    if (!isMapReady || !mapInstanceRef.current) return;

    const base = API_BASE?.replace(/\/$/, '') || 'http://127.0.0.1:8000';
    setIsLoading(true);
    setError(null);

    // Fetch GeoJSON first, then batch predictions
    fetch(`${base}/wards/geojson`)
      .then(res => {
        if (!res.ok) throw new Error(`GeoJSON fetch failed: ${res.status} ${res.statusText}`);
        return res.json();
      })
      .then(geo => {
        if (!geo || !geo.features || !Array.isArray(geo.features)) {
          throw new Error('Invalid GeoJSON structure');
        }
        const L = window.L;
        if (!L) throw new Error('Leaflet not available');
        
        // Calculate centroids from GeoJSON features
        const centroids = geo.features.map(f => {
          try {
            const layer = L.geoJSON(f);
            const c = layer.getBounds().getCenter();
            return { 
              latitude: c.lat, 
              longitude: c.lng,
              wardId: f.properties?.Ward_ID || f.properties?.Ward_No || null
            };
          } catch (e) {
            console.warn('Error calculating centroid for feature:', e);
            return null;
          }
        }).filter(c => c !== null);

        if (centroids.length === 0) {
          throw new Error('No valid centroids found in GeoJSON');
        }

        // Request batch predictions
        return fetch(`${base}/predict_ward_batch`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(centroids.map(c => ({ latitude: c.latitude, longitude: c.longitude })))
        }).then(r => {
          if (!r.ok) {
            throw new Error(`Batch prediction API error: ${r.status} ${r.statusText}`);
          }
          return r.json();
        }).then(resp => ({ geo, centroids, resp }));
      })
      .then(({ geo, centroids, resp }) => {
        // Validate response structure
        if (!resp || !resp.results || !Array.isArray(resp.results)) {
          throw new Error('Invalid API response structure');
        }

        // Set GeoJSON and batch results - this will trigger the rendering effect
        setGeojson(geo);
        setBatchResults({ centroids, batchResp: resp });
        
        console.log(`Data loaded: ${resp.results.length} predictions, ${geo.features.length} wards`);
    })
    .catch((err) => {
      console.error('Heatmap loading error:', err);
      setError(`Failed to load heatmap: ${err.message || 'Unknown error'}`);
    })
    .finally(() => {
      setIsLoading(false);
    });
  }, [isMapReady, API_BASE]);

  /* ---------------- BUILD WARD LOOKUP MAP ---------------- */
  // Build comprehensive ward lookup map combining GeoJSON + batch predictions
  const [wardLookupMap, setWardLookupMap] = useState(new Map());

  useEffect(() => {
    if (!geojson || !batchResults) {
      setWardLookupMap(new Map());
      return;
    }

    const resp = batchResults.batchResp;
    const centroids = batchResults.centroids;
    
    if (!resp || !resp.results || !Array.isArray(resp.results) || !centroids) {
      return;
    }

    // Build comprehensive ward lookup map: { wardNumber: { wardName, wardNumber, riskValue, riskLevel, lat, lng } }
    const lookup = new Map();
    
    // First, index GeoJSON features by normalized ward number
    const geoJsonMap = new Map();
    geojson.features.forEach((feature, idx) => {
      const props = feature.properties || {};
      let wardId = props.Ward_ID !== undefined ? props.Ward_ID : props.Ward_No;
      
      if (wardId != null && wardId !== undefined) {
        // Normalize to string for consistent lookup
        const wardNumberStr = String(wardId).trim();
        const wardNumberNum = parseInt(wardId, 10);
        
        // Get centroid for this feature
        let centroid = centroids.find(c => {
          const cWardId = c.wardId;
          return cWardId == wardId || String(cWardId) === String(wardId);
        });
        
        if (!centroid && idx < centroids.length) {
          centroid = centroids[idx];
        }
        
        if (centroid) {
          geoJsonMap.set(wardNumberStr, {
            feature,
            centroid,
            wardId: wardId,
            wardNumberStr,
            wardNumberNum: isNaN(wardNumberNum) ? null : wardNumberNum
          });
          // Also index by numeric value if valid
          if (!isNaN(wardNumberNum)) {
            geoJsonMap.set(wardNumberNum, {
              feature,
              centroid,
              wardId: wardId,
              wardNumberStr,
              wardNumberNum
            });
          }
        }
      }
    });

    // Now merge with batch prediction results
    resp.results.forEach(result => {
      if (result.error) return;

      const wardId = result.Ward_ID;
      if (wardId == null || wardId === undefined) return;

      // Normalize ward ID to string and number
      const wardNumberStr = String(wardId).trim();
      const wardNumberNum = parseInt(wardId, 10);
      const isValidNum = !isNaN(wardNumberNum) && wardNumberNum > 0;

      // Find matching GeoJSON data
      let geoData = geoJsonMap.get(wardNumberStr);
      if (!geoData && isValidNum) {
        geoData = geoJsonMap.get(wardNumberNum);
      }
      if (!geoData && isValidNum) {
        geoData = geoJsonMap.get(String(wardNumberNum));
      }

      if (!geoData) {
        console.warn(`No GeoJSON data found for Ward_ID: ${wardId}`);
        return;
      }

      const { feature, centroid } = geoData;
      const props = feature.properties || {};
      const wardName = props.Ward_Name || `Ward ${wardId}`;
      
      // Get risk values
      let riskValue = result.Flood_Risk_Score;
      const riskLevel = result.Flood_Risk_Class || 'Unknown';
      
      // Normalize risk value - convert to 0-1 scale
      if (riskValue == null || riskValue === undefined || isNaN(riskValue)) {
        // Fallback based on risk class
        if (riskLevel === 'High') riskValue = 0.85;
        else if (riskLevel === 'Medium') riskValue = 0.5;
        else if (riskLevel === 'Low') riskValue = 0.15;
        else riskValue = 0.3;
      } else {
        riskValue = parseFloat(riskValue);
        // Ensure value is in reasonable range
        riskValue = Math.max(0.05, Math.min(1.0, riskValue));
      }

      // Store in lookup map with multiple keys for flexible search
      const wardData = {
        wardName,
        wardNumber: wardNumberStr,
        wardNumberNum: isValidNum ? wardNumberNum : null,
        riskValue,
        riskLevel,
        lat: centroid.latitude,
        lng: centroid.longitude,
        feature,
        result
      };

      // Store by string key
      lookup.set(wardNumberStr, wardData);
      // Store by numeric key if valid
      if (isValidNum) {
        lookup.set(wardNumberNum, wardData);
      }
      // Store by original ID
      lookup.set(wardId, wardData);
    });

    setWardLookupMap(lookup);
    console.log(`Built ward lookup map with ${lookup.size} entries`);
  }, [geojson, batchResults]);

  /* ---------------- UPDATE HEATMAP WHEN DATA CHANGES ---------------- */
  // Render heatmap ONLY after:
  // 1. GeoJSON is fully loaded (via wardLookupMap which depends on geojson)
  // 2. Bulk prediction data is ready (via wardLookupMap which depends on batchResults)
  // 3. Map instance is ready (isMapReady && mapInstanceRef.current)
  // This ensures we NEVER render with empty data
  useEffect(() => {
    // Guard: Only proceed if ALL conditions are met
    if (!isMapReady || !mapInstanceRef.current || wardLookupMap.size === 0) {
      if (isMapReady && mapInstanceRef.current && wardLookupMap.size === 0) {
        console.log('Waiting for ward lookup map to be built from GeoJSON and batch predictions...');
      }
      return;
    }
    
    console.log(`Rendering heatmap with ${wardLookupMap.size} wards...`);

    // Build heatmap points array: [latitude, longitude, intensity]
    // Use Set to track processed wards to avoid duplicates
    const processedWards = new Set();
    const points = [];
    const intensities = [];

    // Collect all valid points and intensities for normalization
    // Only process each unique ward once (avoid duplicates from multiple map keys)
    wardLookupMap.forEach((wardData, key) => {
      // Use ward number as unique identifier
      const wardKey = wardData.wardNumberNum !== null 
        ? `num_${wardData.wardNumberNum}` 
        : `str_${wardData.wardNumber}`;
      
      // Only process if not already seen
      if (!processedWards.has(wardKey)) {
        processedWards.add(wardKey);
        
        const intensity = wardData.riskValue;
        if (intensity > 0 && !isNaN(intensity) && !isNaN(wardData.lat) && !isNaN(wardData.lng)) {
          points.push([wardData.lat, wardData.lng, intensity]);
          intensities.push(intensity);
        }
      }
    });

    // Normalize intensities for stronger visual output
    // Scale to ensure full range 0-1 is used for maximum visibility
    if (intensities.length > 0) {
      const minIntensity = Math.min(...intensities);
      const maxIntensity = Math.max(...intensities);
      const range = maxIntensity - minIntensity || 1; // Avoid division by zero
      
      // Normalize intensities to 0-1 scale with STRONG visual output
      // Convert model output (probability/score) into visual range 0-1
      console.log(`Intensity normalization: min=${minIntensity.toFixed(3)}, max=${maxIntensity.toFixed(3)}, range=${range.toFixed(3)}`);
      
      const normalizedPoints = points.map(([lat, lng, intensity]) => {
        // Step 1: Min-max normalization: (value - min) / range
        let normalized = range > 0 ? (intensity - minIntensity) / range : intensity;
        
        // Step 2: Ensure we're working with a valid number
        normalized = parseFloat(normalized);
        if (isNaN(normalized) || normalized <= 0) {
          normalized = 0.5; // Default visible value for invalid data
        }
        
        // Step 3: Apply contrast enhancement for stronger visual output
        // Use a power curve to enhance differences (values closer to 1 get boosted more)
        normalized = Math.pow(normalized, 0.75); // Exponential curve for better contrast
        
        // Step 4: Scale to ensure minimum visibility (0.35-1.0 range)
        // This prevents faint rendering while maintaining full range
        normalized = normalized * 0.65 + 0.35; // Scale: [0-1] -> [0.35-1.0]
        
        // Step 5: Final validation and clamping
        normalized = Math.max(0.35, Math.min(1.0, normalized));
        
        // Ensure format is exactly: [latitude, longitude, intensity] with intensity > 0
        return [lat, lng, normalized];
      });

      // Calculate explicit max value for heatLayer (should be 1.0 after normalization)
      const heatMapMax = Math.max(...normalizedPoints.map(p => p[2]), 1.0);
      
      // Validate all points have correct format: [latitude, longitude, intensity]
      const validPoints = normalizedPoints.filter(p => {
        return Array.isArray(p) && 
               p.length === 3 && 
               typeof p[0] === 'number' && !isNaN(p[0]) && // latitude
               typeof p[1] === 'number' && !isNaN(p[1]) && // longitude
               typeof p[2] === 'number' && !isNaN(p[2]) && p[2] > 0; // intensity > 0
      });
      
      if (validPoints.length === 0) {
        console.warn('No valid points after normalization and validation');
        return;
      }

      // Render heatmap only if we have valid points AND map is ready
      if (validPoints.length > 0 && mapInstanceRef.current) {
        // Remove existing layer if present
        if (heatLayerRef.current) {
          try {
            mapInstanceRef.current.removeLayer(heatLayerRef.current);
          } catch (e) {
            console.warn('Error removing existing heat layer:', e);
          }
          heatLayerRef.current = null;
        }

        // Create heat layer with STRONG, VISIBLE configuration
        try {
          const L = window.L;
          if (!L || !L.heatLayer) {
            throw new Error('Leaflet.heat plugin not available');
          }

          // Explicitly configure heatmap with strong defaults for maximum visibility
          heatLayerRef.current = L.heatLayer(validPoints, {
            radius: 50,          // Larger radius (50) for better coverage and visibility
            blur: 30,            // Adequate blur (30) for smooth transitions
            maxZoom: 18,         // Proper max zoom for detailed rendering
            max: heatMapMax,     // Explicit max value to ensure full color range is used
            gradient: {          // Clear gradient: Low → Medium → High risk
              0.0: 'blue',       // Low risk: Blue
              0.25: 'cyan',      // Low-Medium: Cyan
              0.5: 'lime',       // Medium: Lime green
              0.65: 'yellow',    // Medium-High: Yellow
              0.8: 'orange',     // High: Orange
              1.0: 'red'         // Very High: Red
            },
            minOpacity: 0.3      // Ensure minimum opacity for visibility
          }).addTo(mapInstanceRef.current);
          
          console.log(`✅ Heatmap rendered with ${validPoints.length} valid points`);
          console.log(`   Original intensity range: ${minIntensity.toFixed(3)} - ${maxIntensity.toFixed(3)}`);
          console.log(`   Normalized max: ${heatMapMax.toFixed(3)}`);
          console.log(`   Configuration: radius=50, blur=30, maxZoom=18, max=${heatMapMax.toFixed(3)}`);
          setError(null); // Clear any previous errors
        } catch (e) {
          console.error('❌ Error creating heat layer:', e);
          setError(`Failed to render heatmap: ${e.message}`);
        }
      } else {
        if (validPoints.length === 0) {
          console.warn('⚠️ No valid heatmap points found after normalization and validation.');
          setError('No valid heatmap data points found.');
        } else if (!mapInstanceRef.current) {
          console.warn('⚠️ Map instance not available for heatmap rendering.');
        }
      }
    } else {
      console.warn('No intensities found for normalization.');
    }
  }, [isMapReady, wardLookupMap]);

  /* ---------------- SEARCH WARD ---------------- */
  const handleSearch = () => {
    if (!searchText || wardLookupMap.size === 0) {
      setSelectedWard({ error: 'Please enter a ward number or name' });
      return;
    }

    // Normalize search input: trim whitespace, convert to string
    const normalizedInput = String(searchText).trim();
    if (normalizedInput.length === 0) {
      setSelectedWard({ error: 'Please enter a ward number or name' });
      return;
    }

    const searchLower = normalizedInput.toLowerCase();
    
    // Try to parse as number for ward ID search
    const searchNumber = parseInt(normalizedInput, 10);
    const isNumericSearch = !isNaN(searchNumber) && searchNumber > 0;

    // Search in ward lookup map
    let foundWard = null;

    // First try: Exact numeric match
    if (isNumericSearch) {
      foundWard = wardLookupMap.get(searchNumber);
      if (!foundWard) {
        // Try string version of number
        foundWard = wardLookupMap.get(String(searchNumber));
      }
    }

    // Second try: Exact string match
    if (!foundWard) {
      foundWard = wardLookupMap.get(normalizedInput);
    }

    // Third try: Case-insensitive name match
    if (!foundWard) {
      for (const [key, wardData] of wardLookupMap.entries()) {
        // Only check each unique ward once (avoid duplicates)
        if (wardData.wardNumberNum !== null && key === wardData.wardNumberNum) {
          const wardNameLower = String(wardData.wardName || '').toLowerCase();
          if (wardNameLower.includes(searchLower)) {
            foundWard = wardData;
            break;
          }
        } else if (wardData.wardNumberNum === null && typeof key === 'string') {
          const wardNameLower = String(wardData.wardName || '').toLowerCase();
          if (wardNameLower.includes(searchLower)) {
            foundWard = wardData;
            break;
          }
        }
      }
    }

    // Fourth try: Partial ward number match
    if (!foundWard && isNumericSearch) {
      for (const [key, wardData] of wardLookupMap.entries()) {
        if (wardData.wardNumberNum === searchNumber || 
            String(wardData.wardNumber || '').includes(normalizedInput)) {
          foundWard = wardData;
          break;
        }
      }
    }

    if (!foundWard) {
      setSelectedWard({ 
        error: `Ward not found: "${normalizedInput}". Try searching by ward number (e.g., "44") or ward name.` 
      });
      // Remove any existing selection layer
      if (selectedLayerRef.current && mapInstanceRef.current) {
        try {
          mapInstanceRef.current.removeLayer(selectedLayerRef.current);
        } catch (e) {
          console.warn('Error removing selection layer:', e);
        }
        selectedLayerRef.current = null;
      }
      return;
    }

    // Remove existing selection layer
    if (selectedLayerRef.current && mapInstanceRef.current) {
      try {
        mapInstanceRef.current.removeLayer(selectedLayerRef.current);
      } catch (e) {
        console.warn('Error removing existing selection layer:', e);
      }
      selectedLayerRef.current = null;
    }

    // Add new selection layer for the matched ward
    try {
      const L = window.L;
      if (!L || !mapInstanceRef.current) {
        throw new Error('Map not ready');
      }

      selectedLayerRef.current = L.geoJSON(foundWard.feature, {
        style: { 
          color: '#ffffff', 
          weight: 4, 
          fillColor: '#9333EA', 
          fillOpacity: 0.2 
        }
      }).addTo(mapInstanceRef.current);

      // Zoom to selected ward
      const bounds = selectedLayerRef.current.getBounds();
      mapInstanceRef.current.fitBounds(bounds, { padding: [50, 50] });
    } catch (e) {
      console.error('Error adding selection layer:', e);
    }

    // Display risk analysis using data from lookup map
    setSelectedWard({
      Ward_ID: foundWard.wardNumberNum !== null ? foundWard.wardNumberNum : foundWard.wardNumber,
      Ward_Name: foundWard.wardName,
      Flood_Risk_Score: foundWard.riskValue,
      Flood_Risk_Class: foundWard.riskLevel
    });
    
    console.log(`Found ward: ${foundWard.wardName} (ID: ${foundWard.wardNumber}) with risk: ${foundWard.riskLevel} (${foundWard.riskValue})`);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const getRiskColor = (risk) => {
    if (!risk) return 'from-purple-400 to-fuchsia-500';
    switch(risk.toLowerCase()) {
      case 'high': return 'from-red-400 to-rose-600';
      case 'medium': return 'from-yellow-400 to-orange-500';
      case 'low': return 'from-green-400 to-emerald-500';
      default: return 'from-purple-400 to-fuchsia-500';
    }
  };

  const getRiskBorderColor = (risk) => {
    if (!risk) return 'border-purple-400/30';
    switch(risk.toLowerCase()) {
      case 'high': return 'border-red-400/50';
      case 'medium': return 'border-yellow-400/50';
      case 'low': return 'border-green-400/50';
      default: return 'border-purple-400/30';
    }
  };

  return (
    <div className="relative w-full min-h-screen overflow-x-hidden overflow-y-auto font-['Poppins',sans-serif]" style={{ background: '#000000' }}>
      {/* Squares background */}
      <div className="absolute inset-0 z-0">
        <Squares
          speed={0.6}
          squareSize={40}
          direction='diagonal'
          borderColor='#9a69b5'
          hoverFillColor='#222222'
        />
      </div>

      {/* Dock Navigation */}
      <div className="fixed top-0 left-0 right-0 z-50 flex justify-center pt-4">
        <Dock 
          items={dockItems}
          panelHeight={68}
          baseItemSize={50}
          magnification={70}
          className="bg-purple-900/20 backdrop-blur-xl"
        />
      </div>

      {/* Main Content */}
      <div className="relative z-10 px-4 py-24 max-w-7xl mx-auto">
        
        {/* Page Header */}
        <div className="text-center mb-12 mt-8">
          <ShinyText
            text="Flood Risk Heatmap"
            disabled={false}
            speed={3}
            className="text-5xl md:text-6xl lg:text-7xl font-bold leading-tight mb-6"
          />
          <p className="text-white/80 text-lg md:text-xl leading-relaxed max-w-3xl mx-auto font-light">
            Visualize flood risk intensity across all Delhi wards. Search below to analyze specific ward risks.
          </p>
        </div>

        {/* Heatmap Hero Section */}
        <div className="mb-12">
          <div className="bg-purple-900/20 backdrop-blur-xl border border-purple-400/30 rounded-3xl p-6 md:p-8 shadow-2xl shadow-purple-900/20">
            <div className="relative w-full" style={{ height: '600px', minHeight: '600px' }}>
              <div
                ref={mapRef}
                className="w-full h-full rounded-2xl border border-purple-400/20 overflow-hidden"
                style={{ borderRadius: '1rem' }}
              />

              {/* Loading Overlay */}
              {isLoading && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-2xl z-10 backdrop-blur-sm">
                  <div className="text-center">
                    <div className="animate-spin h-10 w-10 border-4 border-purple-400 border-t-transparent rounded-full mx-auto mb-4"></div>
                    <p className="text-white/80 text-sm font-light">Loading heatmap data...</p>
                  </div>
        </div>
      )}

              {/* Error Overlay */}
      {error && (
                <div className="absolute inset-0 flex items-center justify-center bg-red-900/30 backdrop-blur-sm rounded-2xl z-10 border border-red-400/30">
                  <div className="text-center p-6">
                    <svg className="w-12 h-12 text-red-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <p className="text-red-300 font-medium mb-2">Error Loading Heatmap</p>
                    <p className="text-red-300/70 text-sm">{error}</p>
                  </div>
                </div>
              )}

              {/* Map Not Ready Overlay */}
              {!isMapReady && !error && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-2xl z-10">
                  <div className="text-center">
                    <div className="animate-spin h-8 w-8 border-4 border-purple-400 border-t-transparent rounded-full mx-auto mb-2"></div>
                    <p className="text-white/60 text-sm">Initializing map...</p>
                  </div>
                </div>
              )}

              {/* Heatmap Legend */}
              {!isLoading && !error && isMapReady && (
                <div className="absolute bottom-6 left-6 bg-purple-900/40 backdrop-blur-md border border-purple-400/30 rounded-xl p-4 shadow-lg z-20">
                  <p className="text-white font-semibold text-sm mb-3">Risk Intensity</p>
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded bg-gradient-to-r from-blue-500 to-cyan-500"></div>
                      <span className="text-white/80 text-xs">Low Risk</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded bg-gradient-to-r from-lime-500 to-yellow-500"></div>
                      <span className="text-white/80 text-xs">Medium Risk</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded bg-gradient-to-r from-orange-500 to-red-500"></div>
                      <span className="text-white/80 text-xs">High Risk</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Ward Search & Analysis Section */}
        <div className="bg-purple-900/20 backdrop-blur-xl border border-purple-400/30 rounded-3xl p-8 shadow-2xl shadow-purple-900/20">
          <h2 className="text-white text-2xl font-bold mb-6 flex items-center gap-3">
            <div className="bg-gradient-to-br from-purple-400 to-fuchsia-500 w-10 h-10 rounded-xl flex items-center justify-center shadow-lg shadow-purple-500/30">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            Ward Risk Analysis
          </h2>

          {/* Search Input */}
          <div className="mb-6">
            <div className="flex gap-3">
              <input
                id="ward-search-input"
                type="text"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Search by ward number or name (e.g., '5' or 'Ward 5')"
                className="flex-1 bg-black/30 border border-purple-400/30 rounded-xl px-4 py-3 text-white placeholder-white/50 focus:outline-none focus:border-purple-400/50 focus:ring-2 focus:ring-purple-400/20 transition-all duration-200"
              />
              <button
                onClick={handleSearch}
                disabled={isLoading || !geojson || !batchResults}
                className="bg-gradient-to-r from-purple-500 to-fuchsia-600 text-white px-6 py-3 rounded-xl font-semibold hover:from-purple-600 hover:to-fuchsia-700 hover:scale-105 transition-all duration-200 shadow-lg shadow-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 flex items-center gap-2"
              >
                <VscSearch size={20} />
                Search
              </button>
            </div>
          </div>

          {/* Ward Analysis Results */}
          {selectedWard && (
            <div className="mt-6">
              {selectedWard.error ? (
                <div className="bg-red-500/10 border border-red-400/30 rounded-2xl p-6">
                  <div className="flex items-start gap-3">
                    <svg className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <div>
                      <p className="text-red-300 font-medium mb-1">Search Error</p>
                      <p className="text-red-300/70 text-sm">{selectedWard.error}</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className={`bg-purple-900/30 backdrop-blur-md border ${getRiskBorderColor(selectedWard.Flood_Risk_Class)} rounded-2xl p-6 shadow-lg transition-all duration-500`}>
                  <div className="space-y-6">
                    {/* Ward Info Header */}
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-white/70 text-sm font-medium mb-1">Ward Name</p>
                        <p className="text-white text-xl font-bold">{selectedWard.Ward_Name || `Ward ${selectedWard.Ward_ID}`}</p>
                        <p className="text-white/60 text-sm mt-1">Ward ID: {selectedWard.Ward_ID}</p>
                      </div>
                      {selectedWard.Flood_Risk_Class && (
                        <div className={`bg-gradient-to-r ${getRiskColor(selectedWard.Flood_Risk_Class)} text-white text-lg font-bold py-2 px-4 rounded-xl shadow-lg uppercase tracking-wider`}>
                          {selectedWard.Flood_Risk_Class}
                        </div>
                      )}
                    </div>

                    {/* Risk Score */}
                    {selectedWard.Flood_Risk_Score !== undefined && selectedWard.Flood_Risk_Score !== null && (
                      <div className="bg-black/30 rounded-xl p-5 border border-purple-400/20">
                        <div className="flex justify-between items-center mb-3">
                          <span className="text-white/70 text-sm font-medium">Risk Probability</span>
                          <span className="text-white font-bold text-xl">{Math.round(selectedWard.Flood_Risk_Score * 100)}%</span>
                        </div>
                        <div className="w-full bg-black/50 rounded-full h-3 overflow-hidden">
                          <div 
                            className={`bg-gradient-to-r ${getRiskColor(selectedWard.Flood_Risk_Class)} h-full rounded-full transition-all duration-1000 ease-out`}
                            style={{ width: `${Math.round(selectedWard.Flood_Risk_Score * 100)}%` }}
                          ></div>
                        </div>
                      </div>
                    )}

                    {/* Risk Category Details */}
                    {selectedWard.Flood_Risk_Class && (
                      <div className="bg-black/30 rounded-xl p-5 border border-purple-400/20">
                        <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          Risk Assessment
                        </h3>
                        <p className="text-white/70 text-sm leading-relaxed font-light">
                          {selectedWard.Flood_Risk_Class === 'Low' && "This ward has minimal flood risk based on current conditions. Normal activities can proceed, but stay aware of weather updates."}
                          {selectedWard.Flood_Risk_Class === 'Medium' && "This ward has moderate flood risk. Monitor weather conditions closely and prepare for potential water accumulation in low-lying areas."}
                          {selectedWard.Flood_Risk_Class === 'High' && "⚠️ High flood risk detected! Take immediate precautions, avoid low-lying areas, and follow local emergency guidelines. Stay informed with latest updates."}
                        </p>
                      </div>
                    )}

                    {/* High Risk Alert */}
                    {selectedWard.Flood_Risk_Class === 'High' && (
                      <div className="bg-red-500/10 border border-red-400/30 rounded-xl p-4 flex items-start gap-3 animate-pulse">
                        <svg className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        <p className="text-red-300 text-sm font-medium">Emergency Alert: High flood risk conditions detected in this ward. Stay safe and follow local emergency protocols.</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Empty State */}
          {!selectedWard && (
            <div className="text-center py-12">
              <div className="bg-gradient-to-br from-purple-400 to-fuchsia-500 w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg shadow-purple-500/30">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <p className="text-white/60 font-light mb-2">Search for a ward to view detailed risk analysis</p>
              <p className="text-white/40 text-sm font-light">Enter a ward number or name in the search field above</p>
            </div>
          )}
        </div>

        {/* Know Your WARD Button Section */}
        <div className="mt-8 flex justify-end">
          <button
            onClick={() => navigate('/know-your-ward')}
            className="bg-gradient-to-r from-purple-500 to-fuchsia-600 text-white px-8 py-4 rounded-xl font-semibold hover:from-purple-600 hover:to-fuchsia-700 hover:scale-105 transition-all duration-200 shadow-lg shadow-purple-500/30 flex items-center gap-3"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Know Your WARD
          </button>
        </div>
      </div>
    </div>
  );
}

export default HeatmapView;
