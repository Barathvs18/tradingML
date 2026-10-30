import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { NavLink, Navigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Activity, ArrowUpRight, BarChart3, BrainCircuit, History, Loader2, SlidersHorizontal, Upload, Wallet, ChartNoAxesCombined, X } from 'lucide-react';
import { dateLabel, errorMessage, researchApi } from '../lib/research';
import type { Direction, Stock } from '../lib/research';
import { useAuthStore } from '../store/auth';

export function StockSelect({ stocks, symbol, onChange, disabled = false }: { stocks: Stock[]; symbol: string; onChange: (value: string) => void; disabled?: boolean }) {
  return <label className="block min-w-0"><span className="research-label">NSE stock</span><select aria-label="NSE stock" className="research-input mt-2 w-full" value={symbol} onChange={event => onChange(event.target.value)} disabled={!stocks.length || disabled}>
    {!stocks.length && <option value="">No datasets yet</option>}
    {stocks.map(stock => <option key={stock.symbol} value={stock.symbol}>{stock.symbol} · {stock.name}</option>)}
  </select></label>;
}

export function DirectionBadge({ value }: { value: Direction }) {
  const colors = { UP: 'bg-emerald-400/10 text-emerald-300 border-emerald-400/20', DOWN: 'bg-rose-400/10 text-rose-300 border-rose-400/20', SIDEWAYS: 'bg-amber-400/10 text-amber-200 border-amber-400/20' };
  return <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${colors[value]}`}>{value === 'UP' ? '↗ Up' : value === 'DOWN' ? '↘ Down' : '→ Sideways'}</span>;
}

export function ResearchError({ error }: { error: unknown }) {
  return error ? <div role="alert" className="rounded-xl border border-rose-400/20 bg-rose-400/5 p-4 text-sm text-rose-200">{errorMessage(error)}</div> : null;
}

function ImportData() {
  const [open, setOpen] = useState(false);
  const [symbol, setSymbol] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [success, setSuccess] = useState('');
  const client = useQueryClient();
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file || !symbol.trim()) return;
    setBusy(true); setError(null); setSuccess('');
    try {
      const { data } = await researchApi.post<Stock>('/app/analysis/import', file, { params: { symbol: symbol.trim().toUpperCase() }, headers: { 'Content-Type': 'text/csv' } });
      await client.invalidateQueries({ queryKey: ['research-stocks'] });
      await client.invalidateQueries({ queryKey: ['research-dates'] });
      await client.invalidateQueries({ queryKey: ['research-performance'] });
      setSuccess(`${data.symbol} is ready: ${data.rows.toLocaleString()} sessions, through ${dateLabel(data.end)}.`);
    } catch (problem) { setError(problem); }
    finally { setBusy(false); }
  };
  return <>
    <button className="research-button-secondary" onClick={() => setOpen(!open)}><Upload size={15} /> Import CSV</button>
    {open && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" role="dialog" aria-modal="true" aria-labelledby="import-title">
      <form onSubmit={submit} className="research-panel w-full max-w-lg space-y-5 bg-[#11141d] p-6">
        <div className="flex items-center justify-between"><h2 id="import-title" className="text-lg font-semibold">Add an Indian stock</h2><button type="button" aria-label="Close import" onClick={() => setOpen(false)} disabled={busy}><X size={20} /></button></div>
        <p className="text-sm leading-6 text-slate-400">Upload daily prices with columns <span className="text-slate-200">date, open, high, low, close, volume</span>. Use YYYY-MM-DD dates and at least 300 trading sessions. Prices should use a consistent corporate-action adjustment.</p>
        <label className="block"><span className="research-label">Stock symbol</span><input className="research-input mt-2 w-full" placeholder="HDFCBANK" required maxLength={20} value={symbol} onChange={event => setSymbol(event.target.value.toUpperCase())} /></label>
        <label className="block"><span className="research-label">Daily CSV · maximum 4 MB</span><input className="research-input mt-2 w-full text-sm" type="file" accept=".csv,text/csv" required onChange={event => { setFile(event.target.files?.[0] || null); setError(null); setSuccess(''); }} /></label>
        <ResearchError error={error} />
        {success && <p role="status" className="text-sm text-emerald-300">{success}</p>}
        <button className="research-button w-full" type="submit" disabled={busy || !file || !symbol}>{busy ? <><Loader2 size={16} className="animate-spin" /> Training and evaluating…</> : 'Import and train model'}</button>
      </form>
    </div>}
  </>;
}

export default function ResearchShell({ children }: { children: ReactNode }) {
  const authenticated = useAuthStore(state => state.isAuthenticated);
  const configuration = useQuery({ queryKey: ['research-config'], queryFn: async () => (await researchApi.get<{ mode: string; authentication_required: boolean }>('/app/analysis/config')).data, staleTime: Infinity });
  useEffect(() => { document.title = 'Indian Market Lab · AlgoPredict'; }, []);
  if (configuration.isPending) return <div className="grid min-h-[50vh] place-items-center"><Loader2 className="animate-spin text-indigo-300" aria-label="Loading workspace" /></div>;
  if (configuration.isError) return <div className="mx-auto max-w-3xl space-y-4 p-8"><ResearchError error={configuration.error} /><button className="research-button" onClick={() => configuration.refetch()}>Retry connection</button></div>;
  if (configuration.data.authentication_required && !authenticated) return <Navigate to="/login" replace />;
  return <div className="research-workspace mx-auto w-full max-w-[1400px] px-1 py-5 sm:px-5">
    <header className="mb-7 flex flex-wrap items-center justify-between gap-5">
      <div><div className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[.2em] text-indigo-300"><span className="h-1.5 w-1.5 rounded-full bg-indigo-300" /> Indian market lab <span className="tracking-normal text-slate-500">/ Research & intraday signals</span></div><h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">A little context. A clearer view.</h1><p className="mt-3 text-sm text-slate-400">Explore stock history and calculate indicator signals from available candles.</p></div>
      <ImportData />
    </header>
    <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-white/10">
      <nav aria-label="Research workspace" className="flex gap-5 sm:gap-8">{[{ to: '/analyze', icon: BrainCircuit, name: 'Analyze' }, { to: '/intraday', icon: Activity, name: 'Intraday' }, { to: '/strategies', icon: SlidersHorizontal, name: 'Strategies' }, { to: '/portfolio', icon: Wallet, name: 'Paper portfolio' }, { to: '/compare', icon: ChartNoAxesCombined, name: 'Algo comparison' }, { to: '/history', icon: History, name: 'History' }, { to: '/performance', icon: BarChart3, name: 'Model performance' }].map(({ to, icon: Icon, name }) => <NavLink key={to} to={to} className={({ isActive }) => `flex items-center gap-2 border-b-2 py-4 text-sm transition ${isActive ? 'border-indigo-300 text-white' : 'border-transparent text-slate-400 hover:text-white'}`}><Icon size={16} /><span>{name}</span></NavLink>)}</nav>
      <span className="pb-2 text-xs text-slate-500">{configuration.data.mode === 'local' ? 'Local workspace · no account needed' : 'Your research workspace'}</span>
    </div>
    {children}
    <footer className="mt-8 flex flex-wrap justify-between gap-3 border-t border-white/8 pt-5 text-xs leading-5 text-slate-500"><span>Research and paper trading only · No broker orders are placed</span><span className="flex items-center gap-1">Signals are estimates, not guaranteed outcomes. <ArrowUpRight size={12} /></span></footer>
  </div>;
}
