import { Marker, Popup } from 'react-leaflet';
import L from 'leaflet';

// Clean camera icon - Green glow = LIVE, Red pulse = ALERT detected
const createCameraIcon = (isActive, hasAlert = false, alertCount = 0) => {
  // Map colors: Green = active camera, White = inactive, Red pulse = alert
  const color = isActive ? '#00ff00' : '#ffffff';
  const pulseClass = hasAlert ? 'pulsing' : (isActive ? 'active' : '');
  
  return L.divIcon({
    html: `
      <div class="camera-marker-container ${pulseClass}">
        ${hasAlert ? `<div class="camera-alert-badge">${alertCount}</div>` : ''}
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="40" height="40">
          <!-- Camera body -->
          <rect x="8" y="16" width="24" height="16" rx="2" fill="#1a1a2e" stroke="${color}" stroke-width="2"/>
          <!-- Lens housing -->
          <circle cx="20" cy="24" r="6" fill="#0a0a15" stroke="${color}" stroke-width="1.5"/>
          <!-- Lens -->
          <circle cx="20" cy="24" r="3" fill="${color}" opacity="0.9"/>
          <!-- Inner lens -->
          <circle cx="20" cy="24" r="1.5" fill="#0a0a15"/>
          <!-- Recording light - always red -->
          <circle cx="28" cy="19" r="2" fill="#ff0000" class="recording-light"/>
          <!-- Mount arm -->
          <path d="M32 20 L38 16 L38 32 L32 28" fill="#1a1a2e" stroke="${color}" stroke-width="1.5"/>
          <!-- Wall mount -->
          <rect x="38" y="14" width="4" height="20" rx="1" fill="#1a1a2e" stroke="${color}" stroke-width="1.5"/>
        </svg>
      </div>
    `,
    className: `camera-icon-wrapper ${hasAlert ? 'has-alert' : ''}`,
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    popupAnchor: [0, -20]
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
