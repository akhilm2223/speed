import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/dmv.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

function DMVDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [activeFilter, setActiveFilter] = useState('high_risk');
  const [selectedDrivers, setSelectedDrivers] = useState(new Set());
  const [localCourts, setLocalCourts] = useState(null);
  const [countyStats, setCountyStats] = useState(null);
  const [impactMetrics, setImpactMetrics] = useState(null);
  const [showLocalCourtsPanel, setShowLocalCourtsPanel] = useState(false);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const navigate = useNavigate();

  // Enable page scrolling (override body overflow:hidden)
  useEffect(() => {
    document.body.style.overflow = 'auto';
    return () => {
      document.body.style.overflow = '';
    };
  }, []);

  // Scroll to top button visibility
  useEffect(() => {
    const handleScroll = () => {
      setShowScrollTop(window.scrollY > 300);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  useEffect(() => {
    loadDashboard();
    loadAlerts();
    loadLocalCourts();
    loadCountyStats();
    loadImpactMetrics();
  }, []);

  const loadDashboard = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dmv/dashboard`);
      if (res.ok) setDashboard(await res.json());
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

  const loadLocalCourts = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dmv/local-courts/summary`);
      if (res.ok) setLocalCourts(await res.json());
    } catch (err) {
      console.error('Error loading local courts:', err);
    }
  };

  const loadCountyStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dmv/county-stats`);
      if (res.ok) setCountyStats(await res.json());
    } catch (err) {
      console.error('Error loading county stats:', err);
    }
  };

  const loadImpactMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dmv/impact-metrics`);
      if (res.ok) setImpactMetrics(await res.json());
    } catch (err) {
      console.error('Error loading impact metrics:', err);
    }
  };

  const handleSendNotice = async (plateId) => {
    setActionLoading(plateId);
    try {
      const res = await fetch(`${API_BASE}/api/dmv/alerts/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plate_id: plateId })
      });
      if (res.ok) {
        loadDashboard();
        loadAlerts();
      }
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleBatchSend = async () => {
    if (selectedDrivers.size === 0) return;
    setActionLoading('batch');
    for (const plateId of selectedDrivers) {
      await handleSendNotice(plateId);
    }
    setSelectedDrivers(new Set());
    setActionLoading(null);
  };

  const toggleDriverSelection = (plateId) => {
    setSelectedDrivers(prev => {
      const next = new Set(prev);
      if (next.has(plateId)) next.delete(plateId);
      else next.add(plateId);
      return next;
    });
  };

  // CRASH RISK BADGES
  const getCrashRiskBadge = (score) => {
    if (score >= 75) return { label: 'HIGH RISK', class: 'crash-high' };
    if (score >= 50) return { label: 'DANGEROUS', class: 'crash-danger' };
    if (score >= 25) return { label: 'CONCERNING', class: 'crash-warning' };
    return { label: 'LOW', class: 'crash-low' };
  };

  // ENFORCEMENT STAGE
  const getEnforcementButton = (driver) => {
    const status = driver.enforcement_status;
    if (status === 'COMPLIANT') return { label: 'Compliant', class: 'stage-compliant', disabled: true };
    if (status === 'ESCALATED') return { label: 'Escalated', class: 'stage-escalated', disabled: true };
    if (status === 'FOLLOW_UP_DUE') return { label: 'Follow-Up', class: 'stage-followup', disabled: false };
    if (status === 'NOTICE_SENT') return { label: 'Sent', class: 'stage-sent', disabled: true };
    if (driver.status === 'ISA_REQUIRED') return { label: 'New', class: 'stage-new', disabled: false };
    return { label: 'Monitor', class: 'stage-monitor', disabled: true };
  };

  // RECENCY INDICATOR - Shows actual date for historical data
  const getRecencyBadge = (lastViolation) => {
    if (!lastViolation) return { class: 'recency-old', label: '—' };
    const date = new Date(lastViolation);
    const formatted = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' });
    return { class: 'recency-moderate', label: formatted };
  };

  // FILTER LOGIC
  const getFilteredQueue = () => {
    if (!dashboard?.queue) return [];
    let filtered = [...dashboard.queue];
    
    switch (activeFilter) {
      case 'high_risk': filtered = filtered.filter(d => d.crash_risk_score >= 50); break;
      case 'pending_followup': filtered = filtered.filter(d => d.enforcement_status === 'FOLLOW_UP_DUE'); break;
      case 'nighttime': filtered = filtered.filter(d => d.is_night_heavy); break;
      case 'isa_required': filtered = filtered.filter(d => d.status === 'ISA_REQUIRED' && d.enforcement_status === 'NEW'); break;
      case 'recent': 
        // Sort by most recent violation date (not filter - show all sorted by recency)
        filtered = filtered.filter(d => d.last_violation).sort((a, b) => 
          new Date(b.last_violation) - new Date(a.last_violation)
        );
        break;
      default: break;
    }
    return filtered;
  };

  const formatDate = (d) => d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '—';
  const formatTime = (d) => d ? new Date(d).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : '';

  if (loading) return <div className="dmv-loading"><div className="spinner"></div><p>Loading...</p></div>;

  const policy = dashboard?.policy;
  const filteredQueue = getFilteredQueue();
  const canBatchSend = selectedDrivers.size > 0;

  return (
    <div className="dmv-dashboard">
      {/* HEADER */}
      <header className="dmv-header">
        <div className="header-left">
          <div className="dmv-logo">
            <span className="logo-text">NY DMV — ISA Enforcement Command</span>
          </div>
        </div>
        <div className="header-right">
          <button className="nav-link" onClick={() => navigate('/map')}>Camera Network</button>
        </div>
      </header>

      {/* POLICY BAR */}
      <div className="policy-banner">
        <div className="policy-badge">
          <span className="policy-version">Policy {policy?.version}</span>
          <span className="policy-rule">ISA: ≥{policy?.isa_points_threshold} pts OR ≥{policy?.isa_ticket_threshold} tickets</span>
        </div>
        {dashboard?.data_source && (
          <div className="data-source-tag">{dashboard.data_source.name}</div>
        )}
      </div>

      <div className="dmv-content">
        <div className="dmv-main">
          {/* GOVERNOR-READY IMPACT STRIP */}
          {impactMetrics && (
            <div className="impact-strip">
              <div className="impact-item">
                <span className="impact-value">{impactMetrics.high_risk_pending_notice?.toLocaleString()}</span>
                <span className="impact-label">High-Risk Pending Notice</span>
              </div>
              <div className="impact-item">
                <span className="impact-value">{impactMetrics.cross_jurisdiction_offenders?.toLocaleString()}</span>
                <span className="impact-label">Cross-Jurisdiction Offenders</span>
              </div>
              <div className="impact-item highlight">
                <span className="impact-value">{impactMetrics.potential_lives_saved?.toLocaleString()}</span>
                <span className="impact-label">Est. Lives Saveable (ISA)</span>
              </div>
            </div>
          )}

          {/* KPI CARDS */}
          <div className="kpi-strip">
            <div className="kpi-card kpi-critical" onClick={() => setActiveFilter('isa_required')}>
              <div className="kpi-value">{dashboard?.kpis?.isa_required || 0}</div>
              <div className="kpi-label">ISA Required</div>
              <div className="kpi-action">Click to filter →</div>
            </div>
            <div className="kpi-card" onClick={() => setActiveFilter('all')}>
              <div className="kpi-value">{dashboard?.kpis?.monitoring || 0}</div>
              <div className="kpi-label">Monitoring</div>
            </div>
            <div className="kpi-card" onClick={() => setActiveFilter('nighttime')}>
              <div className="kpi-value">{dashboard?.kpis?.super_speeders || 0}</div>
              <div className="kpi-label">Super Speeders</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-value">{dashboard?.kpis?.cross_jurisdiction_offenders || dashboard?.kpis?.cross_borough_violators || 0}</div>
              <div className="kpi-label">Cross-Jurisdiction</div>
            </div>
          </div>

          {/* COUNTY RISK CARDS */}
          {countyStats && (
            <div className="county-risk-strip">
              <div className="county-card top-risk">
                <div className="county-info">
                  <div className="county-label">Top Risk County</div>
                  <div className="county-name">{countyStats.top_risk_county?.county || 'N/A'}</div>
                  <div className="county-stat">{countyStats.top_risk_county?.crash_risk_score}% crash risk</div>
                </div>
              </div>
              <div className="county-card most-severe">
                <div className="county-info">
                  <div className="county-label">Most 1180D Violations</div>
                  <div className="county-name">{countyStats.most_1180d_county?.county || 'N/A'}</div>
                  <div className="county-stat">{countyStats.most_1180d_county?.count?.toLocaleString()} severe</div>
                </div>
              </div>
              <div className="county-card top-five">
                <div className="county-info">
                  <div className="county-label">Top 5 Counties by Risk</div>
                  <div className="county-list">
                    {countyStats.county_crash_risk?.slice(0, 5).map((c, i) => (
                      <span key={i} className="county-tag">{c.county}</span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* LOCAL COURTS ADAPTER PANEL */}
          <div className="local-courts-panel">
            <div className="panel-header" onClick={() => setShowLocalCourtsPanel(!showLocalCourtsPanel)}>
              <span className="panel-title">Local Courts Adapter</span>
              {localCourts && (
                <span className="panel-stats">
                  {localCourts.unique_courts?.toLocaleString()} courts • {localCourts.unique_counties?.toLocaleString()} counties
                </span>
              )}
              <span className="panel-toggle">{showLocalCourtsPanel ? '−' : '+'}</span>
            </div>
            {showLocalCourtsPanel && localCourts && (
              <div className="panel-content">
                <div className="courts-summary">
                  <div className="summary-item">
                    <span className="summary-value">{localCourts.unique_counties?.toLocaleString()}</span>
                    <span className="summary-label">Counties Loaded</span>
                  </div>
                  <div className="summary-item">
                    <span className="summary-value">{localCourts.unique_courts?.toLocaleString()}</span>
                    <span className="summary-label">Courts Detected</span>
                  </div>
                  <div className="summary-item">
                    <span className="summary-value">{localCourts.unique_police_agencies?.toLocaleString()}</span>
                    <span className="summary-label">Police Agencies</span>
                  </div>
                </div>
                <div className="courts-lists">
                  <div className="courts-list-section">
                    <h4>Most Active Counties</h4>
                    {localCourts.top_counties?.slice(0, 5).map((c, i) => (
                      <div key={i} className="list-item">
                        <span className="item-name">{c.county}</span>
                        <span className="item-count">{c.count?.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                  <div className="courts-list-section">
                    <h4>Top Ticket Issuers</h4>
                    {localCourts.top_courts?.slice(0, 5).map((c, i) => (
                      <div key={i} className="list-item">
                        <span className="item-name">{c.court}</span>
                        <span className="item-count">{c.count?.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <button className="upload-btn" onClick={() => navigate('/dmv/courts-upload')}>
                  Upload Court CSV
                </button>
              </div>
            )}
          </div>

          {/* FILTER BAR */}
          <div className="filter-bar">
            <span className="filter-label">Filters:</span>
            {[
              { key: 'high_risk', label: 'High Risk' },
              { key: 'isa_required', label: 'Needs Notice' },
              { key: 'pending_followup', label: 'Follow-Up' },
              { key: 'nighttime', label: 'Nighttime' },
              { key: 'recent', label: 'By Date' },
              { key: 'all', label: 'All' },
            ].map(f => (
              <button key={f.key} className={`filter-btn ${activeFilter === f.key ? 'active' : ''}`} onClick={() => setActiveFilter(f.key)}>
                {f.label}
              </button>
            ))}
            <span className="filter-count">{filteredQueue.length} drivers</span>
            
            {/* BATCH ACTIONS */}
            {canBatchSend && (
              <button className="batch-btn" onClick={handleBatchSend} disabled={actionLoading === 'batch'}>
                Send {selectedDrivers.size} Notices
              </button>
            )}
          </div>

          {/* ENFORCEMENT QUEUE */}
          <div className="queue-section">
            <h2 className="section-title">Enforcement Queue</h2>
            <div className="queue-table-container">
              <table className="queue-table">
                <thead>
                  <tr>
                    <th className="col-select">
                      <input type="checkbox" onChange={(e) => {
                        if (e.target.checked) {
                          const actionable = filteredQueue.filter(d => d.status === 'ISA_REQUIRED' && d.enforcement_status === 'NEW');
                          setSelectedDrivers(new Set(actionable.map(d => d.plate_id)));
                        } else {
                          setSelectedDrivers(new Set());
                        }
                      }} />
                    </th>
                    <th>License / Plate</th>
                    <th>Violations / Points</th>
                    <th>Crash Risk</th>
                    <th>Risk Factors</th>
                    <th>Last Seen</th>
                    <th>Agency</th>
                    <th>Ticket Issuer</th>
                    <th>Stage</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredQueue.length === 0 && (
                    <tr><td colSpan="10" className="empty-queue">
                      <div className="empty-state">
                        <p className="empty-title">No drivers match this filter</p>
                      </div>
                    </td></tr>
                  )}
                  {filteredQueue.map((driver, i) => {
                    const crashBadge = getCrashRiskBadge(driver.crash_risk_score);
                    const stageBtn = getEnforcementButton(driver);
                    const recency = getRecencyBadge(driver.last_violation);
                    const isHighRisk = driver.crash_risk_score >= 50;
                    const canSelect = driver.status === 'ISA_REQUIRED' && driver.enforcement_status === 'NEW';
                    
                    return (
                      <tr key={i} className={isHighRisk ? 'row-critical' : ''}>
                        <td className="col-select">
                          {canSelect && (
                            <input type="checkbox" checked={selectedDrivers.has(driver.plate_id)} onChange={() => toggleDriverSelection(driver.plate_id)} />
                          )}
                        </td>
                        <td>
                          <div className="driver-info">
                            {driver.driver_license_number && (
                              <div className="license-number">
                                <span className="label">License:</span>
                                <span className="value">{driver.driver_license_number}</span>
                              </div>
                            )}
                            <button className="plate-link" onClick={() => navigate(`/dmv/drivers/${driver.plate_id}`)}>
                              Plate: {driver.plate_id}
                            </button>
                            <div className="driver-meta-small">{driver.state}</div>
                          </div>
                        </td>
                        <td>
                          <div className="violations-points">
                            <div className="violations-count">
                              <span className="label">Violations:</span>
                              <span className="value">{driver.violation_count}</span>
                            </div>
                            <div className="points-count">
                              <span className="label">Points:</span>
                              <span className="value">{driver.total_points || driver.risk_points}</span>
                            </div>
                          </div>
                        </td>
                        <td>
                          <div className="crash-cell">
                            <span className={`crash-badge ${crashBadge.class}`}>{driver.crash_risk_score}%</span>
                            <span className="crash-label">{crashBadge.label}</span>
                          </div>
                        </td>
                        <td>
                          <div className="risk-factors">
                            {driver.severe_count > 0 && <span className="factor-tag severe">{driver.severe_count} severe</span>}
                            {driver.is_night_heavy && <span className="factor-tag night">{driver.night_percentage}% night</span>}
                            {driver.is_cross_borough && <span className="factor-tag geo">{driver.borough_count} areas</span>}
                            {driver.violation_count >= 5 && <span className="factor-tag repeat">{driver.violation_count} tickets</span>}
                          </div>
                        </td>
                        <td>
                          <span className={`recency-badge ${recency.class}`}>{recency.label}</span>
                        </td>
                        <td>
                          <span className="agency-tag" title={driver.police_agency}>
                            {driver.police_agency ? (driver.police_agency.length > 15 ? driver.police_agency.substring(0, 15) + '...' : driver.police_agency) : '—'}
                          </span>
                        </td>
                        <td>
                          <span className={driver.jurisdiction_type === 'NYC_DOF' ? 'court-nyc' : 'court-local'} title={driver.court_name || driver.ticket_issuer}>
                            {driver.court_name || driver.ticket_issuer ? ((driver.court_name || driver.ticket_issuer).length > 15 ? (driver.court_name || driver.ticket_issuer).substring(0, 15) + '...' : (driver.court_name || driver.ticket_issuer)) : 'Local'}
                          </span>
                        </td>
                        <td>
                          <span className={`stage-badge ${stageBtn.class}`}>{stageBtn.label}</span>
                        </td>
                        <td>
                          {canSelect && (
                            <button className="action-btn-send" onClick={() => handleSendNotice(driver.plate_id)} disabled={actionLoading === driver.plate_id}>
                              {actionLoading === driver.plate_id ? '...' : 'Send'}
                            </button>
                          )}
                          {driver.enforcement_status === 'FOLLOW_UP_DUE' && (
                            <button className="action-btn-review" onClick={() => navigate(`/dmv/drivers/${driver.plate_id}`)}>Review</button>
                          )}
                          {stageBtn.disabled && stageBtn.label !== 'Monitor' && <span className="action-done">✓</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* ACTIVITY FEED */}
        <aside className="alert-feed">
          <h3 className="feed-title">Activity Log</h3>
          <div className="feed-list">
            {alerts.slice(0, 20).map((alert, i) => (
              <div key={i} className="feed-item">
                <div className="feed-time">{formatTime(alert.timestamp)}</div>
                <div className="feed-content">
                  <div className="feed-message">{alert.message}</div>
                </div>
              </div>
            ))}
            {alerts.length === 0 && <p className="feed-empty">No activity yet</p>}
          </div>
        </aside>
      </div>

      {/* Scroll to Top Button */}
      {showScrollTop && (
        <button className="scroll-top-btn" onClick={scrollToTop} title="Scroll to top">
          ↑
        </button>
      )}
    </div>
  );
}

export default DMVDashboard;
