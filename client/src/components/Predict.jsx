import React, { useState } from 'react';
import Squares from './Squares';
import Dock from './Dock';
import ShinyText from './ShinyText';
import { VscHome, VscGraphLine, VscInfo, VscGithubInverted } from 'react-icons/vsc';
import { useNavigate } from 'react-router-dom';

function Predict() {
  const navigate = useNavigate();
  
  const [formData, setFormData] = useState({
    elevation: '',
    roadDensity: '',
    rainMm: '',
    rainPast3h: '',
    drainWaterLevel: '',
    soilMoisture: '',
    hourOfDay: '',
    month: '',
    dayOfWeek: ''
  });

  const [prediction, setPrediction] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const dockItems = [
    { icon: <VscHome size={24} />, label: 'Home', onClick: () => navigate('/') },
    { icon: <VscGraphLine size={24} />, label: 'Predict', onClick: () => window.scrollTo({ top: 0, behavior: 'smooth' }) },
    { icon: <VscInfo size={24} />, label: 'Info', onClick: () => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }) },
    { icon: <VscGithubInverted size={24} />, label: 'GitHub', onClick: () => window.open('https://github.com/JUGADU-GEEKS/DelhiFlow', '_blank') },
  ];

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handlePredict = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    
    // Simulate API call - Replace this with actual API endpoint later
    setTimeout(() => {
      const risks = ['Low', 'Medium', 'High'];
      const randomRisk = risks[Math.floor(Math.random() * risks.length)];
      setPrediction({
        risk: randomRisk,
        confidence: (Math.random() * 30 + 70).toFixed(1) // Random confidence between 70-100%
      });
      setIsLoading(false);
    }, 1500);
  };

  const handleReset = () => {
    setFormData({
      elevation: '',
      roadDensity: '',
      rainMm: '',
      rainPast3h: '',
      drainWaterLevel: '',
      soilMoisture: '',
      hourOfDay: '',
      month: '',
      dayOfWeek: ''
    });
    setPrediction(null);
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
            text="Flood Risk Predictor"
            disabled={false}
            speed={3}
            className="text-5xl md:text-6xl lg:text-7xl font-bold leading-tight mb-6"
          />
          <p className="text-white/80 text-lg md:text-xl leading-relaxed max-w-3xl mx-auto font-light">
            Enter the environmental parameters below to predict flood risk for your location
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Input Form Section */}
          <div className="lg:col-span-2">
            <div className="bg-purple-900/20 backdrop-blur-xl border border-purple-400/30 rounded-3xl p-8 shadow-2xl shadow-purple-900/20">
              <h2 className="text-white text-2xl font-bold mb-6 flex items-center gap-3">
                <div className="bg-gradient-to-br from-purple-400 to-fuchsia-500 w-10 h-10 rounded-xl flex items-center justify-center shadow-lg shadow-purple-500/30">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                Input Parameters
              </h2>
              
              <form onSubmit={handlePredict} className="space-y-6">
                
                {/* Geographical Parameters */}
                <div className="space-y-4">
                  <h3 className="text-white/70 text-sm font-semibold uppercase tracking-wider">Geographical Data</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-white/90 text-sm font-medium mb-2 block">Elevation (meters)</label>
                      <input
                        type="number"
                        name="elevation"
                        value={formData.elevation}
                        onChange={handleInputChange}
                        step="0.1"
                        required
                        placeholder="e.g., 215.0"
                        className="w-full bg-black/30 border border-purple-400/30 rounded-xl px-4 py-3 text-white placeholder-white/40 focus:outline-none focus:border-purple-400/60 focus:ring-2 focus:ring-purple-400/20 transition-all"
                      />
                    </div>
                    
                    <div>
                      <label className="text-white/90 text-sm font-medium mb-2 block">Road Density (0-1)</label>
                      <input
                        type="number"
                        name="roadDensity"
                        value={formData.roadDensity}
                        onChange={handleInputChange}
                        step="0.01"
                        min="0"
                        max="1"
                        required
                        placeholder="e.g., 0.7"
                        className="w-full bg-black/30 border border-purple-400/30 rounded-xl px-4 py-3 text-white placeholder-white/40 focus:outline-none focus:border-purple-400/60 focus:ring-2 focus:ring-purple-400/20 transition-all"
                      />
                    </div>
                  </div>
                </div>

                {/* Weather Parameters */}
                <div className="space-y-4">
                  <h3 className="text-white/70 text-sm font-semibold uppercase tracking-wider">Weather Conditions</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-white/90 text-sm font-medium mb-2 block">Rainfall (mm)</label>
                      <input
                        type="number"
                        name="rainMm"
                        value={formData.rainMm}
                        onChange={handleInputChange}
                        step="0.1"
                        min="0"
                        required
                        placeholder="e.g., 12.0"
                        className="w-full bg-black/30 border border-purple-400/30 rounded-xl px-4 py-3 text-white placeholder-white/40 focus:outline-none focus:border-purple-400/60 focus:ring-2 focus:ring-purple-400/20 transition-all"
                      />
                    </div>
                    
                    <div>
                      <label className="text-white/90 text-sm font-medium mb-2 block">Rain Past 3h (mm)</label>
                      <input
                        type="number"
                        name="rainPast3h"
                        value={formData.rainPast3h}
                        onChange={handleInputChange}
                        step="0.1"
                        min="0"
                        required
                        placeholder="e.g., 5.0"
                        className="w-full bg-black/30 border border-purple-400/30 rounded-xl px-4 py-3 text-white placeholder-white/40 focus:outline-none focus:border-purple-400/60 focus:ring-2 focus:ring-purple-400/20 transition-all"
                      />
                    </div>
                  </div>
                </div>

                {/* Hydrological Parameters */}
                <div className="space-y-4">
                  <h3 className="text-white/70 text-sm font-semibold uppercase tracking-wider">Hydrological Data</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-white/90 text-sm font-medium mb-2 block">Drain Water Level (meters)</label>
                      <input
                        type="number"
                        name="drainWaterLevel"
                        value={formData.drainWaterLevel}
                        onChange={handleInputChange}
                        step="0.1"
                        min="0"
                        required
                        placeholder="e.g., 0.8"
                        className="w-full bg-black/30 border border-purple-400/30 rounded-xl px-4 py-3 text-white placeholder-white/40 focus:outline-none focus:border-purple-400/60 focus:ring-2 focus:ring-purple-400/20 transition-all"
                      />
                    </div>
                    
                    <div>
                      <label className="text-white/90 text-sm font-medium mb-2 block">Soil Moisture (0-1)</label>
                      <input
                        type="number"
                        name="soilMoisture"
                        value={formData.soilMoisture}
                        onChange={handleInputChange}
                        step="0.01"
                        min="0"
                        max="1"
                        required
                        placeholder="e.g., 0.3"
                        className="w-full bg-black/30 border border-purple-400/30 rounded-xl px-4 py-3 text-white placeholder-white/40 focus:outline-none focus:border-purple-400/60 focus:ring-2 focus:ring-purple-400/20 transition-all"
                      />
                    </div>
                  </div>
                </div>

                {/* Time Parameters */}
                <div className="space-y-4">
                  <h3 className="text-white/70 text-sm font-semibold uppercase tracking-wider">Time Information</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="text-white/90 text-sm font-medium mb-2 block">Hour of Day (0-23)</label>
                      <input
                        type="number"
                        name="hourOfDay"
                        value={formData.hourOfDay}
                        onChange={handleInputChange}
                        min="0"
                        max="23"
                        required
                        placeholder="e.g., 14"
                        className="w-full bg-black/30 border border-purple-400/30 rounded-xl px-4 py-3 text-white placeholder-white/40 focus:outline-none focus:border-purple-400/60 focus:ring-2 focus:ring-purple-400/20 transition-all"
                      />
                    </div>
                    
                    <div>
                      <label className="text-white/90 text-sm font-medium mb-2 block">Month (1-12)</label>
                      <input
                        type="number"
                        name="month"
                        value={formData.month}
                        onChange={handleInputChange}
                        min="1"
                        max="12"
                        required
                        placeholder="e.g., 8"
                        className="w-full bg-black/30 border border-purple-400/30 rounded-xl px-4 py-3 text-white placeholder-white/40 focus:outline-none focus:border-purple-400/60 focus:ring-2 focus:ring-purple-400/20 transition-all"
                      />
                    </div>

                    <div>
                      <label className="text-white/90 text-sm font-medium mb-2 block">Day of Week (0-6)</label>
                      <input
                        type="number"
                        name="dayOfWeek"
                        value={formData.dayOfWeek}
                        onChange={handleInputChange}
                        min="0"
                        max="6"
                        required
                        placeholder="e.g., 2"
                        className="w-full bg-black/30 border border-purple-400/30 rounded-xl px-4 py-3 text-white placeholder-white/40 focus:outline-none focus:border-purple-400/60 focus:ring-2 focus:ring-purple-400/20 transition-all"
                      />
                      <p className="text-white/50 text-xs mt-1">0=Mon, 6=Sun</p>
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex flex-col sm:flex-row gap-4 pt-4">
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="flex-1 bg-gradient-to-r from-purple-500 to-fuchsia-600 text-white px-8 py-4 rounded-xl font-semibold hover:from-purple-600 hover:to-fuchsia-700 hover:scale-105 transition-all duration-200 shadow-lg shadow-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                  >
                    {isLoading ? (
                      <span className="flex items-center justify-center gap-2">
                        <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Analyzing...
                      </span>
                    ) : 'Predict Flood Risk'}
                  </button>
                  <button
                    type="button"
                    onClick={handleReset}
                    className="flex-1 bg-black/40 border-2 border-purple-400/30 text-white px-8 py-4 rounded-xl font-semibold hover:bg-black/60 hover:border-purple-400/50 hover:scale-105 transition-all duration-200"
                  >
                    Reset Form
                  </button>
                </div>
              </form>
            </div>
          </div>

          {/* Prediction Result Section */}
          <div className="lg:col-span-1">
            <div className={`bg-purple-900/20 backdrop-blur-xl border ${prediction ? getRiskBorderColor(prediction.risk) : 'border-purple-400/30'} rounded-3xl p-8 shadow-2xl shadow-purple-900/20 sticky top-28 transition-all duration-500`}>
              <h2 className="text-white text-2xl font-bold mb-6 flex items-center gap-3">
                <div className={`bg-gradient-to-br ${prediction ? getRiskColor(prediction.risk) : 'from-purple-400 to-fuchsia-500'} w-10 h-10 rounded-xl flex items-center justify-center shadow-lg transition-all duration-500`}>
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                Prediction Result
              </h2>

              {!prediction ? (
                <div className="text-center py-12">
                  <div className="bg-gradient-to-br from-purple-400 to-fuchsia-500 w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg shadow-purple-500/30 animate-pulse">
                    <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                  <p className="text-white/60 font-light">
                    Fill in the parameters and click "Predict Flood Risk" to see the results
                  </p>
                </div>
              ) : (
                <div className="space-y-6 animate-fadeIn">
                  {/* Risk Level */}
                  <div className="text-center">
                    <p className="text-white/70 text-sm font-medium mb-3">Flood Risk Level</p>
                    <div className={`bg-gradient-to-r ${getRiskColor(prediction.risk)} text-white text-4xl font-bold py-6 px-8 rounded-2xl shadow-lg uppercase tracking-wider`}>
                      {prediction.risk}
                    </div>
                  </div>

                  {/* Confidence Score */}
                  <div className="bg-black/30 rounded-2xl p-6 border border-purple-400/20">
                    <div className="flex justify-between items-center mb-3">
                      <span className="text-white/70 text-sm font-medium">Confidence</span>
                      <span className="text-white font-bold text-lg">{prediction.confidence}%</span>
                    </div>
                    <div className="w-full bg-black/50 rounded-full h-3 overflow-hidden">
                      <div 
                        className={`bg-gradient-to-r ${getRiskColor(prediction.risk)} h-full rounded-full transition-all duration-1000 ease-out`}
                        style={{ width: `${prediction.confidence}%` }}
                      ></div>
                    </div>
                  </div>

                  {/* Risk Description */}
                  <div className="bg-black/30 rounded-2xl p-6 border border-purple-400/20">
                    <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Recommendation
                    </h3>
                    <p className="text-white/70 text-sm leading-relaxed font-light">
                      {prediction.risk === 'Low' && "Minimal flood risk detected. Normal activities can proceed, but stay aware of weather conditions."}
                      {prediction.risk === 'Medium' && "Moderate flood risk detected. Monitor weather updates and prepare for potential water accumulation."}
                      {prediction.risk === 'High' && "High flood risk detected! Take immediate precautions, avoid low-lying areas, and follow local emergency guidelines."}
                    </p>
                  </div>

                  {/* Alert Icon */}
                  {prediction.risk === 'High' && (
                    <div className="bg-red-500/10 border border-red-400/30 rounded-2xl p-4 flex items-start gap-3 animate-pulse">
                      <svg className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      <p className="text-red-300 text-sm font-medium">Emergency alert: Severe flood conditions expected!</p>
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
              How It Works
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="space-y-3">
                <div className="bg-gradient-to-br from-purple-400 to-fuchsia-500 w-12 h-12 rounded-xl flex items-center justify-center shadow-lg shadow-purple-500/30">
                  <span className="text-white text-xl font-bold">1</span>
                </div>
                <h3 className="text-white font-semibold text-lg">Input Data</h3>
                <p className="text-white/70 text-sm leading-relaxed font-light">
                  Enter environmental parameters including elevation, rainfall, drainage levels, and time information.
                </p>
              </div>

              <div className="space-y-3">
                <div className="bg-gradient-to-br from-fuchsia-400 to-pink-500 w-12 h-12 rounded-xl flex items-center justify-center shadow-lg shadow-fuchsia-500/30">
                  <span className="text-white text-xl font-bold">2</span>
                </div>
                <h3 className="text-white font-semibold text-lg">AI Analysis</h3>
                <p className="text-white/70 text-sm leading-relaxed font-light">
                  Our Random Forest model analyzes patterns across multiple variables to assess flood probability.
                </p>
              </div>

              <div className="space-y-3">
                <div className="bg-gradient-to-br from-pink-400 to-purple-500 w-12 h-12 rounded-xl flex items-center justify-center shadow-lg shadow-pink-500/30">
                  <span className="text-white text-xl font-bold">3</span>
                </div>
                <h3 className="text-white font-semibold text-lg">Get Results</h3>
                <p className="text-white/70 text-sm leading-relaxed font-light">
                  Receive instant risk classification (Low/Medium/High) with confidence scores and recommendations.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Predict;
