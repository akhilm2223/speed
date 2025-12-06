import { useState, useEffect, useRef } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

// Generate random plate for detection simulation
const generatePlate = () => {
  const prefixes = ['JKL', 'HGT', 'FDR', 'BKN', 'QNS', 'TSQ', 'MNH', 'BRX'];
  const prefix = prefixes[Math.floor(Math.random() * prefixes.length)];
  const num = Math.floor(1000 + Math.random() * 9000);
  return `${prefix}-${num}`;
};

// Generate random detection box position
const generateDetection = (id) => {
  const speedLimit = 30;
  const speed = Math.floor(35 + Math.random() * 40); // 35-75 mph
  return {
    id,
    x: 10 + Math.random() * 60,
    y: 30 + Math.random() * 40,
    w: 12 + Math.random() * 10,
    h: 8 + Math.random() * 6,
    speed,
    limit: speedLimit,
    plate: null, // Will be "read" by OCR
  };
};

function CameraModal({ camera, onClose, onDetectionComplete }) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [detectedVehicles, setDetectedVehicles] = useState([]);
  const [loggedViolations, setLoggedViolations] = useState(null);
  const [error, setError] = useState(null);
  const [videoPlaying, setVideoPlaying] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [scanComplete, setScanComplete] = useState(false);
  const [yoloStatus, setYoloStatus] = useState('READY');
  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [highlightedPlate, setHighlightedPlate] = useState(null);
  const videoRef = useRef(null);
  const scanIntervalRef = useRef(null);

  useEffect(() => {
    return () => {
      if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
    };
  }, []);

  const handleVideoPlay = () => {
    setVideoPlaying(true);
  };

  const startYoloDetection = () => {
    if (isScanning || scanComplete) return;

    setDetectedVehicles([]);
    setIsScanning(true);
    setYoloStatus('INITIALIZING YOLO...');
    
    const numVehicles = 2 + Math.floor(Math.random() * 3); // 2-4 vehicles
    let currentIndex = 0;

    // Simulate YOLO detecting vehicles one by one
    setTimeout(() => {
      setYoloStatus('SCANNING FRAME...');
      
      scanIntervalRef.current = setInterval(() => {
        if (currentIndex < numVehicles) {
          const detection = generateDetection(currentIndex + 1);
          
          // Step 1: YOLO detects vehicle (box appears, no plate)
          setYoloStatus(`VEHICLE ${currentIndex + 1} DETECTED`);
          setDetectedVehicles(prev => [...prev, detection]);
          
          // Step 2: After delay, OCR reads the plate
          setTimeout(() => {
            const plate = generatePlate();
            setYoloStatus(`OCR: ${plate}`);
            setDetectedVehicles(prev => 
              prev.map(v => v.id === detection.id ? { ...v, plate } : v)
            );
          }, 800);
          
          currentIndex++;
        } else {
          clearInterval(scanIntervalRef.current);
          setIsScanning(false);
          setScanComplete(true);
          setYoloStatus('DETECTION COMPLETE');
          
          // Auto-log violations
          setTimeout(() => logViolations(), 500);
        }
      }, 2000);
    }, 500);
  };

  const logViolations = async () => {
    setIsProcessing(true);
    setYoloStatus('LOGGING TO DATABASE...');
    
    // Get detected vehicles with plates (violations only - speed > limit)
    const violations = detectedVehicles.filter(v => v.plate && v.speed > v.limit);
    
    if (violations.length === 0) {
      setYoloStatus('NO VIOLATIONS');
      setIsProcessing(false);
      return;
    }

    try {
      // Send each violation to the API
      const results = [];
      for (const v of violations) {
        const res = await fetch(`${API_BASE}/api/cameras/${camera.camera_id}/detect`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            plate_id: v.plate,
            speed_detected: v.speed,
            speed_limit: v.limit,
            violation_type: v.speed > v.limit + 25 ? 'reckless_speed' : 
                           v.speed > v.limit + 10 ? 'excessive_speed' : 'speeding',
            points: v.speed > v.limit + 25 ? 5 : v.speed > v.limit + 10 ? 4 : 3,
            corridor_name: camera.name,
          })
        });
        
        if (res.ok) {
          const data = await res.json();
          results.push(data);
        }
      }
      
      // Check for high-risk drivers
      const highRiskAlerts = results.filter(r => r.alert || r.is_high_risk);
      
      setLoggedViolations({
        count: results.length,
        violations: results,
        highRiskCount: highRiskAlerts.length,
        alerts: highRiskAlerts.map(r => r.alert).filter(Boolean),
      });
      setYoloStatus(highRiskAlerts.length > 0 
        ? `🚨 ${highRiskAlerts.length} HIGH RISK DETECTED` 
        : `${results.length} VIOLATIONS LOGGED`
      );
      
      if (onDetectionComplete) {
        onDetectionComplete({ 
          violations_logged: results.length,
          high_risk_count: highRiskAlerts.length,
          alerts: highRiskAlerts.map(r => r.alert).filter(Boolean),
        });
      }
    } catch (err) {
      setError(err.message);
      setYoloStatus('ERROR');
    } finally {
      setIsProcessing(false);
    }
  };

  const getBoxColor = (speed, limit) => {
    if (!speed || !limit) return '#00ff00';
    const over = speed - limit;
    if (over > 25) return '#ff0000';
    if (over > 10) return '#ff4500';
    if (over > 0) return '#ff6b35';
    return '#00ff00';
  };

  const handleViolationClick = (v) => {
    setSelectedVehicle(v);
    if (v.plate) {
      setHighlightedPlate(v.plate);
      setTimeout(() => setHighlightedPlate(null), 3000);
    }
  };

  const speedLimit = camera.zone_type === 'high_traffic' ? 15 : 30;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="camera-modal" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>×</button>
        
        <div className="modal-header">
          <div className="modal-title">
            <span className="camera-icon-header">📹</span>
            <h2>{camera.name}</h2>
          </div>
          <div className="camera-meta">
            <span className="zone-badge">{camera.zone_type?.replace('_', ' ')}</span>
            <span className="speed-limit-badge">{speedLimit} MPH LIMIT</span>
          </div>
        </div>

        <div className="modal-content">
          <div className="video-section">
            <div className="video-placeholder">
              {!videoPlaying ? (
                <div className="video-start-overlay">
                  <div className="play-button-large" onClick={handleVideoPlay}>
                    <span>▶</span>
                  </div>
                  <p>Start Camera Feed</p>
                </div>
              ) : (
                <div className="video-feed">
                  <div className="feed-header">
                    <div className="feed-left">
                      <span className="live-indicator">● LIVE</span>
                      <span className="camera-id">{camera.camera_id}</span>
                    </div>
                    <div className="feed-right">
                      <span className={`yolo-status ${isScanning ? 'scanning' : ''}`}>
                        🤖 {yoloStatus}
                      </span>
                    </div>
                  </div>
                  
                  <div className="real-video-container">
                    <video ref={videoRef} autoPlay loop muted playsInline className="camera-video">
                      <source src={camera.video_url} type="video/mp4" />
                    </video>
                    
                    {/* YOLO Detection boxes */}
                    <div className="detection-overlay">
                      {detectedVehicles.map((vehicle) => (
                        <div 
                          key={vehicle.id}
                          className={`detection-box ${highlightedPlate === vehicle.plate ? 'highlighted' : ''}`}
                          style={{
                            left: `${vehicle.x}%`,
                            top: `${vehicle.y}%`,
                            width: `${vehicle.w}%`,
                            height: `${vehicle.h}%`,
                            borderColor: vehicle.plate ? getBoxColor(vehicle.speed, vehicle.limit) : '#00ff00',
                          }}
                        >
                          {/* Plate - shown after OCR reads it */}
                          {vehicle.plate && (
                            <div 
                              className={`plate-only ${highlightedPlate === vehicle.plate ? 'highlighted' : ''}`}
                              style={{ backgroundColor: getBoxColor(vehicle.speed, vehicle.limit) }}
                            >
                              {vehicle.plate}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                    
                    {/* Scanning effect */}
                    {isScanning && (
                      <div className="scanning-overlay active">
                        <div className="scan-line"></div>
                      </div>
                    )}
                    
                    {/* Detection counter */}
                    <div className="detection-counter">
                      {detectedVehicles.filter(v => v.plate).length} plates detected
                    </div>
                    
                    {/* Start Detection Button */}
                    {!isScanning && !scanComplete && (
                      <button className="start-yolo-btn" onClick={startYoloDetection}>
                        🔍 START YOLO DETECTION
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="detection-section">
            <h3>🚨 Detection Results</h3>
            
            {!videoPlaying && <p className="hint">Start camera feed first</p>}
            
            {videoPlaying && !isScanning && !scanComplete && (
              <p className="hint">Click START YOLO to detect vehicles</p>
            )}
            
            {isScanning && (
              <div className="processing">
                <div className="spinner small"></div>
                <p>YOLO scanning...</p>
                <p className="sub-text">Detecting vehicles & reading plates</p>
              </div>
            )}
            
            {isProcessing && (
              <div className="processing">
                <div className="spinner small"></div>
                <p>Logging violations...</p>
              </div>
            )}
            
            {error && <div className="error-msg">{error}</div>}
            
            {/* Vehicle details popup */}
            {selectedVehicle && (
              <div className="vehicle-details-popup">
                <button className="close-popup" onClick={() => setSelectedVehicle(null)}>×</button>
                <h4>🚗 Detected Vehicle</h4>
                <div className="detail-row">
                  <span className="detail-label">Plate:</span>
                  <span className="detail-value plate-highlight">{selectedVehicle.plate || 'Reading...'}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Speed:</span>
                  <span className="detail-value red">{selectedVehicle.speed} MPH</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Limit:</span>
                  <span className="detail-value">{selectedVehicle.limit} MPH</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Status:</span>
                  <span className="detail-value" style={{ color: selectedVehicle.speed > selectedVehicle.limit ? '#ff4500' : '#16A34A' }}>
                    {selectedVehicle.speed > selectedVehicle.limit ? 'VIOLATION' : 'OK'}
                  </span>
                </div>
              </div>
            )}
            
            {/* Detected vehicles list */}
            {scanComplete && detectedVehicles.length > 0 && (
              <div className="detection-results">
                <div className="results-summary">
                  <span className="count">{detectedVehicles.filter(v => v.plate && v.speed > v.limit).length}</span>
                  <span className="label">Violations</span>
                </div>
                
                <div className="violations-list clickable">
                  {detectedVehicles.filter(v => v.plate).map((v, i) => (
                    <div 
                      key={i} 
                      className={`violation-item clickable-item ${v.speed <= v.limit ? 'ok' : ''}`}
                      onClick={() => handleViolationClick(v)}
                      style={{ borderLeftColor: getBoxColor(v.speed, v.limit) }}
                    >
                      <div className="violation-header">
                        <span className="plate">{v.plate}</span>
                        <span className="speed-badge" style={{ color: getBoxColor(v.speed, v.limit) }}>
                          {v.speed} mph
                        </span>
                      </div>
                      <div className="violation-details">
                        {v.speed > v.limit ? (
                          <span className="violation-type">
                            {v.speed > v.limit + 25 ? 'RECKLESS' : 
                             v.speed > v.limit + 10 ? 'EXCESSIVE' : 'SPEEDING'}
                          </span>
                        ) : (
                          <span className="ok-badge">Within limit</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
                
                {loggedViolations && (
                  <div className={`logged-notice ${loggedViolations.highRiskCount > 0 ? 'high-risk' : ''}`}>
                    ✓ {loggedViolations.count} violations logged to DMV database
                    {loggedViolations.highRiskCount > 0 && (
                      <div className="high-risk-alert">
                        🚨 {loggedViolations.highRiskCount} HIGH-RISK driver(s) flagged for ISA enforcement
                      </div>
                    )}
                    {loggedViolations.alerts?.map((alert, i) => (
                      <div key={i} className="alert-item">
                        ⚠️ {alert.message} (Crash Risk: {alert.crash_risk}%)
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default CameraModal;
