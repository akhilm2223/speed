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

  const handleTransition = async (alertId, newStatus) => {
    setActionLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/dmv/alerts/${alertId}/transition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
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

  const getCrashRiskColor = (score) => {
    if (score >= 75) return '#B71C1C';
    if (score >= 50) return '#E65100';
    if (score >= 25) return '#F57F17';
    return '#2E7D32';
  };

  const getCrashRiskBadge = (score) => {
    if (score >= 75) return { label: 'HIGH RISK', class: 'crash-high' };
    if (score >= 50) return { label: 'DANGEROUS', class: 'crash-danger' };
    if (score >= 25) return { label: 'CONCERNING', class: 'crash-warning' };
    return { label: 'LOW', class: 'crash-low' };
  };

  const formatDate = (d) => d ? new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : '—';
  const formatDateTime = (d) => d ? new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';

  if (loading) return <div className="dmv-loading"><div className="spinner"></div><p>Loading...</p></div>;

  if (!profile) {
    return (
      <div className="driver-profile">
        <header className="dmv-header">
          <div className="header-left"><div className="dmv-logo"><span className="logo-icon">🛡️</span><span className="logo-text">NY DMV — ISA Enforcement Operations</span></div></div>
        </header>
        <div style={{ padding: '60px', textAlign: 'center' }}>
          <p style={{ fontSize: '18px', marginBottom: '20px' }}>Driver not found: {plateId}</p>
          <button className="action-btn action-secondary" onClick={() => navigate('/dmv')}>← Back to Dashboard</button>
        </div>
      </div>
    );
  }

  const { driver, violations, alerts, policy } = profile;
  const isaThreshold = policy?.isa_points_threshold || 11;
  const crashBadge = getCrashRiskBadge(driver.crash_risk_score);
  const latestAlert = alerts?.[0];
  const enforcementStatus = driver.enforcement_status || 'NEW';

  return (
    <div className="driver-profile">
      <header className="dmv-header">
        <div className="header-left"><div className="dmv-logo"><span className="logo-icon">🛡️</span><span className="logo-text">NY DMV — ISA Enforcement Operations</span></div></div>
        <div className="header-right"><button className="nav-link" onClick={() => navigate('/dmv')}>← Back to Dashboard</button></div>
      </header>

      {/* Policy Badge */}
      {policy && (
        <div className="policy-banner">
          <div className="policy-badge">
            <span className="policy-version">Policy: ISA Draft {policy.version}</span>
            <span className="policy-hint">
              Court: {driver.court_name} ({driver.jurisdiction_type === 'NYC_DOF' ? 'NYC' : 'Local'})
            </span>
          </div>
        </div>
      )}

      <div className="profile-content">
        <div className="profile-main">
          {/* Driver Header */}
          <div className="driver-header-card">
            <div className="driver-header-top">
              <div className="driver-identity">
                <h1>{driver.plate_id}</h1>
                <div className="driver-meta">
                  <span>State: {driver.state}</span>
                  <span>Court: {driver.court_name}</span>
                  {driver.is_cross_borough && <span className="cross-borough-tag">Cross-Jurisdiction</span>}
                </div>
              </div>
              <div className="crash-risk-display">
                <div className={`crash-badge-large ${crashBadge.class}`}>
                  <span className="crash-score">{driver.crash_risk_score}%</span>
                  <span className="crash-label">{crashBadge.label}</span>
                </div>
              </div>
            </div>

            {/* Crash Risk Bar */}
            <div className="risk-score-display">
              <div className="risk-score-big">
                <div className="risk-number" style={{ color: getCrashRiskColor(driver.crash_risk_score) }}>
                  {driver.crash_risk_score}
                </div>
                <div className="risk-label">Crash Risk %</div>
              </div>
              <div className="risk-bar-large">
                <div className="risk-bar-track">
                  <div className="risk-bar-fill-large" style={{ 
                    width: `${driver.crash_risk_score}%`,
                    backgroundColor: getCrashRiskColor(driver.crash_risk_score)
                  }}></div>
                  <div className="risk-threshold-line" style={{ left: '50%' }}></div>
                  <span className="risk-threshold-label" style={{ left: '50%' }}>Danger Zone (50%)</span>
                </div>
                <div className="risk-bar-labels">
                  <span>0% Low</span>
                  <span>25% Moderate</span>
                  <span>50% Dangerous</span>
                  <span>75%+ High Fatality</span>
                </div>
              </div>
            </div>
          </div>

          {/* Why This Driver Matters Card */}
          <div className="why-matters-card">
            <h3 className="card-title">⚠️ Why This Driver Matters</h3>
            <div className="why-matters-content">
              <div className="matter-stat">
                <span className="matter-value" style={{ color: getCrashRiskColor(driver.crash_risk_score) }}>
                  {driver.crash_risk_score}%
                </span>
                <span className="matter-label">Crash Risk Score</span>
              </div>
              <div className="matter-stat">
                <span className="matter-value">{driver.night_percentage}%</span>
                <span className="matter-label">Nighttime Violations</span>
              </div>
              <div className="matter-stat">
                <span className="matter-value">{driver.borough_count}</span>
                <span className="matter-label">Jurisdictions</span>
              </div>
              <div className="matter-stat">
                <span className="matter-value">{driver.severe_count}</span>
                <span className="matter-label">Severe Violations</span>
              </div>
              <div className="matter-stat lives-stat">
                <span className="matter-value">{driver.lives_at_stake}</span>
                <span className="matter-label">Lives at Stake*</span>
              </div>
            </div>
            <p className="matter-footnote">*Predicted crash likelihood × 1.8 avg vehicle occupancy</p>
          </div>

          {/* Risk Signal Cards */}
          <div className="signal-cards">
            <div className="signal-card">
              <div className="signal-icon">⚡</div>
              <div className="signal-content">
                <div className="signal-title">Severity</div>
                <div className="signal-value">Severe: {driver.severe_count} of {driver.violation_count}</div>
                <div className="signal-sub">High-tier (1180D): {driver.high_tier_count}</div>
              </div>
            </div>
            <div className={`signal-card ${driver.night_percentage >= 50 ? 'signal-warning' : ''}`}>
              <div className="signal-icon">🌙</div>
              <div className="signal-content">
                <div className="signal-title">Nighttime</div>
                <div className="signal-value">{driver.night_percentage}% at night</div>
                <div className="signal-sub">{driver.night_violations} violations (10pm-4am)</div>
              </div>
            </div>
            <div className={`signal-card ${driver.is_cross_borough ? 'signal-warning' : ''}`}>
              <div className="signal-icon">📍</div>
              <div className="signal-content">
                <div className="signal-title">Cross-Jurisdiction</div>
                <div className="signal-value">{driver.borough_count} jurisdiction{driver.borough_count > 1 ? 's' : ''}</div>
                <div className="signal-sub">{driver.boroughs_affected?.join(', ')}</div>
              </div>
            </div>
            <div className="signal-card">
              <div className="signal-icon">⚖️</div>
              <div className="signal-content">
                <div className="signal-title">Court</div>
                <div className="signal-value">{driver.court_name}</div>
                <div className="signal-sub">{driver.jurisdiction_type === 'NYC_DOF' ? 'NYC Dept of Finance' : 'Local Court'}</div>
              </div>
            </div>
          </div>

          {/* Cross-Jurisdiction Badges */}
          {driver.is_cross_borough && (
            <div className="cross-jurisdiction-badges">
              <span className="cj-badge counties">📍 Cross-County Offender: {driver.borough_count} counties</span>
              {driver.violation_count >= 5 && <span className="cj-badge repeat">🔁 Repeat Offender</span>}
            </div>
          )}

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
                  <div className="violation-points">+{v.points} pts</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <aside className="case-sidebar">
          {/* Enforcement Actions */}
          <div className="case-actions-card">
            <h3 className="card-title">Enforcement Actions</h3>
            <div className="case-actions-content">
              {enforcementStatus === 'NEW' && driver.status === 'ISA_REQUIRED' && (
                <button className="action-btn-full primary" onClick={handleSendNotice} disabled={actionLoading}>
                  {actionLoading ? 'Sending...' : '📨 Send ISA Notice'}
                </button>
              )}
              {enforcementStatus === 'NOTICE_SENT' && latestAlert && (
                <>
                  <div className="action-status-box blue">
                    <strong>📨 Notice Sent</strong>
                    <span>{formatDate(latestAlert.created_at)}</span>
                  </div>
                  <button className="action-btn-full secondary" onClick={() => handleTransition(latestAlert.id, 'FOLLOW_UP_DUE')} disabled={actionLoading}>
                    {actionLoading ? 'Updating...' : '📋 Mark Follow-Up Due'}
                  </button>
                </>
              )}
              {enforcementStatus === 'FOLLOW_UP_DUE' && latestAlert && (
                <>
                  <div className="action-status-box amber">
                    <strong>📋 Follow-Up Due</strong>
                    <span>Action required</span>
                  </div>
                  <button className="action-btn-full primary" onClick={handleMarkCompliant} disabled={actionLoading}>
                    {actionLoading ? 'Updating...' : '✓ Mark Compliant'}
                  </button>
                  <button className="action-btn-full danger" onClick={() => handleTransition(latestAlert.id, 'ESCALATED')} disabled={actionLoading}>
                    ⚠️ Escalate
                  </button>
                </>
              )}
              {enforcementStatus === 'COMPLIANT' && (
                <div className="action-status-box green">
                  <strong>✓ ISA Installed</strong>
                  <span>{formatDate(latestAlert?.updated_at)}</span>
                </div>
              )}
              {enforcementStatus === 'ESCALATED' && (
                <div className="action-status-box red">
                  <strong>⚠️ Escalated</strong>
                  <span>Requires supervisor review</span>
                </div>
              )}
              {enforcementStatus === 'NEW' && driver.status !== 'ISA_REQUIRED' && (
                <div className="action-status-box gray">
                  <strong>Below ISA Threshold</strong>
                  <span>Points must reach {isaThreshold}</span>
                </div>
              )}
            </div>
          </div>

          {/* Case History */}
          <div className="case-history-card">
            <h3 className="card-title">Enforcement History</h3>
            <div className="history-timeline">
              {alerts.map((alert, i) => (
                <div key={i} className="history-item">
                  <div className={`history-dot ${alert.status === 'COMPLIANT' ? 'dot-green' : alert.status === 'ESCALATED' ? 'dot-red' : ''}`}></div>
                  <div className="history-content">
                    <div className="history-action">
                      {alert.status === 'NOTICE_SENT' && '📨 Notice Sent'}
                      {alert.status === 'FOLLOW_UP_DUE' && '📋 Follow-Up Due'}
                      {alert.status === 'COMPLIANT' && '✓ Compliant'}
                      {alert.status === 'ESCALATED' && '⚠️ Escalated'}
                      {alert.status === 'NEW' && '🆕 Case Created'}
                    </div>
                    <div className="history-meta">{formatDateTime(alert.updated_at || alert.created_at)}</div>
                  </div>
                </div>
              ))}
              {alerts.length === 0 && <p className="history-empty">No enforcement history</p>}
            </div>
          </div>

          {/* Summary */}
          <div className="case-history-card">
            <h3 className="card-title">Case Summary</h3>
            <div className="summary-content">
              <div className="summary-row">
                <span>Crash Risk</span>
                <strong style={{ color: getCrashRiskColor(driver.crash_risk_score) }}>{driver.crash_risk_score}%</strong>
              </div>
              <div className="summary-row"><span>ISA Points</span><strong>{driver.risk_points}</strong></div>
              <div className="summary-row"><span>Total Tickets</span><strong>{driver.violation_count}</strong></div>
              <div className="summary-row"><span>Severe</span><strong>{driver.severe_count}</strong></div>
              <div className="summary-row"><span>Night %</span><strong>{driver.night_percentage}%</strong></div>
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
