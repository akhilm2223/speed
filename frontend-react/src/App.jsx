import React, { useState, useEffect } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

function App() {
  const [violations, setViolations] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [filters, setFilters] = useState({
    plate_id: '',
    state: '',
    violation_code: '',
  });

  useEffect(() => {
    fetchStats();
    fetchViolations();
  }, [page]);

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/stats`);
      if (!response.ok) throw new Error('Failed to fetch stats');
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  const fetchViolations = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: '50',
        ...Object.fromEntries(
          Object.entries(filters).filter(([_, v]) => v !== '')
        ),
      });

      const response = await fetch(`${API_BASE}/api/violations?${params}`);
      if (!response.ok) throw new Error('Failed to fetch violations');
      const data = await response.json();
      setViolations(data.violations);
      setTotalPages(data.pagination.pages);
    } catch (err) {
      setError(err.message);
      console.error('Error fetching violations:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (e) => {
    setFilters({
      ...filters,
      [e.target.name]: e.target.value,
    });
  };

  const handleFilterSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    fetchViolations();
  };

  const handleClearFilters = () => {
    setFilters({
      plate_id: '',
      state: '',
      violation_code: '',
    });
    setPage(1);
  };

  useEffect(() => {
    if (page > 0) {
      fetchViolations();
    }
  }, [page]);

  return (
    <div className="app">
      <div className="header">
        <h1>🚗 Traffic Violations Dashboard</h1>
        <p>Monitor and analyze traffic violations data</p>
      </div>

      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <h3>Total Violations</h3>
            <div className="value">{stats.total_violations.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <h3>Total Vehicles</h3>
            <div className="value">{stats.total_vehicles.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <h3>Top Violation Code</h3>
            <div className="value">
              {stats.violations_by_code[0]?.code || 'N/A'}
            </div>
            <div style={{ marginTop: '10px', color: '#666', fontSize: '0.9em' }}>
              {stats.violations_by_code[0]?.count.toLocaleString() || 0} violations
            </div>
          </div>
        </div>
      )}

      <div className="filters">
        <form onSubmit={handleFilterSubmit}>
          <div className="form-group">
            <label htmlFor="plate_id">Plate ID</label>
            <input
              type="text"
              id="plate_id"
              name="plate_id"
              value={filters.plate_id}
              onChange={handleFilterChange}
              placeholder="Enter plate ID"
            />
          </div>
          <div className="form-group">
            <label htmlFor="state">State</label>
            <input
              type="text"
              id="state"
              name="state"
              value={filters.state}
              onChange={handleFilterChange}
              placeholder="e.g., NY"
              maxLength="2"
            />
          </div>
          <div className="form-group">
            <label htmlFor="violation_code">Violation Code</label>
            <input
              type="text"
              id="violation_code"
              name="violation_code"
              value={filters.violation_code}
              onChange={handleFilterChange}
              placeholder="e.g., 1180"
            />
          </div>
          <div className="form-group">
            <button type="submit" className="btn">Search</button>
          </div>
          <div className="form-group">
            <button
              type="button"
              className="btn"
              onClick={handleClearFilters}
              style={{ background: '#999' }}
            >
              Clear
            </button>
          </div>
        </form>
      </div>

      {error && <div className="error">Error: {error}</div>}

      <div className="violations-table">
        <div className="table-container">
          {loading ? (
            <div className="loading">Loading violations...</div>
          ) : violations.length === 0 ? (
            <div className="loading">No violations found</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Plate ID</th>
                  <th>State</th>
                  <th>Violation Code</th>
                  <th>Issue Date</th>
                  <th>Location</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {violations.map((violation) => (
                  <tr key={violation.violation_id}>
                    <td>{violation.plate_id}</td>
                    <td>{violation.registration_state}</td>
                    <td>{violation.violation_code}</td>
                    <td>
                      {violation.issue_date
                        ? new Date(violation.issue_date).toLocaleDateString()
                        : 'N/A'}
                    </td>
                    <td>{violation.violation_location || 'N/A'}</td>
                    <td>{violation.source_type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {!loading && violations.length > 0 && (
        <div className="pagination">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </button>
          <span>
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

export default App;

