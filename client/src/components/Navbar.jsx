import React from 'react';

function Navbar() {
  return (
    <div className="relative z-20 flex justify-center pt-8">
      <nav className="bg-purple-900/20 backdrop-blur-xl border border-purple-400/30 rounded-full px-10 py-4 flex items-center min-w-[600px] shadow-lg shadow-purple-900/30 hover:bg-purple-900/30 hover:border-purple-400/40 transition-all duration-300 justify-around">
        <div className="flex items-center space-x-8">
          <a href="#" className="text-white hover:text-purple-300 transition-all duration-200 font-medium text-base drop-shadow-sm hover:drop-shadow-md">Home</a>
          <a href="#" className="text-white hover:text-purple-300 transition-all duration-200 font-medium text-base drop-shadow-sm hover:drop-shadow-md">Team</a>
          <a href="#" className="text-white hover:text-purple-300 transition-all duration-200 font-medium text-base drop-shadow-sm hover:drop-shadow-md">About</a>
          <a href="#" className="text-white hover:text-purple-300 transition-all duration-200 font-medium text-base drop-shadow-sm hover:drop-shadow-md">Star Repo</a>
        </div>
      </nav>
    </div>
  );
}

export default Navbar;