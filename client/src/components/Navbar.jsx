import React from 'react';
import { useNavigate } from 'react-router-dom';
import Dock from './Dock';
import { Activity, TrendingUp, AlertCircle, MapPin, Navigation, HomeIcon } from 'lucide-react';

export default function Navbar() {
  const navigate = useNavigate();

  const navItems = [
    {
      icon: <HomeIcon size={24} />,
      label: 'Home',
      onClick: () => navigate('/')
    },
    {
      icon: <Activity size={24} />,
      label: 'Risk in your Area',
      onClick: () => navigate('/test-predict')
    },
    {
      icon: <TrendingUp size={24} />,
      label: 'Heatmap',
      onClick: () => navigate('/heatmap')
    },
    {
      icon: <AlertCircle size={24} />,
      label: 'Report Pothole',
      onClick: () => navigate('/potholes')
    },
    {
      icon: <MapPin size={24} />,
      label: 'Pothole Map',
      onClick: () => navigate('/potholes-map')
    },
    {
      icon: <Navigation size={24} />,
      label: 'Traffic Control',
      onClick: () => navigate('/route')
    }
  ];

  return (
    <div className="fixed top-0 left-0 right-0 z-50 flex justify-center pt-4">
      <Dock items={navItems} />
    </div>
  );
}
