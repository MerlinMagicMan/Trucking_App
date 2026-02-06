import React, { useEffect, useState, useCallback } from 'react';
import type { RouteRecord } from '../types/org';
import { getDataClient } from '../services/dataClient';
import { CsvUpload } from '../components/preflight/CsvUpload';

export const RoutesPage: React.FC = () => {
  const [routes, setRoutes] = useState<RouteRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [pickupFilter, setPickupFilter] = useState('');
  const [deliveryFilter, setDeliveryFilter] = useState('');
  const [showUpload, setShowUpload] = useState(false);

  const loadRoutes = useCallback(async () => {
    setLoading(true);
    try {
      const filters: Record<string, string> = {};
      if (pickupFilter) filters.pickup_state = pickupFilter;
      if (deliveryFilter) filters.delivery_state = deliveryFilter;
      const data = await getDataClient().getRoutes(filters);
      setRoutes(data);
    } catch {
      setRoutes([]);
    } finally {
      setLoading(false);
    }
  }, [pickupFilter, deliveryFilter]);

  useEffect(() => { loadRoutes(); }, [loadRoutes]);

  const handleDelete = async (id: string) => {
    try {
      await getDataClient().deleteRoute(id);
      setRoutes((prev) => prev.filter((r) => r.id !== id));
    } catch {
      // ignore
    }
  };

  const handleImported = (_count: number) => {
    setShowUpload(false);
    loadRoutes();
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1>Routes Library</h1>
          <p className="page-subtitle">{routes.length} route{routes.length !== 1 ? 's' : ''} in library</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowUpload(!showUpload)} type="button">
          {showUpload ? 'Close Upload' : 'Upload CSV'}
        </button>
      </div>

      {showUpload && (
        <div className="card" style={{ marginBottom: '16px' }}>
          <CsvUpload onImported={handleImported} />
        </div>
      )}

      <div className="filters-row">
        <div className="filter-group">
          <label>Pickup State</label>
          <input
            type="text"
            value={pickupFilter}
            onChange={(e) => setPickupFilter(e.target.value.toUpperCase())}
            placeholder="e.g. TX"
            maxLength={2}
          />
        </div>
        <div className="filter-group">
          <label>Delivery State</label>
          <input
            type="text"
            value={deliveryFilter}
            onChange={(e) => setDeliveryFilter(e.target.value.toUpperCase())}
            placeholder="e.g. OK"
            maxLength={2}
          />
        </div>
        <button className="btn btn-sm" onClick={loadRoutes} type="button">Apply</button>
      </div>

      {loading ? (
        <div className="empty-state"><p>Loading routes...</p></div>
      ) : routes.length === 0 ? (
        <div className="empty-state">
          <h2>No routes yet</h2>
          <p>Upload a CSV to add routes to your library.</p>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Route</th>
              <th>Miles</th>
              <th>Rate</th>
              <th>$/Mile</th>
              <th>Source</th>
              <th>Added</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {routes.map((r) => {
              const rpm = r.miles && r.miles > 0 ? r.rate_total / r.miles : 0;
              return (
                <tr key={r.id}>
                  <td className="td-bold">{r.pickup_city}, {r.pickup_state} → {r.delivery_city}, {r.delivery_state}</td>
                  <td className="td-mono">{r.miles?.toLocaleString() || '—'}</td>
                  <td className="td-green">${r.rate_total.toLocaleString()}</td>
                  <td className="td-mono">${rpm.toFixed(2)}</td>
                  <td>{r.source}</td>
                  <td>{new Date(r.created_at).toLocaleDateString()}</td>
                  <td>
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete(r.id)} type="button">Delete</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
};
