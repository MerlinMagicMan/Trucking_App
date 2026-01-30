/**
 * Main application component with routing
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TruckSnapshotPage from './pages/TruckSnapshotPage';
import RecommendationsPage from './pages/RecommendationsPage';
import ForwardLookPage from './pages/ForwardLookPage';
import { PlansPage } from './pages/PlansPage';
import './styles/index.css';

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="app">
          <header className="app-header">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h1>Truck Optimizer</h1>
                <p>Single-Truck Decision Support for Reefer Operations</p>
              </div>
              <nav style={{ display: 'flex', gap: '20px' }}>
                <a href="/" style={{ color: 'white', textDecoration: 'none', fontWeight: '500' }}>
                  Single Load
                </a>
                <a href="/plans" style={{ color: 'white', textDecoration: 'none', fontWeight: '500' }}>
                  Multi-Load Plans
                </a>
              </nav>
            </div>
          </header>

          <main className="app-main">
            <Routes>
              <Route path="/" element={<TruckSnapshotPage />} />
              <Route path="/recommendations" element={<RecommendationsPage />} />
              <Route path="/forward-look" element={<ForwardLookPage />} />
              <Route path="/plans" element={<PlansPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>

          <footer className="app-footer">
            <p>Decision intelligence for stressed humans</p>
          </footer>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
