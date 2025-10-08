import React, { useState, useEffect } from 'react';
import Squares from './Squares';
import Dock from './Dock';
import ShinyText from './ShinyText';
import { VscHome, VscLocation, VscRefresh, VscGithubInverted } from 'react-icons/vsc';
import { useNavigate } from 'react-router-dom';

function PredictTest() {
  const navigate = useNavigate();
  const API_BASE = import.meta.env.VITE_API_BASE || window.__API_BASE__ || 'http://127.0.0.1:8000';
  
  const [location, setLocation] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [geolocationSupported, setGeolocationSupported] = useState(true);

  // NEW: Destination states
  const [destAddress, setDestAddress] = useState('');
  const [destLocation, setDestLocation] = useState(null);
  const [destPrediction, setDestPrediction] = useState(null);

  const dockItems = [
    { icon: <VscHome size={24} />, label: 'Home', onClick: () => navigate('/') },
    { icon: <VscLocation size={24} />, label: 'Get Location', onClick: () => getCurrentLocation() },
    { icon: <VscRefresh size={24} />, label: 'Refresh', onClick: () => handleRefresh() },
    { icon: <VscGithubInverted size={24} />, label: 'GitHub', onClick: () => window.open('https://github.com/JUGADU-GEEKS/DelhiFlow', '_blank') },
  ];

  useEffect(() => {
    // Check if geolocation is supported
    if (!navigator.geolocation) {
      setGeolocationSupported(false);
      setError('Geolocation is not supported by this browser');
    }
  }, []);

  const getCurrentLocation = () => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by this browser');
      return;
    }

    setIsLoading(true);
    setError(null);

    const options = {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 300000 // 5 minutes
    };

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords;
        setLocation({ latitude, longitude });
        
        try {
          await predictFromLocation(latitude, longitude);
        } catch (err) {
          console.error('Prediction error:', err);
          setError('Failed to get prediction for your location');
        } finally {
          setIsLoading(false);
        }
      },
      (error) => {
        console.error('Geolocation error:', error);
        let errorMessage;
        switch (error.code) {
          case error.PERMISSION_DENIED:
            errorMessage = 'Location access denied. Please enable location permissions and try again.';
            break;
          case error.POSITION_UNAVAILABLE:
            errorMessage = 'Location information is unavailable.';
            break;
          case error.TIMEOUT:
            errorMessage = 'Location request timed out. Please try again.';
            break;
          default:
            errorMessage = 'An unknown error occurred while retrieving location.';
            break;
        }
        setError(errorMessage);
        setIsLoading(false);
      },
      options
    );
  };

  const predictFromLocation = async (latitude, longitude) => {
    // Prefer dataset-driven endpoint that accounts for time + grid mapping
    const base = API_BASE.replace(/\/$/, '');
    const urlTime = `${base}/predict_location_time`;
    const urlLegacy = `${base}/predict_location`;
    try {
      const timestamp = new Date().toISOString();
      let response = await fetch(urlTime, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ latitude, longitude, timestamp }),
      });

      if (!response.ok) {
        // fallback to legacy endpoint (without grid lookup)
        response = await fetch(urlLegacy, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ latitude, longitude })
        });
        if (!response.ok) {
          const text = await response.text();
          let parsed;
          try { parsed = JSON.parse(text); } catch(e) { parsed = text; }
          const detail = parsed && parsed.detail ? parsed.detail : (typeof parsed === 'string' ? parsed : JSON.stringify(parsed));
          const msg = `Prediction API error: HTTP ${response.status} - ${detail}`;
          console.error(msg, parsed);
          setError(msg);
          return;
        }
      }

      // parse JSON safely
      const text = await response.text();
      if (!text) {
        const msg = 'Prediction API returned empty response';
        console.error(msg);
        setError(msg);
        return;
      }
      let data;
      try { data = JSON.parse(text); } catch (e) {
        console.error('Failed to parse JSON from prediction API:', text);
        setError('Prediction API returned invalid JSON');
        return;
      }

      setPrediction(data);
    } catch (err) {
      console.error('Network or fetch error calling prediction API:', err);
      setError(`Network error: ${err.message}`);
      return;
    }
  };

  // NEW: Predict destination using same time-aware endpoint
  const predictDestinationFromCoordinates = async (latitude, longitude) => {
    const base = API_BASE.replace(/\/$/, '');
    const urlTime = `${base}/predict_location_time`;
    const urlLegacy = `${base}/predict_location`;
    try {
      const timestamp = new Date().toISOString();
      let response = await fetch(urlTime, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ latitude, longitude, timestamp }),
      });

      if (!response.ok) {
        response = await fetch(urlLegacy, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ latitude, longitude })
        });
        if (!response.ok) {
          const text = await response.text();
          let parsed;
          try { parsed = JSON.parse(text); } catch(e) { parsed = text; }
          const detail = parsed && parsed.detail ? parsed.detail : (typeof parsed === 'string' ? parsed : JSON.stringify(parsed));
          const msg = `Destination prediction error: HTTP ${response.status} - ${detail}`;
          console.error(msg, parsed);
          setError(msg);
          return;
        }
      }

      // parse JSON safely
      const text = await response.text();
      if (!text) {
        const msg = 'Destination prediction returned empty response';
        console.error(msg);
        setError(msg);
        return;
      }
      let data;
      try { data = JSON.parse(text); } catch (e) {
        console.error('Failed to parse JSON for destination:', text);
        setError('Destination prediction returned invalid JSON');
        return;
      }
      setDestPrediction(data);
    } catch (err) {
      console.error('Network or fetch error calling destination prediction API:', err);
      setError(`Network error: ${err.message}`);
      return;
    }
  };

  // NEW: Geocode destination address -> lat/lon via OpenStreetMap Nominatim
  const geocodeDestination = async () => {
    if (!destAddress || destAddress.trim().length === 0) {
      setError('Enter a destination address');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(destAddress)}&limit=1`;
      const resp = await fetch(url, { headers: { 'Accept': 'application/json' } });
      if (!resp.ok) {
        setError(`Geocoding failed: HTTP ${resp.status}`);
        return;
      }
      const data = await resp.json();
      if (!Array.isArray(data) || data.length === 0) {
        setError('Destination not found');
        return;
      }
      const lat = parseFloat(data[0].lat);
      const lon = parseFloat(data[0].lon);
      setDestLocation({ latitude: lat, longitude: lon });

      // Immediately get destination risk for the same time context
      await predictDestinationFromCoordinates(lat, lon);
    } catch (e) {
      console.error('Geocoding error:', e);
      setError('Failed to geocode destination');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = () => {
    setLocation(null);
    setPrediction(null);
    setError(null);
    // NEW: reset destination
    setDestAddress('');
    setDestLocation(null);
    setDestPrediction(null);
    getCurrentLocation();
  };

  const getRiskColor = (risk) => {
    switch(risk?.toLowerCase()) {
      case 'low': return 'from-green-400 to-emerald-500';
      case 'medium': return 'from-yellow-400 to-orange-500';
      case 'high': return 'from-red-400 to-rose-600';
      default: return 'from-purple-400 to-fuchsia-500';
    }
  };

  const getRiskBorderColor = (risk) => {
    switch(risk?.toLowerCase()) {
      case 'low': return 'border-green-400/50';
      case 'medium': return 'border-yellow-400/50';
      case 'high': return 'border-red-400/50';
      default: return 'border-purple-400/30';
    }
  };

  const formatCoordinate = (coord, type) => {
    if (!coord && coord !== 0) return 'N/A';
    const direction = type === 'lat' ? (coord >= 0 ? 'N' : 'S') : (coord >= 0 ? 'E' : 'W');
    return `${Math.abs(coord).toFixed(6)}° ${direction}`;
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
        <div className="text-center mb-16 mt-8">
          <ShinyText
            text="Location-Based Predictor"
            disabled={false}
            speed={3}
            className="text-5xl md:text-6xl lg:text-7xl font-bold leading-tight mb-6"
          />
          <p className="text-white/80 text-lg md:text-xl leading-relaxed max-w-3xl mx-auto font-light">
            Allow location access to automatically predict flood risk for your current position
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          
          {/* Left: Location & Destination */}
          <div>
            <div className="bg-purple-900/20 backdrop-blur-xl border border-purple-400/30 rounded-3xl p-8 shadow-2xl shadow-purple-900/20 mb-6">
              {/* Start location block (unchanged aside from minor tweaks) */}
              <h2 className="text-white text-2xl font-bold mb-6 flex items-center gap-3">
                <div className="bg-gradient-to-br from-purple-400 to-fuchsia-500 w-10 h-10 rounded-xl flex items-center justify-center shadow-lg shadow-purple-500/30">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                Your Location
              </h2>

              {!geolocationSupported ? (
                <div className="text-center py-8">
                  <div className="bg-red-500/10 border border-red-400/30 rounded-2xl p-6">
                    <svg className="w-12 h-12 text-red-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <p className="text-red-300 font-medium">Geolocation Not Supported</p>
                    <p className="text-red-300/70 text-sm mt-2">Your browser doesn't support geolocation services.</p>
                  </div>
                </div>
              ) : (
                <>
                  {location ? (
                    <div className="space-y-4">
                      <div className="bg-black/30 rounded-2xl p-4 border border-purple-400/20">
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <p className="text-white/70 text-sm">Latitude</p>
                            <p className="text-white font-mono text-lg">{formatCoordinate(location.latitude, 'lat')}</p>
                          </div>
                          <div>
                            <p className="text-white/70 text-sm">Longitude</p>
                            <p className="text-white font-mono text-lg">{formatCoordinate(location.longitude, 'lng')}</p>
                          </div>
                        </div>
                      </div>

                      {prediction && prediction.derived_features && (
                        <div className="bg-black/30 rounded-2xl p-4 border border-purple-400/20">
                          <h3 className="text-white font-semibold mb-3">Derived Features</h3>
                          <div className="grid grid-cols-2 gap-2 text-sm">
                            <div>
                              <span className="text-white/70">Elevation:</span>
                              <span className="text-white ml-2">{prediction.derived_features.Elevation?.toFixed(1)}m</span>
                            </div>
                            <div>
                              <span className="text-white/70">Road Density:</span>
                              <span className="text-white ml-2">{prediction.derived_features.Road_Density?.toFixed(2)}</span>
                            </div>
                            <div>
                              <span className="text-white/70">Rain:</span>
                              <span className="text-white ml-2">{prediction.derived_features.Rain_mm?.toFixed(1)}mm</span>
                            </div>
                            <div>
                              <span className="text-white/70">Soil Moisture:</span>
                              <span className="text-white ml-2">{prediction.derived_features.Soil_Moisture?.toFixed(2)}</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <div className="bg-gradient-to-br from-purple-400 to-fuchsia-500 w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg shadow-purple-500/30">
                        <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                      </div>
                      <p className="text-white/60 mb-6">Click "Get My Location" to start automatic flood risk prediction</p>
                      
                      <button
                        onClick={getCurrentLocation}
                        disabled={isLoading}
                        className="bg-gradient-to-r from-purple-500 to-fuchsia-600 text-white px-8 py-4 rounded-xl font-semibold hover:from-purple-600 hover:to-fuchsia-700 hover:scale-105 transition-all duration-200 shadow-lg shadow-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                      >
                        {isLoading ? (
                          <span className="flex items-center justify-center gap-2">
                            <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Getting Location...
                          </span>
                        ) : (
                          <span className="flex items-center justify-center gap-2">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            Get My Location
                          </span>
                        )}
                      </button>
                    </div>
                  )}

                  {error && (
                    <div className="bg-red-500/10 border border-red-400/30 rounded-2xl p-4 mt-4">
                      <p className="text-red-300 text-sm">{error}</p>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* NEW: Destination block */}
            <div className="bg-purple-900/20 backdrop-blur-xl border border-purple-400/30 rounded-3xl p-8 shadow-2xl shadow-purple-900/20 mt-8 mb-6">
               <h2 className="text-white text-2xl font-bold mb-6 flex items-center gap-3">
                 <div className="bg-gradient-to-br from-fuchsia-400 to-pink-500 w-10 h-10 rounded-xl flex items-center justify-center shadow-lg shadow-fuchsia-500/30">
                   <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                     <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 2l7 7-7 7-7-7 7-7z" />
                   </svg>
                 </div>
                 Destination
               </h2>

               <div className="flex flex-col sm:flex-row gap-3">
                 <input
                   type="text"
                   value={destAddress}
                   onChange={(e) => setDestAddress(e.target.value)}
                   placeholder="Enter destination address or landmark"
                   className="flex-1 bg-black/40 border border-purple-400/30 rounded-xl px-4 py-3 text-white placeholder-white/40 outline-none focus:border-fuchsia-400/60"
                 />
                 <button
                   onClick={geocodeDestination}
                   disabled={isLoading || !destAddress}
                   className="bg-gradient-to-r from-fuchsia-500 to-pink-600 text-white px-6 py-3 rounded-xl font-semibold hover:from-fuchsia-600 hover:to-pink-700 transition-all duration-200 shadow-lg shadow-fuchsia-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
                 >
                   {isLoading ? 'Resolving...' : 'Set Destination'}
                 </button>
               </div>

               {destLocation && (
                 <div className="bg-black/30 rounded-2xl p-4 border border-fuchsia-400/20 mt-4">
                   <div className="grid grid-cols-2 gap-4">
                     <div>
                       <p className="text-white/70 text-sm">Latitude</p>
                       <p className="text-white font-mono text-lg">{formatCoordinate(destLocation.latitude, 'lat')}</p>
                     </div>
                     <div>
                       <p className="text-white/70 text-sm">Longitude</p>
                       <p className="text-white font-mono text-lg">{formatCoordinate(destLocation.longitude, 'lng')}</p>
                     </div>
                   </div>
                 </div>
               )}

               {/* Destination derived features */}
               {destPrediction && destPrediction.derived_features && (
                 <div className="bg-black/30 rounded-2xl p-4 border border-fuchsia-400/20 mt-4">
                   <h3 className="text-white font-semibold mb-3">Derived Features</h3>
                   <div className="grid grid-cols-2 gap-2 text-sm">
                     <div>
                       <span className="text-white/70">Elevation:</span>
                       <span className="text-white ml-2">{destPrediction.derived_features.Elevation?.toFixed(1)}m</span>
                     </div>
                     <div>
                       <span className="text-white/70">Road Density:</span>
                       <span className="text-white ml-2">{destPrediction.derived_features.Road_Density?.toFixed(2)}</span>
                     </div>
                     <div>
                       <span className="text-white/70">Rain:</span>
                       <span className="text-white ml-2">{destPrediction.derived_features.Rain_mm?.toFixed(1)}mm</span>
                     </div>
                     <div>
                       <span className="text-white/70">Soil Moisture:</span>
                       <span className="text-white ml-2">{destPrediction.derived_features.Soil_Moisture?.toFixed(2)}</span>
                     </div>
                     {typeof destPrediction.derived_features.Rain_Past3h === 'number' && (
                       <div>
                         <span className="text-white/70">Rain (3h):</span>
                         <span className="text-white ml-2">{destPrediction.derived_features.Rain_Past3h?.toFixed(1)}mm</span>
                       </div>
                     )}
                     {typeof destPrediction.derived_features.Drain_Water_Level === 'number' && (
                       <div>
                         <span className="text-white/70">Drain Level:</span>
                         <span className="text-white ml-2">{destPrediction.derived_features.Drain_Water_Level?.toFixed(2)}</span>
                       </div>
                     )}
                   </div>
                 </div>
               )}
             </div>

            {error && (
              <div className="bg-red-500/10 border border-red-400/30 rounded-2xl p-4 mt-4">
                <p className="text-red-300 text-sm">{error}</p>
              </div>
            )}
          </div>

          {/* Right: Prediction Results */}
          <div className="space-y-8">
            {/* START prediction card (existing card but scoped to `prediction`) */}
            <div className={`bg-purple-900/20 backdrop-blur-xl border ${prediction?.prediction ? getRiskBorderColor(prediction.prediction.label) : 'border-purple-400/30'} rounded-3xl p-8 shadow-2xl shadow-purple-900/20 transition-all duration-500`}>
              <h2 className="text-white text-2xl font-bold mb-6 flex items-center gap-3">
                <div className={`bg-gradient-to-br ${prediction?.prediction ? getRiskColor(prediction.prediction.label) : 'from-purple-400 to-fuchsia-500'} w-10 h-10 rounded-xl flex items-center justify-center shadow-lg transition-all duration-500`}>
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                Start Location Risk
              </h2>

              {!prediction?.prediction ? (
                <div className="text-center py-12">
                  <div className="bg-gradient-to-br from-purple-400 to-fuchsia-500 w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg shadow-purple-500/30 animate-pulse">
                    <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                  <p className="text-white/60 font-light">
                    Share your location to get an instant flood risk assessment
                  </p>
                </div>
              ) : (
                <div className="space-y-6 animate-fadeIn">
                  <div className="text-center">
                    <p className="text-white/70 text-sm font-medium mb-3">Current Risk Level</p>
                    <div className={`bg-gradient-to-r ${getRiskColor(prediction.prediction.label)} text-white text-4xl font-bold py-6 px-8 rounded-2xl shadow-lg uppercase tracking-wider`}>
                      {prediction.prediction.label}
                    </div>
                  </div>

                  <div className="bg-black/30 rounded-2xl p-6 border border-purple-400/20">
                    <div className="flex justify-between items-center mb-3">
                      <span className="text-white/70 text-sm font-medium">Confidence</span>
                      <span className="text-white font-bold text-lg">{prediction.prediction.confidence}%</span>
                    </div>
                    <div className="w-full bg-black/50 rounded-full h-3 overflow-hidden">
                      <div 
                        className={`bg-gradient-to-r ${getRiskColor(prediction.prediction.label)} h-full rounded-full transition-all duration-1000 ease-out`}
                        style={{ width: `${prediction.prediction.confidence}%` }}
                      ></div>
                    </div>
                  </div>

                  <div className="bg-black/30 rounded-2xl p-6 border border-purple-400/20">
                    <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Recommendation
                    </h3>
                    <p className="text-white/70 text-sm leading-relaxed font-light">
                      {prediction.prediction.label === 'Low' && "Minimal flood risk detected at your location. Normal activities can proceed, but stay aware of weather conditions."}
                      {prediction.prediction.label === 'Medium' && "Moderate flood risk detected at your location. Monitor weather updates and prepare for potential water accumulation."}
                      {prediction.prediction.label === 'High' && "High flood risk detected at your location! Take immediate precautions, avoid low-lying areas, and follow local emergency guidelines."}
                    </p>
                  </div>

                  {/* Alert for High Risk */}
                  {prediction.prediction.label === 'High' && (
                    <div className="bg-red-500/10 border border-red-400/30 rounded-2xl p-4 flex items-start gap-3 animate-pulse">
                      <svg className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      <p className="text-red-300 text-sm font-medium">Emergency alert: Severe flood conditions expected at your location!</p>
                    </div>
                  )}

                  {/* Time Information */}
                  {prediction.time_used && (
                    <div className="bg-black/30 rounded-2xl p-4 border border-purple-400/20">
                      <h3 className="text-white/70 text-sm font-medium mb-2">Analysis Time</h3>
                      <div className="grid grid-cols-3 gap-3 text-sm">
                        <div>
                          <span className="text-white/70">Hour:</span>
                          <span className="text-white ml-2">{prediction.time_used.hour_of_day}</span>
                        </div>
                        <div>
                          <span className="text-white/70">Month:</span>
                          <span className="text-white ml-2">{prediction.time_used.month}</span>
                        </div>
                        <div>
                          <span className="text-white/70">Day:</span>
                          <span className="text-white ml-2">{prediction.time_used.day_of_week}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* DESTINATION prediction card (mirrors the start card but uses destPrediction) */}
            <div className={`bg-purple-900/20 backdrop-blur-xl border ${destPrediction?.prediction ? getRiskBorderColor(destPrediction.prediction.label) : 'border-purple-400/30'} rounded-3xl p-8 shadow-2xl shadow-purple-900/20 transition-all duration-500`}>
              <h2 className="text-white text-2xl font-bold mb-6 flex items-center gap-3">
                <div className={`bg-gradient-to-br ${destPrediction?.prediction ? getRiskColor(destPrediction.prediction.label) : 'from-pink-400 to-fuchsia-500'} w-10 h-10 rounded-xl flex items-center justify-center shadow-lg transition-all duration-500`}>
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                Destination Risk
              </h2>

              {!destPrediction?.prediction ? (
                <div className="text-center py-12">
                  <div className="bg-gradient-to-br from-pink-400 to-fuchsia-500 w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg shadow-pink-500/30 animate-pulse">
                    <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                  <p className="text-white/60 font-light">
                    Enter a destination to see flood risk at your endpoint
                  </p>
                </div>
              ) : (
                <div className="space-y-6 animate-fadeIn">
                  <div className="text-center">
                    <p className="text-white/70 text-sm font-medium mb-3">Current Risk Level</p>
                    <div className={`bg-gradient-to-r ${getRiskColor(destPrediction.prediction.label)} text-white text-4xl font-bold py-6 px-8 rounded-2xl shadow-lg uppercase tracking-wider`}>
                      {destPrediction.prediction.label}
                    </div>
                  </div>

                  <div className="bg-black/30 rounded-2xl p-6 border border-purple-400/20">
                    <div className="flex justify-between items-center mb-3">
                      <span className="text-white/70 text-sm font-medium">Confidence</span>
                      <span className="text-white font-bold text-lg">{destPrediction.prediction.confidence}%</span>
                    </div>
                    <div className="w-full bg-black/50 rounded-full h-3 overflow-hidden">
                      <div 
                        className={`bg-gradient-to-r ${getRiskColor(destPrediction.prediction.label)} h-full rounded-full transition-all duration-1000 ease-out`}
                        style={{ width: `${destPrediction.prediction.confidence}%` }}
                      ></div>
                    </div>
                  </div>

                  <div className="bg-black/30 rounded-2xl p-6 border border-purple-400/20">
                    <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Recommendation
                    </h3>
                    <p className="text-white/70 text-sm leading-relaxed font-light">
                      {destPrediction.prediction.label === 'Low' && "Destination shows minimal risk. Proceed normally but keep an eye on weather updates."}
                      {destPrediction.prediction.label === 'Medium' && "Destination shows moderate risk. Plan for possible waterlogging and delays."}
                      {destPrediction.prediction.label === 'High' && "Destination shows high risk! Consider alternate routes or rescheduling if possible."}
                    </p>
                  </div>

                  {destPrediction.prediction.label === 'High' && (
                    <div className="bg-red-500/10 border border-red-400/30 rounded-2xl p-4 flex items-start gap-3 animate-pulse">
                      <svg className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      <p className="text-red-300 text-sm font-medium">Warning: Destination has severe flood risk!</p>
                    </div>
                  )}

                  {destPrediction.time_used && (
                    <div className="bg-black/30 rounded-2xl p-4 border border-purple-400/20">
                      <h3 className="text-white/70 text-sm font-medium mb-2">Analysis Time</h3>
                      <div className="grid grid-cols-3 gap-3 text-sm">
                        <div>
                          <span className="text-white/70">Hour:</span>
                          <span className="text-white ml-2">{destPrediction.time_used.hour_of_day}</span>
                        </div>
                        <div>
                          <span className="text-white/70">Month:</span>
                          <span className="text-white ml-2">{destPrediction.time_used.month}</span>
                        </div>
                        <div>
                          <span className="text-white/70">Day:</span>
                          <span className="text-white ml-2">{destPrediction.time_used.day_of_week}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Info Section */}
        <div className="mt-16">
          <div className="bg-purple-900/20 backdrop-blur-xl border border-purple-400/30 rounded-3xl p-8 shadow-2xl shadow-purple-900/20">
            <h2 className="text-white text-2xl font-bold mb-6 flex items-center gap-3">
              <div className="bg-gradient-to-br from-fuchsia-400 to-pink-500 w-10 h-10 rounded-xl flex items-center justify-center shadow-lg shadow-fuchsia-500/30">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              How Location-Based Prediction Works
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="space-y-3">
                <div className="bg-gradient-to-br from-purple-400 to-fuchsia-500 w-12 h-12 rounded-xl flex items-center justify-center shadow-lg shadow-purple-500/30">
                  <span className="text-white text-xl font-bold">1</span>
                </div>
                <h3 className="text-white font-semibold text-lg">Get Location</h3>
                <p className="text-white/70 text-sm leading-relaxed font-light">
                  Your browser requests your GPS coordinates. We only use this data for flood risk calculation - no storage or tracking.
                </p>
              </div>

              <div className="space-y-3">
                <div className="bg-gradient-to-br from-fuchsia-400 to-pink-500 w-12 h-12 rounded-xl flex items-center justify-center shadow-lg shadow-fuchsia-500/30">
                  <span className="text-white text-xl font-bold">2</span>
                </div>
                <h3 className="text-white font-semibold text-lg">Derive Features</h3>
                <p className="text-white/70 text-sm leading-relaxed font-light">
                  We automatically estimate environmental factors like elevation, road density, and seasonal rainfall patterns for your location.
                </p>
              </div>

              <div className="space-y-3">
                <div className="bg-gradient-to-br from-pink-400 to-purple-500 w-12 h-12 rounded-xl flex items-center justify-center shadow-lg shadow-pink-500/30">
                  <span className="text-white text-xl font-bold">3</span>
                </div>
                <h3 className="text-white font-semibold text-lg">AI Analysis</h3>
                <p className="text-white/70 text-sm leading-relaxed font-light">
                  Our trained model analyzes all factors plus current time to provide instant, personalized flood risk assessment.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PredictTest;
