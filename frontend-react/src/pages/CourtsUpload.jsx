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
      setResult(data);
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
            <h4>Expected CSV Format:</h4>
            <div className="format-columns">
              <span className="col-tag">plate_id</span>
              <span className="col-tag">violation_code</span>
              <span className="col-tag">violation_date</span>
              <span className="col-tag">court</span>
              <span className="col-tag">county</span>
              <span className="col-tag">police_agency</span>
              <span className="col-tag">disposition</span>
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
                <p>❌ Error: {result.error}</p>
              ) : (
                <>
                  <p>✅ {result.message}</p>
                  {result.columns_detected && (
                    <p>Columns: {result.columns_detected.join(', ')}</p>
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
              <li>Export violation records as CSV</li>
              <li>Include all required columns</li>
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
