import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import MapView from './pages/MapView';
import DriverProfile from './pages/DriverProfile';
import LicenseViolations from './pages/LicenseViolations';
import DMVDashboard from './pages/DMVDashboard';
import './index.css';
import './styles/dmv.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

// ============================================
// DMV DASHBOARD CONTENT (Tab 1)
// ============================================
function DMVDashboardContent() {
  const [dashboard, setDashboard] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [activeFilter, setActiveFilter] = useState('high_risk');
  const [selectedDrivers, setSelectedDrivers] = useState(new Set());
  const [countyStats, setCountyStats] = useState(null);
  const [impactMetrics, setImpactMetrics] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadDashboard();
    loadAlerts();
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

  const getCrashRiskBadge = (score) => {
    if (score >= 75) return { label: 'HIGH RISK', class: 'crash-high' };
    if (score >= 50) return { label: 'DANGEROUS', class: 'crash-danger' };
    if (score >= 25) return { label: 'CONCERNING', class: 'crash-warning' };
    return { label: 'LOW', class: 'crash-low' };
  };

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

  const getRecencyBadge = (lastViolation) => {
    if (!lastViolation) return { class: 'recency-old', label: '—' };
    const date = new Date(lastViolation);
    const formatted = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' });
    return { class: 'recency-moderate', label: formatted };
  };

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
        filtered = filtered.filter(d => d.last_violation).sort((a, b) => 
          new Date(b.last_violation) - new Date(a.last_violation)
        );
        break;
      default: break;
    }
    return filtered;
  };

  const formatTime = (d) => d ? new Date(d).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : '';

  if (loading) return <div className="dmv-loading"><div className="spinner"></div><p>Loading...</p></div>;

  const policy = dashboard?.policy;
  const filteredQueue = getFilteredQueue();
  const canBatchSend = selectedDrivers.size > 0;

  // Calculate status counts and total violations
  const statusCounts = (dashboard?.queue || []).reduce((acc, d) => {
    const points = d.total_points || d.risk_points || 0;
    const tickets = d.violation_count || 0;
    const isSuperSpeeder = d.severe_count > 0 || d.crash_risk_score >= 75;
    
    if (points >= 11 || tickets >= 16) {
      acc.isaNotice++;
    } else if (isSuperSpeeder) {
      acc.superSpeeder++;
    } else {
      acc.monitoring++;
    }
    
    // Track total violations
    acc.totalViolations += tickets;
    
    return acc;
  }, { isaNotice: 0, superSpeeder: 0, monitoring: 0, totalViolations: 0 });

  return (
    <div className="dmv-tab-content">
      {/* POLICY BAR */}
      <div className="policy-banner">
        <div className="policy-badge">
          <span className="policy-version">Policy {policy?.version || '0.1-draft'}</span>
          <span className="policy-rule">ISA Notice: ≥{policy?.isa_points_threshold || 11} pts OR ≥{policy?.isa_ticket_threshold || 16} tickets</span>
          <span className="policy-counter">Monitoring: &lt;{policy?.isa_points_threshold || 11} pts, &lt;{policy?.isa_ticket_threshold || 16} tickets</span>
          <span className="policy-counter">Super Speeder: ≥3 violations</span>
        </div>
      </div>

      <div className="dmv-content">
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

          {/* IMPACT STRIP */}
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
            <div className="kpi-card kpi-critical">
              <div className="kpi-value">{dashboard?.kpis?.isa_required || 0}</div>
              <div className="kpi-label">ISA Required</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-value">{dashboard?.kpis?.monitoring || 0}</div>
              <div className="kpi-label">Monitoring</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-value">{dashboard?.kpis?.super_speeders || 0}</div>
              <div className="kpi-label">Super Speeders</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-value">{dashboard?.kpis?.cross_jurisdiction_offenders || 0}</div>
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
            </div>
          )}

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
                    <th className="col-select"><input type="checkbox" onChange={(e) => {
                      if (e.target.checked) {
                        const actionable = filteredQueue.filter(d => d.status === 'ISA_REQUIRED' && d.enforcement_status === 'NEW');
                        setSelectedDrivers(new Set(actionable.map(d => d.plate_id)));
                      } else {
                        setSelectedDrivers(new Set());
                      }
                    }} /></th>
                    <th>License / Plate</th>
                    <th>Violations / Points</th>
                    <th>Crash Risk</th>
                    <th>Risk Factors</th>
                    <th>Last Seen</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredQueue.length === 0 && (
                    <tr><td colSpan="7" className="empty-queue">
                      <div className="empty-state"><p className="empty-title">No drivers match this filter</p></div>
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
                              <button className="license-link" onClick={() => navigate(`/dmv/license/${driver.driver_license_number}`)}>
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
                            <div className="violations-count"><span className="label">Violations:</span><span className="value">{driver.violation_count}</span></div>
                            <div className="points-count"><span className="label">Points:</span><span className="value">{driver.total_points || driver.risk_points}</span></div>
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
                            {driver.violation_count >= 5 && <span className="factor-tag repeat">{driver.violation_count} tickets</span>}
                          </div>
                        </td>
                        <td><span className={`recency-badge ${recency.class}`}>{recency.label}</span></td>
                        <td><span className={`status-badge ${status.class}`}>{status.label}</span></td>
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
                <div className="feed-content"><div className="feed-message">{alert.message}</div></div>
              </div>
            ))}
            {alerts.length === 0 && <p className="feed-empty">No activity yet</p>}
          </div>
        </aside>
      </div>
    </div>
  );
}

