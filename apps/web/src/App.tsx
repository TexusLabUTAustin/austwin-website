import { Navigate, Route, Routes } from 'react-router-dom'
import CityForesightDashboard from './pages/CityForesight'
import CityGuide from './pages/CityGuide'
import AusTwinOnePager from './pages/OnePager'
import CoolPathRedirect from './pages/CoolPath'
import ThermalscapeRedirect from './pages/Thermalscape'
import UrbanSenseDashboard from './pages/UrbanSense'

function App() {
  return (
    <Routes>
      <Route path="/one-pager" element={<AusTwinOnePager />} />
      <Route path="/cityforesight" element={<CityForesightDashboard />} />
      <Route path="/urbansense" element={<UrbanSenseDashboard />} />
      <Route path="/cityguide" element={<CityGuide />} />
      <Route path="/coolpath" element={<CoolPathRedirect />} />
      <Route path="/thermalscape" element={<ThermalscapeRedirect />} />
      <Route path="/" element={<Navigate to="/one-pager" replace />} />
    </Routes>
  )
}

export default App
