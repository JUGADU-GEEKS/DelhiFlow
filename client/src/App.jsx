import React, { useState } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Landing from './components/landing';
import PredictTest from './components/PredictTest';
import Predict from './components/Predict';
import Potholes from './components/Potholes';

function App() {
  return (
    <Router>
        <div className="app">
          <Routes>
            <Route path="/" element={<Landing/>}/>
            <Route path="/predict" element={<Predict/>}/>
            <Route path="/test-predict" element={<PredictTest/>}/>
            <Route path="/potholes" element={<Potholes/>}/>
          </Routes>
        </div>
      </Router>
  )
}

export default App