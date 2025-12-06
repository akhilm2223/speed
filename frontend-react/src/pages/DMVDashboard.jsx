import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import ActivityLog from '../components/ActivityLog';
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
  const [activeTab, setActiveTab] = useState('dashboard');
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

  // STATUS - Based on ISA threshold: ≥11 pts OR ≥16 tickets
  const getStatus = (driver) => {
    const points = driver.total_points || driver.risk_points || 0;
    const tickets = driver.violation_count || 0;
    const isSuperSpeeder = driver.severe_count > 0 || driver.crash_risk_score >= 75;
    
    // ISA Notice: ≥11 pts OR ≥16 tickets
    if (points >= 11 || tickets >= 16) {
      return { label: 'ISA Notice', class: 'status-isa-notice' };
    }
    // Super Speeder: has severe violations or very high crash risk
    if (isSuperSpeeder) {
      return { label: 'Super Speeder', class: 'status-super-speeder' };
    }
    // Monitoring: everyone else being tracked
    return { label: 'Monitoring', class: 'status-monitoring' };
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
      case 'isa_notice': 
        filtered = filtered.filter(d => {
          const points = d.total_points || d.risk_points || 0;
          const tickets = d.violation_count || 0;
          return (points >= 11 || tickets >= 16);
        });
        break;
      case 'super_speeder':
        filtered = filtered.filter(d => {
          const points = d.total_points || d.risk_points || 0;
          const tickets = d.violation_count || 0;
          const isIsaNotice = points >= 11 || tickets >= 16;
          const isSuperSpeeder = d.severe_count > 0 || d.crash_risk_score >= 75;
          return !isIsaNotice && isSuperSpeeder;
        });
        break;
      case 'nighttime': filtered = filtered.filter(d => d.is_night_heavy); break;
      case 'monitoring': 
        filtered = filtered.filter(d => {
          const points = d.total_points || d.risk_points || 0;
          const tickets = d.violation_count || 0;
          const isIsaNotice = points >= 11 || tickets >= 16;
          const isSuperSpeeder = d.severe_count > 0 || d.crash_risk_score >= 75;
          return !isIsaNotice && !isSuperSpeeder;
        });
        break;
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

  // Use KPIs from backend (accurate counts from full database)
  const statusCounts = {
    isaNotice: dashboard?.kpis?.isa_required || 0,
    monitoring: dashboard?.kpis?.monitoring || 0,
    superSpeeder: dashboard?.kpis?.super_speeders || 0,
    totalViolations: dashboard?.kpis?.total_violations || 0
  };

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
          <div className="header-tabs">
            <button 
              className={`header-tab ${activeTab === 'dashboard' ? 'active' : ''}`}
              onClick={() => setActiveTab('dashboard')}
            >
              Dashboard
            </button>
            <button 
              className={`header-tab ${activeTab === 'courts' ? 'active' : ''}`}
              onClick={() => setActiveTab('courts')}
            >
              Court Adapter
            </button>
          </div>
          <button className="nav-link" onClick={() => navigate('/map')}>Camera Network</button>
        </div>
      </header>

      {/* POLICY BAR */}
      <div className="policy-banner">
        <div className="policy-badge">
          <span className="policy-version">Policy {policy?.version || '0.1-draft'}</span>
          <span className="policy-rule">ISA Notice: ≥{policy?.isa_points_threshold || 11} pts OR ≥{policy?.isa_ticket_threshold || 16} tickets</span>
          <span className="policy-counter">Monitoring: &lt;{policy?.isa_points_threshold || 11} pts, &lt;{policy?.isa_ticket_threshold || 16} tickets</span>
          <span className="policy-counter">Super Speeder: ≥3 violations</span>
        </div>
      </div>

      {activeTab === 'dashboard' ? (
      <div className="dmv-content">
        <div className="dmv-layout-with-sidebar">
          <div className="dmv-main">
          {/* POLICY STATS STRIP */}
          <div className="policy-stats-strip">
            <div className="policy-stat-card">
              <div className="policy-stat-value">{statusCounts.isaNotice.toLocaleString()}</div>
              <div className="policy-stat-label">ISA Notice</div>
            </div>
            <div className="policy-stat-card">
              <div className="policy-stat-value">{statusCounts.monitoring.toLocaleString()}</div>
              <div className="policy-stat-label">Monitoring</div>
            </div>
            <div className="policy-stat-card">
              <div className="policy-stat-value">{statusCounts.superSpeeder.toLocaleString()}</div>
              <div className="policy-stat-label">Super Speeder</div>
            </div>
            <div className="policy-stat-card">
              <div className="policy-stat-value">{statusCounts.totalViolations.toLocaleString()}</div>
              <div className="policy-stat-label">Total Violations</div>
            </div>
          </div>

          {/* FILTER BAR */}
          <div className="filter-bar">
            <span className="filter-label">Filters:</span>
            {[
              { key: 'high_risk', label: 'High Risk' },
              { key: 'isa_notice', label: 'ISA Notice' },
              { key: 'super_speeder', label: 'Super Speeder' },
              { key: 'monitoring', label: 'Monitoring' },
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
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredQueue.length === 0 && (
                    <tr><td colSpan="9" className="empty-queue">
                      <div className="empty-state">
                        <p className="empty-title">No drivers match this filter</p>
                      </div>
                    </td></tr>
                  )}
                  {filteredQueue.map((driver, i) => {
                    const crashBadge = getCrashRiskBadge(driver.crash_risk_score);
                    const status = getStatus(driver);
                    const recency = getRecencyBadge(driver.last_violation);
                    const isHighRisk = driver.crash_risk_score >= 50;
                    
                    return (
                      <tr key={i} className={isHighRisk ? 'row-critical' : ''}>
                        <td className="col-select">
                          <input type="checkbox" checked={selectedDrivers.has(driver.plate_id)} onChange={() => toggleDriverSelection(driver.plate_id)} />
                        </td>
                        <td>
                          <div className="driver-info">
                            {driver.driver_license_number && (
                              <button 
                                className="license-link"
                                onClick={() => navigate(`/dmv/license/${driver.driver_license_number}`)}
                                title="View all violations for this license"
                              >
                                {driver.driver_license_number}
                              </button>
                            )}
                            <div className="plate-display">
                              {driver.plate_id} <span className="state-tag">{driver.state}</span>
                            </div>
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
                          <span className={`status-badge ${status.class}`}>{status.label}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
          {/* ACTIVITY LOG SIDEBAR */}
          <div className="dmv-sidebar-right">
            <ActivityLog onViolationClick={(violation) => {
              if (violation.driver_license_number) {
                navigate(`/dmv/license/${violation.driver_license_number}`);
              }
            }} />
          </div>
        </div>
      </div>
      ) : (
        /* COURT ADAPTER TAB */
        <div className="court-adapter-content">
          <div className="court-adapter-main">
            {/* Stats Strip */}
            {localCourts && (
              <div className="courts-stats-strip">
                <div className="court-stat-card">
                  <div className="stat-value">{localCourts.unique_counties?.toLocaleString()}</div>
                  <div className="stat-label">Counties</div>
                </div>
                <div className="court-stat-card">
                  <div className="stat-value">{localCourts.unique_courts?.toLocaleString()}</div>
                  <div className="stat-label">Courts</div>
                </div>
                <div className="court-stat-card">
                  <div className="stat-value">{localCourts.unique_police_agencies?.toLocaleString()}</div>
                  <div className="stat-label">Police Agencies</div>
                </div>
              </div>
            )}

            {/* Courts Lists */}
            <div className="courts-grid">
              <div className="courts-card">
                <h3>Most Active Counties</h3>
                <div className="courts-list">
                  {localCourts?.top_counties?.slice(0, 10).map((c, i) => (
                    <div key={i} className="court-list-item">
                      <span className="court-name">{c.county}</span>
                      <span className="court-count">{c.count?.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="courts-card">
                <h3>Top Ticket Issuers</h3>
                <div className="courts-list">
                  {localCourts?.top_courts?.slice(0, 10).map((c, i) => (
                    <div key={i} className="court-list-item">
                      <span className="court-name">{c.court}</span>
                      <span className="court-count">{c.count?.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Upload Button */}
            <div className="upload-section">
              <button className="upload-btn-large" onClick={() => navigate('/dmv/courts-upload')}>
                📤 Upload Court CSV
              </button>
              <p className="upload-hint">Upload violation records from local courts</p>
            </div>
          </div>
        </div>
      )}

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
