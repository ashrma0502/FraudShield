import React, { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { ShieldAlert, CheckCircle2, XCircle, AlertTriangle, ChevronRight, Activity } from 'lucide-react';
import api from '../api';
import { formatCurrency, cn } from '../utils';

export default function AnalystQueue() {
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTx, setSelectedTx] = useState(null);
  const [processingId, setProcessingId] = useState(null);

  useEffect(() => {
    fetchQueue();
  }, []);

  const fetchQueue = async () => {
    try {
      setLoading(true);
      const response = await api.get('/transactions/review-queue/');
      setQueue(response.data.results || []);
    } catch (error) {
      console.error("Failed to fetch review queue", error);
    } finally {
      setLoading(false);
    }
  };

  const handleDecision = async (id, decision) => {
    setProcessingId(id);
    try {
      await api.post('/transactions/decide/', {
        transaction: id,
        decision: decision
      });
      // Remove from list
      setQueue(q => q.filter(tx => tx.id !== id));
      if (selectedTx?.id === id) setSelectedTx(null);
    } catch (error) {
      console.error("Failed to submit decision", error);
      alert("Error submitting decision");
    } finally {
      setProcessingId(null);
    }
  };

  const getRiskColor = (score) => {
    if (score >= 0.8) return 'text-red-400 bg-red-400/10 border-red-400/20';
    if (score >= 0.5) return 'text-orange-400 bg-orange-400/10 border-orange-400/20';
    return 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20';
  };

  if (loading && queue.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="w-12 h-12 border-4 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in flex h-[calc(100vh-8rem)] gap-6">
      {/* Queue List */}
      <div className={cn(
        "glass-card flex flex-col overflow-hidden transition-all duration-300",
        selectedTx ? "w-1/3" : "w-full"
      )}>
        <div className="p-6 border-b border-white/5 bg-dark-800/80 backdrop-blur-xl flex justify-between items-center z-10 relative">
          <div>
            <h2 className="text-xl font-display font-bold text-white flex items-center">
              <ShieldAlert className="w-5 h-5 text-brand-400 mr-2" />
              Review Queue
            </h2>
            <p className="text-sm text-gray-400 mt-1">{queue.length} items pending manual review</p>
          </div>
          <button onClick={fetchQueue} className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-300 transition-colors">
            <Activity className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {queue.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-gray-500">
              <CheckCircle2 className="w-12 h-12 mb-4 text-emerald-500/50" />
              <p>Queue is empty! Great job.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {queue.map(tx => (
                <button
                  key={tx.id}
                  onClick={() => setSelectedTx(tx)}
                  className={cn(
                    "w-full text-left p-4 rounded-xl border transition-all",
                    selectedTx?.id === tx.id 
                      ? "bg-brand-500/10 border-brand-500/50" 
                      : "bg-dark-800/30 border-white/5 hover:bg-white/5 hover:border-white/10"
                  )}
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className="font-medium text-white">{formatCurrency(tx.amount)}</span>
                    <span className={cn("px-2 py-0.5 rounded text-xs font-bold border", getRiskColor(tx.fraud_score))}>
                      {(tx.fraud_score * 100).toFixed(0)}% RISK
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-sm text-gray-400">
                    <span className="truncate pr-4">{tx.merchant_name || 'Unknown Merchant'}</span>
                    <span>{format(new Date(tx.submitted_at), 'HH:mm')}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Details Panel */}
      {selectedTx && (
        <div className="w-2/3 glass-card flex flex-col overflow-hidden animate-slide-up">
          <div className="p-6 border-b border-white/5 bg-dark-800/80 backdrop-blur-xl">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-display font-bold text-white">Transaction Details</h2>
              <button 
                onClick={() => setSelectedTx(null)}
                className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-white/10"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>
          </div>
          
          <div className="flex-1 overflow-y-auto p-6 space-y-8">
            {/* Top Stats */}
            <div className="flex items-center gap-6 p-6 rounded-2xl bg-dark-900/50 border border-white/5">
              <div>
                <p className="text-sm text-gray-400 mb-1">Amount</p>
                <p className="text-4xl font-bold text-white">{formatCurrency(selectedTx.amount)}</p>
              </div>
              <div className="h-12 w-px bg-white/10"></div>
              <div>
                <p className="text-sm text-gray-400 mb-1">Fraud Score</p>
                <p className={cn("text-3xl font-bold", getRiskColor(selectedTx.fraud_score).split(' ')[0])}>
                  {(selectedTx.fraud_score * 100).toFixed(1)}%
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Entities</h3>
                <div className="p-4 rounded-xl bg-dark-800/30 border border-white/5">
                  <div className="mb-3">
                    <p className="text-xs text-gray-500 mb-1">Merchant</p>
                    <p className="text-sm text-white font-medium">{selectedTx.merchant_name || 'N/A'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Customer</p>
                    <p className="text-sm text-white font-medium">{selectedTx.customer_email || 'N/A'}</p>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Metadata</h3>
                <div className="p-4 rounded-xl bg-dark-800/30 border border-white/5">
                  <div className="mb-3">
                    <p className="text-xs text-gray-500 mb-1">Time</p>
                    <p className="text-sm text-white">{format(new Date(selectedTx.submitted_at), 'PPP pp')}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1">ID</p>
                    <p className="text-xs text-gray-400 font-mono truncate">{selectedTx.id}</p>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Features (if any) */}
            {selectedTx.feature_snapshot && (
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Model Features</h3>
                <div className="p-4 rounded-xl bg-dark-800/30 border border-white/5 overflow-x-auto">
                  <pre className="text-xs text-gray-300 font-mono">
                    {JSON.stringify(selectedTx.feature_snapshot, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>

          <div className="p-6 border-t border-white/5 bg-dark-800/80 backdrop-blur-xl flex gap-4">
            <button
              onClick={() => handleDecision(selectedTx.id, 'declined')}
              disabled={processingId === selectedTx.id}
              className="flex-1 py-4 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 rounded-xl font-bold transition-all flex justify-center items-center"
            >
              <XCircle className="w-5 h-5 mr-2" />
              Decline Fraud
            </button>
            <button
              onClick={() => handleDecision(selectedTx.id, 'approved')}
              disabled={processingId === selectedTx.id}
              className="flex-1 py-4 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-xl font-bold transition-all flex justify-center items-center"
            >
              <CheckCircle2 className="w-5 h-5 mr-2" />
              Approve Safe
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
