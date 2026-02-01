/**
 * Main application — enterprise shell with nested routes
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from './components/layout/AppShell';
import { PreflightPage } from './pages/PreflightPage';
import { RoutesPage } from './pages/RoutesPage';
import { TrucksPage } from './pages/TrucksPage';
import { PlanHistoryPage } from './pages/PlanHistoryPage';
import TruckSnapshotPage from './pages/TruckSnapshotPage';
import RecommendationsPage from './pages/RecommendationsPage';
import ForwardLookPage from './pages/ForwardLookPage';
import './styles/index.css';

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
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<Navigate to="/plans" replace />} />
            <Route path="/plans" element={<PreflightPage />} />
            <Route path="/routes" element={<RoutesPage />} />
            <Route path="/assets/trucks" element={<TrucksPage />} />
            <Route path="/plans/history" element={<PlanHistoryPage />} />
            <Route path="/snapshot" element={<TruckSnapshotPage />} />
            <Route path="/recommendations" element={<RecommendationsPage />} />
            <Route path="/forward-look" element={<ForwardLookPage />} />
            <Route path="*" element={<Navigate to="/plans" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
