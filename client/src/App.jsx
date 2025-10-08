import React, { useState } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Landing from './components/landing';
import Predict from './components/Predict';

function App() {
  return (
    <Router>
        <div className="app">
          <Routes>
            <Route path="/" element={<Landing/>}/>
            <Route path="/predict" element={<Predict/>}/>
          </Routes>
        </div>
      </Router>
  )
}

export default App