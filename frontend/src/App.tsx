import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/common/Layout';

// Catalog Pages
import { CatalogListPage } from './pages/catalog/CatalogListPage';
import { CatalogSearchPage } from './pages/catalog/CatalogSearchPage';
import { SourceDetailPage } from './pages/catalog/SourceDetailPage';

// Factor Pages
import { FactorGraphPage } from './pages/factors/FactorGraphPage';
import { FactorDetailPage } from './pages/factors/FactorDetailPage';
import { FactorComparePage } from './pages/factors/FactorComparePage';
import { FactorBlendPage } from './pages/factors/FactorBlendPage';

// Alert Pages
import { AlertsListPage } from './pages/alerts/AlertsListPage';
import { AlertCreatePage } from './pages/alerts/AlertCreatePage';
import { AlertHistoryPage } from './pages/alerts/AlertHistoryPage';

// Geo Pages
import { EarthquakeMapPage } from './pages/geo/EarthquakeMapPage';
import { PowerGridMapPage } from './pages/geo/PowerGridMapPage';
import { ThresholdConfigPage } from './pages/geo/ThresholdConfigPage';

// Backtest Pages
import { BacktestRunPage } from './pages/backtest/BacktestRunPage';
import { DecayAnalysisPage } from './pages/backtest/DecayAnalysisPage';
import { SeasonalityPage } from './pages/backtest/SeasonalityPage';
import { ExperimentsPage } from './pages/backtest/ExperimentsPage';

// Admin Pages
import { EntityMappingsPage } from './pages/admin/EntityMappingsPage';
import { CollectorHealthPage } from './pages/admin/CollectorHealthPage';
import { DataRequestsPage } from './pages/admin/DataRequestsPage';

// Account Pages
import { UsagePage } from './pages/account/UsagePage';
import { ApiKeysPage } from './pages/account/ApiKeysPage';
import { UpgradePage } from './pages/account/UpgradePage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            {/* Redirect root to catalog */}
            <Route path="/" element={<Navigate to="/catalog" replace />} />

            {/* Catalog Routes */}
            <Route path="/catalog" element={<CatalogListPage />} />
            <Route path="/catalog/search" element={<CatalogSearchPage />} />
            <Route path="/catalog/sources/:sourceId" element={<SourceDetailPage />} />

            {/* Factor Routes */}
            <Route path="/factors" element={<Navigate to="/factors/graph" replace />} />
            <Route path="/factors/graph" element={<FactorGraphPage />} />
            <Route path="/factors/:factorId" element={<FactorDetailPage />} />
            <Route path="/factors/compare" element={<FactorComparePage />} />
            <Route path="/factors/blend" element={<FactorBlendPage />} />

            {/* Alert Routes */}
            <Route path="/alerts" element={<AlertsListPage />} />
            <Route path="/alerts/create" element={<AlertCreatePage />} />
            <Route path="/alerts/history" element={<AlertHistoryPage />} />

            {/* Geo Routes */}
            <Route path="/geo" element={<Navigate to="/geo/earthquakes" replace />} />
            <Route path="/geo/earthquakes" element={<EarthquakeMapPage />} />
            <Route path="/geo/power-grid" element={<PowerGridMapPage />} />
            <Route path="/geo/thresholds" element={<ThresholdConfigPage />} />

            {/* Backtest Routes */}
            <Route path="/backtest" element={<BacktestRunPage />} />
            <Route path="/backtest/decay" element={<DecayAnalysisPage />} />
            <Route path="/backtest/seasonality" element={<SeasonalityPage />} />
            <Route path="/backtest/experiments" element={<ExperimentsPage />} />

            {/* Admin Routes */}
            <Route path="/admin" element={<Navigate to="/admin/mappings" replace />} />
            <Route path="/admin/mappings" element={<EntityMappingsPage />} />
            <Route path="/admin/health" element={<CollectorHealthPage />} />
            <Route path="/admin/requests" element={<DataRequestsPage />} />

            {/* Account Routes */}
            <Route path="/account" element={<Navigate to="/account/usage" replace />} />
            <Route path="/account/usage" element={<UsagePage />} />
            <Route path="/account/api-keys" element={<ApiKeysPage />} />
            <Route path="/account/upgrade" element={<UpgradePage />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
