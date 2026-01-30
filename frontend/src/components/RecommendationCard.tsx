/**
 * Recommendation card component
 * Displays a single load recommendation with expandable explanations
 */
import { useState } from 'react';
import type { Recommendation } from '../types/models';

interface RecommendationCardProps {
  recommendation: Recommendation;
}

export default function RecommendationCard({ recommendation }: RecommendationCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const confidenceColor = {
    high: '#10b981',
    medium: '#f59e0b',
    low: '#ef4444',
  }[recommendation.confidence];

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  return (
    <div className="recommendation-card">
      <div className="card-header">
        <div className="rank-badge">#{recommendation.rank}</div>
        <div className="score-section">
          <div className="reload-score">
            <span className="score-value">{recommendation.reload_score}</span>
            <span className="score-label">/100</span>
          </div>
          <div className="confidence-badge" style={{ backgroundColor: confidenceColor }}>
            {recommendation.confidence} confidence
          </div>
        </div>
      </div>

      <div className="card-body">
        <div className="load-details">
          <div className="detail-row">
            <span className="label">Deadhead:</span>
            <span className="value">{recommendation.deadhead_miles?.toFixed(0)} mi</span>
          </div>
          <div className="detail-row">
            <span className="label">Total Miles:</span>
            <span className="value">{recommendation.total_miles?.toFixed(0)} mi</span>
          </div>
          <div className="detail-row">
            <span className="label">Est. Time:</span>
            <span className="value">
              {recommendation.estimated_total_time_min
                ? `${(recommendation.estimated_total_time_min / 60).toFixed(1)} hrs`
                : 'N/A'}
            </span>
          </div>
        </div>

        <div className="timeline-brief">
          <div className="timeline-item">
            <span className="timeline-label">Pickup:</span>
            <span className="timeline-value">{formatDate(recommendation.arrival_at_pickup)}</span>
          </div>
          <div className="timeline-item">
            <span className="timeline-label">Delivery:</span>
            <span className="timeline-value">{formatDate(recommendation.arrival_at_delivery)}</span>
          </div>
        </div>
      </div>

      <button
        className="why-this-button"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
      >
        {isExpanded ? '▼ Hide Details' : '▶ Why this?'}
      </button>

      {isExpanded && (
        <div className="explanations">
          <h4>Recommendations</h4>
          <ul>
            {recommendation.explanations.map((explanation, idx) => (
              <li key={idx}>{explanation}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
