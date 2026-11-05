import { useState, useEffect } from 'react';
import {
  CreditCard,
  Shield,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Zap,
  Cpu,
  ArrowRight,
  RefreshCw,
  Sliders,
  DollarSign,
  Building,
} from 'lucide-react';
import api from '../api';
import { formatCurrency, cn } from '../utils';

export default function CustomerSimulate() {
  const [merchants, setMerchants] = useState([]);
  const [thresholds, setThresholds] = useState({ flag_threshold: 0.50, auto_block_threshold: 0.90 });
  const [presets, setPresets] = useState([]);
  const [loadingMeta, setLoadingMeta] = useState(true);

  // Form State
  const [merchant, setMerchant] = useState('');
  const [amount, setAmount] = useState('49.99');
  const [card4, setCard4] = useState('visa');
  const [card6, setCard6] = useState('credit');
  const [productCd, setProductCd] = useState('W');
  const [pEmail, setPEmail] = useState('gmail.com');
  const [rEmail, setREmail] = useState('gmail.com');

  // Execution & Result State
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);

  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const response = await api.get('/transactions/simulate/');
        if (response.data) {
          if (response.data.merchants && response.data.merchants.length > 0) {
            setMerchants(response.data.merchants);
            setMerchant(response.data.merchants[0].id);
          }
          if (response.data.thresholds) {
            setThresholds(response.data.thresholds);
          }
          if (response.data.presets) {
            setPresets(response.data.presets);
          }
        }
      } catch (err) {
        console.warn('Using default simulation presets:', err);
      } finally {
        setLoadingMeta(false);
      }
    };

    fetchMetadata();
  }, []);

  const applyPreset = (preset) => {
    if (preset.amount !== undefined) setAmount(String(preset.amount));
    if (preset.card4) setCard4(preset.card4);
    if (preset.card6) setCard6(preset.card6);
    if (preset.product_cd) setProductCd(preset.product_cd);
    if (preset.p_emaildomain) setPEmail(preset.p_emaildomain);
    if (preset.r_emaildomain) setREmail(preset.r_emaildomain);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      const payload = {
        amount: parseFloat(amount),
        merchant_id: merchant || undefined,
        card4,
        card6,
        product_cd: productCd,
        p_emaildomain: pEmail,
        r_emaildomain: rEmail,
      };

      const response = await api.post('/transactions/simulate/', payload);
      setResult(response.data);
      setHistory((prev) => [response.data, ...prev.slice(0, 4)]);
    } catch (err) {
      const msg = err.response?.data?.amount?.[0] || err.response?.data?.detail || 'Simulation request failed. Check inputs.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const getOutcomeTheme = (outcome) => {
    switch (outcome) {
      case 'approved':
        return {
          title: 'Transaction Approved',
          description: 'Transaction cleared both rule pre-filters and ML risk evaluation.',
          badgeBg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
          borderAccent: 'border-t-emerald-500',
          Icon: CheckCircle2,
          scoreColor: 'text-emerald-400',
        };
      case 'flagged_for_review':
        return {
          title: 'Flagged for Manual Review',
          description: 'Risk score elevated above review threshold. Queued for fraud analyst investigation.',
          badgeBg: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
          borderAccent: 'border-t-amber-500',
          Icon: AlertTriangle,
          scoreColor: 'text-amber-400',
        };
      case 'declined':
      default:
        return {
          title: 'Transaction Declined',
          description: 'Severe fraud risk detected (rule trigger or score exceeding auto-block limit).',
          badgeBg: 'bg-red-500/10 text-red-400 border-red-500/30',
          borderAccent: 'border-t-red-500',
          Icon: XCircle,
          scoreColor: 'text-red-400',
        };
    }
  };

  return (
    <div className="animate-fade-in space-y-8 max-w-6xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center space-x-3 mb-2">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20 text-brand-400">
            <CreditCard className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-3xl font-display font-bold text-white tracking-wide">
              Payment Gateway Simulator
            </h1>
            <p className="text-gray-400 text-sm">
              Submit simulated transactions through the two-layer fraud detection pipeline (Rules + ML Model).
            </p>
          </div>
        </div>
      </div>

      {/* Quick Presets */}
      {loadingMeta ? (
        <div className="glass-card p-4 text-xs text-gray-500 animate-pulse">Loading gateway presets …</div>
      ) : presets.length > 0 ? (
        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center">
              <Sliders className="w-4 h-4 mr-1.5 text-brand-400" />
              Quick Test Presets
            </span>
            <span className="text-xs text-gray-500">Click a preset to populate test parameters</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {presets.map((p, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => applyPreset(p)}
                className="text-left p-3.5 rounded-xl bg-dark-900/60 hover:bg-dark-900 border border-white/5 hover:border-brand-500/40 transition-all group"
              >
                <div className="font-medium text-sm text-white group-hover:text-brand-300 transition-colors">
                  {p.name}
                </div>
                <div className="text-xs text-gray-400 mt-1 flex items-center justify-between">
                  <span>${parseFloat(p.amount).toFixed(2)} • {p.card4.toUpperCase()}</span>
                  <span className="text-brand-400/80 group-hover:translate-x-0.5 transition-transform">Use →</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Form Column */}
        <div className="lg:col-span-7">
          <form onSubmit={handleSubmit} className="glass-card p-6 md:p-8 space-y-6">
            <h2 className="text-lg font-display font-bold text-white flex items-center border-b border-white/5 pb-4">
              <Building className="w-5 h-5 mr-2 text-brand-400" />
              Transaction Details
            </h2>

            {error && (
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center">
                <AlertTriangle className="w-4 h-4 mr-2 flex-shrink-0" />
                {error}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              {/* Merchant Dropdown */}
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium uppercase tracking-wider text-gray-300 mb-2">
                  Merchant
                </label>
                <select
                  value={merchant}
                  onChange={(e) => setMerchant(e.target.value)}
                  className="w-full px-4 py-3 glass-input text-white bg-dark-900/80"
                >
                  {merchants.length > 0 ? (
                    merchants.map((m) => (
                      <option key={m.id} value={m.id} className="bg-dark-800 text-white">
                        {m.business_name}
                      </option>
                    ))
                  ) : (
                    <option value="" className="bg-dark-800 text-white">
                      Acme Electronics (Default Merchant)
                    </option>
                  )}
                </select>
              </div>

              {/* Amount */}
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium uppercase tracking-wider text-gray-300 mb-2">
                  Amount (USD $)
                </label>
                <div className="relative">
                  <DollarSign className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="w-full pl-11 pr-4 py-3 glass-input text-white text-lg font-semibold"
                    placeholder="0.00"
                  />
                </div>
                <p className="text-xs text-gray-500 mt-1.5">
                  Amounts &ge; $5,000.00 trigger the high-amount rule pre-filter.
                </p>
              </div>

              {/* Card Brand */}
              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-gray-300 mb-2">
                  Card Brand (card4)
                </label>
                <select
                  value={card4}
                  onChange={(e) => setCard4(e.target.value)}
                  className="w-full px-4 py-3 glass-input text-white bg-dark-900/80"
                >
                  <option value="visa" className="bg-dark-800">Visa</option>
                  <option value="mastercard" className="bg-dark-800">Mastercard</option>
                  <option value="discover" className="bg-dark-800">Discover</option>
                  <option value="american express" className="bg-dark-800">American Express</option>
                </select>
              </div>

              {/* Card Type */}
              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-gray-300 mb-2">
                  Card Type (card6)
                </label>
                <select
                  value={card6}
                  onChange={(e) => setCard6(e.target.value)}
                  className="w-full px-4 py-3 glass-input text-white bg-dark-900/80"
                >
                  <option value="credit" className="bg-dark-800">Credit</option>
                  <option value="debit" className="bg-dark-800">Debit</option>
                </select>
              </div>

              {/* Product Code */}
              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-gray-300 mb-2">
                  Product Category (ProductCD)
                </label>
                <select
                  value={productCd}
                  onChange={(e) => setProductCd(e.target.value)}
                  className="w-full px-4 py-3 glass-input text-white bg-dark-900/80"
                >
                  <option value="W" className="bg-dark-800">W (Merchandise / Retail)</option>
                  <option value="C" className="bg-dark-800">C (Payment / Transfer)</option>
                  <option value="R" className="bg-dark-800">R (Services)</option>
                  <option value="H" className="bg-dark-800">H (Digital Goods)</option>
                  <option value="S" className="bg-dark-800">S (Specialty / Storage)</option>
                </select>
              </div>

              {/* Email Domain */}
              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-gray-300 mb-2">
                  Purchaser Email Domain
                </label>
                <select
                  value={pEmail}
                  onChange={(e) => setPEmail(e.target.value)}
                  className="w-full px-4 py-3 glass-input text-white bg-dark-900/80"
                >
                  <option value="gmail.com" className="bg-dark-800">gmail.com</option>
                  <option value="yahoo.com" className="bg-dark-800">yahoo.com</option>
                  <option value="hotmail.com" className="bg-dark-800">hotmail.com</option>
                  <option value="protonmail.com" className="bg-dark-800">protonmail.com (High-Risk)</option>
                  <option value="anonymous.com" className="bg-dark-800">anonymous.com (High-Risk)</option>
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-3.5 px-6 bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-400 hover:to-brand-500 text-white rounded-xl font-medium shadow-lg shadow-brand-500/25 transition-all flex items-center justify-center space-x-2 group disabled:opacity-60"
            >
              {submitting ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  <span>Screening Transaction …</span>
                </>
              ) : (
                <>
                  <span>Submit Payment for Screening</span>
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>
        </div>

        {/* Live Result Column */}
        <div className="lg:col-span-5 space-y-6">
          {result ? (
            (() => {
              const theme = getOutcomeTheme(result.outcome);
              const OutcomeIcon = theme.Icon;
              const scorePercent = (result.fraud_score * 100).toFixed(1);

              return (
                <div className={cn('glass-card p-6 border-t-4 transition-all animate-slide-up', theme.borderAccent)}>
                  <div className="flex items-start justify-between">
                    <div>
                      <span className={cn('inline-flex items-center px-3 py-1 rounded-full text-xs font-bold border uppercase tracking-wider', theme.badgeBg)}>
                        <OutcomeIcon className="w-3.5 h-3.5 mr-1.5" />
                        {result.outcome.replace('_', ' ')}
                      </span>
                      <h3 className="text-xl font-display font-bold text-white mt-3">{theme.title}</h3>
                      <p className="text-xs text-gray-400 mt-1">{theme.description}</p>
                    </div>
                  </div>

                  {/* Score Gauge */}
                  <div className="mt-6 p-4 rounded-xl bg-dark-900/70 border border-white/5 space-y-3">
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs uppercase tracking-wider text-gray-400 font-medium">Combined Fraud Score</span>
                      <span className={cn('text-2xl font-bold font-mono', theme.scoreColor)}>
                        {result.fraud_score.toFixed(4)}
                        <span className="text-xs text-gray-400 font-normal ml-1">({scorePercent}%)</span>
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full bg-dark-700 h-2.5 rounded-full overflow-hidden relative">
                      <div
                        className={cn(
                          'h-full transition-all duration-500',
                          result.fraud_score >= thresholds.auto_block_threshold
                            ? 'bg-red-500'
                            : result.fraud_score >= thresholds.flag_threshold
                            ? 'bg-amber-500'
                            : 'bg-emerald-500'
                        )}
                        style={{ width: `${Math.min(100, Math.max(5, result.fraud_score * 100))}%` }}
                      />
                    </div>

                    <div className="flex justify-between text-[11px] text-gray-500">
                      <span>0.0 (Clean)</span>
                      <span>Review: &ge; {thresholds.flag_threshold.toFixed(2)}</span>
                      <span>Block: &ge; {thresholds.auto_block_threshold.toFixed(2)}</span>
                    </div>
                  </div>

                  {/* Layer Attribution */}
                  <div className="mt-6 space-y-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                      Contributing Screening Layers
                    </div>

                    <div className="grid grid-cols-2 gap-3 text-xs">
                      {/* Rules Layer */}
                      <div className="p-3 rounded-xl bg-dark-900/50 border border-white/5">
                        <div className="flex items-center text-gray-300 font-medium mb-1">
                          <Zap className="w-3.5 h-3.5 mr-1.5 text-amber-400" />
                          Rule Engine
                        </div>
                        <div className="mt-1">
                          {result.rule_flagged ? (
                            <span className="text-red-400 font-semibold">Flagged ({result.triggered_rules.join(', ')})</span>
                          ) : (
                            <span className="text-emerald-400">Passed (Clean)</span>
                          )}
                        </div>
                      </div>

                      {/* ML Model Layer */}
                      <div className="p-3 rounded-xl bg-dark-900/50 border border-white/5">
                        <div className="flex items-center text-gray-300 font-medium mb-1">
                          <Cpu className="w-3.5 h-3.5 mr-1.5 text-brand-400" />
                          ML Model
                        </div>
                        <div className="mt-1">
                          {result.model_flagged ? (
                            <span className="text-amber-400 font-semibold">Flagged (Risk Score)</span>
                          ) : (
                            <span className="text-emerald-400">Low Probability</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Stored Transaction Metadata */}
                  <div className="mt-6 pt-4 border-t border-white/5 text-xs text-gray-400 space-y-1">
                    <div className="flex justify-between">
                      <span>Stored Transaction ID:</span>
                      <span className="font-mono text-gray-300 truncate max-w-[200px]">{result.transaction_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Merchant:</span>
                      <span className="text-gray-300">{result.merchant}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Amount:</span>
                      <span className="text-gray-300 font-medium">{formatCurrency(result.amount)}</span>
                    </div>
                  </div>
                </div>
              );
            })()
          ) : (
            <div className="glass-card p-8 text-center text-gray-500 border border-dashed border-white/10 space-y-3">
              <Shield className="w-12 h-12 mx-auto text-gray-600 animate-pulse-slow" />
              <h3 className="text-base font-semibold text-gray-300">Awaiting Submission</h3>
              <p className="text-xs text-gray-500 max-w-xs mx-auto">
                Fill in the payment parameters or pick a preset, then submit to view real-time fraud scoring.
              </p>
            </div>
          )}

          {/* Session History */}
          {history.length > 0 && (
            <div className="glass-card p-5 space-y-3">
              <div className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center justify-between">
                <span>Recent Replay History</span>
                <span className="text-[10px] text-gray-500">{history.length} stored</span>
              </div>
              <div className="space-y-2">
                {history.map((item, idx) => (
                  <div key={idx} className="p-2.5 rounded-lg bg-dark-900/50 border border-white/5 flex items-center justify-between text-xs">
                    <div>
                      <span className="font-medium text-white">{formatCurrency(item.amount)}</span>
                      <span className="text-gray-500 ml-2">Score: {item.fraud_score.toFixed(3)}</span>
                    </div>
                    <span
                      className={cn(
                        'px-2 py-0.5 rounded text-[10px] font-bold uppercase',
                        item.outcome === 'approved' ? 'bg-emerald-500/10 text-emerald-400' :
                        item.outcome === 'declined' ? 'bg-red-500/10 text-red-400' :
                        'bg-amber-500/10 text-amber-400'
                      )}
                    >
                      {item.outcome.replace('_', ' ')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

