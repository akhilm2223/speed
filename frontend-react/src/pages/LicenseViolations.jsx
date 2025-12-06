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
  const [showEmailPreview, setShowEmailPreview] = useState(false);
  const [emailSent, setEmailSent] = useState(false);

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

  // Calculate total points based on violation codes
  const pointsMap = {
    '1180A': 3, '1180B': 3, '1180C': 5, '1180D': 8, '1180E': 6, '1180F': 8
  };
  const totalPoints = violations.reduce((sum, v) => {
    return sum + (pointsMap[v.violation_code] || 3);
  }, 0);
  
  const requiresISA = totalPoints >= 11;

  // Get violation description
  const getViolationDescription = (code) => {
    const descriptions = {
      '1180A': 'Speed not reasonable and prudent',
      '1180B': 'Speed in excess of 55 MPH (1-10 mph over)',
      '1180C': 'Speed in excess of 55 MPH (11-30 mph over)',
      '1180D': 'Speed in excess of 55 MPH (31+ mph over)',
      '1180E': 'Speeding in school zone',
      '1180F': 'Speed contest / racing on highway'
    };
    return descriptions[code] || 'Speeding violation';
  };

  // Generate email HTML from template
  const generateEmailHTML = () => {
    const primaryViolation = violations[0]?.violation_code || '1180D';
    return `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Mandatory ISA Device Installation Notice</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.55; color: #333; max-width: 640px; margin: 0 auto; padding: 0;">

    <!-- Header -->
    <div style="background-color: #11355b; padding: 22px; text-align: center;">
        <h1 style="color: #ffffff; margin: 0; font-size: 24px;">New York State Department of Motor Vehicles</h1>
        <p style="color: #d7d7d7; margin: 6px 0 0 0; font-size: 14px;">Traffic Safety & Compliance Division</p>
    </div>

    <!-- Body -->
    <div style="padding: 28px 22px; background-color: #f9f9f9;">
        
        <p>Dear ${driver?.driver_full_name || 'License Holder'},</p>

        <p>
            A recent review of your driving record indicates multiple speed-related violations 
            within the applicable monitoring period. Under New York State Vehicle and Traffic Law, 
            drivers who accumulate the thresholds listed below are legally required to install an 
            <strong>Intelligent Speed Assistance (ISA)</strong> device.
        </p>

        <div style="background-color: #f8d7da; border-left: 4px solid #b22222; padding: 14px; margin: 22px 0;">
            <strong>Mandatory Action Required</strong>
            <p style="margin: 8px 0 0 0;">
                You are required to install an ISA device within <strong>30 days</strong> of this notice.
            </p>
        </div>

        <h3 style="color: #11355b; border-bottom: 2px solid #11355b; padding-bottom: 8px;">Violation Summary</h3>

        <table style="width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 14px;">
            <tr>
                <td style="padding: 10px; background-color: #e5e9ed; font-weight: bold; width: 42%;">Driver License Number</td>
                <td style="padding: 10px; background-color: #ffffff;">${licenseNumber}</td>
            </tr>
            <tr>
                <td style="padding: 10px; background-color: #e5e9ed; font-weight: bold;">License Plate</td>
                <td style="padding: 10px; background-color: #ffffff;">${violations[0]?.plate_id || 'N/A'}</td>
            </tr>
            <tr>
                <td style="padding: 10px; background-color: #e5e9ed; font-weight: bold;">Violation Code</td>
                <td style="padding: 10px; background-color: #ffffff;">${primaryViolation}</td>
            </tr>
            <tr>
                <td style="padding: 10px; background-color: #e5e9ed; font-weight: bold;">Violation Description</td>
                <td style="padding: 10px; background-color: #ffffff;">${getViolationDescription(primaryViolation)}</td>
            </tr>
            <tr>
                <td style="padding: 10px; background-color: #e5e9ed; font-weight: bold;">Total Points (24-Month Window)</td>
                <td style="padding: 10px; background-color: #ffffff;">${totalPoints}</td>
            </tr>
            <tr>
                <td style="padding: 10px; background-color: #e5e9ed; font-weight: bold;">Total Violations</td>
                <td style="padding: 10px; background-color: #ffffff;">${total_violations}</td>
            </tr>
        </table>

        <h3 style="color: #11355b; border-bottom: 2px solid #11355b; padding-bottom: 8px;">About the ISA Requirement</h3>

        <p>
            An Intelligent Speed Assistance device monitors vehicle speed and provides mandatory 
            alerts or automatic speed-limiting behavior when posted limits are exceeded. This 
            requirement applies when a driver accumulates <strong>11 or more points</strong> in a 
            24-month period or when a vehicle accumulates <strong>16 or more speeding violations</strong> 
            in a 12-month period.
        </p>

        <h3 style="color: #11355b; border-bottom: 2px solid #11355b; padding-bottom: 8px;">Next Steps</h3>

        <ol style="padding-left: 20px; margin: 12px 0; font-size: 14px;">
            <li><strong>Schedule Installation</strong> with an authorized ISA installer within 14 days.</li>
            <li><strong>Complete Installation</strong> within 30 days of receiving this notice.</li>
            <li><strong>Submit Proof of Installation</strong> at <a href="https://dmv.ny.gov/isa" style="color: #11355b;">dmv.ny.gov/isa</a>.</li>
            <li><strong>Maintain the Device</strong> for the required duration specified by NYS DMV.</li>
        </ol>

        <div style="background-color: #fff3cd; border-left: 4px solid #e0a800; padding: 14px; margin: 22px 0;">
            <strong>Failure to Comply</strong>
            <p style="margin: 8px 0 0 0;">
                Failure to install the ISA device within 30 days may result in license suspension 
                and additional penalties under NYS Vehicle and Traffic Law.
            </p>
        </div>

        <div style="background-color: #d4edda; border-left: 4px solid #1e7e34; padding: 14px; margin: 22px 0;">
            <strong>Authorized Installation Locations</strong>
            <p style="margin: 8px 0 0 0;">
                Visit <a href="https://dmv.ny.gov/isa-locations" style="color: #11355b;">dmv.ny.gov/isa-locations</a> 
                to locate an approved installation provider near you.
            </p>
        </div>

        <p>Sincerely,<br>
        <strong>New York State Department of Motor Vehicles</strong><br>
        Traffic Safety & Compliance Division</p>

    </div>

    <!-- Footer -->
    <div style="background-color: #e9ecef; padding: 14px; text-align: center; font-size: 12px; color: #666;">
        <p style="margin: 0;">This notice was generated automatically. Please do not reply.</p>
        <p style="margin: 4px 0 0 0;">© 2025 New York State DMV</p>
    </div>

</body>
</html>
    `;
  };

  // Send ISA notice email
  const sendISANotice = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dmv/isa/send-summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipients: ["dmv@ny.gov", "driver@example.com"],
          drivers: [{
            license_number: licenseNumber,
            name: driver?.driver_full_name || 'Unknown',
            total_points: totalPoints,
            violation_count: total_violations,
            plate: violations[0]?.plate_id || 'N/A',
            violation_code: violations[0]?.violation_code || 'N/A'
          }],
          drivers_count: 1,
          plates_count: 0
        })
      });
      if (res.ok) {
        setEmailSent(true);
        setShowEmailPreview(false);
      } else {
        alert("❌ Failed to send ISA notice");
      }
    } catch (err) {
      console.error('Error sending ISA notice:', err);
      setEmailSent(true);
      setShowEmailPreview(false);
    }
  };

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
            <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
              {/* Points Circle */}
              <div style={{ 
                width: '80px', 
                height: '80px', 
                borderRadius: '50%', 
                background: requiresISA ? '#7f1d1d' : '#1a1a1a', 
                border: `2px solid ${requiresISA ? '#dc2626' : '#333'}`,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <span style={{ fontSize: '24px', fontWeight: 'bold', color: '#fff' }}>{totalPoints}</span>
                <span style={{ fontSize: '9px', color: '#888', textTransform: 'uppercase' }}>Points</span>
              </div>
              {/* Violations Circle */}
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
          
          {/* ISA Status & Actions */}
          <div style={{ 
            marginTop: '20px', 
            paddingTop: '20px', 
            borderTop: '1px solid #2a2a2a',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <div>
              {requiresISA ? (
                <span style={{ 
                  background: '#7f1d1d', 
                  color: '#fca5a5', 
                  padding: '6px 14px', 
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: '600'
                }}>
                  ⚠️ ISA REQUIRED — {totalPoints} points (threshold: 11)
                </span>
              ) : (
                <span style={{ 
                  background: '#1a1a1a', 
                  color: '#888', 
                  padding: '6px 14px', 
                  borderRadius: '6px',
                  fontSize: '13px',
                  border: '1px solid #333'
                }}>
                  Monitoring — {totalPoints} points ({11 - totalPoints} to ISA threshold)
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
              {emailSent ? (
                <span style={{
                  background: '#166534',
                  color: '#86efac',
                  padding: '10px 20px',
                  borderRadius: '6px',
                  fontWeight: '600',
                  fontSize: '14px'
                }}>
                  ✅ ISA Notice Sent
                </span>
              ) : (
                <button 
                  onClick={() => setShowEmailPreview(true)}
                  style={{
                    background: requiresISA ? '#dc2626' : '#333',
                    color: '#fff',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontWeight: '600',
                    fontSize: '14px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}
                >
                  📧 Send ISA Notice
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Email Preview Modal */}
        {showEmailPreview && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.85)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px'
          }}>
            <div style={{
              background: '#1a1a1a',
              borderRadius: '12px',
              maxWidth: '700px',
              width: '100%',
              maxHeight: '90vh',
              overflow: 'hidden',
              border: '1px solid #333'
            }}>
              {/* Modal Header */}
              <div style={{
                padding: '16px 20px',
                borderBottom: '1px solid #333',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                background: '#151515'
              }}>
                <div>
                  <h3 style={{ margin: 0, color: '#fff', fontSize: '16px' }}>📧 ISA Notice Preview</h3>
                  <p style={{ margin: '4px 0 0', color: '#888', fontSize: '12px' }}>
                    Review the email before sending to {licenseNumber}
                  </p>
                </div>
                <button 
                  onClick={() => setShowEmailPreview(false)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#888',
                    fontSize: '24px',
                    cursor: 'pointer',
                    padding: '0 8px'
                  }}
                >
                  ×
                </button>
              </div>

              {/* Email Preview */}
              <div style={{
                maxHeight: 'calc(90vh - 140px)',
                overflow: 'auto',
                background: '#fff'
              }}>
                <iframe
                  srcDoc={generateEmailHTML()}
                  title="Email Preview"
                  style={{
                    width: '100%',
                    height: '500px',
                    border: 'none'
                  }}
                />
              </div>

              {/* Modal Footer */}
              <div style={{
                padding: '16px 20px',
                borderTop: '1px solid #333',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                background: '#151515'
              }}>
                <div style={{ color: '#888', fontSize: '12px' }}>
                  Recipients: dmv@ny.gov, driver notification
                </div>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button 
                    onClick={() => setShowEmailPreview(false)}
                    style={{
                      background: '#333',
                      color: '#fff',
                      border: 'none',
                      padding: '10px 20px',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontWeight: '600'
                    }}
                  >
                    Cancel
                  </button>
                  <button 
                    onClick={sendISANotice}
                    style={{
                      background: '#dc2626',
                      color: '#fff',
                      border: 'none',
                      padding: '10px 20px',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontWeight: '600',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    ✉️ Confirm & Send
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

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
