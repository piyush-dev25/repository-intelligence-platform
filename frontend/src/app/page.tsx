'use client';

import { useEffect, useState } from 'react';

export default function Home() {
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Fetch data from our FastAPI backend
    fetch('http://127.0.0.1:8000/health')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to connect to backend');
        return res.json();
      })
      .then((data) => setHealthStatus(data))
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1>Repository Intelligence Platform</h1>
      <p>Testing Connection to Backend...</p>

      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      
      {healthStatus ? (
        <div style={{ background: '#f0f0f0', padding: '1rem', borderRadius: '8px' }}>
          <p><strong>Status:</strong> {healthStatus.status}</p>
          <p><strong>Database:</strong> {healthStatus.database}</p>
        </div>
      ) : (
        !error && <p>Loading backend status...</p>
      )}
    </div>
  );
}