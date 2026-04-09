import { Navigate, Route, Routes } from 'react-router-dom'
import AusTwinOnePager from './pages/OnePager'
import CoolPathRedirect from './pages/CoolPath'
import ThermalscapeRedirect from './pages/Thermalscape'

function App() {
  return (
    <Routes>
      <Route path="/one-pager" element={<AusTwinOnePager />} />
      <Route path="/coolpath" element={<CoolPathRedirect />} />
      <Route path="/thermalscape" element={<ThermalscapeRedirect />} />
      <Route path="/" element={<Navigate to="/one-pager" replace />} />
    </Routes>
  )
}

export default App
