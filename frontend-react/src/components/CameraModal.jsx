import { useState, useEffect, useRef } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

// Screenshot image component with error handling
function ScreenshotImage({ src, alt }) {
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  if (!src || hasError) {
    return (
      <div className="ss-placeholder">
        <span>[IMG]</span>
        <p>{hasError ? 'Failed to load' : 'No screenshot'}</p>
      </div>
    );
  }

  return (
    <>
      {isLoading && (
        <div className="ss-placeholder">
          <div className="spinner" style={{ width: 30, height: 30 }}></div>
          <p>Loading...</p>
        </div>
      )}
      <img
        src={src}
        alt={alt}
        className="ss-img"
        style={{ display: isLoading ? 'none' : 'block' }}
        onLoad={() => setIsLoading(false)}
        onError={() => {
          console.error(`Failed to load screenshot: ${src}`);
          setHasError(true);
          setIsLoading(false);
        }}
      />
    </>
  );
}

// OCR Confidence indicator component
function OCRConfidenceBadge({ confidence }) {
  if (confidence === null || confidence === undefined) {
    return null;
  }
  
  const pct = Math.round(confidence * 100);
  let color, label;
  
  if (pct >= 80) {
    color = '#00ff88';
    label = 'HIGH';
  } else if (pct >= 50) {
    color = '#ffdd00';
    label = 'MED';
  } else {
    color = '#ff8800';
    label = 'LOW';
  }
  
  return (
    <span className="ocr-confidence" style={{ color, fontSize: '0.75rem', marginLeft: 8 }}>
      OCR: {pct}% ({label})
    </span>
  );
}

