import React, { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { CreditCard, ArrowUpRight, ArrowDownRight, Clock, CheckCircle2, XCircle, Search } from 'lucide-react';
import api from '../api';
import { formatCurrency, cn } from '../utils';

export default function MerchantDashboard() {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTransactions = async () => {
      try {
        const response = await api.get('/transactions/mine/');
        setTransactions(response.data.results || []);
      } catch (error) {
        console.error("Failed to fetch transactions", error);
      } finally {
        setLoading(false);
      }
    };
    fetchTransactions();
  }, []);

  // Stats
  const totalAmount = transactions.reduce((sum, t) => sum + parseFloat(t.amount), 0);
  const approvedCount = transactions.filter(t => t.status === 'approved').length;
  const declinedCount = transactions.filter(t => t.status === 'declined').length;
  const pendingCount = transactions.filter(t => ['pending', 'under_review'].includes(t.status)).length;

  const getStatusBadge = (status) => {
    switch(status) {
      case 'approved':
        return <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><CheckCircle2 className="w-3 h-3 mr-1" /> Approved</span>;
      case 'declined':
        return <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20"><XCircle className="w-3 h-3 mr-1" /> Declined</span>;
      default:
        return <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20"><Clock className="w-3 h-3 mr-1" /> Reviewing</span>;
    }
  };

  if (loading) {
    return <div className="animate-pulse-slow h-full flex flex-col space-y-6">
      <div className="h-10 w-48 bg-dark-700 rounded-lg"></div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {[1,2,3,4].map(i => <div key={i} className="h-32 bg-dark-700 rounded-2xl"></div>)}
      </div>
      <div className="h-96 bg-dark-700 rounded-2xl"></div>
    </div>;
  }

  return (
    <div className="animate-fade-in space-y-8">
      <div>
        <h1 className="text-3xl font-display font-bold text-white mb-2">Transactions</h1>
        <p className="text-gray-400">Overview of your recent payment activity</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="glass-card p-6 border-t-2 border-t-brand-500">
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-brand-500/10 rounded-lg text-brand-400">
              <CreditCard className="w-6 h-6" />
            </div>
          </div>
          <h3 className="text-gray-400 text-sm font-medium">Total Volume</h3>
          <div className="text-3xl font-bold text-white mt-1">{formatCurrency(totalAmount)}</div>
        </div>

        <div className="glass-card p-6">
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400">
              <ArrowUpRight className="w-6 h-6" />
            </div>
          </div>
          <h3 className="text-gray-400 text-sm font-medium">Approved</h3>
          <div className="text-3xl font-bold text-white mt-1">{approvedCount}</div>
        </div>

        <div className="glass-card p-6">
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-red-500/10 rounded-lg text-red-400">
              <ArrowDownRight className="w-6 h-6" />
            </div>
          </div>
          <h3 className="text-gray-400 text-sm font-medium">Declined</h3>
          <div className="text-3xl font-bold text-white mt-1">{declinedCount}</div>
        </div>

        <div className="glass-card p-6">
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-amber-500/10 rounded-lg text-amber-400">
              <Clock className="w-6 h-6" />
            </div>
          </div>
          <h3 className="text-gray-400 text-sm font-medium">In Review</h3>
          <div className="text-3xl font-bold text-white mt-1">{pendingCount}</div>
        </div>
      </div>

      {/* Transactions Table */}
      <div className="glass-card overflow-hidden">
        <div className="p-6 border-b border-white/5 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-white">Recent Transactions</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-dark-800/50">
                <th className="px-6 py-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">Transaction ID</th>
                <th className="px-6 py-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">Date</th>
                <th className="px-6 py-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">Amount</th>
                <th className="px-6 py-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {transactions.map((tx) => (
                <tr key={tx.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-6 py-4">
                    <span className="text-sm text-gray-300 font-mono">{tx.id.split('-')[0]}...</span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-sm text-gray-400">
                      {format(new Date(tx.submitted_at), 'MMM d, yyyy HH:mm')}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-sm font-medium text-white">{formatCurrency(tx.amount)}</span>
                  </td>
                  <td className="px-6 py-4">
                    {getStatusBadge(tx.status)}
                  </td>
                </tr>
              ))}
              {transactions.length === 0 && (
                <tr>
                  <td colSpan="4" className="px-6 py-12 text-center text-gray-500">
                    No transactions found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
