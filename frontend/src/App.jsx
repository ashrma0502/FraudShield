import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import MerchantDashboard from './pages/MerchantDashboard';
import AnalystQueue from './pages/AnalystQueue';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          
          <Route element={<Layout allowedRoles={['merchant']} />}>
            <Route path="/merchant" element={<MerchantDashboard />} />
          </Route>

          <Route element={<Layout allowedRoles={['analyst', 'admin']} />}>
            <Route path="/analyst" element={<AnalystQueue />} />
          </Route>

          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
