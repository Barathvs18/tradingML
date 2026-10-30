import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, Clock3, RefreshCw } from 'lucide-react';
import { api } from '../lib/api';
import ResearchShell, { ResearchError } from '../components/ResearchShell';

interface StockSearch { items: { symbol: string; name: string; exchange: string }[]; total: number }
interface AlgorithmGroup { category: string; algorithms: { key: string; name: string; lookback_minutes: number }[] }
interface IntradayResult {
  symbol: string; algorithm: string; interval: string; as_of: string; last_price: number;
  signal: { signal: string; confidence: number; reason: string; target_price?: number | null; stop_loss?: number | null };
  candle_count: number; data_age_seconds: number; data_status: string; data_source: string;
  is_live_feed: boolean; disclaimer: string;
}

function IntradayWorkspace() {
  const [symbol, setSymbol] = useState('');
  const [interval, setInterval] = useState('5m');
  const [algorithm, setAlgorithm] = useState('supertrend');
  const stocks = useQuery({ queryKey: ['intraday-stocks'], queryFn: async () => (await api.get<StockSearch>('/app/stocks?limit=100')).data });
  const algorithms = useQuery({ queryKey: ['intraday-algorithms'], queryFn: async () => (await api.get<AlgorithmGroup[]>('/app/algorithms')).data });
  const symbols = stocks.data?.items ?? [];
  const selectedSymbol = symbols.some(item => item.symbol === symbol) ? symbol : symbols[0]?.symbol ?? '';
  const choices = useMemo(() => algorithms.data?.flatMap(group => group.algorithms) ?? [], [algorithms.data]);
  const result = useQuery({
    queryKey: ['intraday-prediction', selectedSymbol, interval, algorithm], enabled: !!selectedSymbol && !!algorithm,
    queryFn: async () => (await api.post<IntradayResult>('/app/predict/intraday', { symbol: selectedSymbol, interval, algorithm })).data,
    refetchInterval: 30_000, refetchIntervalInBackground: false,
  });
  const error = stocks.error || algorithms.error || result.error;
  const signal = result.data?.signal;
  const signalColor = signal?.signal === 'BUY' ? 'text-emerald-300' : signal?.signal === 'SELL' ? 'text-rose-300' : 'text-amber-200';
  return <div className="space-y-5">
    <section className="research-panel grid gap-4 p-5 md:grid-cols-4 md:items-end">
      <label><span className="research-label">Available stock</span><select className="research-input mt-2 w-full" value={selectedSymbol} onChange={event => setSymbol(event.target.value)}>{symbols.map(item => <option key={item.symbol} value={item.symbol}>{item.symbol} · {item.name}</option>)}</select></label>
      <label><span className="research-label">Candle interval</span><select className="research-input mt-2 w-full" value={interval} onChange={event => setInterval(event.target.value)}>{['1m','5m','10m','15m','30m'].map(value => <option key={value}>{value}</option>)}</select></label>
      <label><span className="research-label">Indicator</span><select className="research-input mt-2 w-full" value={algorithm} onChange={event => setAlgorithm(event.target.value)}>{choices.map(item => <option key={item.key} value={item.key}>{item.name}</option>)}</select></label>
      <button className="research-button h-[46px]" onClick={() => result.refetch()} disabled={result.isFetching || !selectedSymbol}><RefreshCw size={15} className={result.isFetching ? 'animate-spin' : ''} /> Refresh signal</button>
    </section>
    <ResearchError error={error} />
    {result.data && <section className="research-panel p-6">
      <div className="flex flex-wrap items-start justify-between gap-4"><div><span className="research-label flex items-center gap-2"><Activity size={15} /> Intraday indicator signal · {result.data.interval}</span><h2 className={`mt-4 text-4xl font-semibold ${signalColor}`}>{signal?.signal}</h2><p className="mt-2 text-sm text-slate-400">{signal?.reason}</p></div><div className="text-right"><span className="research-label">Last stored candle close</span><p className="mt-2 text-2xl font-semibold">₹{result.data.last_price.toLocaleString('en-IN',{maximumFractionDigits:2})}</p></div></div>
      <div className="mt-6 grid gap-3 sm:grid-cols-3"><div className="rounded-xl border border-white/8 p-4"><span className="research-label">Signal strength</span><p className="mt-2">{Math.round((signal?.confidence ?? 0)*100)}%</p></div><div className="rounded-xl border border-white/8 p-4"><span className="research-label">Candles used</span><p className="mt-2">{result.data.candle_count} × {result.data.interval}</p></div><div className="rounded-xl border border-white/8 p-4"><span className="research-label flex items-center gap-1"><Clock3 size={12}/> Candle time / age</span><p className="mt-2">{new Date(result.data.as_of).toLocaleString()} · {Math.floor(result.data.data_age_seconds/60)}m old</p></div></div>
      <p className={`mt-5 text-xs ${result.data.data_status === 'recent' ? 'text-emerald-300' : 'text-amber-200'}`}>{result.data.is_live_feed ? 'Live feed connected' : 'Stored candles only · no live market provider is connected'}{result.data.data_status === 'stale' ? ' · latest candle is stale' : ''}</p>
      <p className="mt-2 text-xs leading-5 text-slate-500">{result.data.disclaimer} Refresh checks the database every 30 seconds; it does not fetch prices from the exchange. Signal strength is an indicator score, not a calibrated probability.</p>
    </section>}
    {!result.data && !result.isPending && !error && <section className="research-panel p-8 text-center text-sm text-slate-400">Choose an available stock. The selected interval needs enough stored minute candles before a signal can be calculated.</section>}
    {!symbols.length && !stocks.isPending && <section className="research-panel p-8 text-center text-sm text-amber-200">No intraday stocks are loaded. The daily research datasets cannot be used as minute candles. Load recent intraday candles into the market data store.</section>}
  </div>;
}

export default function Intraday() { return <ResearchShell><IntradayWorkspace /></ResearchShell>; }
