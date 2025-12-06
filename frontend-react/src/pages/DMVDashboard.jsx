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
  const [sixteenPlusData, setSixteenPlusData] = useState(null);
  const [platesData, setPlatesData] = useState(null);
  const [isaDrivers, setIsaDrivers] = useState(null);
  const [isaPlates, setIsaPlates] = useState(null);
  const [isaSummary, setIsaSummary] = useState(null);
  const [warningDrivers, setWarningDrivers] = useState(null);
  const [warningPlates, setWarningPlates] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
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
    loadSixteenPlusData();
    loadPlatesData();
    loadIsaData();
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

  const loadSixteenPlusData = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dmv/sixteen-plus-tickets`);
      if (res.ok) setSixteenPlusData(await res.json());
    } catch (err) {
      console.error('Error loading 16+ tickets data:', err);
    }
  };

  const loadPlatesData = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dmv/plates-violations`);
      if (res.ok) setPlatesData(await res.json());
    } catch (err) {
      console.error('Error loading plates data:', err);
    }
  };

  const loadIsaData = async () => {
    try {
      // Load ISA summary counts
      const summaryRes = await fetch(`${API_BASE}/api/dmv/isa/summary`);
      if (summaryRes.ok) setIsaSummary(await summaryRes.json());
      
      // Load drivers with 11+ points (24 month window)
      const driversRes = await fetch(`${API_BASE}/api/dmv/isa/drivers-24m`);
      if (driversRes.ok) setIsaDrivers(await driversRes.json());
      
      // Load plates with 16+ tickets (12 month window)
      const platesRes = await fetch(`${API_BASE}/api/dmv/isa/plates-12m`);
      if (platesRes.ok) setIsaPlates(await platesRes.json());
      
      // Load warning band data (near-threshold)
      const warnDriversRes = await fetch(`${API_BASE}/api/dmv/isa/warnings/drivers`);
      if (warnDriversRes.ok) setWarningDrivers(await warnDriversRes.json());
      
      const warnPlatesRes = await fetch(`${API_BASE}/api/dmv/isa/warnings/plates`);
      if (warnPlatesRes.ok) setWarningPlates(await warnPlatesRes.json());
    } catch (err) {
      console.error('Error loading ISA data:', err);
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

  // STATUS - Based on ISA threshold: ≥11 pts OR ≥16 tickets
  const getStatus = (driver) => {
    const points = driver.total_points || driver.risk_points || 0;
    const tickets = driver.violation_count || 0;
    const isSuperSpeeder = driver.severe_count > 0;
    
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
    
    // Apply category filter first
    switch (activeFilter) {
      case 'high_risk': filtered = filtered.filter(d => (d.total_points || d.risk_points || 0) >= 15 || (d.severe_count || 0) >= 3); break;
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
          const isSuperSpeeder = d.severe_count > 0;
          return !isIsaNotice && isSuperSpeeder;
        });
        break;
      case 'nighttime': filtered = filtered.filter(d => d.is_night_heavy); break;
      case 'monitoring': 
        filtered = filtered.filter(d => {
          const points = d.total_points || d.risk_points || 0;
          const tickets = d.violation_count || 0;
          const isIsaNotice = points >= 11 || tickets >= 16;
          const isSuperSpeeder = d.severe_count > 0;
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
    
    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      filtered = filtered.filter(d => {
        // Search by plate
        if (d.plate?.toLowerCase().includes(query)) return true;
        
        // Search by driver license
        if (d.driver_license_number?.toLowerCase().includes(query)) return true;
        if (d.license?.toLowerCase().includes(query)) return true;
        
        // Search by driver name
        if (d.name?.toLowerCase().includes(query)) return true;
        if (d.driver_name?.toLowerCase().includes(query)) return true;
        
        // Search by violation code
        if (d.most_common_violation?.toLowerCase().includes(query)) return true;
        
        // Search by date (format: YYYY-MM-DD or MM/DD/YYYY)
        if (d.last_violation) {
          const dateStr = new Date(d.last_violation).toLocaleDateString('en-US');
          const isoDate = new Date(d.last_violation).toISOString().split('T')[0];
          if (dateStr.includes(query) || isoDate.includes(query)) return true;
        }
        
        // Search by county/location
        if (d.top_county?.toLowerCase().includes(query)) return true;
        
        // Search by agency
        if (d.top_agency?.toLowerCase().includes(query)) return true;
        
        return false;
      });
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
      <header className="dmv-header centered">
        <div className="dmv-logo">
          <span className="logo-text">NY DMV — ISA Enforcement Command</span>
        </div>
      </header>

      {activeTab === 'sixteen-plus' ? (
        /* 16+ TICKETS TAB - Tracks licenses with 16+ violations in trailing window */
        <div className="sixteen-plus-content">
          <div className="sixteen-plus-main">
            <div className="sixteen-plus-header">
              <h2>Licenses with 16+ Tickets (12-Month Window)</h2>
              <p className="threshold-info">
                Tracking driver licenses that trigger ISA requirement based on ticket count threshold
              </p>
              {sixteenPlusData && (
                <div className="sixteen-plus-stats">
                  <div className="stat-box threshold-hit">
                    <div className="stat-value">{sixteenPlusData.threshold_count?.toLocaleString() || 0}</div>
                    <div className="stat-label">At 16+ Tickets (ISA Required)</div>
                  </div>
                  <div className="stat-box">
                    <div className="stat-value">{sixteenPlusData.total_count?.toLocaleString() || 0}</div>
                    <div className="stat-label">Total Licenses Tracked</div>
                  </div>
                  <div className="stat-box">
                    <div className="stat-value">{sixteenPlusData.time_window_months || 12} mo</div>
                    <div className="stat-label">Trailing Window</div>
                  </div>
                </div>
              )}
            </div>

            {sixteenPlusData && sixteenPlusData.drivers && (
              <div className="queue-section">
                <div className="queue-table-container">
                  <table className="queue-table">
                    <thead>
                      <tr>
                        <th>License #</th>
                        <th>Driver Name</th>
                        <th>Tickets</th>
                        <th>Plates Used</th>
                        <th>Severe</th>
                        <th>Night %</th>
                        <th>Last Violation</th>
                        <th>Primary Issuer</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sixteenPlusData.drivers.length === 0 && (
                        <tr><td colSpan="9" className="empty-queue">
                          <div className="empty-state">
                            <p className="empty-title">No licenses found</p>
                          </div>
                        </td></tr>
                      )}
                      {sixteenPlusData.drivers.map((driver, i) => {
                        const hitsThreshold = driver.hits_threshold;
                        const recency = getRecencyBadge(driver.last_violation);
                        
                        return (
                          <tr key={i} className={hitsThreshold ? 'row-threshold-hit' : ''}>
                            <td>
                              <button 
                                className="license-link"
                                onClick={() => navigate(`/dmv/license/${driver.driver_license_number}`)}
                              >
                                {driver.driver_license_number}
                              </button>
                            </td>
                            <td>{driver.driver_name || '—'}</td>
                            <td>
                              <div className="violations-count">
                                <span className={`value ${hitsThreshold ? 'highlight-tickets' : ''}`}>
                                  {driver.total_tickets}
                                </span>
                                {hitsThreshold && <span className="threshold-badge">ISA</span>}
                              </div>
                            </td>
                            <td>
                              <span className="plates-count">{driver.plate_count} plate{driver.plate_count !== 1 ? 's' : ''}</span>
                            </td>
                            <td>{driver.severe_count > 0 ? <span className="factor-tag severe">{driver.severe_count}</span> : '—'}</td>
                            <td>{driver.is_night_heavy ? <span className="factor-tag night">{driver.night_percentage}%</span> : `${driver.night_percentage}%`}</td>
                            <td><span className={`recency-badge ${recency.class}`}>{recency.label}</span></td>
                            <td>
                              <span className="agency-tag" title={driver.primary_issuer}>
                                {driver.primary_issuer ? (driver.primary_issuer.length > 18 ? driver.primary_issuer.substring(0, 18) + '...' : driver.primary_issuer) : '—'}
                              </span>
                            </td>
                            <td>
                              <span className={`status-badge ${hitsThreshold ? 'status-isa-notice' : 'status-monitoring'}`}>
                                {hitsThreshold ? 'ISA Required' : 'Monitoring'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {!sixteenPlusData && (
              <div className="dmv-loading">
                <div className="spinner"></div>
                <p>Loading license data...</p>
              </div>
            )}
          </div>
        </div>
      ) : activeTab === 'dashboard' ? (
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

          {/* SEARCH BAR */}
          <div className="search-bar">
            <input 
              type="text"
              placeholder="Search by plate, driver license, name, violation code, date (MM/DD/YYYY), county, or agency..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="search-input"
            />
            {searchQuery && (
              <button className="search-clear" onClick={() => setSearchQuery('')}>
                ✕
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
                    <th>Risk Factors</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredQueue.length === 0 && (
                    <tr><td colSpan="6" className="empty-queue">
                      <div className="empty-state">
                        <p className="empty-title">No drivers match this filter</p>
                      </div>
                    </td></tr>
                  )}
                  {filteredQueue.map((driver, i) => {
                    const status = getStatus(driver);
                    const isHighRisk = (driver.total_points || driver.risk_points || 0) >= 15 || (driver.severe_count || 0) >= 3;
                    
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
                          <div className="risk-factors">
                            {driver.severe_count > 0 && <span className="factor-tag severe">{driver.severe_count} severe</span>}
                            {driver.is_night_heavy && <span className="factor-tag night">{driver.night_percentage}% night</span>}
                            {driver.is_cross_borough && <span className="factor-tag geo">{driver.borough_count} areas</span>}
                            {driver.violation_count >= 5 && <span className="factor-tag repeat">{driver.violation_count} tickets</span>}
                          </div>
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
      ) : activeTab === 'isa-list' ? (
        /* ISA THRESHOLD LIST TAB */
        <div className="isa-list-content">
          <div className="isa-list-main">
            {/* CSV Download Helper */}
            {(() => {
              // November stats calculation
              const novemberDriverCount = isaDrivers?.data ? new Set(
                isaDrivers.data.filter(d => 
                  d.violations?.some(v => {
                    const dt = new Date(v.date_of_violation);
                    return !isNaN(dt) && dt.getMonth() === 10; // 0=Jan, 10=Nov
                  })
                ).map(d => d.driver_license_number)
              ).size : 0;
              
              const novemberPlateCount = isaPlates?.data ? new Set(
                isaPlates.data.filter(p => 
                  p.violations?.some(v => {
                    const dt = new Date(v.date_of_violation);
                    return !isNaN(dt) && dt.getMonth() === 10;
                  })
                ).map(p => p.plate_id)
              ).size : 0;

              // CSV download function
              const downloadCSV = (filename, rows) => {
                if (!rows || rows.length === 0) return;
                const header = Object.keys(rows[0]);
                const csv = [
                  header.join(","),
                  ...rows.map(row =>
                    header.map(h => JSON.stringify(row[h] ?? "")).join(",")
                  )
                ].join("\n");
                const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.setAttribute("download", filename);
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
              };

              // Flatten drivers data for CSV
              const flattenDriversForCSV = () => {
                if (!isaDrivers?.data) return [];
                return isaDrivers.data.flatMap(d => 
                  d.violations?.map(v => ({
                    license_number: d.driver_license_number,
                    driver_name: d.driver_full_name,
                    license_state: d.license_state,
                    total_points: d.total_points,
                    violation_count: d.violation_count,
                    violation_code: v.violation_code,
                    violation_date: v.date_of_violation,
                    ticket_issuer: v.ticket_issuer,
                    police_agency: v.police_agency,
                    plate_id: v.plate_id,
                    points: v.points
                  })) || []
                );
              };

              // Flatten plates data for CSV
              const flattenPlatesForCSV = () => {
                if (!isaPlates?.data) return [];
                return isaPlates.data.flatMap(p => 
                  p.violations?.map(v => ({
                    plate_id: p.plate_id,
                    plate_state: p.plate_state,
                    ticket_count: p.ticket_count,
                    driver_license_number: v.driver_license_number,
                    violation_code: v.violation_code,
                    violation_date: v.date_of_violation,
                    ticket_issuer: v.ticket_issuer,
                    police_agency: v.police_agency
                  })) || []
                );
              };

              // Send email stub
              const sendEmailSummary = async () => {
                try {
                  const res = await fetch(`${API_BASE}/api/dmv/isa/send-summary`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      recipients: ["dmv@ny.gov", "isa-vendor@example.com"],
                      drivers_count: isaSummary?.drivers_11_plus_points_24m || 0,
                      plates_count: isaSummary?.plates_16_plus_tickets_12m || 0
                    })
                  });
                  if (res.ok) {
                    alert("✅ ISA summary email sent to DMV and vendor (demo stub)");
                  }
                } catch (err) {
                  alert("Email stub triggered (backend not running)");
                }
              };

              return (
                <>
                  {/* Action Bar */}
                  <div className="isa-action-bar">
                    <div className="isa-action-left">
                      <h1 className="isa-page-title">ISA Threshold List</h1>
                      <p className="isa-page-desc">
                        Drivers and plates that trigger ISA requirements per NY State policy
                      </p>
                    </div>
                    <div className="isa-action-buttons">
                      <button 
                        className="isa-btn export drivers"
                        onClick={() => downloadCSV("drivers_isa_11pts_24m.csv", flattenDriversForCSV())}
                      >
                        📥 Export Drivers CSV
                      </button>
                      <button 
                        className="isa-btn export plates"
                        onClick={() => downloadCSV("plates_isa_16tickets_12m.csv", flattenPlatesForCSV())}
                      >
                        📥 Export Plates CSV
                      </button>
                      <button 
                        className="isa-btn email"
                        onClick={sendEmailSummary}
                      >
                        📧 Send ISA Email
                      </button>
                    </div>
                  </div>

                  {/* Summary Stats with November */}
                  <div className="isa-stats-grid">
                    <div className="isa-stat-card drivers">
                      <div className="stat-value">{isaSummary?.drivers_11_plus_points_24m?.toLocaleString() || 0}</div>
                      <div className="stat-label">Drivers ≥11 pts (24 mo)</div>
                    </div>
                    <div className="isa-stat-card plates">
                      <div className="stat-value">{isaSummary?.plates_16_plus_tickets_12m?.toLocaleString() || 0}</div>
                      <div className="stat-label">Plates ≥16 tickets (12 mo)</div>
                    </div>
                    <div className="isa-stat-card november drivers-nov">
                      <div className="stat-value">{novemberDriverCount}</div>
                      <div className="stat-label">Drivers triggered in Nov</div>
                    </div>
                    <div className="isa-stat-card november plates-nov">
                      <div className="stat-value">{novemberPlateCount}</div>
                      <div className="stat-label">Plates triggered in Nov</div>
                    </div>
                  </div>
                </>
              );
            })()}

            {/* DRIVERS TABLE - 11+ Points */}
            <div className="isa-table-section">
              <h2 className="isa-section-title drivers">
                🚨 Drivers Requiring ISA (11+ Points in 24 Months)
              </h2>
              <p className="isa-section-desc">
                Driver licenses that have accumulated {isaSummary?.points_threshold || 11}+ violation points in the trailing 24-month window
              </p>
              
              {isaDrivers?.data?.length > 0 ? (
                <div className="isa-table-wrapper">
                  <table className="isa-table">
                    <thead>
                      <tr>
                        <th>License #</th>
                        <th>Name</th>
                        <th>Violation Date</th>
                        <th>Violation Code</th>
                        <th>Ticket Issuer</th>
                        <th>Police Agency</th>
                        <th>Points</th>
                        <th>Total Pts</th>
                      </tr>
                    </thead>
                    <tbody>
                      {isaDrivers.data.map((driver, idx) => (
                        driver.violations?.map((v, vidx) => (
                          <tr key={`${idx}-${vidx}`} className={vidx === 0 ? 'first-row' : ''}>
                            {vidx === 0 && (
                              <>
                                <td rowSpan={driver.violations.length} className="license-cell">
                                  <button 
                                    className="license-link"
                                    onClick={() => navigate(`/dmv/license/${driver.driver_license_number}`)}
                                  >
                                    {driver.driver_license_number}
                                  </button>
                                </td>
                                <td rowSpan={driver.violations.length} className="name-cell">
                                  {driver.driver_full_name}
                                </td>
                              </>
                            )}
                            <td>{v.date_of_violation ? new Date(v.date_of_violation).toLocaleDateString() : '-'}</td>
                            <td><span className="violation-code">{v.violation_code}</span></td>
                            <td>{v.ticket_issuer}</td>
                            <td>{v.police_agency}</td>
                            <td className="points-cell">{v.points}</td>
                            {vidx === 0 && (
                              <td rowSpan={driver.violations.length} className="total-points-cell">
                                <span className="total-points-badge">{driver.total_points}</span>
                              </td>
                            )}
                          </tr>
                        ))
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="no-data">No drivers currently meet the 11+ points threshold</p>
              )}
              <div className="isa-count">
                Showing {isaDrivers?.unique_drivers || 0} drivers with {isaDrivers?.data?.reduce((acc, d) => acc + (d.violations?.length || 0), 0) || 0} violations
              </div>
            </div>

            {/* PLATES TABLE - 16+ Tickets */}
            <div className="isa-table-section">
              <h2 className="isa-section-title plates">
                🚗 Plates with 16+ Tickets (12 Months)
              </h2>
              <p className="isa-section-desc">
                Vehicle plates that have accumulated {isaSummary?.ticket_threshold || 16}+ speeding tickets in the trailing 12-month window
              </p>
              
              {isaPlates?.data?.length > 0 ? (
                <div className="isa-table-wrapper">
                  <table className="isa-table">
                    <thead>
                      <tr>
                        <th>Plate</th>
                        <th>State</th>
                        <th>Violation Date</th>
                        <th>Violation Code</th>
                        <th>Ticket Issuer</th>
                        <th>Police Agency</th>
                        <th>Total Tickets</th>
                      </tr>
                    </thead>
                    <tbody>
                      {isaPlates.data.map((plate, idx) => (
                        plate.violations?.map((v, vidx) => (
                          <tr key={`${idx}-${vidx}`} className={vidx === 0 ? 'first-row' : ''}>
                            {vidx === 0 && (
                              <>
                                <td rowSpan={plate.violations.length} className="plate-cell">
                                  <span className="plate-badge">{plate.plate_id}</span>
                                </td>
                                <td rowSpan={plate.violations.length}>{plate.plate_state}</td>
                              </>
                            )}
                            <td>{v.date_of_violation ? new Date(v.date_of_violation).toLocaleDateString() : '-'}</td>
                            <td><span className="violation-code">{v.violation_code}</span></td>
                            <td>{v.ticket_issuer}</td>
                            <td>{v.police_agency}</td>
                            {vidx === 0 && (
                              <td rowSpan={plate.violations.length} className="total-tickets-cell">
                                <span className="total-tickets-badge">{plate.ticket_count}</span>
                              </td>
                            )}
                          </tr>
                        ))
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="no-data">No plates currently meet the 16+ tickets threshold</p>
              )}
              <div className="isa-count">
                Showing {isaPlates?.unique_plates || 0} plates with {isaPlates?.data?.reduce((acc, p) => acc + (p.violations?.length || 0), 0) || 0} violations
              </div>
            </div>

            {/* WARNING BAND SECTION */}
            <div className="isa-warning-section">
              <h2 className="isa-warning-title">⚠️ Warning Band — Approaching Threshold</h2>
              <p className="isa-section-desc">
                Drivers and plates that are close to triggering ISA requirements. Proactive outreach recommended.
              </p>
              
              <div className="isa-warning-grid">
                {/* Warning Drivers (8-10 points) */}
                <div className="isa-warning-card">
                  <div className="warning-card-header drivers">
                    <span className="warning-icon">👤</span>
                    <span className="warning-label">Drivers 8-10 Points</span>
                    <span className="warning-count">{warningDrivers?.count || 0}</span>
                  </div>
                  {warningDrivers?.data?.length > 0 ? (
                    <div className="warning-table-wrapper">
                      <table className="warning-table">
                        <thead>
                          <tr>
                            <th>License</th>
                            <th>Name</th>
                            <th>Points</th>
                            <th>To Threshold</th>
                          </tr>
                        </thead>
                        <tbody>
                          {warningDrivers.data.slice(0, 10).map((d, i) => (
                            <tr key={i}>
                              <td>
                                <button 
                                  className="license-link"
                                  onClick={() => navigate(`/dmv/license/${d.driver_license_number}`)}
                                >
                                  {d.driver_license_number}
                                </button>
                              </td>
                              <td>{d.driver_full_name}</td>
                              <td className="points-cell">{d.total_points}</td>
                              <td className="to-threshold">+{d.points_to_threshold} to ISA</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="no-warnings">No drivers in warning band</p>
                  )}
                </div>

                {/* Warning Plates (12-15 tickets) */}
                <div className="isa-warning-card">
                  <div className="warning-card-header plates">
                    <span className="warning-icon">🚗</span>
                    <span className="warning-label">Plates 12-15 Tickets</span>
                    <span className="warning-count">{warningPlates?.count || 0}</span>
                  </div>
                  {warningPlates?.data?.length > 0 ? (
                    <div className="warning-table-wrapper">
                      <table className="warning-table">
                        <thead>
                          <tr>
                            <th>Plate</th>
                            <th>State</th>
                            <th>Tickets</th>
                            <th>To Threshold</th>
                          </tr>
                        </thead>
                        <tbody>
                          {warningPlates.data.slice(0, 10).map((p, i) => (
                            <tr key={i}>
                              <td><span className="plate-badge">{p.plate_id}</span></td>
                              <td>{p.plate_state}</td>
                              <td className="tickets-cell">{p.ticket_count}</td>
                              <td className="to-threshold">+{p.tickets_to_threshold} to ISA</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="no-warnings">No plates in warning band</p>
                  )}
                </div>
              </div>
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

            {/* Top Ticket Issuers */}
            <div className="courts-grid single">
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

      {/* FOOTER NAVIGATION - Instagram Style */}
      <nav className="footer-nav">
        <button 
          className={`footer-nav-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          <div className="nav-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke={activeTab === 'dashboard' ? "#fff" : "#888"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="7" height="7" rx="1" fill={activeTab === 'dashboard' ? "#fff" : "none"}/>
              <rect x="14" y="3" width="7" height="7" rx="1" fill={activeTab === 'dashboard' ? "#fff" : "none"}/>
              <rect x="3" y="14" width="7" height="7" rx="1" fill={activeTab === 'dashboard' ? "#fff" : "none"}/>
              <rect x="14" y="14" width="7" height="7" rx="1" fill={activeTab === 'dashboard' ? "#fff" : "none"}/>
            </svg>
          </div>
          <span className="nav-label">Dashboard</span>
        </button>
        
        <button 
          className={`footer-nav-btn ${activeTab === 'isa-list' ? 'active' : ''}`}
          onClick={() => setActiveTab('isa-list')}
        >
          <div className="nav-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke={activeTab === 'isa-list' ? "#fff" : "#888"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 11l3 3L22 4" strokeWidth="2"/>
              <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" fill="none"/>
            </svg>
          </div>
          <span className="nav-label">ISA List</span>
        </button>
        
        <button 
          className={`footer-nav-btn ${activeTab === 'courts' ? 'active' : ''}`}
          onClick={() => setActiveTab('courts')}
        >
          <div className="nav-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke={activeTab === 'courts' ? "#fff" : "#888"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z" fill={activeTab === 'courts' ? "#fff" : "none"}/>
              <path d="M2 17l10 5 10-5"/>
              <path d="M2 12l10 5 10-5"/>
            </svg>
          </div>
          <span className="nav-label">Court Adapter</span>
        </button>
        
        <button 
          className="footer-nav-btn"
          onClick={() => navigate('/map')}
        >
          <div className="nav-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="#888" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M23 7l-7 5 7 5V7z" fill="none"/>
              <rect x="1" y="5" width="15" height="14" rx="2" fill="none"/>
              <circle cx="8" cy="12" r="2" stroke="#888" fill="none"/>
            </svg>
          </div>
          <span className="nav-label">Camera Network</span>
        </button>
      </nav>
    </div>
  );
}

export default DMVDashboard;
