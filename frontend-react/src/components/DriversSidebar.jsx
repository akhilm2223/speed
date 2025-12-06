import React, { useState, useEffect } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

function DriversSidebar({ refreshTrigger }) {
  const [drivers, setDrivers] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('drivers');

  useEffect(() => {
    fetchData();
  }, [refreshTrigger]);

  const fetchData = async () => {
    try {
      const [driversRes, alertsRes] = await Promise.all([
        fetch(`${API_BASE}/api/drivers`),
        fetch(`${API_BASE}/api/alerts`)
      ]);
      
      if (driversRes.ok) {
        const driversData = await driversRes.json();
        setDrivers(driversData);
      }
      
      if (alertsRes.ok) {
        const alertsData = await alertsRes.json();
        setAlerts(alertsData);
      }
    } catch (err) {
      console.error('Error fetching data:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'ISA_REQUIRED': return '#ff0000';
      case 'MONITOR': return '#888888';
      default: return '#4ade80';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'ISA_REQUIRED': return '🔴';
      case 'MONITOR': return '🟡';
      default: return '🟢';
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Reset all demo data?')) return;
    
    try {
      await fetch(`${API_BASE}/api/reset-demo`, { method: 'POST' });
      fetchData();
    } catch (err) {
      console.error('Reset failed:', err);
    }
  };

  return (
    <div className="drivers-sidebar">
      <div className="sidebar-tabs">
        <button 
          className={`tab ${activeTab === 'drivers' ? 'active' : ''}`}
          onClick={() => setActiveTab('drivers')}
        >
          🚗 Drivers ({drivers.length})
        </button>
        <button 
          className={`tab ${activeTab === 'alerts' ? 'active' : ''}`}
          onClick={() => setActiveTab('alerts')}
        >
          🚨 Alerts ({alerts.length})
        </button>
      </div>

      {loading ? (
        <div className="loading-small">Loading...</div>
      ) : activeTab === 'drivers' ? (
        <div className="drivers-list">
          {drivers.length === 0 ? (
            <p className="empty-state">No tracked drivers yet. Click a camera to detect violations.</p>
          ) : (
            drivers.map((driver, i) => (
              <div key={i} className="driver-card">
                <div className="driver-header">
                  <span className="plate-number">{driver.plate_id}</span>
                  <span className="state-badge">{driver.registration_state}</span>
                </div>
                
                <div className="driver-stats">
                  <div className="stat">
                    <span className="stat-value">{driver.total_violations}</span>
                    <span className="stat-label">Violations</span>
                  </div>
                  <div className="stat">
                    <span className="stat-value" style={{color: getStatusColor(driver.isa_status)}}>
                      {driver.risk_points}
                    </span>
                    <span className="stat-label">Risk Points</span>
                  </div>
                </div>
                
                <div className="risk-meter">
                  <div className="risk-track">
                    <div 
                      className="risk-fill"
                      style={{
                        width: `${Math.min(driver.risk_points * 10, 100)}%`,
                        backgroundColor: getStatusColor(driver.isa_status)
                      }}
                    ></div>
                    <div className="threshold-marker" style={{left: '50%'}} title="Monitor threshold"></div>
                    <div className="threshold-marker isa" style={{left: '100%'}} title="ISA threshold"></div>
                  </div>
                  <div className="risk-labels">
                    <span>0</span>
                    <span>5</span>
                    <span>10</span>
                  </div>
                </div>
                
                <div className="driver-status">
                  {getStatusIcon(driver.isa_status)} {driver.isa_status.replace('_', ' ')}
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="alerts-list">
          {alerts.length === 0 ? (
            <p className="empty-state">No DMV alerts yet. Drivers exceeding 10 risk points will trigger ISA alerts.</p>
          ) : (
            alerts.map((alert, i) => (
              <div key={i} className="alert-card">
                <div className="alert-header">
                  <span className="alert-type">{alert.alert_type}</span>
                  <span className="alert-status">{alert.status}</span>
                </div>
                <div className="alert-plate">{alert.plate_id}</div>
                <p className="alert-reason">{alert.reason}</p>
                <div className="alert-meta">
                  <span>Risk: {alert.risk_score}</span>
                  <span>Violations: {alert.total_violations}</span>
                </div>
                <div className="alert-time">
                  {new Date(alert.created_at).toLocaleString()}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      <button className="reset-btn" onClick={handleReset}>
        🔄 Reset Demo
      </button>
    </div>
  );
}

export default DriversSidebar;
