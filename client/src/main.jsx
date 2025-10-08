import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'


function OmnidimensionWidget() {
  useEffect(() => {
    if (!document.getElementById('omnidimension-web-widget')) {
      const script = document.createElement('script');
      script.id = 'omnidimension-web-widget';
      script.async = true;
      script.src = 'https://backend.omnidim.io/web_widget.js?secret_key=789b65c86610a7dab3372bcac54119b7';
      document.body.appendChild(script);
    }
  }, []);
  return null;
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <OmnidimensionWidget />
    <App />
  </StrictMode>,
)
