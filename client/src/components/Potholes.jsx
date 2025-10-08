import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Squares from './Squares';
import Dock from './Dock';
import ShinyText from './ShinyText';
import { VscHome, VscGithubInverted, VscRefresh } from 'react-icons/vsc';

function Potholes() {
  const navigate = useNavigate();
  const API_BASE = import.meta.env.VITE_API_BASE || window.__API_BASE__ || 'http://127.0.0.1:8000';

  const [file, setFile] = useState(null);
  const [imageURL, setImageURL] = useState(null);
  const [detections, setDetections] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const imgRef = useRef(null);
  const canvasRef = useRef(null);

  const dockItems = [
    { icon: <VscHome size={24} />, label: 'Home', onClick: () => navigate('/') },
    { icon: <span className="text-white text-base">Predict</span>, label: 'Predict', onClick: () => navigate('/test-predict') },
    { icon: <VscRefresh size={24} />, label: 'Reset', onClick: () => handleReset() },
    { icon: <VscGithubInverted size={24} />, label: 'GitHub', onClick: () => window.open('https://github.com/JUGADU-GEEKS/DelhiFlow', '_blank') },
  ];

  useEffect(() => {
    return () => {
      if (imageURL) URL.revokeObjectURL(imageURL);
    };
  }, [imageURL]);

  useEffect(() => {
    drawDetections();
  }, [imageURL, detections]);

  const handleReset = () => {
    setFile(null);
    if (imageURL) URL.revokeObjectURL(imageURL);
    setImageURL(null);
    setDetections([]);
    setError(null);
    clearCanvas();
  };

  const onPickFile = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setError(null);
    setFile(f);
    if (imageURL) URL.revokeObjectURL(imageURL);
    setImageURL(URL.createObjectURL(f));
    setDetections([]);
  };

  const detectPotholes = async () => {
    if (!file) {
      setError('Select or capture an image first.');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append('image', file);
      // Add optional params if your backend expects them:
      // fd.append('model', 'yolov8');

      const resp = await fetch(`${API_BASE.replace(/\/$/, '')}/potholes/detect`, {
        method: 'POST',
        body: fd,
      });

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${text || 'Detection API error'}`);
      }

      const data = await resp.json();
      // Expected shape: { detections: [{x, y, width, height, score, label}], image_size: {width, height} }
      setDetections(Array.isArray(data?.detections) ? data.detections : []);
    } catch (e) {
      console.error(e);
      setError(e.message || 'Failed to detect potholes.');
    } finally {
      setIsLoading(false);
    }
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  };

  const drawDetections = () => {
    const img = imgRef.current;
    const canvas = canvasRef.current;
    if (!img || !canvas || !imageURL) return;

    // Ensure canvas matches displayed image size
    const rect = img.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // If the backend boxes are relative to original image size, scale them.
    const scaleX = canvas.width / img.naturalWidth;
    const scaleY = canvas.height / img.naturalHeight;

    detections.forEach((d) => {
      const x = (d.x ?? d.left ?? 0) * (d.relative ? canvas.width : scaleX);
      const y = (d.y ?? d.top ?? 0) * (d.relative ? canvas.height : scaleY);
      const w = (d.width ?? d.w ?? 0) * (d.relative ? canvas.width : scaleX);
      const h = (d.height ?? d.h ?? 0) * (d.relative ? canvas.height : scaleY);

      // fallback if x/y are absolute in original pixels
      const X = d.relative ? x : (d.x ?? d.left ?? 0) * scaleX;
      const Y = d.relative ? y : (d.y ?? d.top ?? 0) * scaleY;
      const W = d.relative ? w : (d.width ?? d.w ?? 0) * scaleX;
      const H = d.relative ? h : (d.height ?? d.h ?? 0) * scaleY;

      // Style
      ctx.lineWidth = 3;
      ctx.strokeStyle = 'rgba(236, 72, 153, 0.95)'; // pink-500
      ctx.fillStyle = 'rgba(236, 72, 153, 0.18)';

      // Box
      ctx.beginPath();
      ctx.rect(X, Y, W, H);
      ctx.fill();
      ctx.stroke();

      // Label
      const label = `${d.label || 'Pothole'} ${d.score ? Math.round(d.score * 100) + '%' : ''}`.trim();
      ctx.font = '12px Poppins, sans-serif';
      ctx.fillStyle = 'rgba(17, 24, 39, 0.9)'; // gray-900
      const padding = 4;
      const textWidth = ctx.measureText(label).width + padding * 2;
      const textHeight = 16 + padding * 2;
      ctx.fillRect(X, Math.max(0, Y - textHeight), textWidth, textHeight);
      ctx.fillStyle = 'white';
      ctx.fillText(label, X + padding, Math.max(10, Y - textHeight / 2));
    });
  };

  const totalPotholes = detections.length;
  const severeCount = detections.filter(d => (d.score ?? 0) >= 0.6).length;

  return (
    <div className="relative w-full min-h-screen overflow-x-hidden overflow-y-auto font-['Poppins',sans-serif]" style={{ background: '#000000' }}>
      {/* Background squares */}
      <div className="absolute inset-0 z-0">
        <Squares
          speed={0.6}
          squareSize={40}
          direction="diagonal"
          borderColor="#9a69b5"
          hoverFillColor="#222222"
        />
      </div>

      {/* Dock */}
      <div className="fixed top-0 left-0 right-0 z-50 flex justify-center pt-4">
        <Dock
          items={dockItems}
          panelHeight={68}
          baseItemSize={50}
          magnification={70}
          className="bg-purple-900/20 backdrop-blur-xl"
        />
      </div>

      {/* Content */}
      <div className="relative z-10 px-4 py-24 max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <ShinyText
            text="Pothole Detection"
            disabled={false}
            speed={3}
            className="text-4xl md:text-6xl font-bold leading-tight mb-4"
          />
          <p className="text-white/70 text-lg max-w-2xl mx-auto font-light">
            Upload a road image or capture from your camera. We’ll detect potholes and highlight them.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Controls Card */}
          <div className="bg-purple-900/20 backdrop-blur-xl border border-purple-400/30 rounded-3xl p-8 shadow-2xl shadow-purple-900/20">
            <h2 className="text-white text-2xl font-bold mb-6 flex items-center gap-3">
              <div className="bg-gradient-to-br from-purple-400 to-fuchsia-500 w-10 h-10 rounded-xl flex items-center justify-center shadow-lg shadow-purple-500/30">
                <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" d="M3 7h4l2-3h6l2 3h4v12H3V7z" />
                  <circle cx="12" cy="13" r="3" />
                </svg>
              </div>
              Input
            </h2>

            <div className="space-y-4">
              <label className="block">
                <span className="text-white/80 text-sm">Choose Image</span>
                <input
                  type="file"
                  accept="image/*"
                  onChange={onPickFile}
                  className="mt-2 block w-full text-sm text-white/80 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-purple-600/20 file:text-white hover:file:bg-purple-600/30"
                />
              </label>

              <label className="block">
                <span className="text-white/80 text-sm">Capture (mobile)</span>
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  onChange={onPickFile}
                  className="mt-2 block w-full text-sm text-white/80 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-fuchsia-600/20 file:text-white hover:file:bg-fuchsia-600/30"
                />
              </label>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={detectPotholes}
                  disabled={!file || isLoading}
                  className="bg-gradient-to-r from-fuchsia-500 to-pink-600 text-white px-6 py-3 rounded-xl font-semibold hover:from-fuchsia-600 hover:to-pink-700 transition-all duration-200 shadow-lg shadow-fuchsia-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? 'Detecting…' : 'Detect Potholes'}
                </button>
                <button
                  onClick={handleReset}
                  className="bg-purple-600/20 backdrop-blur-md border border-purple-400/30 text-white px-6 py-3 rounded-xl font-semibold hover:bg-purple-600/30 transition-all duration-200"
                >
                  Reset
                </button>
              </div>

              {error && (
                <div className="bg-red-500/10 border border-red-400/30 rounded-2xl p-4">
                  <p className="text-red-300 text-sm">{error}</p>
                  <p className="text-white/50 text-xs mt-1">
                    Ensure your backend exposes POST {API_BASE.replace(/\/$/, '')}/potholes/detect returning JSON with boxes.
                  </p>
                </div>
              )}

              {detections.length > 0 && (
                <div className="bg-black/30 rounded-2xl p-4 border border-purple-400/20">
                  <h3 className="text-white font-semibold mb-2">Summary</h3>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-white/70">Total:</span>
                      <span className="text-white ml-2">{totalPotholes}</span>
                    </div>
                    <div>
                      <span className="text-white/70">High confidence (≥60%):</span>
                      <span className="text-white ml-2">{severeCount}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Preview Card */}
          <div className="bg-purple-900/20 backdrop-blur-xl border border-purple-400/30 rounded-3xl p-4 md:p-6 lg:p-8 shadow-2xl shadow-purple-900/20">
            <h2 className="text-white text-2xl font-bold mb-4 flex items-center gap-3">
              <div className="bg-gradient-to-br from-pink-400 to-fuchsia-500 w-10 h-10 rounded-xl flex items-center justify-center shadow-lg shadow-pink-500/30">
                <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" d="M15 10l4.553-2.276A2 2 0 0122 9.553V18a2 2 0 01-2 2H4a2 2 0 01-2-2V6.447A2 2 0 014.447 5L9 7" />
                  <rect x="7" y="9" width="10" height="8" rx="1" />
                </svg>
              </div>
              Preview
            </h2>

            <div className="relative w-full aspect-[16/10] bg-black/30 border border-purple-400/20 rounded-2xl overflow-hidden flex items-center justify-center">
              {!imageURL ? (
                <div className="text-white/60 text-sm p-6 text-center">
                  Upload or capture a road image to see detections here.
                </div>
              ) : (
                <>
                  <img
                    ref={imgRef}
                    src={imageURL}
                    alt="preview"
                    className="max-h-full max-w-full object-contain"
                    onLoad={() => drawDetections()}
                  />
                  <canvas
                    ref={canvasRef}
                    className="absolute inset-0 pointer-events-none"
                  />
                </>
              )}
            </div>

            {detections.length > 0 && (
              <div className="mt-4 bg-black/30 rounded-2xl p-4 border border-purple-400/20 max-h-52 overflow-auto">
                <h3 className="text-white font-semibold mb-2">Detections</h3>
                <ul className="space-y-1 text-sm">
                  {detections.map((d, i) => (
                    <li key={i} className="text-white/80">
                      #{i + 1} • {d.label || 'Pothole'} • {d.score ? `${Math.round(d.score * 100)}%` : '—'}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Potholes;
