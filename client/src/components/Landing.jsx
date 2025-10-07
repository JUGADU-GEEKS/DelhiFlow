import React from 'react'
import TrueFocus from './TrueFocus';
import Hyperspeed from './Hyperspeed';

function Landing() {
  return (
    <div className="relative w-full h-screen overflow-hidden" style={{ background: '#1a1a2e' }}>
      {/* Hyperspeed background */}
      <div className="absolute inset-0 z-0">
        <Hyperspeed
          effectOptions={{
            onSpeedUp: () => { },
            onSlowDown: () => { },
            distortion: 'turbulentDistortion',
            length: 400,
            roadWidth: 10,
            islandWidth: 2,
            lanesPerRoad: 4,
            fov: 90,
            fovSpeedUp: 150,
            speedUp: 2,
            carLightsFade: 0.4,
            totalSideLightSticks: 20,
            lightPairsPerRoadWay: 40,
            shoulderLinesWidthPercentage: 0.05,
            brokenLinesWidthPercentage: 0.1,
            brokenLinesLengthPercentage: 0.5,
            lightStickWidth: [0.12, 0.5],
            lightStickHeight: [1.3, 1.7],
            movingAwaySpeed: [60, 80],
            movingCloserSpeed: [-120, -160],
            carLightsLength: [400 * 0.03, 400 * 0.2],
            carLightsRadius: [0.05, 0.14],
            carWidthPercentage: [0.3, 0.5],
            carShiftX: [-0.8, 0.8],
            carFloorSeparation: [0, 5],
            colors: {
              roadColor: 0x080808,
              islandColor: 0x0a0a0a,
              background: 0x000000,
              shoulderLines: 0xFFFFFF,
              brokenLines: 0xFFFFFF,
              leftCars: [0xD856BF, 0x6750A2, 0xC247AC],
              rightCars: [0x03B3C3, 0x0E5EA5, 0x324555],
              sticks: 0x03B3C3,
            }
          }}
        />
      </div>
      
      {/* Navigation Bar - Centered with rounded background */}
      <div className="relative z-20 flex justify-center pt-8">
        <nav className="bg-gray-800/60 backdrop-blur-md border border-gray-700/50 rounded-full px-8 py-4 flex items-center justify-between min-w-[600px]">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="black" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M2 17L12 22L22 17" stroke="black" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M2 12L12 17L22 12" stroke="black" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <span className="text-white text-lg font-medium">React Bits</span>
          </div>
          <div className="flex items-center space-x-6">
            <a href="#" className="text-white hover:text-gray-300 transition-colors font-medium">Home</a>
            <a href="#" className="text-white hover:text-gray-300 transition-colors font-medium">Docs</a>
          </div>
        </nav>
      </div>

      {/* New Background Button - Centered */}
      <div className="relative z-20 flex justify-center mt-12">
        <button className="bg-gray-800/80 backdrop-blur-sm border border-gray-600/50 text-white px-5 py-2.5 rounded-full text-sm hover:bg-gray-700/80 transition-all duration-200 flex items-center space-x-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" stroke="currentColor" strokeWidth="2"/>
            <circle cx="8.5" cy="8.5" r="1.5" stroke="currentColor" strokeWidth="2"/>
            <path d="M21 15L16 10L5 21" stroke="currentColor" strokeWidth="2"/>
          </svg>
          <span>New Background</span>
        </button>
      </div>

      {/* Main Content */}
      <div className="relative z-10 flex flex-col items-center justify-center flex-1 px-4 mt-8">

        {/* Main Heading */}
        <div className="text-center mb-16 max-w-6xl">
          <h1 className="text-white text-5xl md:text-6xl lg:text-7xl xl:text-8xl font-bold leading-[0.9] tracking-tight">
            Click & hold to see the real{' '}
            <span className="block mt-2">magic of hyperspeed!</span>
          </h1>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-6">
          <button className="bg-white text-black px-10 py-4 rounded-full font-semibold hover:bg-gray-100 transition-colors text-base">
            Get Started
          </button>
          <button className="bg-gray-800/70 backdrop-blur-sm border border-gray-600/50 text-white px-10 py-4 rounded-full font-semibold hover:bg-gray-700/70 transition-colors text-base">
            Learn More
          </button>
        </div>
      </div>

      {/* Demo Content Toggle */}
      <div className="absolute bottom-8 right-8 z-20 flex items-center space-x-3">
        <span className="text-gray-400 text-sm font-medium">Demo Content</span>
        <div className="relative">
          <input type="checkbox" className="sr-only" defaultChecked />
          <div className="w-11 h-6 bg-gray-700 rounded-full shadow-inner border border-gray-600"></div>
          <div className="absolute w-5 h-5 bg-white rounded-full shadow-sm top-0.5 right-0.5 transition-all duration-200 ease-in-out"></div>
        </div>
      </div>
    </div>
  )
}

export default Landing
