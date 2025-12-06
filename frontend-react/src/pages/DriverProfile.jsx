import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import '../styles/dmv.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

function DriverProfile() {
  const { plateId } = useParams();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => { loadProfile(); }, [plateId]);

  const loadProfile = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dmv/drivers/${plateId}`);
      if (res.ok) setProfile(await res.json());
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSendNotice = async () => {
    setActionLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/dmv/alerts/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plate_id: plateId })
      });
      if (res.ok) loadProfile();
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleMarkCompliant = async () => {
    if (!profile?.alerts?.[0]) return;
    setActionLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/dmv/alerts/${profile.alerts[0].id}/comply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      if (res.ok) loadProfile();
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const getRiskColor = (risk) => {
    if (risk >= 10) return '#B0181A';
    if (risk >= 5) return '#C98F00';
    return '#3E6D45';
  };

  const formatDate = (d) => d ? new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : '—';
  const formatDateTime = (d) => d ? new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';

  if (loading) return <div className="dmv-loading"><div className="spinner"></div><p>Loading...</p></div>;

  if (!profile) {
    return (
      <div className="driver-profile">
        <header className="dmv-header">
          <div className="header-left"><div className="dmv-logo"><span className="logo-icon">🛡️</span><span className="logo-text">NYC DMV — ISA Enforcement Operations</span></div></div>
        </header>
        <div style={{ padding: '60px', textAlign: 'center' }}>
          <p style={{ fontSize: '18px', marginBottom: '20px' }}>Driver not found: {plateId}</p>
          <button className="action-btn action-secondary" onClick={() => navigate('/dmv')}>← Back to Dashboard</button>
        </div>
      </div>
    );
  }

  const { driver, violations, alerts, action_state } = profile;

  return (
    <div className="driver-profile">
      <header className="dmv-header">
        <div className="header-left"><div className="dmv-logo"><span className="logo-icon">🛡️</span><span className="logo-text">NYC DMV — ISA Enforcement Operations</span></div></div>
        <div className="header-right"><button className="nav-link" onClick={() => navigate('/dmv')}>← Back to Dashboard</button></div>
      </header>

      <div className="profile-content">
        <div className="profile-main">
          {/* Driver Header */}
          <div className="driver-header-card">
            <div className="driver-header-top">
              <div className="driver-identity">
                <h1>{driver.plate_id}</h1>
                <div className="driver-meta">
                  <span>State: {driver.state}</span>
                  <span>Primary Area: {driver.primary_borough}</span>
                  {driver.is_cross_borough && <span className="cross-borough-tag">Cross-Borough Speeder</span>}
                </div>
              </div>
              <span className={`status-badge ${
                action_state === 'COMPLIANT' ? 'badge-green' : 
                action_state === 'ALERT_SENT' ? 'badge-blue' : 
                driver.status === 'ISA_REQUIRED' ? 'badge-red' : 'badge-amber'
              }`}>
                {action_state === 'COMPLIANT' ? 'Compliant' : 
                 action_state === 'ALERT_SENT' ? 'Notice Sent' :
                 driver.status === 'ISA_REQUIRED' ? 'ISA Required' : 'Monitoring'}
              </span>
            </div>

            {/* Risk Bar */}
            <div className="risk-score-display">
              <div className="risk-score-big">
                <div className="risk-number" style={{ color: getRiskColor(driver.risk_points) }}>{driver.risk_points}</div>
                <div className="risk-label">Risk Points</div>
              </div>
              <div className="risk-bar-large">
                <div className="risk-bar-track">
                  <div className="risk-bar-fill-large" style={{ 
                    width: `${Math.min(driver.risk_points / 15 * 100, 100)}%`,
                    backgroundColor: getRiskColor(driver.risk_points)
                  }}></div>
                  <div className="risk-threshold-line"></div>
                  <span className="risk-threshold-label">ISA Threshold (10)</span>
                </div>
                <div className="risk-bar-labels">
                  <span>0</span><span>5 (Monitor)</span><span>10 (ISA Required)</span><span>15</span>
                </div>
              </div>
            </div>
          </div>

          {/* Risk Signal Cards */}
          <div className="signal-cards">
            <div className="signal-card">
              <div className="signal-icon">⚡</div>
              <div className="signal-content">
                <div className="signal-title">Severity</div>
                <div className="signal-value">High-tier (1180D): {driver.high_tier_count} of {driver.violation_count}</div>
                <div className="signal-sub">Low-tier (1180A): {driver.low_tier_count}</div>
              </div>
            </div>
            <div className="signal-card">
              <div className="signal-icon">📅</div>
              <div className="signal-content">
                <div className="signal-title">Time Span</div>
                <div className="signal-value">{driver.violation_count} violations total</div>
                <div className="signal-sub">Jan - Sep 2025</div>
              </div>
            </div>
            <div className={`signal-card ${driver.night_percentage >= 50 ? 'signal-warning' : ''}`}>
              <div className="signal-icon">🌙</div>
              <div className="signal-content">
                <div className="signal-title">Nighttime</div>
                <div className="signal-value">{driver.night_percentage}% of violations</div>
                <div className="signal-sub">{driver.night_violations} nighttime (10pm-4am)</div>
              </div>
            </div>
            <div className={`signal-card ${driver.is_cross_borough ? 'signal-warning' : ''}`}>
              <div className="signal-icon">📍</div>
              <div className="signal-content">
                <div className="signal-title">Geography</div>
                <div className="signal-value">{driver.borough_count} borough{driver.borough_count > 1 ? 's' : ''}</div>
                <div className="signal-sub">{driver.boroughs_affected?.join(', ')}</div>
              </div>
            </div>
          </div>

          {/* Violations Timeline */}
          <div className="violations-section">
            <div className="section-header">
              <h2>Violations Timeline</h2>
              <span className="violation-count">{violations.length} speeding violations</span>
            </div>
            <div className="violations-list">
              {violations.map((v, i) => (
                <div key={i} className={`violation-row ${v.is_high_tier ? 'high-tier' : ''} ${v.is_night ? 'night-violation' : ''}`}>
                  <div className="violation-date">{formatDate(v.date)}</div>
                  <div className="violation-details">
                    <span className="violation-type">
                      {v.code}
                      {v.is_high_tier && <span className="tier-badge high">HIGH</span>}
                      {v.is_night && <span className="tier-badge night">NIGHT</span>}
                    </span>
                    {v.description && <span className="violation-description">{v.description}</span>}
                    <span className="violation-location">{v.borough}</span>
                  </div>
                  <div className="violation-points">+3 pts</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <aside className="case-sidebar">
          <div className="case-actions-card">
            <h3 className="card-title">Case Actions</h3>
            <div className="case-actions-content">
              {action_state === 'READY_FOR_ALERT' && (
                <button className="action-btn-full primary" onClick={handleSendNotice} disabled={actionLoading}>
                  {actionLoading ? 'Sending...' : '📨 Send ISA Notice'}
                </button>
              )}
              {action_state === 'ALERT_SENT' && (
                <>
                  <div className="action-status-box blue"><strong>📨 ISA Notice Sent</strong><span>{formatDate(alerts[0]?.created_at)}</span></div>
                  <button className="action-btn-full secondary" onClick={handleMarkCompliant} disabled={actionLoading}>
                    {actionLoading ? 'Updating...' : '✓ Mark Compliant'}
                  </button>
                </>
              )}
              {action_state === 'COMPLIANT' && (
                <div className="action-status-box green"><strong>✓ ISA Installed</strong><span>{formatDate(alerts[0]?.updated_at)}</span></div>
              )}
              {action_state === 'BELOW_THRESHOLD' && (
                <div className="action-status-box gray"><strong>Below ISA Threshold</strong><span>Risk must reach 10 points</span></div>
              )}
            </div>
          </div>

          <div className="case-history-card">
            <h3 className="card-title">Case History</h3>
            <div className="history-timeline">
              {alerts.map((alert, i) => (
                <div key={i} className="history-item">
                  <div className="history-dot"></div>
                  <div className="history-content">
                    <div className="history-action">{alert.status === 'SENT' ? '📨 ISA Notice Sent' : alert.status === 'COMPLIANT' ? '✓ Compliant' : alert.status}</div>
                    <div className="history-meta">{formatDateTime(alert.updated_at || alert.created_at)}</div>
                  </div>
                </div>
              ))}
              {alerts.length === 0 && <p className="history-empty">No case history</p>}
            </div>
          </div>

          <div className="case-history-card">
            <h3 className="card-title">Summary</h3>
            <div className="summary-content">
              <div className="summary-row"><span>Total Violations</span><strong>{driver.violation_count}</strong></div>
              <div className="summary-row"><span>Risk Points</span><strong style={{ color: getRiskColor(driver.risk_points) }}>{driver.risk_points}</strong></div>
              <div className="summary-row"><span>First Violation</span><strong>{formatDate(driver.first_violation)}</strong></div>
              <div className="summary-row"><span>Last Violation</span><strong>{formatDate(driver.last_violation)}</strong></div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

export default DriverProfile;
