import React, { useState, useRef } from 'react';

interface CsvRow {
  route_name: string;
  pickup_city: string;
  pickup_state: string;
  delivery_city: string;
  delivery_state: string;
  miles: string;
  rate_total: string;
  pickup_date: string;
  delivery_date: string;
  [key: string]: string;
}

interface CsvUploadProps {
  onImported: (count: number) => void;
}

const REQUIRED_COLS = ['pickup_city', 'pickup_state', 'delivery_city', 'delivery_state', 'miles', 'rate_total'];

const parseCsv = (text: string): { headers: string[]; rows: CsvRow[] } => {
  const lines = text.trim().split('\n');
  if (lines.length < 2) return { headers: [], rows: [] };
  const headers = lines[0].split(',').map(h => h.trim().toLowerCase().replace(/\s+/g, '_'));
  const rows: CsvRow[] = [];
  for (let i = 1; i < lines.length; i++) {
    const vals = lines[i].split(',').map(v => v.trim());
    const row: any = {};
    headers.forEach((h, j) => { row[h] = vals[j] || ''; });
    rows.push(row);
  }
  return { headers, rows };
};

export const CsvUpload: React.FC<CsvUploadProps> = ({ onImported }) => {
  const [rows, setRows] = useState<CsvRow[]>([]);
  const [, setHeaders] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = (file: File) => {
    setError(null);
    setStatus(null);
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const { headers: h, rows: r } = parseCsv(text);
      const missing = REQUIRED_COLS.filter(c => !h.includes(c));
      if (missing.length > 0) {
        setError(`Missing columns: ${missing.join(', ')}`);
        setRows([]);
        setHeaders([]);
        return;
      }
      setHeaders(h);
      setRows(r);
    };
    reader.readAsText(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith('.csv')) handleFile(file);
    else setError('Please drop a .csv file');
  };

  const handleImport = async () => {
    setUploading(true);
    setError(null);
    try {
      const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const resp = await fetch(`${API_BASE}/api/routes/import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ routes: rows }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `Import failed (${resp.status})`);
      }
      const data = await resp.json();
      setStatus(`${data.imported} routes imported`);
      onImported(data.imported);
      setRows([]);
      setHeaders([]);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleClear = () => {
    setRows([]);
    setHeaders([]);
    setError(null);
    setStatus(null);
  };

  const previewRows = rows.slice(0, 5);
  const displayCols = ['pickup_city', 'delivery_city', 'miles', 'rate_total'];

  return (
    <div className="pf-csv-section">
      <span className="pf-field-label">Routes (CSV)</span>

      {rows.length === 0 ? (
        <>
          <div
            className={`pf-csv-dropzone ${dragOver ? 'dragover' : ''}`}
            onClick={() => fileRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            Drop CSV or click to upload
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            style={{ display: 'none' }}
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
          />
        </>
      ) : (
        <>
          <div className="pf-csv-preview">
            <table>
              <thead>
                <tr>{displayCols.map(c => <th key={c}>{c}</th>)}</tr>
              </thead>
              <tbody>
                {previewRows.map((r, i) => (
                  <tr key={i}>{displayCols.map(c => <td key={c}>{r[c]}</td>)}</tr>
                ))}
              </tbody>
            </table>
            {rows.length > 5 && (
              <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                +{rows.length - 5} more rows
              </div>
            )}
          </div>
          <div className="pf-csv-actions">
            <button className="pf-csv-btn pf-csv-btn-primary" onClick={handleImport} disabled={uploading}>
              {uploading ? 'Importing...' : `Import ${rows.length} routes`}
            </button>
            <button className="pf-csv-btn" onClick={handleClear}>Clear</button>
          </div>
        </>
      )}

      {error && <div className="pf-csv-status pf-csv-status-error">{error}</div>}
      {status && <div className="pf-csv-status pf-csv-status-success">{status}</div>}
    </div>
  );
};
