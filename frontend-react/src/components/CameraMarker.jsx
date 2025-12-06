import { Marker, Popup } from 'react-leaflet';
import L from 'leaflet';

// Modern white glowing camera icon
const createCameraIcon = (isActive, hasAlert = false, alertCount = 0) => {
  const glowColor = hasAlert ? 'rgba(255, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.9)';
  const pulseClass = hasAlert ? 'pulsing' : (isActive ? 'active' : '');
  
  return L.divIcon({
    html: `
      <div class="camera-marker-container ${pulseClass}" style="filter: drop-shadow(0 0 12px ${glowColor});">
        ${hasAlert ? `<div class="camera-alert-badge">${alertCount}</div>` : ''}
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="48" height="48">
          <!-- Outer glow circle -->
          <circle cx="32" cy="32" r="28" fill="rgba(255, 255, 255, 0.1)" opacity="0.5"/>
          
          <!-- Camera body - modern design -->
          <rect x="18" y="22" width="28" height="20" rx="3" fill="#ffffff" stroke="none"/>
          
          <!-- Lens outer ring -->
          <circle cx="32" cy="32" r="8" fill="#1a1a2e" stroke="#ffffff" stroke-width="2"/>
          
          <!-- Lens glass effect -->
          <circle cx="32" cy="32" r="6" fill="url(#lensGradient)"/>
          
          <!-- Lens reflection -->
          <circle cx="30" cy="30" r="2" fill="rgba(255, 255, 255, 0.6)"/>
          
          <!-- Recording indicator -->
          <circle cx="42" cy="26" r="2.5" fill="#ff0000">
            <animate attributeName="opacity" values="1;0.3;1" dur="1.5s" repeatCount="indefinite"/>
          </circle>
          
          <!-- Microphone holes -->
          <circle cx="22" cy="26" r="1" fill="#1a1a2e"/>
          <circle cx="22" cy="30" r="1" fill="#1a1a2e"/>
          <circle cx="22" cy="34" r="1" fill="#1a1a2e"/>
          
          <!-- Mount bracket -->
          <path d="M46 28 L52 24 L52 40 L46 36 Z" fill="#ffffff" opacity="0.9"/>
          
          <!-- Gradient definitions -->
          <defs>
            <radialGradient id="lensGradient">
              <stop offset="0%" stop-color="#4a90e2"/>
              <stop offset="50%" stop-color="#2c5aa0"/>
              <stop offset="100%" stop-color="#1a1a2e"/>
            </radialGradient>
          </defs>
        </svg>
      </div>
    `,
    className: `camera-icon-wrapper ${hasAlert ? 'has-alert' : ''}`,
    iconSize: [48, 48],
    iconAnchor: [24, 24],
    popupAnchor: [0, -24]
  });
};

function CameraMarker({ camera, onClick, isActive, hasAlert = false, alertCount = 0 }) {
  return (
    <Marker
      position={[camera.latitude, camera.longitude]}
      icon={createCameraIcon(isActive, hasAlert, alertCount)}
      eventHandlers={{
        click: () => onClick(camera)
      }}
    >
      <Popup>
        <div className="camera-popup">
          <h4>📹 {camera.name}</h4>
          <p className="camera-zone">{camera.zone_type?.replace('_', ' ').toUpperCase()}</p>
          <p className="camera-borough">{camera.borough}</p>
          <p className="camera-desc">{camera.description}</p>
          <button className="view-feed-btn" onClick={() => onClick(camera)}>
            ▶ View Live Feed
          </button>
        </div>
      </Popup>
    </Marker>
  );
}

export default CameraMarker;
