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
// NYC center (focused on the 5 boroughs)
const NYC_CENTER = [40.7128, -74.0060];
const DEFAULT_ZOOM = 11;

// High-performance Canvas-based layer for 100k+ points
function ViolationLayer({ points, onPointClick, onPointsDrawn }) {
  const map = useMap();
  const canvasRef = useRef(null);
  const layerRef = useRef(null);
  const pointsRef = useRef([]);

  useEffect(() => {
    if (!points || points.length === 0) return;
    if (layerRef.current) map.removeLayer(layerRef.current);
    
    // Store points for click detection
    pointsRef.current = points;

    // Create custom Canvas layer for high performance
    const CanvasLayer = L.Layer.extend({
      onAdd: function(map) {
        this._map = map;
        this._lastThrottle = 0;
        this._canvas = L.DomUtil.create('canvas', 'leaflet-canvas-layer');
        const size = map.getSize();
        this._canvas.width = size.x;
        this._canvas.height = size.y;
        this._canvas.style.position = 'absolute';
        this._canvas.style.top = '0';
        this._canvas.style.left = '0';
        this._canvas.style.pointerEvents = 'auto';
        this._canvas.style.cursor = 'pointer';
        
        // Click handler
        L.DomEvent.on(this._canvas, 'click', this._onClick, this);
        
        map.getPanes().overlayPane.appendChild(this._canvas);
        map.on('move', this._throttledReset, this);
        map.on('moveend', this._reset, this);
        map.on('zoom', this._throttledReset, this);
        map.on('zoomend', this._reset, this);
        map.on('resize', this._resize, this);
        this._reset();
      },

      onRemove: function(map) {
        L.DomEvent.off(this._canvas, 'click', this._onClick, this);
        map.getPanes().overlayPane.removeChild(this._canvas);
        map.off('move', this._throttledReset, this);
        map.off('moveend', this._reset, this);
        map.off('zoom', this._throttledReset, this);
        map.off('zoomend', this._reset, this);
        map.off('resize', this._resize, this);
      },

      _onClick: function(e) {
        // Get click position relative to map container
        const mapContainer = this._map.getContainer();
        const rect = mapContainer.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const clickY = e.clientY - rect.top;
        
        // Convert to map coordinates
        const clickContainerPoint = L.point(clickX, clickY);
        const clickLatLng = this._map.containerPointToLatLng(clickContainerPoint);
        
        // Larger click threshold - includes glow area
        const zoom = this._map.getZoom();
        const baseSize = zoom >= 15 ? 4 : zoom >= 13 ? 3 : zoom >= 11 ? 2 : 1.5;
        const clickThreshold = (baseSize * 2.5) + 8; // Glow radius + extra padding
        
        let nearestPoint = null;
        let nearestPointXY = null;
        let minDistance = Infinity;
        
        const bounds = this._map.getBounds();
        const minLat = bounds.getSouth();
        const maxLat = bounds.getNorth();
        const minLng = bounds.getWest();
        const maxLng = bounds.getEast();
        
        // Check all visible points
        for (const point of pointsRef.current) {
          const lat = point.lat || point[0];
          const lon = point.lon || point[1];
          
          // Quick bounds check
          if (lat < minLat || lat > maxLat || lon < minLng || lon > maxLng) continue;
          
          const pointXY = this._map.latLngToContainerPoint([lat, lon]);
          const distance = Math.sqrt(
            Math.pow(pointXY.x - clickX, 2) +
            Math.pow(pointXY.y - clickY, 2)
          );
          
          if (distance < clickThreshold && distance < minDistance) {
            minDistance = distance;
            nearestPoint = point;
            nearestPointXY = pointXY;
          }
        }
        
        if (nearestPoint && onPointClick) {
          // Pass the screen position for popup placement
          onPointClick(nearestPoint, nearestPointXY);
        }
        
        L.DomEvent.stopPropagation(e);
      },

      _throttledReset: function() {
        const now = Date.now();
        if (now - this._lastThrottle < 50) return; // Throttle to max 20fps during movement
        this._lastThrottle = now;
        this._reset();
      },

      _resize: function() {
        const size = this._map.getSize();
        this._canvas.width = size.x;
        this._canvas.height = size.y;
        this._reset();
      },

      _reset: function() {
        const topLeft = this._map.containerPointToLayerPoint([0, 0]);
        L.DomUtil.setPosition(this._canvas, topLeft);
        this._draw();
      },

      _draw: function() {
        const startTime = performance.now();
        const ctx = this._canvas.getContext('2d');
        const size = this._map.getSize();
        ctx.clearRect(0, 0, size.x, size.y);

        const zoom = this._map.getZoom();
        const bounds = this._map.getBounds();
        
        // Adjust point size based on zoom - larger dots for better visibility
        const baseSize = zoom >= 15 ? 5 : zoom >= 13 ? 4 : zoom >= 11 ? 3 : 2;
        
        // Performance optimization: pre-calculate bounds for faster filtering
        const minLat = bounds.getSouth();
        const maxLat = bounds.getNorth();
        const minLng = bounds.getWest();
        const maxLng = bounds.getEast();
        
        // Show all points (no sampling) - viewport culling handles performance
        let pointsDrawn = 0;
        let pointsChecked = 0;

        // Batch drawing operations for better performance
        const colorMap = {
          severe: { color: '#ff3333', glow: 'rgba(255, 51, 51, 0.5)' },
          high: { color: '#ff8800', glow: 'rgba(255, 136, 0, 0.4)' },
          moderate: { color: '#ffdd00', glow: 'rgba(255, 221, 0, 0.3)' },
          standard: { color: '#00ddff', glow: 'rgba(0, 221, 255, 0.25)' }
        };

        // Draw all points in viewport
        for (let i = 0; i < points.length; i++) {
          
          // Handle both old array format and new object format
          const point = points[i];
          const lat = point.lat || point[0];
          const lon = point.lon || point[1];
          const intensity = point.severity || point[2] || 0.5;
          
          pointsChecked++;
          
          // Fast bounds check
          if (lat < minLat || lat > maxLat || lon < minLng || lon > maxLng) continue;
          
          const pointXY = this._map.latLngToContainerPoint([lat, lon]);
          
          // Skip if outside canvas bounds
          if (pointXY.x < -50 || pointXY.x > size.x + 50 || pointXY.y < -50 || pointXY.y > size.y + 50) continue;
          
          // Get color based on severity
          let style;
          if (intensity >= 0.85) {
            style = colorMap.severe;
          } else if (intensity >= 0.65) {
            style = colorMap.high;
          } else if (intensity >= 0.4) {
            style = colorMap.moderate;
          } else {
            style = colorMap.standard;
          }

          // Glow effect
          ctx.beginPath();
          ctx.arc(pointXY.x, pointXY.y, baseSize * 2.5, 0, Math.PI * 2);
          ctx.fillStyle = style.glow;
          ctx.fill();

          // Main dot
          ctx.beginPath();
          ctx.arc(pointXY.x, pointXY.y, baseSize, 0, Math.PI * 2);
          ctx.fillStyle = style.color;
          ctx.fill();
          
          pointsDrawn++;
        }
        
        // Notify parent component of points drawn
        if (onPointsDrawn) {
          onPointsDrawn(pointsDrawn, points.length);
        }
        
        const renderTime = performance.now() - startTime;
        console.log(`Rendered ${pointsDrawn.toLocaleString()} of ${points.length.toLocaleString()} points in ${renderTime.toFixed(0)}ms (viewport: ${pointsChecked.toLocaleString()} checked)`);
      }
    });

    const layer = new CanvasLayer();
    layer.addTo(map);
    layerRef.current = layer;

    return () => { if (layerRef.current) map.removeLayer(layerRef.current); };
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
  const [recentViolations, setRecentViolations] = useState([]);
  const [showViolationsPanel, setShowViolationsPanel] = useState(true);
  const [selectedViolation, setSelectedViolation] = useState(null);
  const [violationPopupPos, setViolationPopupPos] = useState(null);
  const [cameraAlerts, setCameraAlerts] = useState({});  // {camera_id: alertCount}
  const [livesSaved, setLivesSaved] = useState({ count: 0, devices: 0 });
  const [mapMode, setMapMode] = useState('statewide'); // 'statewide', 'nyc', 'suffolk'
  const [pointsDisplayed, setPointsDisplayed] = useState(0);

  useEffect(() => {
    loadData();
    loadLivesSaved();
  }, [mapMode]);

  // Close tooltip when map moves
  useEffect(() => {
    if (!mapInstance) return;
    
    const closeTooltip = () => {
      setSelectedViolation(null);
      setViolationPopupPos(null);
    };
    
    mapInstance.on('move', closeTooltip);
    mapInstance.on('zoom', closeTooltip);
    
    return () => {
      mapInstance.off('move', closeTooltip);
      mapInstance.off('zoom', closeTooltip);
    };
  }, [mapInstance]);

  const loadData = async () => {
    try {
      // Build URL with region filter
      let heatmapUrl = `${API_BASE}/api/heatmap?limit=50000`;
      if (mapMode === 'nyc') {
        heatmapUrl += '&region=nyc';
      } else if (mapMode === 'suffolk') {
        heatmapUrl += '&region=suffolk';
      }
      
      const [heatmapRes, camerasRes] = await Promise.all([
        fetch(heatmapUrl),
        fetch(`${API_BASE}/api/cameras`)
      ]);

      if (heatmapRes.ok) {
        const points = await heatmapRes.json();
        console.log(`Loaded ${points.length.toLocaleString()} violation points from API`);
        if (Array.isArray(points)) setHeatmapPoints(points);
      }

      if (camerasRes.ok) {
        const cams = await camerasRes.json();
        console.log(`Loaded ${cams.length} cameras from API:`, cams);
        setCameras(cams);
      } else {
        console.error('Failed to load cameras:', camerasRes.status, camerasRes.statusText);
      }
    } catch (err) {
      console.error('Error loading map data:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadLivesSaved = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/stats/lives-saved`);
      if (res.ok) {
        const data = await res.json();
        setLivesSaved({ 
          count: data.lives_saved_estimate || 0, 
          devices: data.isa_devices_installed || 0 
        });
      }
    } catch (err) {
      console.error('Error loading lives saved:', err);
    }
  };
  
  const loadRecentViolations = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/recent-violations`);
      if (res.ok) {
        const data = await res.json();
        setRecentViolations(data.slice(0, 10)); // Show last 10
      }
    } catch (err) {
      console.error('Error loading violations:', err);
    }
  };
  
  // Load violations on mount and refresh every 10 seconds
  useEffect(() => {
    loadRecentViolations();
    const interval = setInterval(loadRecentViolations, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleCameraClick = (camera) => {
    setSelectedCamera(camera);
  };

  const handleDetectionComplete = (result) => {
    // Track alerts per camera
    if (result?.high_risk_count > 0 && selectedCamera) {
      setCameraAlerts(prev => ({
        ...prev,
        [selectedCamera.camera_id]: (prev[selectedCamera.camera_id] || 0) + result.high_risk_count
      }));
    }
    // Refresh lives saved counter and violations
    loadLivesSaved();
    loadRecentViolations();
  };

  return (
    <div className="map-view-page">
      {/* Header */}
      <header className="map-header">
        <div className="header-left">
          <span className="logo-icon">🗺️</span>
          <span className="logo-text">NY State Violation Map</span>
          <div className="map-mode-toggle">
            <button 
              className={`mode-btn ${mapMode === 'statewide' ? 'active' : ''}`}
              onClick={() => {
                setMapMode('statewide');
                if (mapInstance) mapInstance.setView([42.5, -75.5], 7);
              }}
            >
              🗽 Statewide
            </button>
            <button 
              className={`mode-btn ${mapMode === 'nyc' ? 'active' : ''}`}
              onClick={() => {
                setMapMode('nyc');
                if (mapInstance) mapInstance.setView([40.7128, -74.0060], 11);
              }}
            >
              🏙️ NYC Only
            </button>
            <button 
              className={`mode-btn ${mapMode === 'suffolk' ? 'active' : ''}`}
              onClick={() => {
                setMapMode('suffolk');
                if (mapInstance) mapInstance.setView([40.88, -72.7], 10);
              }}
            >
              📍 Suffolk
            </button>
          </div>
        </div>
        <div className="header-right">
          <span className="points-count">{heatmapPoints.length.toLocaleString()} violations loaded</span>
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
              attribution='&copy; Esri, Maxar, Earthstar Geographics'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              maxZoom={19}
            />
            
            {heatmapPoints.length > 0 && (
              <ViolationLayer 
                points={heatmapPoints} 
                onPointClick={(point, screenPos) => {
                  setSelectedViolation(point);
                  setViolationPopupPos(screenPos);
                }}
              />
            )}
            
            {cameras.map((camera, i) => (
              <CameraMarker
                key={camera.camera_id || i}
                camera={camera}
                onClick={handleCameraClick}
                isActive={camera.is_active !== false}
                hasAlert={cameraAlerts[camera.camera_id] > 0}
                alertCount={cameraAlerts[camera.camera_id] || 0}
              />
            ))}
          </MapContainer>
        )}

        {/* Stats Overlay */}
        <div className="map-stats-overlay">
          <div className="stat-item">
            <span className="stat-value">{heatmapPoints.length.toLocaleString()}</span>
            <span className="stat-label">Total Violations</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{cameras.length}</span>
            <span className="stat-label">AI Cameras</span>
          </div>
          <div className="stat-item highlight">
            <span className="stat-value">{Object.values(cameraAlerts).reduce((a, b) => a + b, 0)}</span>
            <span className="stat-label">High-Risk Detected</span>
          </div>
        </div>

        {/* Lives Saved Counter */}
        {livesSaved.devices > 0 && (
          <div className="lives-saved-counter">
            <span className="count">{livesSaved.count}</span>
            <span className="label">Lives Saved (Est.)</span>
            <span className="sub-label">{livesSaved.devices} ISA Devices Installed</span>
          </div>
        )}

        {/* Violation Legend */}
        <div className="heatmap-legend">
          <h4>Violation Severity</h4>
          <div className="legend-dots">
            <div className="legend-dot-item">
              <span className="dot glow" style={{background: '#00ddff', boxShadow: '0 0 8px #00ddff'}}></span>
              <span>1-10 mph over</span>
            </div>
            <div className="legend-dot-item">
              <span className="dot glow" style={{background: '#ffdd00', boxShadow: '0 0 8px #ffdd00'}}></span>
              <span>11-20 mph over</span>
            </div>
            <div className="legend-dot-item">
              <span className="dot glow" style={{background: '#ff8800', boxShadow: '0 0 8px #ff8800'}}></span>
              <span>21-30 mph over</span>
            </div>
            <div className="legend-dot-item">
              <span className="dot glow" style={{background: '#ff3333', boxShadow: '0 0 8px #ff3333'}}></span>
              <span>31+ mph over</span>
            </div>
          </div>
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

      {/* Violation Info Tooltip - Government Style */}
      {selectedViolation && violationPopupPos && (
        <div 
          className="violation-tooltip-gov"
          style={{
            position: 'absolute',
            left: `${violationPopupPos.x + 15}px`,
            top: `${violationPopupPos.y - 10}px`,
            transform: 'translateY(-50%)'
          }}
        >
          <button className="tooltip-close-gov" onClick={() => {
            setSelectedViolation(null);
            setViolationPopupPos(null);
          }}>×</button>
          <div className="tooltip-header-gov">
            <span className="tooltip-code-gov">{selectedViolation.code || '1180A'}</span>
            <span className={`tooltip-severity-gov ${
              selectedViolation.severity >= 0.85 ? 'severe' :
              selectedViolation.severity >= 0.65 ? 'high' :
              selectedViolation.severity >= 0.4 ? 'moderate' : 'standard'
            }`}>
              {selectedViolation.severity >= 0.85 ? 'SEVERE' :
               selectedViolation.severity >= 0.65 ? 'HIGH' :
               selectedViolation.severity >= 0.4 ? 'MODERATE' : 'STANDARD'}
            </span>
          </div>
          <div className="tooltip-body-gov">
            <div className="tooltip-row-gov">
              <span className="row-label">Violation</span>
              <span className="row-value">{selectedViolation.code || '1180A'}</span>
            </div>
            {selectedViolation.plate && (
              <div className="tooltip-row-gov">
                <span className="row-label">Plate</span>
                <span className="row-value">{selectedViolation.plate} ({selectedViolation.state || 'NY'})</span>
              </div>
            )}
            {selectedViolation.date && (
              <div className="tooltip-row-gov">
                <span className="row-label">Date</span>
                <span className="row-value">{new Date(selectedViolation.date).toLocaleDateString()} {new Date(selectedViolation.date).toLocaleTimeString()}</span>
              </div>
            )}
            {selectedViolation.police_agency && (
              <div className="tooltip-row-gov">
                <span className="row-label">Agency</span>
                <span className="row-value">{selectedViolation.police_agency}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default MapView;
