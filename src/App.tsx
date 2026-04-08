import { Navigate, Route, Routes } from 'react-router-dom'
import AusTwinOnePager from './pages/OnePager'
import ThermalscapeRedirect from './pages/Thermalscape'

function App() {
  return (
    <Routes>
      <Route path="/one-pager" element={<AusTwinOnePager />} />
      <Route path="/thermalscape" element={<ThermalscapeRedirect />} />
      <Route path="/" element={<Navigate to="/one-pager" replace />} />
    </Routes>
  )
}

export default App
