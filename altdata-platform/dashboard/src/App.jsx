import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'

// Lazy load pages for code splitting
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Factors = lazy(() => import('./pages/Factors'))
const FactorDetail = lazy(() => import('./pages/FactorDetail'))
const Entities = lazy(() => import('./pages/Entities'))
const EntityDetail = lazy(() => import('./pages/EntityDetail'))
const Sources = lazy(() => import('./pages/Sources'))
const Alerts = lazy(() => import('./pages/Alerts'))
const Backtest = lazy(() => import('./pages/Backtest'))

// Loading fallback component
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
    </div>
  )
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={
          <Suspense fallback={<PageLoader />}>
            <Dashboard />
          </Suspense>
        } />
        <Route path="factors" element={
          <Suspense fallback={<PageLoader />}>
            <Factors />
          </Suspense>
        } />
        <Route path="factors/:id" element={
          <Suspense fallback={<PageLoader />}>
            <FactorDetail />
          </Suspense>
        } />
        <Route path="entities" element={
          <Suspense fallback={<PageLoader />}>
            <Entities />
          </Suspense>
        } />
        <Route path="entities/:id" element={
          <Suspense fallback={<PageLoader />}>
            <EntityDetail />
          </Suspense>
        } />
        <Route path="sources" element={
          <Suspense fallback={<PageLoader />}>
            <Sources />
          </Suspense>
        } />
        <Route path="alerts" element={
          <Suspense fallback={<PageLoader />}>
            <Alerts />
          </Suspense>
        } />
        <Route path="backtest" element={
          <Suspense fallback={<PageLoader />}>
            <Backtest />
          </Suspense>
        } />
      </Route>
    </Routes>
  )
}

export default App
