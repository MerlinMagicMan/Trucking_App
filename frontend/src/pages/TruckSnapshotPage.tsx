/**
 * Truck Snapshot input page (Screen 1)
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import TruckSnapshotForm from '../components/TruckSnapshotForm';
import { optimizeRoute } from '../services/api';
import type { TruckSnapshot, OptimizeResponse } from '../types/models';

export default function TruckSnapshotPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const optimizeMutation = useMutation<OptimizeResponse, Error, TruckSnapshot>({
    mutationFn: (snapshot) => optimizeRoute(snapshot),
    onSuccess: (data) => {
      // Store result in sessionStorage for recommendations page
      sessionStorage.setItem('optimizeResult', JSON.stringify(data));
      navigate('/recommendations');
    },
    onError: (error) => {
      setError(error.message || 'Failed to optimize route');
    },
  });

  const handleSubmit = (snapshot: TruckSnapshot) => {
    setError(null);
    optimizeMutation.mutate(snapshot);
  };

  return (
    <div className="page truck-snapshot-page">
      <div className="page-header">
        <h2>Where are you now?</h2>
        <p>Enter your current location and remaining Hours of Service</p>
      </div>

      {error && (
        <div className="error-message">
          <strong>Error:</strong> {error}
        </div>
      )}

      <TruckSnapshotForm
        onSubmit={handleSubmit}
        isLoading={optimizeMutation.isPending}
      />
    </div>
  );
}
