import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/dmv.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

function CourtsUpload() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const navigate = useNavigate();

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    processFile(selectedFile);
  };

  const processFile = (selectedFile) => {
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
        
        setPreview({ headers, rows, totalLines: text.split('\n').length - 1 });
      };
      reader.readAsText(selectedFile);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
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

  const clearFile = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
  };

  return (
    <div className="court-upload-page">
      {/* Header */}
      <header className="court-upload-header">
        <button className="back-btn" onClick={() => navigate('/dmv')}>
          ← Back
        </button>
        <h1>Court Data Upload</h1>
        <span className="header-badge">Statewide Integration</span>
      </header>

      <div className="court-upload-content">
        {/* Main Upload Area */}
        <div className="upload-main-section">
          {!file ? (
            <div 
              className={`drop-zone ${dragActive ? 'active' : ''}`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
            >
              <div className="drop-zone-content">
                <div className="drop-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
                  </svg>
                </div>
                <h3>Drop your CSV file here</h3>
                <p>or click to browse</p>
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  id="csv-upload"
                  className="file-input-hidden"
                />
                <label htmlFor="csv-upload" className="browse-btn">
                  Browse Files
                </label>
              </div>
            </div>
          ) : (
            <div className="file-selected">
              <div className="file-info">
                <div className="file-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                    <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>
                  </svg>
                </div>
                <div className="file-details">
                  <span className="file-name">{file.name}</span>
                  <span className="file-meta">
                    {(file.size / 1024).toFixed(1)} KB • {preview?.totalLines || 0} records
                  </span>
                </div>
                <button className="clear-btn" onClick={clearFile}>×</button>
              </div>

              {/* Preview Table */}
              {preview && (
                <div className="preview-container">
                  <div className="preview-header">
                    <span>Preview</span>
                    <span className="preview-count">Showing first 10 of {preview.totalLines} rows</span>
                  </div>
                  <div className="preview-table-scroll">
                    <table className="preview-table">
                      <thead>
                        <tr>
                          {preview.headers.slice(0, 8).map((h, i) => (
                            <th key={i}>{h.replace(/_/g, ' ')}</th>
                          ))}
                          {preview.headers.length > 8 && <th>...</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {preview.rows.map((row, i) => (
                          <tr key={i}>
                            {preview.headers.slice(0, 8).map((h, j) => (
                              <td key={j}>{row[h]}</td>
                            ))}
                            {preview.headers.length > 8 && <td>...</td>}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Upload Button */}
              <button
                className={`upload-btn ${uploading ? 'uploading' : ''}`}
                onClick={handleUpload}
                disabled={uploading}
              >
                {uploading ? (
                  <>
                    <span className="spinner-sm"></span>
                    Processing...
                  </>
                ) : (
                  <>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
                    </svg>
                    Upload to DMV System
                  </>
                )}
              </button>

              {/* Result */}
              {result && (
                <div className={`upload-result ${result.error ? 'error' : 'success'}`}>
                  {result.error ? (
                    <div className="result-content">
                      <span className="result-icon">✕</span>
                      <div>
                        <strong>Upload Failed</strong>
                        <p>{result.error}</p>
                      </div>
                    </div>
                  ) : (
                    <div className="result-content">
                      <span className="result-icon">✓</span>
                      <div>
                        <strong>{result.inserted?.toLocaleString()} records imported</strong>
                        <p>Data synced to DMV enforcement system</p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Sidebar Info */}
        <div className="upload-sidebar">
          <div className="sidebar-card">
            <h4>Required Columns</h4>
            <div className="column-list">
              <span>driver_license_number</span>
              <span>driver_full_name</span>
              <span>date_of_birth</span>
              <span>plate_id</span>
              <span>violation_code</span>
              <span>date_of_violation</span>
              <span>police_agency</span>
              <span>ticket_issuer</span>
            </div>
          </div>

          <div className="sidebar-card">
            <h4>Violation Codes</h4>
            <div className="code-list">
              <div className="code-item">
                <span className="code">1180A</span>
                <span className="desc">1-10 mph over</span>
              </div>
              <div className="code-item">
                <span className="code">1180B</span>
                <span className="desc">11-20 mph over</span>
              </div>
              <div className="code-item">
                <span className="code">1180C</span>
                <span className="desc">21-30 mph over</span>
              </div>
              <div className="code-item">
                <span className="code">1180D</span>
                <span className="desc">31+ mph over</span>
              </div>
              <div className="code-item">
                <span className="code">1180E</span>
                <span className="desc">School zone</span>
              </div>
            </div>
          </div>

          <div className="sidebar-card stats">
            <div className="stat-row">
              <span className="stat-label">Courts Supported</span>
              <span className="stat-value">1,800+</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Counties</span>
              <span className="stat-value">62</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Processing</span>
              <span className="stat-value">Real-time</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CourtsUpload;
