import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import '../styles/dmv.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

function LicenseViolations() {
  const { licenseNumber } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadViolations = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`${API_BASE}/api/license/${licenseNumber}/violations`);
        if (res.ok) {
          const jsonData = await res.json();
          setData(jsonData);
        } else {
          setError('No violations found');
          setData(null);
        }
      } catch (err) {
        console.error('Error loading violations:', err);
        setError(err.message);
        setData(null);
      } finally {
        setLoading(false);
      }
    };
    
    if (licenseNumber) {
      loadViolations();
    }
  }, [licenseNumber]);

  if (loading) {
    return (
      <div className="dmv-dashboard">
        <header className="dmv-header">
          <div className="header-left">
            <div className="dmv-logo">
              <span className="logo-text">NY DMV — License Violations</span>
            </div>
          </div>
        </header>
        <div style={{ padding: '60px', textAlign: 'center' }}>
          <div className="spinner"></div>
          <p style={{ color: '#888', marginTop: '20px' }}>Loading...</p>
        </div>
      </div>
    );
  }

  if (error || !data || !data.violations) {
    return (
      <div className="dmv-dashboard">
        <header className="dmv-header">
          <div className="header-left">
            <div className="dmv-logo">
              <span className="logo-text">NY DMV — License Violations</span>
            </div>
          </div>
          <div className="header-right">
            <button className="nav-link" onClick={() => navigate(-1)}>← Back</button>
          </div>
        </header>
        <div style={{ padding: '60px', textAlign: 'center' }}>
          <h2 style={{ color: '#fff', marginBottom: '10px' }}>No Records Found</h2>
          <p style={{ color: '#666', marginBottom: '30px' }}>
            No violations found for license: <strong style={{ color: '#fff' }}>{licenseNumber}</strong>
          </p>
          <button className="nav-link" onClick={() => navigate(-1)}>← Back to Dashboard</button>
        </div>
      </div>
    );
  }

  const { driver, violations = [] } = data;
  const total_violations = violations.length;

  return (
    <div className="dmv-dashboard">
      <header className="dmv-header">
        <div className="header-left">
          <div className="dmv-logo">
            <span className="logo-text">NY DMV — License Violations</span>
          </div>
        </div>
        <div className="header-right">
          <button className="nav-link" onClick={() => navigate(-1)}>← Back</button>
        </div>
      </header>

      <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
        {/* Header Card */}
        <div style={{ 
          background: '#1a1a1a', 
          border: '1px solid #2a2a2a', 
          borderRadius: '10px', 
          padding: '24px',
          marginBottom: '20px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: '11px', color: '#666', textTransform: 'uppercase', marginBottom: '6px' }}>
                Driver License Number
              </div>
              <h1 style={{ fontFamily: 'monospace', fontSize: '24px', color: '#fff', margin: 0 }}>
                {licenseNumber}
              </h1>
              {driver && (
                <div style={{ marginTop: '10px', color: '#888', fontSize: '14px' }}>
                  {driver.driver_full_name} • {driver.license_state}
                </div>
              )}
            </div>
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

        {/* Violations Table */}
        <div style={{ 
          background: '#1a1a1a', 
          border: '1px solid #2a2a2a', 
          borderRadius: '10px',
          overflow: 'hidden'
        }}>
          <div style={{ 
            padding: '18px 20px', 
            borderBottom: '1px solid #2a2a2a',
            background: '#151515'
          }}>
            <h2 style={{ margin: 0, fontSize: '16px', color: '#fff' }}>Violation History</h2>
          </div>
          
          <table className="queue-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Code</th>
                <th>Plate</th>
                <th>Agency</th>
                <th>Issuer</th>
              </tr>
            </thead>
            <tbody>
              {violations.map((v, i) => (
                <tr key={i}>
                  <td>{v.date_of_violation ? new Date(v.date_of_violation).toLocaleDateString() : '—'}</td>
                  <td>{v.violation_code}</td>
                  <td>{v.plate_id}</td>
                  <td>{v.police_agency || '—'}</td>
                  <td>{v.ticket_issuer || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default LicenseViolations;
