/**
 * Forward Look timeline page (Screen 3)
 * Shows 24-48 hour projection
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Timeline from '../components/Timeline';
import type { OptimizeResponse } from '../types/models';

export default function ForwardLookPage() {
  const navigate = useNavigate();
  const [result, setResult] = useState<OptimizeResponse | null>(null);

  useEffect(() => {
    const stored = sessionStorage.getItem('optimizeResult');
    if (!stored) {
      navigate('/');
      return;
    }

    try {
      const data = JSON.parse(stored) as OptimizeResponse;
      setResult(data);
    } catch (error) {
      console.error('Failed to parse result:', error);
      navigate('/');
    }
  }, [navigate]);

  if (!result || !result.forward_look) {
    return <div className="page">Loading...</div>;
  }

  return (
    <div className="page forward-look-page">
      <div className="page-header">
        <h2>Forward Look</h2>
        <p>Timeline for top recommended load</p>
      </div>

      <Timeline forwardLook={result.forward_look} />

      <div className="button-group">
        <button className="btn-outline" onClick={() => navigate('/recommendations')}>
          ← Back to Recommendations
        </button>
        <button className="btn-primary" onClick={() => navigate('/')}>
          New Search
        </button>
      </div>
    </div>
  );
}
