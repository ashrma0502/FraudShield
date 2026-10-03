import React from 'react';
import { Outlet, Navigate, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Shield, LayoutDashboard, LogOut, CheckSquare } from 'lucide-react';
import { cn } from '../utils';

export default function Layout({ allowedRoles }) {
  const { user, logout } = useAuth();
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    // Basic redirect if they don't have access
    return <Navigate to={user.role === 'merchant' ? '/merchant' : '/analyst'} replace />;
  }

  const navigation = [
    { name: 'Dashboard', href: '/merchant', icon: LayoutDashboard, role: 'merchant' },
    { name: 'Review Queue', href: '/analyst', icon: CheckSquare, role: 'analyst' },
    { name: 'Review Queue', href: '/analyst', icon: CheckSquare, role: 'admin' },
  ].filter(item => item.role === user.role);

  return (
    <div className="min-h-screen bg-dark-900 flex">
      {/* Sidebar */}
      <div className="w-64 glass border-r border-white/5 flex flex-col hidden md:flex">
        <div className="h-20 flex items-center px-8 border-b border-white/5">
          <Shield className="w-8 h-8 text-brand-500 mr-3 animate-pulse-slow" />
          <span className="text-xl font-display font-bold text-white tracking-wide">
            Fraud<span className="text-brand-500">Shield</span>
          </span>
        </div>
        
        <nav className="flex-1 px-4 py-8 space-y-2">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={cn(
                  'flex items-center px-4 py-3 rounded-xl transition-all duration-200 group',
                  isActive 
                    ? 'bg-brand-500/10 text-brand-400' 
                    : 'text-gray-400 hover:bg-white/5 hover:text-white'
                )}
              >
                <item.icon className={cn('w-5 h-5 mr-3', isActive ? 'text-brand-400' : 'text-gray-500 group-hover:text-gray-300')} />
                <span className="font-medium">{item.name}</span>
              </Link>
            )
          })}
        </nav>

        <div className="p-4 border-t border-white/5">
          <div className="flex items-center px-4 py-3 mb-2 rounded-xl bg-dark-800/50 border border-white/5">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-brand-500 to-indigo-500 flex items-center justify-center text-sm font-bold text-white mr-3">
              {user.username.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="text-sm font-medium text-white truncate">{user.username}</p>
              <p className="text-xs text-gray-500 capitalize">{user.role}</p>
            </div>
          </div>
          <button
            onClick={logout}
            className="w-full flex items-center px-4 py-3 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-colors"
          >
            <LogOut className="w-5 h-5 mr-3" />
            <span className="font-medium">Logout</span>
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-h-screen overflow-hidden">
        {/* Mobile Header */}
        <div className="md:hidden h-16 glass border-b border-white/5 flex items-center justify-between px-4">
          <div className="flex items-center">
            <Shield className="w-6 h-6 text-brand-500 mr-2" />
            <span className="font-display font-bold text-white">FraudShield</span>
          </div>
          <button onClick={logout} className="p-2 text-gray-400 hover:text-white">
            <LogOut className="w-5 h-5" />
          </button>
        </div>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-8 lg:p-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
