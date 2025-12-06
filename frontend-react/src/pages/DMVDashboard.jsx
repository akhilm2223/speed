import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/dmv.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

function DMVDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sendingNotice, setSendingNotice] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadDashboard();
    loadAlerts();
  }, []);

  const loadDashboard = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dmv/dashboard`);
      if (res.ok) {
        setDashboard(await res.json());
      }
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadAlerts = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dmv/alerts`);
      if (res.ok) setAlerts(await res.json());
    } catch (err) {
      console.error('Error:', err);
    }
  };

  const handleSendNotice = async (plateId) => {
    setSendingNotice(plateId);
    try {
      const res = await fetch(`${API_BASE}/api/dmv/alerts/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plate_id: plateId })
      });
      if (res.ok) {
        const data = await res.json();
        setAlerts(prev => [{
          id: data.alert_id, plate_id: plateId, status: 'SENT',
          timestamp: new Date().toISOString(), message: `${plateId} – ISA Notice Sent`
        }, ...prev]);
        loadDashboard();
      }
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setSendingNotice(null);
    }
  };

  const getRiskColor = (risk) => {
    if (risk >= 10) return '#B0181A';
    if (risk >= 5) return '#C98F00';
    return '#3E6D45';
  };

  const getStatusBadge = (driver) => {
    if (driver.action_state === 'COMPLIANT') return { label: 'Compliant', class: 'badge-green' };
    if (driver.action_state === 'ALERT_SENT') return { label: 'Notice Sent', class: 'badge-blue' };
    if (driver.status === 'ISA_REQUIRED') return { label: 'ISA Required', class: 'badge-red' };
    return { label: 'Monitoring', class: 'badge-amber' };
  };

  const formatDate = (d) => d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—';
  const formatTime = (d) => d ? new Date(d).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : '';

  if (loading) {
    return <div className="dmv-loading"><div className="spinner"></div><p>Loading...</p></div>;
  }

  return (
    <div className="dmv-dashboard">
      <header className="dmv-header">
        <div className="header-left">
          <div className="dmv-logo">
            <span className="logo-icon">🛡️</span>
            <span className="logo-text">NYC DMV — ISA Enforcement Operations</span>
          </div>
        </div>
        <div className="header-right">
          <button className="nav-link" onClick={() => navigate('/map')}>🗺️ Camera Network</button>
        </div>
      </header>

      <div className="dmv-content">
        <div className="dmv-main">
          {/* KPI Cards */}
          <div className="kpi-strip">
            <div className="kpi-card kpi-red">
              <div className="kpi-value">{dashboard?.kpis?.isa_required || 0}</div>
              <div className="kpi-label">ISA-Required Drivers</div>
              <div className="kpi-sublabel">Risk ≥ 10 points</div>
            </div>
            <div className="kpi-card kpi-amber">
              <div className="kpi-value">{dashboard?.kpis?.monitoring || 0}</div>
              <div className="kpi-label">Under Monitoring</div>
              <div className="kpi-sublabel">Risk 5-9 points</div>
            </div>
            <div className="kpi-card kpi-blue">
              <div className="kpi-value">{dashboard?.kpis?.super_speeders || 0}</div>
              <div className="kpi-label">🔥 Super Speeders</div>
              <div className="kpi-sublabel">3+ violations (Jan-Sep 2025)</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-value">{dashboard?.kpis?.cross_borough_violators || 0}</div>
              <div className="kpi-label">Cross-Borough</div>
              <div className="kpi-sublabel">Multi-area speeders</div>
            </div>
          </div>

          {/* Secondary KPIs */}
          <div className="kpi-secondary">
            <span>📍 Highest-Risk Corridor: <strong>{dashboard?.kpis?.highest_corridor}</strong> ({dashboard?.kpis?.corridor_violations?.toLocaleString()} violations)</span>
            <span>📅 Latest Violation: <strong>{formatDate(dashboard?.kpis?.latest_violation)}</strong></span>
          </div>

          {/* Enforcement Queue */}
          <div className="queue-section">
            <h2 className="section-title">Enforcement Queue</h2>
            <div className="queue-table-container">
              <table className="queue-table">
                <thead>
                  <tr>
                    <th>Plate ID</th>
                    <th>Violations</th>
                    <th>Severe (1180D)</th>
                    <th>Risk Score</th>
                    <th>Last Violation</th>
                    <th>Borough</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard?.queue?.length === 0 && (
                    <tr><td colSpan="8" className="empty-queue">
                      <div className="empty-state">
                        <span className="empty-icon">📋</span>
                        <p className="empty-title">No drivers in queue</p>
                      </div>
                    </td></tr>
                  )}
                  {dashboard?.queue?.map((driver, i) => {
                    const badge = getStatusBadge(driver);
                    return (
                      <tr key={i} className={driver.status === 'ISA_REQUIRED' && driver.action_state === 'READY_FOR_ALERT' ? 'row-highlight' : ''}>
                        <td>
                          <button className="plate-link" onClick={() => navigate(`/dmv/drivers/${driver.plate_id}`)}>
                            {driver.plate_id}
                          </button>
                        </td>
                        <td>{driver.violation_count}</td>
                        <td className={driver.high_tier_count > 0 ? 'severe-count' : ''}>{driver.high_tier_count}</td>
                        <td>
                          <div className="risk-cell">
                            <span className="risk-value" style={{ color: getRiskColor(driver.risk_points) }}>
                              {driver.risk_points}
                            </span>
                            <div className="risk-bar-container">
                              <div className="risk-bar-fill" style={{ 
                                width: `${Math.min(driver.risk_points / 15 * 100, 100)}%`,
                                backgroundColor: getRiskColor(driver.risk_points)
                              }}></div>
                              <div className="risk-threshold-marker"></div>
                            </div>
                          </div>
                        </td>
                        <td>{formatDate(driver.last_violation)}</td>
                        <td>
                          {driver.primary_borough}
                          {driver.is_cross_borough && <span className="cross-badge" title="Multiple boroughs">+</span>}
                        </td>
                        <td>
                          <span className={`status-badge ${badge.class}`}>{badge.label}</span>
                          {driver.is_night_heavy && <span className="night-badge" title="50%+ nighttime">🌙</span>}
                        </td>
                        <td>
                          {driver.action_state === 'READY_FOR_ALERT' && (
                            <button className="action-btn action-primary" onClick={() => handleSendNotice(driver.plate_id)} disabled={sendingNotice === driver.plate_id}>
                              {sendingNotice === driver.plate_id ? 'Sending...' : 'Send ISA Notice'}
                            </button>
                          )}
                          {driver.action_state === 'ALERT_SENT' && (
                            <button className="action-btn action-secondary" onClick={() => navigate(`/dmv/drivers/${driver.plate_id}`)}>View Case</button>
                          )}
                          {driver.action_state === 'COMPLIANT' && <span className="compliant-text">✓ ISA Installed</span>}
                          {driver.action_state === 'BELOW_THRESHOLD' && <span className="threshold-text">Below threshold</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Alert Feed */}
        <aside className="alert-feed">
          <h3 className="feed-title">Alert Activity Log</h3>
          <div className="feed-list">
            {alerts.map((alert, i) => (
              <div key={i} className="feed-item">
                <div className="feed-time">{formatTime(alert.timestamp)}</div>
                <div className="feed-content">
                  <div className="feed-message">{alert.message}</div>
                </div>
              </div>
            ))}
            {alerts.length === 0 && <p className="feed-empty">No alerts yet</p>}
          </div>
        </aside>
      </div>
    </div>
  );
}

export default DMVDashboard;
