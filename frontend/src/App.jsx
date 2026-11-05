import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import MerchantDashboard from './pages/MerchantDashboard';
import AnalystQueue from './pages/AnalystQueue';
import CustomerSimulate from './pages/CustomerSimulate';
import ModelPerformance from './pages/ModelPerformance';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          
          <Route element={<Layout allowedRoles={['customer']} />}>
            <Route path="/simulate" element={<CustomerSimulate />} />
          </Route>

          <Route element={<Layout allowedRoles={['analyst', 'merchant']} />}>
            <Route path="/dashboard" element={<MerchantDashboard />} />
            <Route path="/merchant" element={<MerchantDashboard />} />
          </Route>

          <Route element={<Layout allowedRoles={['analyst']} />}>
            <Route path="/analyst" element={<AnalystQueue />} />
          </Route>

          <Route element={<Layout allowedRoles={['admin']} />}>
            <Route path="/model-performance" element={<ModelPerformance />} />
          </Route>

          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
