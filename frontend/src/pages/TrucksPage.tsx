import React, { useEffect, useState } from 'react';
import type { Truck } from '../types/org';
import { fetchTrucks, createTruck } from '../services/api';
import { getActiveTruckId, setActiveTruckId } from '../services/orgContext';

export const TrucksPage: React.FC = () => {
  const [trucks, setTrucks] = useState<Truck[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTruck, setActiveTruckState] = useState<string>(getActiveTruckId() || '');
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [name, setName] = useState('');
  const [equipment, setEquipment] = useState('reefer');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [creating, setCreating] = useState(false);

  const loadTrucks = async () => {
    setLoading(true);
    try {
      const data = await fetchTrucks();
      setTrucks(data);
    } catch {
      setTrucks([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTrucks(); }, []);

  const handleSetActive = (id: string) => {
    setActiveTruckId(id);
    setActiveTruckState(id);
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await createTruck({
        name: name.trim(),
        equipment_type: equipment,
        home_base_city: city.trim() || undefined,
        home_base_state: state.trim().toUpperCase() || undefined,
      });
      setName('');
      setCity('');
      setState('');
      setShowForm(false);
      loadTrucks();
    } catch {
      // ignore
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1>Trucks</h1>
          <p className="page-subtitle">{trucks.length} truck{trucks.length !== 1 ? 's' : ''} in fleet</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)} type="button">
          {showForm ? 'Cancel' : 'Add Truck'}
        </button>
      </div>

      {showForm && (
        <div className="card">
          <div className="form-row">
            <div className="form-field">
              <label>Truck Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Truck 002" />
            </div>
            <div className="form-field">
              <label>Equipment</label>
              <select value={equipment} onChange={(e) => setEquipment(e.target.value)}>
                <option value="reefer">Reefer</option>
                <option value="dry_van">Dry Van</option>
                <option value="flatbed">Flatbed</option>
              </select>
            </div>
          </div>
          <div className="form-row">
            <div className="form-field">
              <label>Home Base City</label>
              <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="e.g. Dallas" />
            </div>
            <div className="form-field">
              <label>State</label>
              <input value={state} onChange={(e) => setState(e.target.value)} placeholder="TX" maxLength={2} />
            </div>
            <div className="form-field" style={{ justifyContent: 'flex-end' }}>
              <button className="btn btn-primary" onClick={handleCreate} disabled={creating || !name.trim()} type="button">
                {creating ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="empty-state"><p>Loading trucks...</p></div>
      ) : trucks.length === 0 ? (
        <div className="empty-state">
          <h2>No trucks</h2>
          <p>Add your first truck to get started.</p>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Equipment</th>
              <th>Home Base</th>
              <th>Added</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {trucks.map((t) => (
              <tr key={t.id} className={t.id === activeTruck ? 'active-row' : ''}>
                <td className="td-bold">{t.name}</td>
                <td>{t.equipment_type}</td>
                <td>{t.home_base_city && t.home_base_state ? `${t.home_base_city}, ${t.home_base_state}` : '—'}</td>
                <td>{new Date(t.created_at).toLocaleDateString()}</td>
                <td>{t.id === activeTruck ? <span className="active-badge">Active</span> : null}</td>
                <td>
                  {t.id !== activeTruck && (
                    <button className="btn btn-sm" onClick={() => handleSetActive(t.id)} type="button">Set Active</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};
