import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.heat';
import CameraMarker from '../components/CameraMarker';
import CameraModal from '../components/CameraModal';
import '../index.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';
const NYC_CENTER = [40.7128, -74.0060];
const DEFAULT_ZOOM = 11;

function HeatmapLayer({ points }) {
  const map = useMap();
  const heatLayerRef = useRef(null);

  useEffect(() => {
    if (!points || points.length === 0) return;
    if (heatLayerRef.current) map.removeLayer(heatLayerRef.current);

    const heatLayer = L.heatLayer(points, {
      radius: 25, blur: 20, maxZoom: 17, max: 1.0, minOpacity: 0.4,
      gradient: {
        0.0: '#000000', 0.2: '#4a0000', 0.4: '#ff4500',
        0.6: '#ff6600', 0.8: '#ff8c00', 1.0: '#ffcc00'
      }
    });
    heatLayer.addTo(map);
    heatLayerRef.current = heatLayer;

    return () => { if (heatLayerRef.current) map.removeLayer(heatLayerRef.current); };
  }, [points, map]);

  return null;
}

function MapController({ onMapReady }) {
  const map = useMap();
  useEffect(() => { if (onMapReady && map) onMapReady(map); }, [map, onMapReady]);
  return null;
}

function MapView() {
  const navigate = useNavigate();
  const [heatmapPoints, setHeatmapPoints] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCamera, setSelectedCamera] = useState(null);
  const [mapInstance, setMapInstance] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [heatmapRes, camerasRes] = await Promise.all([
        fetch(`${API_BASE}/api/heatmap?limit=50000`),
        fetch(`${API_BASE}/api/cameras`)
      ]);

      if (heatmapRes.ok) {
        const points = await heatmapRes.json();
        if (Array.isArray(points)) setHeatmapPoints(points);
      }

      if (camerasRes.ok) {
        const cams = await camerasRes.json();
        setCameras(cams);
      }
    } catch (err) {
      console.error('Error loading map data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCameraClick = (camera) => {
    setSelectedCamera(camera);
  };

  const handleDetectionComplete = () => {
    // Could refresh data here
  };

  return (
    <div className="map-view-page">
      {/* Header */}
      <header className="map-header">
        <div className="header-left">
          <span className="logo-icon">🗺️</span>
          <span className="logo-text">NYC Violation Heatmap</span>
        </div>
        <div className="header-right">
          <button className="nav-link primary" onClick={() => navigate('/dmv')}>
            ← Back to DMV Dashboard
          </button>
        </div>
      </header>

      {/* Map */}
      <div className="map-container">
        {loading ? (
          <div className="map-loading">
            <div className="spinner"></div>
            <p>Loading map data...</p>
          </div>
        ) : (
          <MapContainer
            center={NYC_CENTER}
            zoom={DEFAULT_ZOOM}
            style={{ height: '100%', width: '100%' }}
            zoomControl={true}
          >
            <MapController onMapReady={setMapInstance} />
            <TileLayer
              attribution='&copy; OpenStreetMap'
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            />
            
            {heatmapPoints.length > 0 && <HeatmapLayer points={heatmapPoints} />}
            
            {cameras.map((camera, i) => (
              <CameraMarker
                key={i}
                camera={camera}
                onClick={handleCameraClick}
                isActive={selectedCamera?.camera_id === camera.camera_id}
              />
            ))}
          </MapContainer>
        )}

        {/* Stats Overlay */}
        <div className="map-stats-overlay">
          <div className="stat-item">
            <span className="stat-value">{heatmapPoints.length.toLocaleString()}</span>
            <span className="stat-label">Violations</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{cameras.length}</span>
            <span className="stat-label">AI Cameras</span>
          </div>
        </div>

        {/* Camera List */}
        <div className="camera-list-overlay">
          <h3>Enforcement Cameras</h3>
          {cameras.map((cam, i) => (
            <div 
              key={i}
              className="camera-list-item"
              onClick={() => {
                if (mapInstance) {
                  mapInstance.setView([cam.latitude, cam.longitude], 14, { animate: true });
                }
                setSelectedCamera(cam);
              }}
            >
              <span className="cam-name">{cam.name}</span>
              <span className="cam-zone">{cam.zone_type?.replace('_', ' ')}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Camera Modal */}
      {selectedCamera && (
        <CameraModal
          camera={selectedCamera}
          onClose={() => setSelectedCamera(null)}
          onDetectionComplete={handleDetectionComplete}
        />
      )}
    </div>
  );
}

export default MapView;