// ============================================
// LOCAL COURT ADAPTER CONTENT (Tab 2)
// ============================================
function LocalCourtAdapterContent() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [localCourts, setLocalCourts] = useState(null);

  useEffect(() => {
    loadLocalCourts();
  }, []);

  const loadLocalCourts = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dmv/local-courts/summary`);
      if (res.ok) setLocalCourts(await res.json());
    } catch (err) {
      console.error('Error loading local courts:', err);
    }
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    setFile(selectedFile);
    setResult(null);
    
    if (selectedFile) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const text = event.target.result;
        const lines = text.split('\n').slice(0, 11);
        const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
        const rows = lines.slice(1).map(line => {
          const values = line.split(',').map(v => v.trim().replace(/"/g, ''));
          const row = {};
          headers.forEach((h, i) => row[h] = values[i] || '');
          return row;
        }).filter(row => Object.values(row).some(v => v));
        setPreview({ headers, rows });
      };
      reader.readAsText(selectedFile);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_BASE}/api/dmv/local-courts/upload`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (!res.ok) {
        setResult({ error: data.error || 'Upload failed', ...data });
      } else {
        setResult(data);
        loadLocalCourts();
      }
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="courts-tab-content">
      {/* Summary Stats */}
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
          <div className="court-stat-card">
            <div className="stat-value">{localCourts.total_records?.toLocaleString() || '—'}</div>
            <div className="stat-label">Total Records</div>
          </div>
        </div>
      )}

      <div className="courts-content-grid">
        {/* Upload Section */}
        <div className="upload-card">
          <h2>Upload Court Violation Data</h2>
          <p className="upload-desc">
            Local courts can upload CSV files containing violation records.
          </p>

          <div className="expected-format">
            <h4>Required CSV Columns:</h4>
            <div className="format-columns">
              <span className="col-tag">driver_license_number</span>
              <span className="col-tag">driver_full_name</span>
              <span className="col-tag">plate_id</span>
              <span className="col-tag">violation_code</span>
              <span className="col-tag">date_of_violation</span>
              <span className="col-tag">latitude</span>
              <span className="col-tag">longitude</span>
              <span className="col-tag">police_agency</span>
            </div>
          </div>

          <div className="file-input-area">
            <input type="file" accept=".csv" onChange={handleFileChange} id="csv-upload" className="file-input" />
            <label htmlFor="csv-upload" className="file-label">
              {file ? file.name : 'Choose CSV File'}
            </label>
          </div>

          {preview && (
            <div className="preview-section">
              <h4>Preview (First 10 Rows)</h4>
              <div className="preview-table-container">
                <table className="preview-table">
                  <thead><tr>{preview.headers.map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
                  <tbody>
                    {preview.rows.map((row, i) => (
                      <tr key={i}>{preview.headers.map((h, j) => <td key={j}>{row[h]}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {file && (
            <button className="upload-submit-btn" onClick={handleUpload} disabled={uploading}>
              {uploading ? 'Uploading...' : 'Upload to DMV System'}
            </button>
          )}

          {result && (
            <div className={`upload-result ${result.error ? 'error' : 'success'}`}>
              {result.error ? (
                <p><strong>Error:</strong> {result.error}</p>
              ) : (
                <p><strong>{result.message || 'Upload successful!'}</strong> — {result.inserted} records inserted</p>
              )}
            </div>
          )}
        </div>

        {/* Courts Lists */}
        {localCourts && (
          <div className="courts-lists-card">
            <div className="courts-list-section">
              <h4>Top Counties</h4>
              {localCourts.top_counties?.slice(0, 8).map((c, i) => (
                <div key={i} className="list-item">
                  <span className="item-name">{c.county}</span>
                  <span className="item-count">{c.count?.toLocaleString()}</span>
                </div>
              ))}
            </div>
            <div className="courts-list-section">
              <h4>Top Ticket Issuers</h4>
              {localCourts.top_courts?.slice(0, 8).map((c, i) => (
                <div key={i} className="list-item">
                  <span className="item-name">{c.court}</span>
                  <span className="item-count">{c.count?.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================
// MAP CONTENT (Tab 3)
// ============================================
function MapContent() {
  return (
    <div className="map-tab-content">
      <MapView />
    </div>
  );
}

// ============================================
// FOOTER NAV ICONS (SVG)
// ============================================
const DashboardIcon = ({ active }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={active ? "#fff" : "#888"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7" rx="1" fill={active ? "#fff" : "none"}/>
    <rect x="14" y="3" width="7" height="7" rx="1" fill={active ? "#fff" : "none"}/>
    <rect x="3" y="14" width="7" height="7" rx="1" fill={active ? "#fff" : "none"}/>
    <rect x="14" y="14" width="7" height="7" rx="1" fill={active ? "#fff" : "none"}/>
  </svg>
);

const CourtIcon = ({ active }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={active ? "#fff" : "#888"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2L2 7l10 5 10-5-10-5z" fill={active ? "#fff" : "none"}/>
    <path d="M2 17l10 5 10-5"/>
    <path d="M2 12l10 5 10-5"/>
  </svg>
);

const CameraIcon = ({ active }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={active ? "#fff" : "#888"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M23 7l-7 5 7 5V7z" fill={active ? "#fff" : "none"}/>
    <rect x="1" y="5" width="15" height="14" rx="2" fill={active ? "#fff" : "none"}/>
    <circle cx="8" cy="12" r="2" stroke={active ? "#1a1a1a" : "#888"} fill="none"/>
  </svg>
);

// ============================================
// MAIN TABBED APP
// ============================================
function TabbedApp() {
  const navigate = useNavigate();
  const location = useLocation();
  
  const getActiveTab = () => {
    if (location.pathname === '/courts') return 'courts';
    if (location.pathname === '/map') return 'map';
    return 'dashboard';
  };

  const activeTab = getActiveTab();

  return (
    <div className="tabbed-app">
      {/* HEADER */}
      <header className="app-header">
        <div className="header-left">
          <span className="app-logo">🚗</span>
          <span className="app-title">NY DMV — ISA Enforcement Command</span>
        </div>
      </header>

      {/* TAB CONTENT */}
      <div className="tab-panel">
        {activeTab === 'dashboard' && <DMVDashboardContent />}
        {activeTab === 'courts' && <LocalCourtAdapterContent />}
        {activeTab === 'map' && <MapContent />}
      </div>

      {/* FOOTER NAVIGATION - Instagram Style */}
      <nav className="footer-nav">
        <button 
          className={`footer-nav-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => navigate('/')}
        >
          <div className="nav-icon">
            <DashboardIcon active={activeTab === 'dashboard'} />
          </div>
          <span className="nav-label">Dashboard</span>
        </button>
        
        <button 
          className={`footer-nav-btn ${activeTab === 'courts' ? 'active' : ''}`}
          onClick={() => navigate('/courts')}
        >
          <div className="nav-icon">
            <CourtIcon active={activeTab === 'courts'} />
          </div>
          <span className="nav-label">Court Adapter</span>
        </button>
        
        <button 
          className={`footer-nav-btn ${activeTab === 'map' ? 'active' : ''}`}
          onClick={() => navigate('/map')}
        >
          <div className="nav-icon">
            <CameraIcon active={activeTab === 'map'} />
          </div>
          <span className="nav-label">Camera Network</span>
        </button>
      </nav>
    </div>
  );
}

// ============================================
// APP ROOT
// ============================================
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/dmv" element={<DMVDashboard />} />
        <Route path="/dmv/*" element={<DMVDashboard />} />
        <Route path="/license/:licenseNumber" element={<LicenseViolations />} />
        <Route path="/driver/:plateId" element={<DriverProfile />} />
        <Route path="/" element={<TabbedApp />} />
        <Route path="/courts" element={<TabbedApp />} />
        <Route path="/map" element={<TabbedApp />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
