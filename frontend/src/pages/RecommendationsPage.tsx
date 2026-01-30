/**
 * Recommendations page (Screen 2)
 * Displays top 3 load recommendations
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import RecommendationCard from '../components/RecommendationCard';
import type { OptimizeResponse } from '../types/models';

export default function RecommendationsPage() {
  const navigate = useNavigate();
  const [result, setResult] = useState<OptimizeResponse | null>(null);

  useEffect(() => {
    // Load result from sessionStorage
    const stored = sessionStorage.getItem('optimizeResult');
    if (!stored) {
      // No data, redirect back to input
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

  if (!result) {
    return <div className="page">Loading...</div>;
  }

  return (
    <div className="page recommendations-page">
      <div className="page-header">
        <h2>Top Load Recommendations</h2>
        <p>
          Analyzed {result.loads_analyzed} loads, {result.loads_feasible} HOS-feasible
        </p>
      </div>

      {result.warnings.length > 0 && (
        <div className="warnings">
          {result.warnings.map((warning, idx) => (
            <div key={idx} className="warning-message">
              ⚠️ {warning}
            </div>
          ))}
        </div>
      )}

      <div className="recommendations-list">
        {result.recommendations.length === 0 ? (
          <div className="no-results">
            <h3>No feasible loads found</h3>
            <p>Try adjusting your search radius or take a rest break to restore HOS.</p>
            <button className="btn-primary" onClick={() => navigate('/')}>
              Try Again
            </button>
          </div>
        ) : (
          <>
            {result.recommendations.map((rec) => (
              <RecommendationCard key={rec.load_id} recommendation={rec} />
            ))}

            {result.forward_look && (
              <button
                className="btn-secondary btn-large"
                onClick={() => navigate('/forward-look')}
              >
                View Forward Look Timeline →
              </button>
            )}
          </>
        )}
      </div>

      <button className="btn-outline" onClick={() => navigate('/')}>
        ← New Search
      </button>
    </div>
  );
}
