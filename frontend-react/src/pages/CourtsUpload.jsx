import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/dmv.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

function CourtsUpload() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const navigate = useNavigate();

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
      }
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="dmv-dashboard">
      <header className="dmv-header">
        <div className="header-left">
          <div className="dmv-logo">
            <span className="logo-icon">📤</span>
            <span className="logo-text">Local Court CSV Upload</span>
          </div>
        </div>
        <div className="header-right">
          <button className="nav-link" onClick={() => navigate('/dmv')}>
            ← Back to Dashboard
          </button>
        </div>
      </header>

      <div className="upload-container">
        <div className="upload-card">
          <h2>Upload Court Violation Data</h2>
          <p className="upload-desc">
            Local courts can upload CSV files containing violation records.
            This enables statewide integration with 1,800+ local courts.
          </p>

          <div className="expected-format">
            <h4>Required CSV Columns:</h4>
            <div className="format-section">
              <h5>Required Fields:</h5>
            <div className="format-columns">
                <span className="col-tag required">driver_license_number</span>
                <span className="col-tag required">driver_full_name</span>
                <span className="col-tag required">date_of_birth</span>
                <span className="col-tag required">license_state</span>
                <span className="col-tag required">plate_id</span>
                <span className="col-tag required">plate_state</span>
                <span className="col-tag required">violation_code</span>
                <span className="col-tag required">date_of_violation</span>
                <span className="col-tag required">disposition</span>
                <span className="col-tag required">latitude</span>
                <span className="col-tag required">longitude</span>
                <span className="col-tag required">police_agency</span>
                <span className="col-tag required">ticket_issuer</span>
              </div>
            </div>
            <div className="format-note">
              <p><strong>Note:</strong> All fields are required. Date format: <code>YYYY-MM-DD HH:MM:SS</code> or <code>YYYY-MM-DD</code></p>
              <p><strong>Violation Codes:</strong> 1180A (1-10 mph), 1180B (11-20 mph), 1180C (21-30 mph), 1180D (31+ mph), 1180E (school zone), 1180F (work zone)</p>
            </div>
          </div>

          <div className="file-input-area">
            <input
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              id="csv-upload"
              className="file-input"
            />
            <label htmlFor="csv-upload" className="file-label">
              {file ? `📄 ${file.name}` : '📁 Choose CSV File'}
            </label>
          </div>

          {preview && (
            <div className="preview-section">
              <h4>Preview (First 10 Rows)</h4>
              <div className="preview-table-container">
                <table className="preview-table">
                  <thead>
                    <tr>
                      {preview.headers.map((h, i) => (
                        <th key={i}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row, i) => (
                      <tr key={i}>
                        {preview.headers.map((h, j) => (
                          <td key={j}>{row[h]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {file && (
            <button
              className="upload-submit-btn"
              onClick={handleUpload}
              disabled={uploading}
            >
              {uploading ? 'Uploading...' : '🚀 Upload to DMV System'}
            </button>
          )}

          {result && (
            <div className={`upload-result ${result.error ? 'error' : 'success'}`}>
              {result.error ? (
                <>
                  <p>❌ <strong>Error:</strong> {result.error}</p>
                  {result.first_error && (
                    <p className="error-detail">Details: {result.first_error}</p>
                  )}
                </>
              ) : (
                <>
                  <p>✅ <strong>{result.message || 'Upload successful!'}</strong></p>
                  {result.inserted !== undefined && (
                    <div className="upload-stats">
                      <p>📊 Records inserted: <strong>{result.inserted}</strong></p>
                      {result.errors > 0 && (
                        <p>⚠️ Errors: <strong>{result.errors}</strong></p>
                      )}
                      {result.filename && (
                        <p>📄 File: {result.filename}</p>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        <div className="upload-info-card">
          <h3>📋 Integration Guide</h3>
          <div className="info-section">
            <h4>For Local Courts:</h4>
            <ul>
              <li>Export violation records as CSV with all required columns</li>
              <li>Ensure dates are in format: <code>YYYY-MM-DD HH:MM:SS</code></li>
              <li>Coordinates (latitude/longitude) must be valid decimal numbers</li>
              <li>Upload monthly or as needed</li>
            </ul>
          </div>
          <div className="info-section">
            <h4>Data Processing:</h4>
            <ul>
              <li>Records validated against schema</li>
              <li>Drivers matched to existing profiles</li>
              <li>Risk scores updated automatically</li>
              <li>ISA alerts generated if threshold met</li>
            </ul>
          </div>
          <div className="info-section">
            <h4>Supported Courts:</h4>
            <p className="court-count">1,800+ local courts statewide</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CourtsUpload;
