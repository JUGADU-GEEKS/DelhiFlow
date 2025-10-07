import React from 'react';
import Squares from './Squares';
import Navbar from './Navbar';
import ShinyText from './ShinyText';

function Landing() {
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

      {/* Navigation Bar */}
      <Navbar />

      {/* Main Content */}
      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen px-4 -mt-24">

        {/* Main Heading */}
        <div className="text-center mb-16 max-w-5xl">
          <ShinyText
            text="Delhi Flow"
            disabled={false}
            speed={3}
            className="text-6xl md:text-7xl lg:text-8xl xl:text-9xl font-bold leading-tight mb-10"
          />
          <p className="text-white/80 text-lg md:text-xl lg:text-2xl leading-relaxed max-w-3xl mx-auto font-light">
            AI meets hydrology to forecast urban floods at hyperlocal precision. 
            Smarter data, safer streets, resilient cities.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center gap-5">
          <button className="bg-white text-black px-10 py-4 rounded-full font-semibold hover:bg-purple-50 hover:scale-105 transition-all duration-200 text-lg shadow-lg shadow-purple-500/20 min-w-[160px]">
            Get Started
          </button>
          <button className="bg-purple-600/20 backdrop-blur-md border-2 border-purple-400/30 text-white px-10 py-4 rounded-full font-semibold hover:bg-purple-600/30 hover:border-purple-400/50 hover:scale-105 transition-all duration-200 text-lg min-w-[160px]">
            Learn More
          </button>
        </div>
      </div>

      {/* About Section */}
      <div className="relative z-10 px-4 py-20">
        <div className="max-w-7xl mx-auto">
          {/* Section Title */}
          <div className="text-center mb-16">
            <h2 className="text-transparent bg-clip-text bg-gradient-to-r from-purple-300 via-fuchsia-400 to-pink-400 text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
              About Delhi Flow
            </h2>
            <p className="text-white/70 text-lg md:text-xl max-w-2xl mx-auto font-light">
              Revolutionizing urban flood forecasting with cutting-edge AI technology
            </p>
          </div>

          {/* Feature Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
            {/* Card 1 */}
            <div className="bg-purple-900/20 backdrop-blur-xl border border-purple-400/30 rounded-3xl p-8 hover:bg-purple-900/30 hover:border-purple-400/40 hover:scale-105 transition-all duration-300 shadow-lg shadow-purple-900/20">
              <div className="bg-gradient-to-br from-purple-400 to-fuchsia-500 w-14 h-14 rounded-2xl flex items-center justify-center mb-6 shadow-lg shadow-purple-500/30">
                <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h3 className="text-white text-xl font-bold mb-4">AI-Powered Predictions</h3>
              <p className="text-white/70 leading-relaxed font-light">
                Advanced machine learning algorithms analyze hydrological data to predict urban floods with unprecedented accuracy and precision.
              </p>
            </div>

            {/* Card 2 */}
            <div className="bg-purple-900/20 backdrop-blur-xl border border-purple-400/30 rounded-3xl p-8 hover:bg-purple-900/30 hover:border-purple-400/40 hover:scale-105 transition-all duration-300 shadow-lg shadow-purple-900/20">
              <div className="bg-gradient-to-br from-fuchsia-400 to-pink-500 w-14 h-14 rounded-2xl flex items-center justify-center mb-6 shadow-lg shadow-fuchsia-500/30">
                <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              <h3 className="text-white text-xl font-bold mb-4">Hyperlocal Precision</h3>
              <p className="text-white/70 leading-relaxed font-light">
                Street-level flood forecasting enables targeted alerts and emergency response, protecting communities at a granular level.
              </p>
            </div>

            {/* Card 3 */}
            <div className="bg-purple-900/20 backdrop-blur-xl border border-purple-400/30 rounded-3xl p-8 hover:bg-purple-900/30 hover:border-purple-400/40 hover:scale-105 transition-all duration-300 shadow-lg shadow-purple-900/20">
              <div className="bg-gradient-to-br from-pink-400 to-purple-500 w-14 h-14 rounded-2xl flex items-center justify-center mb-6 shadow-lg shadow-pink-500/30">
                <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
              <h3 className="text-white text-xl font-bold mb-4">Resilient Cities</h3>
              <p className="text-white/70 leading-relaxed font-light">
                Empowering urban planners and residents with real-time data to build safer, more resilient communities for the future.
              </p>
            </div>
          </div>

          {/* Stats Section */}
          <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="text-center p-6 bg-purple-900/10 backdrop-blur-md border border-purple-400/20 rounded-2xl hover:border-purple-400/30 transition-all duration-300">
              <div className="text-4xl md:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-300 to-fuchsia-400 mb-2">98%</div>
              <div className="text-white/70 text-sm md:text-base font-light">Accuracy Rate</div>
            </div>
            <div className="text-center p-6 bg-purple-900/10 backdrop-blur-md border border-purple-400/20 rounded-2xl hover:border-purple-400/30 transition-all duration-300">
              <div className="text-4xl md:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-fuchsia-300 to-pink-400 mb-2">24/7</div>
              <div className="text-white/70 text-sm md:text-base font-light">Monitoring</div>
            </div>
            <div className="text-center p-6 bg-purple-900/10 backdrop-blur-md border border-purple-400/20 rounded-2xl hover:border-purple-400/30 transition-all duration-300">
              <div className="text-4xl md:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-pink-300 to-purple-400 mb-2">15m</div>
              <div className="text-white/70 text-sm md:text-base font-light">Resolution</div>
            </div>
            <div className="text-center p-6 bg-purple-900/10 backdrop-blur-md border border-purple-400/20 rounded-2xl hover:border-purple-400/30 transition-all duration-300">
              <div className="text-4xl md:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-fuchsia-400 mb-2">&lt;5s</div>
              <div className="text-white/70 text-sm md:text-base font-light">Response Time</div>
            </div>
          </div>
        </div>
      </div>

    </div>
  )
}

export default Landing
