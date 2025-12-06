import { useState, useEffect, useRef } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

// Screenshot image component with error handling
function ScreenshotImage({ src, alt }) {
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  if (!src || hasError) {
    return (
      <div className="ss-placeholder">
        <span>📷</span>
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

function CameraModal({ camera, onClose, onDetectionComplete }) {
  const [violations, setViolations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const videoRef = useRef(null);

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.play().catch(err => console.log('Autoplay prevented:', err));
    }
    runDetection();
  }, []);

  const runDetection = async () => {
    setIsLoading(true);
    console.log(`Running detection for camera: ${camera.camera_id}`);
    
    // First, try to get existing violations for this camera (fast)
    try {
      const existingRes = await fetch(`${API_BASE}/api/cameras/${camera.camera_id}/violations`);
      if (existingRes.ok) {
        const existingData = await existingRes.json();
        if (existingData.violations && existingData.violations.length > 0) {
          console.log('Found existing violations:', existingData.violations);
          setViolations(existingData.violations.slice(0, 5));
          setIsLoading(false);
          return;
        }
      }
    } catch (err) {
      console.log('No existing violations, running detection...');
    }
    
    // If no existing violations, run detection (slower)
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout
      
      const res = await fetch(`${API_BASE}/api/cameras/${camera.camera_id}/run-detection`, {
        method: 'POST',
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      if (res.ok) {
        const data = await res.json();
        console.log('Detection response:', data);
        const violationsToShow = (data.violations || []).slice(0, 5);
        setViolations(violationsToShow);
        
        if (onDetectionComplete) {
          onDetectionComplete({ violations_logged: data.violations_count });
        }
      } else {
        console.error('Detection failed:', res.status, res.statusText);
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        console.log('Detection timed out');
      } else {
        console.error('Detection error:', err);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const getViolationReason = (v) => {
    const over = v.speed_detected - v.speed_limit;
    if (v.violation_code === '1180D') {
      return `SEVERE: ${v.speed_detected} MPH in ${v.speed_limit} zone (+${over} over). 8 points. ISA required.`;
    } else if (v.violation_code === '1180C') {
      return `HIGH: ${v.speed_detected} MPH in ${v.speed_limit} zone (+${over} over). 5 points.`;
    } else if (v.violation_code === '1180B') {
      return `MODERATE: ${v.speed_detected} MPH in ${v.speed_limit} zone (+${over} over). 3 points.`;
    }
    return `SPEEDING: ${v.speed_detected} MPH in ${v.speed_limit} zone (+${over} over).`;
  };

  const getSeverityBadge = (v) => {
    if (v.violation_code === '1180D') return { text: '🔴 SEVERE', color: '#ff0000' };
    if (v.violation_code === '1180C') return { text: '🟠 HIGH', color: '#ff8800' };
    if (v.violation_code === '1180B') return { text: '🟡 MODERATE', color: '#ffdd00' };
    return { text: '🔵 STANDARD', color: '#00ddff' };
  };

  return (
    <div className="camera-overlay" onClick={onClose}>
      {/* Screenshots Panel - Left Side */}
      <div className="violations-box" onClick={e => e.stopPropagation()}>
        <h3>📸 Violation Screenshots</h3>
        
        {isLoading ? (
          <div className="loading">
            <div className="spinner"></div>
            <p>Running AI Detection...</p>
          </div>
        ) : violations.length === 0 ? (
          <p className="no-data">No violations detected in this scan</p>
        ) : (
          <>
            <div className="violations-count-badge">
              {violations.length} Violation{violations.length > 1 ? 's' : ''} Captured
            </div>
            {violations.map((v, i) => {
              const severity = getSeverityBadge(v);
              const screenshotSrc = v.screenshot_url ? `${API_BASE}${v.screenshot_url}` : null;
              console.log(`Violation ${i}: plate=${v.plate_id}, screenshot_url=${v.screenshot_url}, full_src=${screenshotSrc}`);
              
              return (
                <div key={i} className="violation-item">
                  <ScreenshotImage src={screenshotSrc} alt={`Violation - ${v.plate_id}`} />
                  <div className="ss-info">
                    <div className="ss-header">
                      <div className="ss-plate">{v.plate_id}</div>
                      <span className="ss-severity" style={{ color: severity.color }}>{severity.text}</span>
                    </div>
                    <div className="ss-speed">{v.speed_detected} MPH</div>
                    <div className="ss-reason">{getViolationReason(v)}</div>
                  </div>
                </div>
              );
            })}
          </>
        )}
      </div>

      {/* Video Panel - Top Right */}
      <div className="video-box" onClick={e => e.stopPropagation()}>
        <button className="close-btn" onClick={onClose}>×</button>
        <video ref={videoRef} autoPlay loop muted playsInline className="video-feed">
          <source src={camera.video_url} type="video/mp4" />
        </video>
        <div className="video-title">{camera.name}</div>
      </div>
    </div>
  );
}

export default CameraModal;
