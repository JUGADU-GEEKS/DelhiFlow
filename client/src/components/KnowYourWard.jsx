import React, { useEffect, useState } from 'react';
import Squares from './Squares';
import Dock from './Dock';
import ShinyText from './ShinyText';
import { VscHome, VscArchive, VscGithubInverted } from 'react-icons/vsc';
import { useNavigate } from 'react-router-dom';

function KnowYourWard() {
  const navigate = useNavigate();
  const API_BASE = import.meta.env.VITE_API_BASE || window.__API_BASE__ || 'http://127.0.0.1:8000';
  
  const [wards, setWards] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const dockItems = [
    { icon: <VscHome size={24} />, label: 'Home', onClick: () => navigate('/') },
    { icon: <VscArchive size={24} />, label: 'Back', onClick: () => navigate('/heatmap') },
    { icon: <VscGithubInverted size={24} />, label: 'GitHub', onClick: () => window.open('https://github.com/JUGADU-GEEKS/DelhiFlow', '_blank') },
  ];

  useEffect(() => {
    const base = API_BASE?.replace(/\/$/, '') || 'http://127.0.0.1:8000';
    setIsLoading(true);
    setError(null);

    fetch(`${base}/wards/geojson`)
      .then(res => {
        if (!res.ok) {
          throw new Error(`Failed to load wards: ${res.status} ${res.statusText}`);
        }
        return res.json();
      })
      .then(geo => {
        if (!geo || !geo.features || !Array.isArray(geo.features)) {
          throw new Error('Invalid GeoJSON structure');
        }

        // Extract all wards from GeoJSON
        const wardList = geo.features.map(feature => {
          const props = feature.properties || {};
          const wardId = props.Ward_ID !== undefined ? props.Ward_ID : props.Ward_No;
          const wardName = props.Ward_Name || `Ward ${wardId || 'Unknown'}`;
          
          return {
            wardNumber: wardId,
            wardName: wardName,
            originalData: props
          };
        }).filter(ward => ward.wardNumber != null && ward.wardNumber !== undefined);

        // Sort by ward number
        wardList.sort((a, b) => {
          const numA = parseInt(a.wardNumber, 10) || 0;
          const numB = parseInt(b.wardNumber, 10) || 0;
          return numA - numB;
        });

        setWards(wardList);
        setIsLoading(false);
      })
      .catch(err => {
        console.error('Error loading wards:', err);
        setError(`Failed to load ward directory: ${err.message}`);
        setIsLoading(false);
      });
  }, [API_BASE]);

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
            text="Know Your WARD"
            disabled={false}
            speed={3}
            className="text-5xl md:text-6xl lg:text-7xl font-bold leading-tight mb-6"
          />
          <p className="text-white/80 text-lg md:text-xl leading-relaxed max-w-3xl mx-auto font-light">
            Browse all Delhi wards. Find your ward number and name from the complete directory.
          </p>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <div className="text-center">
              <div className="animate-spin h-12 w-12 border-4 border-purple-400 border-t-transparent rounded-full mx-auto mb-4"></div>
              <p className="text-white/60 text-sm font-light">Loading ward directory...</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && !isLoading && (
          <div className="bg-red-500/10 border border-red-400/30 rounded-3xl p-8 text-center">
            <svg className="w-12 h-12 text-red-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p className="text-red-300 font-medium mb-2">Error Loading Wards</p>
            <p className="text-red-300/70 text-sm">{error}</p>
          </div>
        )}

        {/* Ward Cards Grid */}
        {!isLoading && !error && wards.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 lg:gap-8">
            {wards.map((ward, index) => (
              <div
                key={`ward-${ward.wardNumber}-${index}`}
                className="bg-purple-900/20 backdrop-blur-xl border border-purple-400/30 rounded-3xl p-6 hover:bg-purple-900/30 hover:border-purple-400/40 hover:scale-105 transition-all duration-300 shadow-lg shadow-purple-900/20"
              >
                <div className="bg-gradient-to-br from-purple-400 to-fuchsia-500 w-14 h-14 rounded-2xl flex items-center justify-center mb-4 shadow-lg shadow-purple-500/30">
                  <span className="text-white text-xl font-bold">{ward.wardNumber}</span>
                </div>
                <div className="space-y-3">
                  <div>
                    <p className="text-white/70 text-xs font-medium uppercase tracking-wider mb-1">Ward No.</p>
                    <p className="text-white text-2xl font-bold">{ward.wardNumber}</p>
                  </div>
                  <div>
                    <p className="text-white/70 text-xs font-medium uppercase tracking-wider mb-1">Ward Name</p>
                    <p className="text-white/90 text-base font-semibold leading-relaxed">{ward.wardName}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && wards.length === 0 && (
          <div className="text-center py-20">
            <div className="bg-gradient-to-br from-purple-400 to-fuchsia-500 w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg shadow-purple-500/30">
              <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-white/60 font-light mb-2">No wards found</p>
            <p className="text-white/40 text-sm font-light">Unable to load ward directory</p>
          </div>
        )}

        {/* Stats Footer */}
        {!isLoading && !error && wards.length > 0 && (
          <div className="mt-12 text-center">
            <div className="bg-purple-900/20 backdrop-blur-xl border border-purple-400/30 rounded-2xl p-6 inline-block">
              <p className="text-white/70 text-sm font-medium mb-1">Total Wards</p>
              <p className="text-white text-3xl font-bold">{wards.length}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default KnowYourWard;

