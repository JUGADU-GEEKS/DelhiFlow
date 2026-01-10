import React, { useEffect, useState, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { motion, AnimatePresence } from 'framer-motion';
import { RefreshCw, MapPin, ChevronDown, ChevronUp } from 'lucide-react';
import 'leaflet/dist/leaflet.css';

// Create custom marker icons for potholes
const createMarkerIcon = (count) => {
  const getColor = (count) => {
    if (count >= 5) return '#ff5252'; // Red - severe
    if (count >= 2) return '#fdd835'; // Yellow - moderate
    return '#66bb6a'; // Green - minor
  };

  const color = getColor(count);
  const size = count >= 5 ? 32 : count >= 2 ? 28 : 24;

  const svgString = `
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
      <circle cx="${size/2}" cy="${size/2}" r="${size/2 - 2}" fill="${color}" stroke="#ffffff" stroke-width="2"/>
      <text x="${size/2}" y="${size/2 + 4}" font-size="11" font-weight="bold" fill="#ffffff" text-anchor="middle" dominant-baseline="middle">${count}</text>
    </svg>
  `;

  return L.icon({
    iconUrl: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svgString)}`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -(size / 2)],
  });
};

const PotholesMap = () => {
  const [potholes, setPotholes] = useState([]);
  const [isListExpanded, setIsListExpanded] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const mapRef = useRef(null);

  const fetchPotholes = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/potholes/map`);
      if (!res.ok) throw new Error('Failed to fetch potholes');
      const data = await res.json();
      console.log('Potholes fetched:', data);
      // Normalize data: ensure numeric lat/lon
      const normalized = (data || []).map((p) => ({
        lat: p.lat != null ? Number(p.lat) : null,
        lon: p.lon != null ? Number(p.lon) : null,
        potholeCount: Number(p.potholeCount || 0),
        status: p.status || 'pending',
        gridId: p.gridId || null,
      })).filter(p => p.lat !== null && p.lon !== null && !Number.isNaN(p.lat) && !Number.isNaN(p.lon));
      setPotholes(normalized);
    } catch (e) {
      console.error('Potholes fetch error', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchPotholes();
  }, []);

  // Auto-fit bounds when potholes data loads
  useEffect(() => {
    if (mapRef.current && potholes.length > 0) {
      const bounds = L.latLngBounds(potholes.map(p => [p.lat, p.lon]));
      mapRef.current.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [potholes]);

  const center = potholes.length > 0 ? {
    lat: potholes.reduce((s, p) => s + p.lat, 0) / potholes.length,
    lng: potholes.reduce((s, p) => s + p.lon, 0) / potholes.length,
  } : { lat: 28.6139, lng: 77.2090 };

  const getSeverityColor = (count) => {
    if (count >= 5) return '#ff5252';
    if (count >= 2) return '#fdd835';
    return '#66bb6a';
  };

  const getSeverityLabel = (count) => {
    if (count >= 5) return 'Severe';
    if (count >= 2) return 'Moderate';
    return 'Minor';
  };

  const handleRecenter = () => {
    if (mapRef.current && potholes.length > 0) {
      const bounds = L.latLngBounds(potholes.map(p => [p.lat, p.lon]));
      mapRef.current.fitBounds(bounds, { padding: [50, 50] });
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-amber-50 via-orange-50 to-yellow-50 relative overflow-hidden">
      {/* Decorative orbs */}
      <div className="absolute top-10 left-10 w-96 h-96 bg-gradient-to-br from-amber-200/20 to-orange-200/20 rounded-full blur-3xl"></div>
      <div className="absolute top-40 right-20 w-80 h-80 bg-gradient-to-br from-yellow-200/20 to-amber-200/20 rounded-full blur-3xl"></div>
      <div className="absolute bottom-20 left-1/4 w-72 h-72 bg-gradient-to-br from-orange-200/20 to-red-200/20 rounded-full blur-3xl"></div>

      <div className="pt-28 px-6 max-w-7xl mx-auto pb-12 relative z-10">
        {/* Page Title Section */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
          className="mb-10"
        >
          <h1 className="text-5xl md:text-6xl font-bold mb-2 bg-gradient-to-r from-amber-600 via-orange-500 to-yellow-600 bg-clip-text text-transparent font-serif">
            Civilian Potholes Map
          </h1>
          <div className="w-24 h-1 bg-gradient-to-r from-amber-500 to-orange-500 rounded-full mb-4"></div>
          <p className="text-lg text-gray-700">Live pothole reporting visualized across the city</p>
        </motion.div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Map Section - Takes 2/3 on large screens */}
          <div className="lg:col-span-2">
            <div className="bg-white/70 backdrop-blur-sm p-6 rounded-3xl shadow-xl border border-white/50 relative">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-bold text-gray-900">Live Map</h3>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-500">{potholes.length} locations</span>
                  {isLoading && (
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-amber-500 border-t-transparent"></div>
                  )}
                </div>
              </div>

              {/* Map Container */}
              <div className="relative h-[600px] md:h-[70vh] rounded-2xl overflow-hidden border border-slate-300 shadow-lg">
                <MapContainer
                  center={[center.lat, center.lng]}
                  zoom={potholes.length > 0 ? 13 : 12}
                  style={{ width: '100%', height: '100%' }}
                  ref={mapRef}
                >
                  <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  />
                  {potholes.map((pothole, idx) => (
                    <Marker
                      key={idx}
                      position={[pothole.lat, pothole.lon]}
                      icon={createMarkerIcon(pothole.potholeCount)}
                    >
                      <Popup>
                        <div className="text-sm">
                          <p className="font-bold">Potholes: {pothole.potholeCount}</p>
                          <p className="text-xs text-gray-600">Severity: {getSeverityLabel(pothole.potholeCount)}</p>
                          <p className="text-xs text-gray-600">Status: {pothole.status}</p>
                          <p className="text-xs text-gray-600">Grid: {pothole.gridId}</p>
                        </div>
                      </Popup>
                    </Marker>
                  ))}
                </MapContainer>

                {/* Control Buttons */}
                <div className="absolute bottom-6 right-6 flex flex-col gap-3 z-[400]">
                  <button
                    onClick={handleRecenter}
                    className="bg-white text-gray-700 p-3 rounded-lg shadow-lg hover:bg-gray-50 transition flex items-center justify-center"
                    title="Recenter map"
                  >
                    <RefreshCw size={18} />
                  </button>
                  <button
                    onClick={fetchPotholes}
                    disabled={isLoading}
                    className="bg-orange-500 text-white p-3 rounded-lg shadow-lg hover:bg-orange-600 transition flex items-center justify-center disabled:opacity-50"
                    title="Refresh data"
                  >
                    <MapPin size={18} />
                  </button>
                </div>

                {/* Legend */}
                <div className="absolute bottom-6 left-6 bg-white/90 backdrop-blur p-4 rounded-lg shadow-lg z-[400]">
                  <h4 className="font-semibold text-gray-900 mb-2 text-sm">Severity Legend</h4>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full" style={{ backgroundColor: '#ff5252' }}></div>
                      <span className="text-xs text-gray-700">Severe (≥5)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full" style={{ backgroundColor: '#fdd835' }}></div>
                      <span className="text-xs text-gray-700">Moderate (2-4)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full" style={{ backgroundColor: '#66bb6a' }}></div>
                      <span className="text-xs text-gray-700">Minor (0-1)</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Sidebar - Stats & List */}
          <div className="flex flex-col gap-6">
            {/* Pothole Locations Card */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="bg-white/70 backdrop-blur-sm p-6 rounded-3xl shadow-xl border border-white/50"
            >
              <button
                onClick={() => setIsListExpanded(!isListExpanded)}
                className="w-full flex items-center justify-between mb-4 group"
              >
                <h3 className="text-xl font-bold text-gray-900">Pothole Locations</h3>
                {isListExpanded ? (
                  <ChevronUp className="text-orange-500 group-hover:text-orange-600 transition" />
                ) : (
                  <ChevronDown className="text-gray-400 group-hover:text-orange-500 transition" />
                )}
              </button>

              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="text-center p-3 bg-gradient-to-br from-red-50 to-red-100 rounded-lg border border-red-200">
                  <p className="text-2xl font-bold text-red-600">{potholes.filter(p => p.potholeCount >= 5).length}</p>
                  <p className="text-xs text-red-700 font-medium">Severe</p>
                </div>
                <div className="text-center p-3 bg-gradient-to-br from-yellow-50 to-yellow-100 rounded-lg border border-yellow-200">
                  <p className="text-2xl font-bold text-yellow-600">{potholes.filter(p => p.potholeCount >= 2 && p.potholeCount < 5).length}</p>
                  <p className="text-xs text-yellow-700 font-medium">Moderate</p>
                </div>
                <div className="text-center p-3 bg-gradient-to-br from-green-50 to-green-100 rounded-lg border border-green-200">
                  <p className="text-2xl font-bold text-green-600">{potholes.filter(p => p.potholeCount < 2).length}</p>
                  <p className="text-xs text-green-700 font-medium">Minor</p>
                </div>
              </div>

              <AnimatePresence>
                {isListExpanded && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="border-t border-gray-200 pt-4 max-h-64 overflow-y-auto"
                  >
                    {potholes.length > 0 ? (
                      <ul className="space-y-2">
                        {potholes.map((p, idx) => (
                          <li key={idx} className="text-sm p-2 bg-gray-50 rounded-lg border border-gray-200 hover:bg-gray-100 transition">
                            <div className="font-medium text-gray-900">Grid {p.gridId}</div>
                            <div className="text-xs text-gray-600">Count: {p.potholeCount} • Status: {p.status}</div>
                            <div className="text-xs text-gray-500">{p.lat.toFixed(4)}, {p.lon.toFixed(4)}</div>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-gray-500 text-center py-4">No potholes reported yet</p>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>

            {/* Statistics Card */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="bg-white/70 backdrop-blur-sm p-6 rounded-3xl shadow-xl border border-white/50"
            >
              <h3 className="text-xl font-bold text-gray-900 mb-4">Statistics</h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center p-3 bg-gradient-to-r from-blue-50 to-blue-100 rounded-lg border border-blue-200">
                  <span className="text-gray-700 font-medium">Total Locations</span>
                  <span className="text-2xl font-bold text-blue-600">{potholes.length}</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-gradient-to-r from-purple-50 to-purple-100 rounded-lg border border-purple-200">
                  <span className="text-gray-700 font-medium">Total Potholes</span>
                  <span className="text-2xl font-bold text-purple-600">{potholes.reduce((sum, p) => sum + p.potholeCount, 0)}</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-gradient-to-r from-orange-50 to-orange-100 rounded-lg border border-orange-200">
                  <span className="text-gray-700 font-medium">Pending</span>
                  <span className="text-2xl font-bold text-orange-600">{potholes.filter(p => p.status === 'pending').length}</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-gradient-to-r from-green-50 to-green-100 rounded-lg border border-green-200">
                  <span className="text-gray-700 font-medium">Resolved</span>
                  <span className="text-2xl font-bold text-green-600">{potholes.filter(p => p.status === 'resolved').length}</span>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PotholesMap;