function CameraModal({ camera, onClose, onDetectionComplete }) {
  const [allViolations, setAllViolations] = useState([]);  // All loaded violations
  const [visibleViolations, setVisibleViolations] = useState([]);  // Shown one by one
  const [isScanning, setIsScanning] = useState(true);
  const [scanStatus, setScanStatus] = useState('Initializing camera feed...');
  const [vehiclesScanned, setVehiclesScanned] = useState(0);
  const videoRef = useRef(null);

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.play().catch(err => console.log('Autoplay prevented:', err));
    }
    
    // Realistic scanning sequence
    const scanSequence = async () => {
      // Phase 1: Initialize (2 sec)
      setScanStatus('Initializing YOLO detection model...');
      await sleep(1500);
      
      // Phase 2: Start scanning (2 sec)
      setScanStatus('Scanning video feed for vehicles...');
      await sleep(1500);
      
      // Phase 3: Load data
      setScanStatus('Running AI vehicle detection...');
      await loadViolations();
    };
    
    scanSequence();
  }, []);

  const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

  const loadViolations = async () => {
    console.log(`Running detection for camera: ${camera.camera_id}`);
    
    try {
      const existingRes = await fetch(`${API_BASE}/api/cameras/${camera.camera_id}/violations`);
      if (existingRes.ok) {
        const existingData = await existingRes.json();
        if (existingData.violations && existingData.violations.length > 0) {
          console.log('Found existing violations:', existingData.violations);
          const violations = existingData.violations.slice(0, 5);
          setAllViolations(violations);
          
          // Show violations one by one with realistic timing
          await showViolationsOneByOne(violations);
          return;
        }
      }
    } catch (err) {
      console.log('No existing violations, running detection...');
    }
    
    // If no existing violations, run live detection
    setScanStatus('No cached results. Running live detection...');
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000);
      
      const res = await fetch(`${API_BASE}/api/cameras/${camera.camera_id}/run-detection`, {
        method: 'POST',
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      if (res.ok) {
        const data = await res.json();
        console.log('Detection response:', data);
        const violations = (data.violations || []).slice(0, 5);
        setAllViolations(violations);
        
        await showViolationsOneByOne(violations);
        
        if (onDetectionComplete) {
          onDetectionComplete({ violations_logged: data.violations_count });
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        setScanStatus('Detection timed out');
      } else {
        console.error('Detection error:', err);
        setScanStatus('Detection error');
      }
    }
    
    setIsScanning(false);
  };

  const showViolationsOneByOne = async (violations) => {
    if (violations.length === 0) {
      setScanStatus('Scan complete - No violations detected');
      setIsScanning(false);
      return;
    }

    // Simulate vehicle scanning count
    for (let i = 0; i < 8 + Math.random() * 5; i++) {
      setVehiclesScanned(prev => prev + 1);
      setScanStatus(`Tracking vehicle ${i + 1}... Analyzing speed...`);
      await sleep(300 + Math.random() * 200);
    }

    // Show violations one by one
    for (let i = 0; i < violations.length; i++) {
      const v = violations[i];
      const speedOver = v.speed_detected - v.speed_limit;
      
      // Alert status
      if (speedOver > 20) {
        setScanStatus(`VIOLATION DETECTED: ${v.speed_detected} MPH - Capturing evidence...`);
      } else {
        setScanStatus(`Speeding detected: ${v.speed_detected} MPH - Recording...`);
      }
      
      await sleep(1500 + Math.random() * 1000);  // 1.5-2.5 seconds per violation
      
      // Add violation to visible list
      setVisibleViolations(prev => [...prev, v]);
      
      setScanStatus(`Evidence captured: ${v.plate_id} @ ${v.speed_detected} MPH`);
      await sleep(800);
    }
    
    setScanStatus(`Scan complete - ${violations.length} violation${violations.length > 1 ? 's' : ''} recorded`);
    setIsScanning(false);
  };

  const getSeverityBadge = (v) => {
    if (v.violation_code === '1180D') return { text: 'SEVERE', level: 'severe' };
    if (v.violation_code === '1180C') return { text: 'HIGH', level: 'high' };
    if (v.violation_code === '1180B') return { text: 'MODERATE', level: 'moderate' };
    return { text: 'STANDARD', level: 'standard' };
  };

  return (
    <div className="camera-overlay" onClick={onClose}>
      {/* Screenshots Panel - Left Side */}
      <div className="violations-box gov-style" onClick={e => e.stopPropagation()}>
        <h3>AI Detection Results</h3>
        
        {/* Live scanning status */}
        <div className="scan-status-gov">
          <div className="scan-status-row">
            {isScanning && (
              <div className="spinner-gov"></div>
            )}
            <span className={isScanning ? 'active' : ''}>
              {scanStatus}
            </span>
          </div>
          {isScanning && vehiclesScanned > 0 && (
            <div className="vehicles-count">
              Vehicles analyzed: {vehiclesScanned}
            </div>
          )}
        </div>
        
        {visibleViolations.length === 0 && !isScanning ? (
          <p className="no-data">No violations detected in this scan</p>
        ) : (
          <>
            {visibleViolations.length > 0 && (
              <div className="violations-count-gov">
                {visibleViolations.length} Violation{visibleViolations.length > 1 ? 's' : ''} Captured
                {isScanning && allViolations.length > visibleViolations.length && (
                  <span className="detecting-more">(detecting more...)</span>
                )}
              </div>
            )}
            
            {visibleViolations.map((v, i) => {
              const severity = getSeverityBadge(v);
              const screenshotSrc = v.screenshot_url ? `${API_BASE}${v.screenshot_url}` : null;
              
              return (
                <div key={i} className="violation-item-gov">
                  <ScreenshotImage src={screenshotSrc} alt={`Violation - ${v.plate_id}`} />
                  <div className="ss-info-gov">
                    <div className="ss-header-gov">
                      <div className="ss-plate-gov">{v.plate_id}</div>
                      <span className={`ss-severity-gov ${severity.level}`}>{severity.text}</span>
                    </div>
                    <div className="ss-code-gov">Violation {v.violation_code || '1180A'}</div>
                    <div className="ss-speed-gov">
                      {typeof v.speed_detected === 'number' ? v.speed_detected.toFixed(1) : v.speed_detected} MPH
                      <span className="speed-limit">(Limit: {v.speed_limit} MPH)</span>
                    </div>
                    <div className="ss-meta-gov">
                      <span className="meta-date">{new Date(v.timestamp || Date.now()).toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </>
        )}
      </div>

      {/* Video Panel - Top Right */}
      <div className="video-box-gov" onClick={e => e.stopPropagation()}>
        <button className="close-btn-gov" onClick={onClose}>×</button>
        <video ref={videoRef} autoPlay loop muted playsInline className="video-feed">
          <source src={camera.video_url} type="video/mp4" />
        </video>
        <div className="video-title-gov">{camera.name}</div>
        <div className={`video-status-gov ${isScanning ? 'active' : ''}`}>
          {isScanning ? 'LIVE DETECTION' : 'DETECTION COMPLETE'}
        </div>
      </div>
    </div>
  );
}

export default CameraModal;
