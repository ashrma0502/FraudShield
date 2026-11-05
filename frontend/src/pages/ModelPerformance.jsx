import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import {
  TrendingUp,
  Target,
  Shield,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Users,
  ArrowRight,
  Filter,
} from 'lucide-react';
import api from '../api';
import { cn } from '../utils';

export default function ModelPerformance() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [days, setDays] = useState('30');
  const [filterMode, setFilterMode] = useState('all');
  const [trendType, setTrendType] = useState('cumulative'); // 'cumulative' | 'daily'

  const handleRefresh = () => {
    setLoading(true);
    api.get('/analytics/model-performance/', {
      params: {
        days,
        filter: filterMode,
      },
    })
      .then((res) => setData(res.data))
      .catch((err) => setError(err.response?.data?.detail || 'Failed to load model performance metrics.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let isMounted = true;
    api.get('/analytics/model-performance/', {
      params: {
        days,
        filter: filterMode,
      },
    })
      .then((res) => {
        if (isMounted) setData(res.data);
      })
      .catch((err) => {
        if (isMounted) setError(err.response?.data?.detail || 'Failed to load model performance metrics.');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [days, filterMode]);

  const metrics = data?.metrics || { precision: 0, recall: 0, f1_score: 0, accuracy: 0 };
  const cm = data?.confusion_matrix || { tp: 0, fp: 0, tn: 0, fn: 0 };
  const trendData = data?.trend || [];

  return (
    <div className="animate-fade-in space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20 text-brand-400">
              <TrendingUp className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-3xl font-display font-bold text-white tracking-wide">
                Model Performance Analytics
              </h1>
              <p className="text-gray-400 text-sm">
                Real-time Precision, Recall, F1, and Confusion Matrix evaluated against labeled transaction outcomes.
              </p>
            </div>
          </div>
        </div>

        {/* Controls: Time Range & Filter */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-1.5 p-1 rounded-xl bg-dark-800/80 border border-white/5 text-xs">
            <Filter className="w-3.5 h-3.5 ml-2 text-gray-400" />
            <select
              value={filterMode}
              onChange={(e) => setFilterMode(e.target.value)}
              className="bg-transparent text-white px-2 py-1 focus:outline-none cursor-pointer"
            >
              <option value="all" className="bg-dark-800">All Labeled Data</option>
              <option value="analyst_only" className="bg-dark-800">Analyst Labeled Only</option>
            </select>
          </div>

          <div className="flex items-center p-1 rounded-xl bg-dark-800/80 border border-white/5 text-xs">
            {['7', '30', '90', 'all'].map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDays(d)}
                className={cn(
                  'px-3 py-1 rounded-lg transition-all',
                  days === d
                    ? 'bg-brand-500/20 text-brand-400 font-semibold shadow-sm'
                    : 'text-gray-400 hover:text-white'
                )}
              >
                {d === 'all' ? 'All' : `${d}d`}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={handleRefresh}
            disabled={loading}
            className="p-2 rounded-xl bg-dark-800 hover:bg-dark-700 border border-white/5 text-gray-400 hover:text-white transition-colors"
            title="Refresh Analytics"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center">
          <AlertTriangle className="w-4 h-4 mr-2" />
          {error}
        </div>
      )}

      {/* Pending Reviews Notice */}
      {data?.pending_review_count > 0 && (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-between text-xs text-amber-300">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <span>
              <strong>{data.pending_review_count} transactions</strong> are currently pending manual review. As analysts decide them, ground-truth metrics update automatically.
            </span>
          </div>
          <Link
            to="/analyst"
            className="inline-flex items-center font-medium text-amber-400 hover:text-amber-300 underline ml-4 flex-shrink-0"
          >
            Open Review Queue <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </Link>
        </div>
      )}

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* F1 Score */}
        <div className="glass-card p-6 border-t-2 border-t-brand-500">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs uppercase tracking-wider text-gray-400 font-semibold">F1-Score</span>
            <Target className="w-4 h-4 text-brand-400" />
          </div>
          <div className="text-3xl font-display font-bold text-white">
            {(metrics.f1_score * 100).toFixed(1)}%
          </div>
          <p className="text-xs text-gray-400 mt-2">
            Harmonic balance: {metrics.f1_score.toFixed(4)}
          </p>
        </div>

        {/* Precision */}
        <div className="glass-card p-6 border-t-2 border-t-emerald-500">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs uppercase tracking-wider text-gray-400 font-semibold">Precision</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-display font-bold text-white">
            {(metrics.precision * 100).toFixed(1)}%
          </div>
          <p className="text-xs text-gray-400 mt-2">
            True fraud vs all flags: {cm.tp} / {cm.tp + cm.fp}
          </p>
        </div>

        {/* Recall */}
        <div className="glass-card p-6 border-t-2 border-t-amber-500">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs uppercase tracking-wider text-gray-400 font-semibold">Recall (Sensitivity)</span>
            <Shield className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-3xl font-display font-bold text-white">
            {(metrics.recall * 100).toFixed(1)}%
          </div>
          <p className="text-xs text-gray-400 mt-2">
            Caught frauds vs actual: {cm.tp} / {cm.tp + cm.fn}
          </p>
        </div>

        {/* Labeled Samples */}
        <div className="glass-card p-6 border-t-2 border-t-indigo-500">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs uppercase tracking-wider text-gray-400 font-semibold">Labeled Outcomes</span>
            <Users className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-3xl font-display font-bold text-white">
            {data?.total_labeled || 0}
          </div>
          <p className="text-xs text-gray-400 mt-2">
            {data?.analyst_labeled_count || 0} analyst-verified decisions
          </p>
        </div>
      </div>

      {/* Middle Section: Confusion Matrix & Trajectory Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Confusion Matrix Visual Grid */}
        <div className="lg:col-span-5 glass-card p-6 space-y-5">
          <div>
            <h2 className="text-lg font-display font-bold text-white">Confusion Matrix</h2>
            <p className="text-xs text-gray-400 mt-1">
              Live predicted screening flags vs verified transaction outcomes.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {/* True Positive */}
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
              <div className="text-xs text-emerald-400 font-semibold uppercase tracking-wider">
                True Positive (TP)
              </div>
              <div className="text-3xl font-mono font-bold text-emerald-300 mt-2">
                {cm.tp}
              </div>
              <div className="text-[11px] text-gray-400 mt-1">
                Predicted Fraud • Actual Fraud
              </div>
            </div>

            {/* False Positive */}
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
              <div className="text-xs text-amber-400 font-semibold uppercase tracking-wider">
                False Positive (FP)
              </div>
              <div className="text-3xl font-mono font-bold text-amber-300 mt-2">
                {cm.fp}
              </div>
              <div className="text-[11px] text-gray-400 mt-1">
                Predicted Fraud • Actual Clean (False Alarm)
              </div>
            </div>

            {/* False Negative */}
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30">
              <div className="text-xs text-red-400 font-semibold uppercase tracking-wider">
                False Negative (FN)
              </div>
              <div className="text-3xl font-mono font-bold text-red-300 mt-2">
                {cm.fn}
              </div>
              <div className="text-[11px] text-gray-400 mt-1">
                Predicted Clean • Actual Fraud (Miss)
              </div>
            </div>

            {/* True Negative */}
            <div className="p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/30">
              <div className="text-xs text-indigo-400 font-semibold uppercase tracking-wider">
                True Negative (TN)
              </div>
              <div className="text-3xl font-mono font-bold text-indigo-300 mt-2">
                {cm.tn}
              </div>
              <div className="text-[11px] text-gray-400 mt-1">
                Predicted Clean • Actual Clean
              </div>
            </div>
          </div>

          {/* Matrix Rates Summary */}
          <div className="p-4 rounded-xl bg-dark-900/60 border border-white/5 space-y-2 text-xs text-gray-400">
            <div className="flex justify-between">
              <span>Overall Accuracy:</span>
              <span className="font-mono text-white font-semibold">{(metrics.accuracy * 100).toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span>False Discovery Rate (FDR):</span>
              <span className="font-mono text-amber-400 font-semibold">
                {cm.tp + cm.fp > 0 ? ((cm.fp / (cm.tp + cm.fp)) * 100).toFixed(1) : '0.0'}%
              </span>
            </div>
            <div className="flex justify-between">
              <span>False Negative Rate (Miss Rate):</span>
              <span className="font-mono text-red-400 font-semibold">
                {cm.tp + cm.fn > 0 ? ((cm.fn / (cm.tp + cm.fn)) * 100).toFixed(1) : '0.0'}%
              </span>
            </div>
            <div className="flex justify-between pt-1 border-t border-white/5 text-[11px] text-gray-500">
              <span>Classification Threshold:</span>
              <span>&ge; {data?.threshold_used || 0.50}</span>
            </div>
          </div>
        </div>

        {/* Trended Over Time Recharts Chart */}
        <div className="lg:col-span-7 glass-card p-6 space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-display font-bold text-white">Performance Trend Over Time</h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Precision, Recall, and F1 progression as labeled transactions accumulate.
              </p>
            </div>

            <div className="flex items-center space-x-1 p-1 rounded-xl bg-dark-900/70 border border-white/5 text-xs">
              <button
                type="button"
                onClick={() => setTrendType('cumulative')}
                className={cn(
                  'px-2.5 py-1 rounded-lg transition-colors',
                  trendType === 'cumulative' ? 'bg-brand-500/20 text-brand-400 font-semibold' : 'text-gray-400 hover:text-white'
                )}
              >
                Cumulative Trend
              </button>
              <button
                type="button"
                onClick={() => setTrendType('daily')}
                className={cn(
                  'px-2.5 py-1 rounded-lg transition-colors',
                  trendType === 'daily' ? 'bg-brand-500/20 text-brand-400 font-semibold' : 'text-gray-400 hover:text-white'
                )}
              >
                Daily Point
              </button>
            </div>
          </div>

          {trendData.length > 0 ? (
            <div className="h-72 w-full pt-4">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData} margin={{ top: 5, right: 15, left: -15, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                  <XAxis
                    dataKey="date"
                    stroke="#9ca3af"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => v.slice(5)} // MM-DD
                  />
                  <YAxis
                    stroke="#9ca3af"
                    tick={{ fontSize: 11 }}
                    domain={[0, 1]}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#181b26',
                      borderColor: '#ffffff15',
                      borderRadius: '0.75rem',
                      color: '#fff',
                      fontSize: '12px',
                    }}
                    formatter={(val, name) => [`${(Number(val) * 100).toFixed(1)}%`, name]}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: '12px', paddingTop: '8px' }}
                  />
                  <Line
                    type="monotone"
                    dataKey={trendType === 'cumulative' ? 'cumulative_f1_score' : 'f1_score'}
                    name="F1-Score"
                    stroke="#818cf8"
                    strokeWidth={2.5}
                    dot={{ r: 3, fill: '#818cf8' }}
                    activeDot={{ r: 5 }}
                  />
                  <Line
                    type="monotone"
                    dataKey={trendType === 'cumulative' ? 'cumulative_precision' : 'precision'}
                    name="Precision"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={{ r: 2.5, fill: '#10b981' }}
                  />
                  <Line
                    type="monotone"
                    dataKey={trendType === 'cumulative' ? 'cumulative_recall' : 'recall'}
                    name="Recall"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={{ r: 2.5, fill: '#f59e0b' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-64 flex flex-col items-center justify-center text-gray-500 border border-dashed border-white/5 rounded-xl">
              <TrendingUp className="w-8 h-8 mb-2 text-gray-600" />
              <p className="text-xs">No time-series data available for selected period.</p>
            </div>
          )}

          {/* Daily Sample Volume Bar Chart */}
          {trendData.length > 0 && (
            <div className="pt-4 border-t border-white/5">
              <div className="text-xs text-gray-400 font-medium mb-3 flex items-center justify-between">
                <span>Daily Labeled Transaction Volume</span>
                <span className="text-[11px] text-gray-500">Green: TP | Amber: FP | Red: FN | Indigo: TN</span>
              </div>
              <div className="h-44 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={trendData} margin={{ top: 5, right: 15, left: -15, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
                    <XAxis
                      dataKey="date"
                      stroke="#6b7280"
                      tick={{ fontSize: 10 }}
                      tickFormatter={(v) => v.slice(5)}
                    />
                    <YAxis stroke="#6b7280" tick={{ fontSize: 10 }} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#181b26',
                        borderColor: '#ffffff15',
                        borderRadius: '0.75rem',
                        fontSize: '11px',
                      }}
                    />
                    <Bar dataKey="tp" name="True Positives" stackId="a" fill="#10b981" />
                    <Bar dataKey="fp" name="False Positives" stackId="a" fill="#f59e0b" />
                    <Bar dataKey="fn" name="False Negatives" stackId="a" fill="#ef4444" />
                    <Bar dataKey="tn" name="True Negatives" stackId="a" fill="#6366f1" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Model Version Breakdown Section: Based on Analyst-Reviewed Transactions Only */}
      <div className="glass-card p-6 space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/5 pb-4">
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-xl font-display font-bold text-white tracking-wide">
                Performance Breakdown by Model Version
              </h2>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/20">
                <Users className="w-3 h-3 mr-1" />
                Based on analyst-reviewed transactions only
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-1">
              Before and after comparative evaluation on live decisions verified by fraud analysts.
            </p>
          </div>
        </div>

        {/* Comparative Chart */}
        {data?.by_model_version && data.by_model_version.length > 0 ? (
          <div className="space-y-6">
            <div className="h-64 w-full pt-2">
              <div className="text-xs text-gray-400 font-medium mb-2">Model Version Comparison (Precision, Recall, F1)</div>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={data.by_model_version.map(v => ({
                    version: `v${v.model_version}`,
                    Precision: Number((v.metrics.precision * 100).toFixed(1)),
                    Recall: Number((v.metrics.recall * 100).toFixed(1)),
                    'F1-Score': Number((v.metrics.f1_score * 100).toFixed(1)),
                    reviewed: v.total_reviewed,
                  }))}
                  margin={{ top: 10, right: 20, left: -10, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
                  <XAxis dataKey="version" stroke="#9ca3af" tick={{ fontSize: 12 }} />
                  <YAxis stroke="#9ca3af" tick={{ fontSize: 11 }} domain={[0, 100]} unit="%" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#181b26',
                      borderColor: '#ffffff15',
                      borderRadius: '0.75rem',
                      fontSize: '12px',
                    }}
                    formatter={(val) => [`${val}%`]}
                  />
                  <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '6px' }} />
                  <Bar dataKey="Precision" fill="#10b981" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Recall" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="F1-Score" fill="#818cf8" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Version Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 pt-4 border-t border-white/5">
              {data.by_model_version.map((v) => (
                <div key={v.model_version} className="p-5 rounded-2xl bg-dark-900/60 border border-white/5 space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="font-display font-bold text-lg text-white">
                      Version {v.model_version}
                    </span>
                    <span className="text-xs px-2.5 py-1 rounded-full bg-white/5 text-gray-300 font-mono">
                      {v.total_reviewed} live reviews
                    </span>
                  </div>

                  {/* Metrics Row */}
                  <div className="grid grid-cols-3 gap-2 text-center py-2 bg-dark-800/40 rounded-xl border border-white/5">
                    <div>
                      <div className="text-[11px] text-gray-400">Precision</div>
                      <div className="text-base font-bold text-emerald-400 font-mono">
                        {(v.metrics.precision * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] text-gray-400">Recall</div>
                      <div className="text-base font-bold text-amber-400 font-mono">
                        {(v.metrics.recall * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] text-gray-400">F1-Score</div>
                      <div className="text-base font-bold text-indigo-400 font-mono">
                        {(v.metrics.f1_score * 100).toFixed(1)}%
                      </div>
                    </div>
                  </div>

                  {/* Confusion Matrix Mini Grid */}
                  <div className="space-y-1.5 pt-1">
                    <div className="text-[11px] text-gray-400 font-medium">Analyst Confusion Matrix:</div>
                    <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                      <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 flex justify-between">
                        <span>TP:</span>
                        <span className="font-bold">{v.confusion_matrix.tp}</span>
                      </div>
                      <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 flex justify-between">
                        <span>FP:</span>
                        <span className="font-bold">{v.confusion_matrix.fp}</span>
                      </div>
                      <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-300 flex justify-between">
                        <span>FN:</span>
                        <span className="font-bold">{v.confusion_matrix.fn}</span>
                      </div>
                      <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 flex justify-between">
                        <span>TN:</span>
                        <span className="font-bold">{v.confusion_matrix.tn}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="py-12 text-center text-gray-500">
            <Users className="w-8 h-8 mx-auto mb-2 text-gray-600" />
            <p className="text-xs">No analyst decisions recorded across model versions yet.</p>
          </div>
        )}
      </div>
    </div>
  );
}
