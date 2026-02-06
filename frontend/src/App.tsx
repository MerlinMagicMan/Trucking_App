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
import { CopilotPage } from './pages/CopilotPage';
import { IntelPage } from './pages/IntelPage';
import { ReportsPage } from './pages/ReportsPage';
import { SettingsPage } from './pages/SettingsPage';
import { MaintenancePage } from './pages/MaintenancePage';
import { AdminPage } from './pages/AdminPage';
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
            <Route path="/copilot" element={<CopilotPage />} />
            <Route path="/intel" element={<IntelPage />} />
            <Route path="/routes" element={<RoutesPage />} />
            <Route path="/assets/trucks" element={<TrucksPage />} />
            <Route path="/maintenance" element={<MaintenancePage />} />
            <Route path="/plans/history" element={<PlanHistoryPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/admin" element={<AdminPage />} />
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
