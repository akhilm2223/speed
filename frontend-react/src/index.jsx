import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import './index.css';

// Pages
import DMVDashboard from './pages/DMVDashboard';
import DriverProfile from './pages/DriverProfile';
import LicenseViolations from './pages/LicenseViolations';
import MapView from './pages/MapView';
import CourtsUpload from './pages/CourtsUpload';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Default route goes to DMV Dashboard */}
        <Route path="/" element={<Navigate to="/dmv" replace />} />
        <Route path="/dmv" element={<DMVDashboard />} />
        <Route path="/dmv/drivers/:plateId" element={<DriverProfile />} />
        <Route path="/dmv/license/:licenseNumber" element={<LicenseViolations />} />
        <Route path="/dmv/courts-upload" element={<CourtsUpload />} />
        <Route path="/map" element={<MapView />} />
      </Routes>
    </BrowserRouter>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
