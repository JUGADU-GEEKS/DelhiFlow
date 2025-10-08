import React from 'react';
import Squares from './Squares';
import Dock from './Dock';
import ShinyText from './ShinyText';
import ChromaGrid from './ChromaGrid';
import { VscHome, VscArchive, VscAccount, VscGithubInverted } from 'react-icons/vsc';
import kunalImage from '../../public/kunal.jpg';
import sangyaImage from '../../public/sangya.jpg';
import dhruvImage from '../../public/dhruv.jpg';
import { Link } from 'react-router-dom';

function Landing() {
  const scrollToSection = (sectionId) => {
    const element = document.getElementById(sectionId);
    if (element) {
      const offset = 100; // Account for fixed dock height
      const elementPosition = element.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.pageYOffset - offset;
      
      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth'
      });
    }
  };

  const dockItems = [
    { icon: <VscHome size={24} />, label: 'Home', onClick: () => window.scrollTo({ top: 0, behavior: 'smooth' }) },
    { icon: <VscArchive size={24} />, label: 'About', onClick: () => scrollToSection('about-section') },
    { icon: <VscAccount size={24} />, label: 'Team', onClick: () => scrollToSection('team-section') },
    { icon: <VscGithubInverted size={24} />, label: 'GitHub', onClick: () => window.open('https://github.com/JUGADU-GEEKS/DelhiFlow', '_blank') },
  ];

  const teamMembers = [
    {
      image: kunalImage,
      title: "Kunal Sharma",
      subtitle: "Full Stack Developer",
      handle: "@kunnusherry",
      borderColor: "#9a69b5",
      gradient: "linear-gradient(145deg, #9a69b5, #000)",
      url: "https://kunal-portfolio-lemon.vercel.app/"
    },
    {
      image: sangyaImage,
      title: "Sangya Ojha",
      subtitle: "Full Stack Developer",
      handle: "@sangya-25",
      borderColor: "#c247ac",
      gradient: "linear-gradient(180deg, #c247ac, #000)",
      url: "https://portfolio-sangya.vercel.app/"
    },
    {
      image: dhruvImage,
      title: "Dhruv Sharma",
      subtitle: "Full Stack Developer",
      handle: "@dhruv0050",
      borderColor: "#d856bf",
      gradient: "linear-gradient(210deg, #d856bf, #000)",
      url: "https://dhruvs-portfolio-khaki.vercel.app/"
    }
  ];

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
      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen px-4 -mt-24">

        {/* Main Heading */}
        <div className="text-center mt-50 mb-16 max-w-5xl">
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
          <button className="bg-white text-black px-10 py-4 rounded-full font-semibold hover:bg-purple-50 hover:scale-105 transition-all duration-200 text-lg shadow-lg shadow-purple-500/20 min-w-[160px]" onClick={() => window.location.href = '/predict'}>
            Get Started
          </button>
          <button className="bg-purple-600/20 backdrop-blur-md border-2 border-purple-400/30 text-white px-10 py-4 rounded-full font-semibold hover:bg-purple-600/30 hover:border-purple-400/50 hover:scale-105 transition-all duration-200 text-lg min-w-[160px]">
            Learn More
          </button>
        </div>
      </div>

      {/* About Section */}
      <div id="about-section" className="relative z-10 px-4 py-20">
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

        </div>
      </div>

      {/* Team Section */}
      <div id="team-section" className="relative z-10 px-4 py-20">
        <div className="max-w-7xl mx-auto">
          {/* Section Title */}
          <div className="text-center mb-16">
            <h2 className="text-transparent bg-clip-text bg-gradient-to-r from-purple-300 via-fuchsia-400 to-pink-400 text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
              Meet Our Team
            </h2>
            <p className="text-white/70 text-lg md:text-xl max-w-2xl mx-auto font-light">
              The brilliant minds behind Delhi Flow's innovative flood forecasting technology
            </p>
          </div>

          {/* ChromaGrid Team Cards */}
          <div style={{ minHeight: '500px', position: 'relative' }}>
            <ChromaGrid 
              items={teamMembers}
              radius={350}
              damping={0.45}
              fadeOut={0.6}
              ease="power3.out"
              className="pb-10"
            />
          </div>
        </div>
      </div>

    </div>
  )
}

export default Landing