import { useState, useEffect, useRef } from 'react';
import '../styles/dmv.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

function ActivityLog({ onViolationClick }) {
  const [violations, setViolations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);
  const lastViolationIdRef = useRef(null);

  // Group violations by camera and time window (detection sessions)
  const groupViolationsBySession = (violations) => {
    if (!violations || violations.length === 0) return [];
    
    const sessions = [];
    const processed = new Set();
    
    // Sort by date (newest first)
    const sorted = [...violations].sort((a, b) => {
      const dateA = new Date(a.date || a.date_of_violation || 0);
      const dateB = new Date(b.date || b.date_of_violation || 0);
      return dateB - dateA;
    });
    
    for (const violation of sorted) {
      if (processed.has(violation.violation_id)) continue;
      
      const violationDate = new Date(violation.date || violation.date_of_violation);
      const cameraId = violation.camera_id;
      
      // Find or create session for this camera within 30 seconds
      let session = sessions.find(s => 
        s.camera_id === cameraId && 
        Math.abs(new Date(s.timestamp) - violationDate) < 30000
      );
      
      if (!session) {
        session = {
          id: `${cameraId}-${violationDate.getTime()}`,
          camera_id: cameraId,
          timestamp: violationDate.toISOString(),
          cars: []
        };
        sessions.push(session);
      }
      
      // Add car to session (group by plate within session)
      let car = session.cars.find(c => c.plate_id === violation.plate_id);
      if (!car) {
        car = {
          plate_id: violation.plate_id,
          violations: [],
          driver_license_number: violation.driver_license_number,
          driver_name: violation.driver_name
        };
        session.cars.push(car);
      }
      
      car.violations.push(violation);
      processed.add(violation.violation_id);
    }
    
    // Sort sessions by timestamp (newest first)
    sessions.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    return sessions;
  };

  const loadActivity = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/recent-violations?limit=50`);
      if (res.ok) {
        const data = await res.json();
        
        // Only update if we have new violations
        if (data.length > 0) {
          const latestId = data[0].violation_id;
          const shouldScroll = lastViolationIdRef.current === null || 
                              (latestId !== lastViolationIdRef.current && scrollRef.current?.scrollTop < 100);
          
          setViolations(data.slice(0, 50)); // Keep last 50
          setError(null);
          
          if (shouldScroll && scrollRef.current) {
            // Auto-scroll to top when new violation arrives
            scrollRef.current.scrollTop = 0;
          }
          
          lastViolationIdRef.current = latestId;
        }
      }
    } catch (err) {
      console.error('Error loading activity:', err);
      setError('Failed to load activity');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadActivity();
    // Poll every 3 seconds for new violations
    const interval = setInterval(loadActivity, 3000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const diffMs = now - date;
      const diffSecs = Math.floor(diffMs / 1000);
      const diffMins = Math.floor(diffSecs / 60);
      
      if (diffSecs < 60) return `${diffSecs}s ago`;
      if (diffMins < 60) return `${diffMins}m ago`;
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return '—';
    }
  };

  const getViolationSeverity = (code) => {
    if (code === '1180D') return { label: 'SEVERE', class: 'severity-severe' };
    if (code === '1180C') return { label: 'HIGH', class: 'severity-high' };
    if (code === '1180B') return { label: 'MOD', class: 'severity-mod' };
    return { label: 'STANDARD', class: 'severity-standard' };
  };

  if (loading && violations.length === 0) {
    return (
      <div className="activity-log">
        <div className="activity-header">
          <h3>🔄 Activity Log</h3>
        </div>
        <div className="activity-content">
          <div className="activity-loading">Loading...</div>
        </div>
      </div>
    );
  }

  const sessions = groupViolationsBySession(violations);
  const totalCars = sessions.reduce((sum, s) => sum + s.cars.length, 0);

  return (
    <div className="activity-log">
      <div className="activity-header">
        <h3>🔄 Live Activity</h3>
        <div className="activity-stats">
          <span className="activity-count">{totalCars} cars</span>
          <span className="activity-violations">{violations.length} violations</span>
        </div>
      </div>
      <div className="activity-content" ref={scrollRef}>
        {sessions.length === 0 ? (
          <div className="activity-empty">
            <p>No recent violations detected</p>
            <span className="activity-hint">Violations will appear here as cameras detect them</span>
          </div>
        ) : (
          <div className="activity-list">
            {sessions.map((session, sessionIdx) => {
              const isNewSession = sessionIdx === 0;
              const totalViolations = session.cars.reduce((sum, car) => sum + car.violations.length, 0);
              
              return (
                <div 
                  key={session.id} 
                  className={`activity-session ${isNewSession ? 'activity-session-new' : ''}`}
                >
                  <div className="activity-session-header">
                    <div className="session-info">
                      <span className="session-camera">📹 {session.camera_id}</span>
                      <span className="session-time">{formatTime(session.timestamp)}</span>
                    </div>
                    <span className="session-badge">{session.cars.length} car{session.cars.length !== 1 ? 's' : ''}</span>
                  </div>
                  
                  <div className="session-cars">
                    {session.cars.map((car, carIdx) => {
                      const maxSeverity = car.violations.reduce((max, v) => {
                        const sev = getViolationSeverity(v.violation_code);
                        if (sev.class === 'severity-severe') return 4;
                        if (sev.class === 'severity-high') return 3;
                        if (sev.class === 'severity-mod') return 2;
                        return max > 1 ? max : 1;
                      }, 0);
                      
                      const severityClass = maxSeverity >= 4 ? 'severity-severe' : 
                                           maxSeverity >= 3 ? 'severity-high' : 
                                           maxSeverity >= 2 ? 'severity-mod' : 'severity-standard';
                      
                      return (
                        <div 
                          key={`${car.plate_id}-${carIdx}`}
                          className={`activity-car ${severityClass}`}
                          onClick={() => {
                            const firstViolation = car.violations[0];
                            if (onViolationClick && firstViolation) {
                              onViolationClick(firstViolation);
                            }
                          }}
                        >
                          <div className="car-header">
                            <span className="car-plate">{car.plate_id}</span>
                            <span className="car-violation-count">{car.violations.length} violation{car.violations.length !== 1 ? 's' : ''}</span>
                          </div>
                          
                          <div className="car-violations-list">
                            {car.violations.map((violation, vIdx) => {
                              const severity = getViolationSeverity(violation.violation_code);
                              const mphOver = violation.speed_detected && violation.speed_limit 
                                ? Math.round(violation.speed_detected - violation.speed_limit)
                                : null;
                              
                              return (
                                <div key={`${violation.violation_id}-${vIdx}`} className="car-violation">
                                  <div className="violation-row">
                                    <span className="violation-code">{violation.violation_code}</span>
                                    {violation.speed_detected && (
                                      <span className="violation-speed">
                                        {Math.round(violation.speed_detected)} MPH
                                        {violation.speed_limit && (
                                          <span className="speed-limit"> / {violation.speed_limit}</span>
                                        )}
                                        {mphOver && mphOver > 0 && (
                                          <span className="speed-over"> +{mphOver}</span>
                                        )}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default ActivityLog;

