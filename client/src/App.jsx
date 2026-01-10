import React, { useState } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Landing from './components/Landing';
import PredictTest from './components/PredictTest';
import Predict from './components/Predict';
import Potholes from './components/Potholes';
import HeatmapView from './components/HeatmapView';
import KnowYourWard from './components/KnowYourWard';
import Chatbot from './components/Chatbot';

function App() {
  return (
    <Router>
        <div className="app">
          <Routes>
            <Route path="/" element={<Landing/>}/>
            <Route path="/predict" element={<Predict/>}/>
            <Route path="/test-predict" element={<PredictTest/>}/>
            <Route path="/potholes" element={<Potholes/>}/>
            <Route path="/heatmap" element={<HeatmapView/>}/>
            <Route path="/know-your-ward" element={<KnowYourWard/>}/>
          </Routes>
          {/* Chatbot available on all pages */}
          <Chatbot />
        </div>
      </Router>
  )
}

export default App