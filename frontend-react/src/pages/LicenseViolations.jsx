import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import '../styles/dmv.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

function LicenseViolations() {
  const { licenseNumber } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(null);

  useEffect(() => { loadViolations(); }, [licenseNumber]);

  const loadViolations = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/license/${licenseNumber}/violations`);
      if (res.ok) {
        setData(await res.json());
      }
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (d) => d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—';
  const formatTime = (d) => d ? new Date(d).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : '';
  
  const getSeverityInfo = (code) => {
    if (code === '1180D') return { text: 'SEVERE', points: 11 };
    if (code === '1180C') return { text: 'HIGH', points: 6 };
    if (code === '1180B') return { text: 'MODERATE', points: 4 };
    return { text: 'STANDARD', points: 3 };
  };

  const getViolationDescription = (code) => {
    const descriptions = {
      '1180A': 'Speeding 1-10 mph over limit',
      '1180B': 'Speeding 11-20 mph over limit',
      '1180C': 'Speeding 21-30 mph over limit',
      '1180D': 'Speeding 31+ mph over limit',
      '1180E': 'Speeding in school zone',
      '1180F': 'Speeding in work zone',
    };
    return descriptions[code] || 'Speeding violation';
  };

  if (loading) {
    return (
      <div className="dmv-loading">
        <div className="spinner"></div>
        <p>Loading violation history...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="driver-profile">
        <header className="dmv-header">
          <div className="header-left">
            <div className="dmv-logo">
              <span className="logo-text">NY DMV — License Violations</span>
            </div>
          </div>
        </header>
        <div style={{ padding: '60px', textAlign: 'center' }}>
          <h2 style={{ color: '#fff', marginBottom: '10px' }}>No Records Found</h2>
          <p style={{ color: '#666', marginBottom: '30px' }}>
            No violations found for license: <strong style={{ color: '#fff' }}>{licenseNumber}</strong>
          </p>
          <button className="nav-link" onClick={() => navigate('/dmv')}>← Back to Dashboard</button>
        </div>
      </div>
    );
  }

  const { driver, violations, summary, total_violations } = data;
  const uniquePlates = [...new Set(violations.map(v => v.plate_id))];
  const cameraViolations = violations.filter(v => v.screenshot_url).length;
  const severeCount = violations.filter(v => v.violation_code === '1180D').length;

  return (
    <div className="driver-profile">
      {/* Header */}
      <header className="dmv-header">
        <div className="header-left">
          <div className="dmv-logo">
            <span className="logo-text">NY DMV — License Violations</span>
          </div>
        </div>
        <div className="header-right">
          <button className="nav-link" onClick={() => navigate('/dmv')}>← Back to Dashboard</button>
        </div>
      </header>

      <div className="profile-content">
        <div className="profile-main">
          {/* Driver Header Card */}
          <div className="driver-header-card">
            <div className="driver-header-top">
              <div className="driver-identity">
                <div style={{ fontSize: '11px', color: '#666', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '6px' }}>
                  Driver License Number
                </div>
                <h1 style={{ fontFamily: 'monospace', letterSpacing: '2px' }}>{licenseNumber}</h1>
                {driver && (
                  <div className="driver-meta">
                    <span>{driver.driver_full_name}</span>
                    <span>State: {driver.license_state}</span>
                  </div>
                )}
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{
                  width: '80px',
                  height: '80px',
                  borderRadius: '50%',
                  background: '#1a1a1a',
                  border: '2px solid #333',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <span style={{ fontSize: '24px', fontWeight: 'bold', color: '#fff' }}>{total_violations}</span>
                  <span style={{ fontSize: '9px', color: '#666', textTransform: 'uppercase' }}>Violations</span>
                </div>
              </div>
            </div>
          </div>

          {/* Violations List */}
          <div className="violations-section">
            <div className="section-header">
              <h2>Violation History</h2>
              <span className="violation-count">{total_violations} violations</span>
            </div>
            
            <div className="violations-list">
              {violations.map((v, i) => {
                const severity = getSeverityInfo(v.violation_code);
                
                return (
                  <div key={i} className="violation-row">
                    <div className="violation-date">
                      <div>{formatDate(v.date_of_violation)}</div>
                      <div style={{ fontSize: '11px', color: '#555' }}>{formatTime(v.date_of_violation)}</div>
                    </div>
                    <div className="violation-details" style={{ flex: 2 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px', flexWrap: 'wrap' }}>
                        <span className="violation-type">
                          {v.violation_code}
                          <span style={{
                            fontSize: '12px',
                            color: '#888',
                            marginLeft: '8px',
                            fontWeight: '400'
                          }}>
                            {getViolationDescription(v.violation_code)}
                          </span>
                          <span style={{
                            display: 'inline-block',
                            padding: '3px 8px',
                            borderRadius: '4px',
                            fontSize: '10px',
                            fontWeight: '700',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px',
                            marginLeft: '8px',
                            background: '#2a2a2a',
                            color: '#888',
                            border: '1px solid #333'
                          }}>
                            {severity.text}
                          </span>
                        </span>
                        {v.speed_detected && (
                          <span style={{ 
                            background: '#1a1a1a', 
                            border: '1px solid #333',
                            padding: '4px 10px', 
                            borderRadius: '4px',
                            fontSize: '13px',
                            color: '#fff'
                          }}>
                            {v.speed_detected} MPH in {v.speed_limit} zone
                          </span>
                        )}
                      </div>
                      <div style={{ 
                        display: 'flex', 
                        gap: '15px', 
                        fontSize: '12px', 
                        color: '#666',
                        flexWrap: 'wrap'
                      }}>
                        <span><strong style={{ color: '#888' }}>Plate:</strong> {v.plate_id}</span>
                        <span><strong style={{ color: '#888' }}>Agency:</strong> {v.police_agency || '—'}</span>
                        <span><strong style={{ color: '#888' }}>Issuer:</strong> {v.ticket_issuer || '—'}</span>
                        {v.camera_id && <span><strong style={{ color: '#888' }}>Camera:</strong> {v.camera_id}</span>}
                      </div>
                      
                      {v.screenshot_url && (
                        <div style={{ marginTop: '12px' }}>
                          <img 
                            src={`${API_BASE}${v.screenshot_url}`} 
                            alt="Violation evidence"
                            onClick={() => setSelectedImage(`${API_BASE}${v.screenshot_url}`)}
                            style={{
                              maxWidth: '180px',
                              maxHeight: '100px',
                              borderRadius: '6px',
                              border: '2px solid #2a2a2a',
                              cursor: 'pointer',
                              transition: 'border-color 0.2s'
                            }}
                            onMouseOver={e => e.target.style.borderColor = '#444'}
                            onMouseOut={e => e.target.style.borderColor = '#2a2a2a'}
                          />
                          {v.ocr_confidence && (
                            <span style={{ marginLeft: '10px', fontSize: '11px', color: '#555' }}>
                              OCR: {Math.round(v.ocr_confidence * 100)}%
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="violation-points">+{severity.points} pts</div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <aside className="case-sidebar">
          {/* Associated Plates */}
          <div className="case-history-card">
            <h3 className="card-title">Associated Plates</h3>
            <div className="history-timeline">
              {uniquePlates.map((plate, i) => {
                const plateViolations = violations.filter(v => v.plate_id === plate).length;
                return (
                  <div key={i} className="history-item">
                    <div className="history-dot"></div>
                    <div className="history-content">
                      <div className="history-action" style={{ fontFamily: 'monospace', fontWeight: 'bold' }}>
                        {plate}
                      </div>
                      <div className="history-meta">
                        {plateViolations} violation{plateViolations > 1 ? 's' : ''}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </aside>
      </div>

      {/* Image Modal */}
      {selectedImage && (
        <div 
          onClick={() => setSelectedImage(null)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.95)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            cursor: 'pointer'
          }}
        >
          <img 
            src={selectedImage}
            alt="Violation evidence"
            style={{
              maxWidth: '90%',
              maxHeight: '90%',
              borderRadius: '8px',
              boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)'
            }}
          />
          <div style={{
            position: 'absolute',
            top: '20px',
            right: '30px',
            color: '#666',
            fontSize: '13px'
          }}>
            Click anywhere to close
          </div>
        </div>
      )}
    </div>
  );
}

export default LicenseViolations;
