import React, { useEffect, useRef, useState } from 'react';
import Squares from './Squares';
import ShinyText from './ShinyText';

function HeatmapView() {
  const API_BASE = import.meta.env.VITE_API_BASE || window.__API_BASE__ || 'http://127.0.0.1:8000';
  
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const heatLayerRef = useRef(null);
  const selectedLayerRef = useRef(null);

  const [isMapReady, setIsMapReady] = useState(false);
  const [isMapInitialized, setIsMapInitialized] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [geojson, setGeojson] = useState(null);
  const [batchResults, setBatchResults] = useState(null);
  const [processedCount, setProcessedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);

  /* ---------------- LOAD LEAFLET & HEAT PLUGIN ---------------- */
  useEffect(() => {
    // Check if both Leaflet and heat plugin are already loaded
    if (window.L && window.L.heatLayer) {
      setIsMapReady(true);
      return;
    }

    let isComponentMounted = true;

    const loadScripts = async () => {
      try {
        // Load Leaflet CSS
        const css = document.createElement('link');
        css.rel = 'stylesheet';
        css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
        document.head.appendChild(css);

        // Load Leaflet JS
        if (!window.L) {
          await new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
            script.async = true;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
          });
        }

        // Load Leaflet.heat plugin
        if (!window.L.heatLayer) {
          await new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js';
            script.async = true;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
          });
        }

        if (isComponentMounted) {
          setIsMapReady(true);
        }
      } catch (error) {
        console.error('Error loading Leaflet or heat plugin:', error);
        if (isComponentMounted) {
          setError(`Failed to load map libraries: ${error.message}`);
        }
      }
    };

    loadScripts();

    return () => {
      isComponentMounted = false;
    };
  }, []);

  /* ---------------- INIT MAP ---------------- */
  useEffect(() => {
    if (!isMapReady || mapInstanceRef.current) return;

    const L = window.L;
    if (!mapRef.current) return; // Ensure map container exists
    
    const map = L.map(mapRef.current).setView([28.6139, 77.2090], 11);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    mapInstanceRef.current = map;
    setIsMapInitialized(true); // Trigger re-render so fetch effect runs

    return () => {
      if (mapInstanceRef.current) {
        map.remove();
      }
      mapInstanceRef.current = null;
      setIsMapInitialized(false);
    };
  }, [isMapReady]);

  /* ---------------- LOAD GEOJSON + HEATMAP ---------------- */
  useEffect(() => {
    if (!isMapReady || !isMapInitialized || !mapInstanceRef.current) {
      console.log('Data fetch skipped:', { isMapReady, isMapInitialized, hasMapInstance: !!mapInstanceRef.current });
      return;
    }

    const base = API_BASE?.replace(/\/$/, '') || 'http://127.0.0.1:8000';
    console.log('Starting data fetch...');
    setIsLoading(true);
    setError(null);
    setProcessedCount(0);
    setTotalCount(0);

    // Fetch GeoJSON first, then batch predictions in chunks
    fetch(`${base}/wards/geojson`)
      .then(res => {
        console.log('GeoJSON fetch response:', res.status, res.statusText);
        if (!res.ok) throw new Error(`GeoJSON fetch failed: ${res.status} ${res.statusText}`);
        return res.json();
      })
      .then(geo => {
        console.log('GeoJSON parsed, features count:', geo?.features?.length);
        if (!geo || !geo.features || !Array.isArray(geo.features)) {
          throw new Error('Invalid GeoJSON structure');
        }
        const L = window.L;
        if (!L) throw new Error('Leaflet not available');
        
        console.log('Calculating centroids...');
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

        console.log('Centroids calculated:', centroids.length);
        if (centroids.length === 0) {
          throw new Error('No valid centroids found in GeoJSON');
        }

        // Set GeoJSON immediately so map can render
        setGeojson(geo);
        setTotalCount(centroids.length);

        // Process predictions in chunks for incremental updates
        const CHUNK_SIZE = 25; // Process 25 predictions at a time
        const chunks = [];
        for (let i = 0; i < centroids.length; i += CHUNK_SIZE) {
          chunks.push(centroids.slice(i, i + CHUNK_SIZE));
        }

        console.log(`Processing ${centroids.length} predictions in ${chunks.length} chunks of ${CHUNK_SIZE}`);

        // Store all results as they come in
        const allResults = [];
        let processedSoFar = 0;

        // Process chunks sequentially to avoid overwhelming the server
        const processChunks = async () => {
          for (let chunkIdx = 0; chunkIdx < chunks.length; chunkIdx++) {
            const chunk = chunks[chunkIdx];
            const requestBody = chunk.map(c => ({ latitude: c.latitude, longitude: c.longitude }));

            try {
              console.log(`Processing chunk ${chunkIdx + 1}/${chunks.length} (${chunk.length} predictions)...`);
              
              const response = await fetch(`${base}/predict_ward_batch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
              });

              if (!response.ok) {
                const errorText = await response.text();
                console.error(`Chunk ${chunkIdx + 1} error:`, errorText);
                // Add error results for this chunk
                chunk.forEach(c => {
                  allResults.push({
                    error: `HTTP ${response.status}: ${errorText.substring(0, 100)}`,
                    location: { latitude: c.latitude, longitude: c.longitude }
                  });
                });
              } else {
                const resp = await response.json();
                if (resp && resp.results && Array.isArray(resp.results)) {
                  allResults.push(...resp.results);
                  processedSoFar += resp.results.filter(r => !r.error).length;
                  setProcessedCount(processedSoFar);
                  console.log(`Chunk ${chunkIdx + 1} completed: ${processedSoFar}/${centroids.length} total`);
                  
                  // Update batch results incrementally so heatmap can render
                  setBatchResults({
                    centroids: centroids,
                    batchResp: {
                      results: allResults,
                      processed: processedSoFar,
                      total: centroids.length
                    }
                  });
                }
              }
            } catch (err) {
              console.error(`Error processing chunk ${chunkIdx + 1}:`, err);
              // Add error results for this chunk
              chunk.forEach(c => {
                allResults.push({
                  error: err.message || 'Unknown error',
                  location: { latitude: c.latitude, longitude: c.longitude }
                });
              });
            }
          }

          // Final update with all results
          console.log(`All chunks processed: ${allResults.length} total results`);
          setBatchResults({
            centroids: centroids,
            batchResp: {
              results: allResults,
              processed: allResults.filter(r => !r.error).length,
              failed: allResults.filter(r => r.error).length,
              total: centroids.length
            }
          });
          setProcessedCount(allResults.length);
          setIsLoading(false);
        };

        // Start processing chunks
        processChunks().catch(err => {
          console.error('Error in chunk processing:', err);
          setError(`Failed to process predictions: ${err.message || 'Unknown error'}`);
          setIsLoading(false);
        });
      })
      .catch((err) => {
        console.error('Heatmap loading error:', err);
        console.error('Error stack:', err.stack);
        setError(`Failed to load heatmap: ${err.message || 'Unknown error'}`);
        setIsLoading(false);
      });
  }, [isMapReady, isMapInitialized, API_BASE]);

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
      console.warn('Missing data for ward lookup map:', { 
        hasResp: !!resp, 
        hasResults: !!(resp && resp.results), 
        resultsLength: resp?.results?.length,
        hasCentroids: !!centroids,
        centroidsLength: centroids?.length 
      });
      return;
    }

    console.log(`Building ward lookup map: ${geojson.features.length} GeoJSON features, ${resp.results.length} prediction results, ${centroids.length} centroids`);

    // Build comprehensive ward lookup map: { wardNumber: { wardName, wardNumber, riskValue, riskLevel, lat, lng } }
    const lookup = new Map();
    
    // First, index GeoJSON features by normalized ward number AND by index
    const geoJsonMap = new Map();
    const geoJsonByIndex = []; // Array for index-based matching
    
    geojson.features.forEach((feature, idx) => {
      const props = feature.properties || {};
      let wardId = props.Ward_ID !== undefined ? props.Ward_ID : props.Ward_No;
      
      if (wardId != null && wardId !== undefined) {
        // Normalize to string for consistent lookup
        const wardNumberStr = String(wardId).trim();
        const wardNumberNum = parseInt(wardId, 10);
        
        // Get centroid for this feature (try matching first, then use index)
        let centroid = centroids.find(c => {
          const cWardId = c.wardId;
          return cWardId == wardId || String(cWardId) === String(wardId);
        });
        
        if (!centroid && idx < centroids.length) {
          centroid = centroids[idx];
        }
        
        if (centroid) {
          const geoData = {
            feature,
            centroid,
            wardId: wardId,
            wardNumberStr,
            wardNumberNum: isNaN(wardNumberNum) ? null : wardNumberNum
          };
          
          geoJsonMap.set(wardNumberStr, geoData);
          // Also index by numeric value if valid
          if (!isNaN(wardNumberNum)) {
            geoJsonMap.set(wardNumberNum, geoData);
            geoJsonMap.set(String(wardNumberNum), geoData);
          }
        }
      }
      
      // Store by index for fallback matching
      if (idx < centroids.length) {
        geoJsonByIndex[idx] = {
          feature,
          centroid: centroids[idx],
          wardId: props.Ward_ID !== undefined ? props.Ward_ID : props.Ward_No,
          index: idx
        };
      }
    });

    console.log(`Indexed ${geoJsonMap.size} GeoJSON entries, ${geoJsonByIndex.length} by index`);

    // Now merge with batch prediction results - use index-based matching as primary strategy
    // since predictions are returned in the same order as request (which matches GeoJSON order)
    let matchedCount = 0;
    let unmatchedCount = 0;
    
    resp.results.forEach((result, resultIdx) => {
      if (result.error) {
        console.warn(`Prediction result ${resultIdx} has error:`, result.error);
        return;
      }

      const wardId = result.Ward_ID;
      if (wardId == null || wardId === undefined) {
        console.warn(`Prediction result ${resultIdx} has no Ward_ID`);
        return;
      }

      // Normalize ward ID to string and number
      const wardNumberStr = String(wardId).trim();
      const wardNumberNum = parseInt(wardId, 10);
      const isValidNum = !isNaN(wardNumberNum) && wardNumberNum >= 0;

      // Try to find matching GeoJSON data - use index first, then Ward_ID match
      let geoData = null;
      
      // Strategy 1: Index-based matching (most reliable since order is preserved)
      if (resultIdx < geoJsonByIndex.length) {
        geoData = geoJsonByIndex[resultIdx];
        // Verify Ward_ID matches if available
        if (geoData && geoData.wardId != null) {
          const geoWardId = String(geoData.wardId);
          const resultWardId = String(wardId);
          if (geoWardId !== resultWardId) {
            console.warn(`Index ${resultIdx}: Ward_ID mismatch - GeoJSON: ${geoWardId}, Result: ${resultWardId}, using index match anyway`);
          }
        }
      }
      
      // Strategy 2: Ward_ID based matching (fallback)
      if (!geoData) {
        geoData = geoJsonMap.get(wardNumberStr);
        if (!geoData && isValidNum) {
          geoData = geoJsonMap.get(wardNumberNum);
        }
        if (!geoData && isValidNum) {
          geoData = geoJsonMap.get(String(wardNumberNum));
        }
      }

      if (!geoData) {
        console.warn(`No GeoJSON data found for Ward_ID: ${wardId} at index ${resultIdx}`);
        unmatchedCount++;
        return;
      }

      matchedCount++;
      const { feature, centroid } = geoData;
      const props = feature.properties || {};
      const wardName = props.Ward_Name || props.WardName || `Ward ${wardId}`;
      
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

    console.log(`Built ward lookup map: ${lookup.size} entries (matched: ${matchedCount}, unmatched: ${unmatchedCount})`);
    setWardLookupMap(lookup);
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

      {/* Main Content */}
      <div className="relative z-10 px-4 py-24 max-w-7xl mx-auto" style={{ paddingTop: '120px' }}>
        
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
                    {totalCount > 0 && (
                      <p className="text-white/60 text-xs mt-2">
                        Processed {processedCount}/{totalCount} wards ({Math.round((processedCount / totalCount) * 100)}%)
                      </p>
                    )}
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
