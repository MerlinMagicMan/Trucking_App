/**
 * Truck snapshot input form
 * Captures current location and HOS remaining minutes
 */
import { useState } from 'react';
import type { TruckSnapshot } from '../types/models';

interface TruckSnapshotFormProps {
  onSubmit: (snapshot: TruckSnapshot) => void;
  isLoading?: boolean;
}

export default function TruckSnapshotForm({ onSubmit, isLoading }: TruckSnapshotFormProps) {
  // Oklahoma City default location
  const [currentLat, setCurrentLat] = useState<number>(35.4676);
  const [currentLng, setCurrentLng] = useState<number>(-97.5164);

  // Default HOS (11 hours drive, 14 hours on-duty, 70 hours cycle)
  const [driveRemaining, setDriveRemaining] = useState<number>(660); // 11 hours in minutes
  const [onDutyRemaining, setOnDutyRemaining] = useState<number>(840); // 14 hours
  const [cycleRemaining, setCycleRemaining] = useState<number>(4200); // 70 hours

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const snapshot: TruckSnapshot = {
      current_lat: currentLat,
      current_lng: currentLng,
      hos: {
        drive_remaining_min: driveRemaining,
        on_duty_remaining_min: onDutyRemaining,
        cycle_remaining_min: cycleRemaining,
      },
    };

    onSubmit(snapshot);
  };

  return (
    <form className="truck-snapshot-form" onSubmit={handleSubmit}>
      <div className="form-section">
        <h3>Current Location</h3>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="lat">Latitude</label>
            <input
              id="lat"
              type="number"
              step="0.0001"
              min="-90"
              max="90"
              value={currentLat}
              onChange={(e) => setCurrentLat(parseFloat(e.target.value))}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="lng">Longitude</label>
            <input
              id="lng"
              type="number"
              step="0.0001"
              min="-180"
              max="180"
              value={currentLng}
              onChange={(e) => setCurrentLng(parseFloat(e.target.value))}
              required
            />
          </div>
        </div>
        <p className="form-hint">Default: Oklahoma City, OK</p>
      </div>

      <div className="form-section">
        <h3>Hours of Service Remaining</h3>

        <div className="form-group">
          <label htmlFor="drive">
            Drive Time (minutes)
            <span className="value-display">{driveRemaining} min ({(driveRemaining / 60).toFixed(1)} hrs)</span>
          </label>
          <input
            id="drive"
            type="range"
            min="0"
            max="660"
            step="30"
            value={driveRemaining}
            onChange={(e) => setDriveRemaining(parseInt(e.target.value))}
          />
        </div>

        <div className="form-group">
          <label htmlFor="onduty">
            On-Duty Time (minutes)
            <span className="value-display">{onDutyRemaining} min ({(onDutyRemaining / 60).toFixed(1)} hrs)</span>
          </label>
          <input
            id="onduty"
            type="range"
            min="0"
            max="840"
            step="30"
            value={onDutyRemaining}
            onChange={(e) => setOnDutyRemaining(parseInt(e.target.value))}
          />
        </div>

        <div className="form-group">
          <label htmlFor="cycle">
            70-Hour Cycle (minutes)
            <span className="value-display">{cycleRemaining} min ({(cycleRemaining / 60).toFixed(1)} hrs)</span>
          </label>
          <input
            id="cycle"
            type="range"
            min="0"
            max="4200"
            step="60"
            value={cycleRemaining}
            onChange={(e) => setCycleRemaining(parseInt(e.target.value))}
          />
        </div>
      </div>

      <button
        type="submit"
        className="btn-primary btn-large"
        disabled={isLoading}
      >
        {isLoading ? 'Finding Best Loads...' : 'Find Best Loads'}
      </button>
    </form>
  );
}
