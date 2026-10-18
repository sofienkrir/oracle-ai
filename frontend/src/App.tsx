import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { PageHeader } from './components/ui'
import { DatasetPage } from './pages/DatasetPage'
import { HistoryPage } from './pages/HistoryPage'
import { HomePage } from './pages/HomePage'
import { ImportPage } from './pages/ImportPage'
import { PlannedPage } from './pages/PlannedPage'
import { WorkspaceProvider } from './state/workspace'

function NotFound() {
  return (
    <>
      <PageHeader title="Page introuvable" />
      <Link to="/">Retour à l'accueil</Link>
    </>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="import" element={<ImportPage />} />
        <Route path="datasets/:id" element={<DatasetPage />} />
        <Route path="explorer" element={<PlannedPage id="explorer" />} />
        <Route path="anomalies" element={<PlannedPage id="anomalies" />} />
        <Route path="forecasting" element={<PlannedPage id="forecasting" />} />
        <Route path="root-cause" element={<PlannedPage id="root-cause" />} />
        <Route path="scenarios" element={<PlannedPage id="scenarios" />} />
        <Route path="report" element={<PlannedPage id="report" />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <WorkspaceProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </WorkspaceProvider>
  )
}
