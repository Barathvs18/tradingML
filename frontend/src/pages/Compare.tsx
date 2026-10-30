import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, ArrowDownRight, ArrowUpRight, Minus, Pause, Play, Sparkles } from 'lucide-react';
import ResearchShell, { ResearchError, StockSelect } from '../components/ResearchShell';
import Chart from '../components/Chart';
import { useResearchStocks } from '../lib/useResearchStocks';
import { dateLabel, money, percent, researchApi } from '../lib/research';
import type { AlgorithmComparison, Candle } from '../lib/research';

const signalStyle = { BUY: 'text-emerald-300 bg-emerald-300/10', SELL: 'text-rose-300 bg-rose-300/10', HOLD: 'text-slate-300 bg-white/5' };
function CompareWorkspace() {
  const { stocks, symbol, setSymbol, stock, error } = useResearchStocks();
  const query = useQuery({ queryKey: ['algorithm-comparison', symbol, stock?.model_version], enabled: !!symbol,
    queryFn: async () => (await researchApi.get<AlgorithmComparison>(`/app/analysis/stocks/${encodeURIComponent(symbol)}/compare`)).data });
  const data = query.data;
  const [streaming, setStreaming] = useState(false);
  const [streamCandles, setStreamCandles] = useState<Candle[]>([]);
  const [streamStatus, setStreamStatus] = useState('Ready to replay cached historical candles.');
  const socket = useRef<WebSocket | null>(null);
  useEffect(() => () => socket.current?.close(), []);
  const toggleStream = () => {
    if (socket.current?.readyState === WebSocket.OPEN) { socket.current.close(); socket.current = null; setStreaming(false); setStreamStatus('Replay paused.'); return; }
    setStreamCandles([]); setStreaming(true); setStreamStatus('Connecting to historical replay…');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const connection = new WebSocket(`${protocol}//${window.location.host}/app/analysis/stream/${encodeURIComponent(symbol)}?speed_ms=500&limit=120`);
    socket.current = connection;
    connection.onmessage = event => {
      const payload = JSON.parse(event.data);
      if (payload.type === 'candle') {
        const candle = payload.candle;
        const time = Math.floor(Date.parse(`${candle.date}T15:30:00+05:30`) / 1000);
        setStreamCandles(current => [...current.slice(-118), { time, open: candle.open, high: candle.high, low: candle.low, close: candle.close, volume: candle.volume }]);
        setStreamStatus(`Replaying cached session ${candle.date} · ${payload.sequence}/${payload.total}`);
      } else if (payload.type === 'complete') { setStreaming(false); setStreamStatus(`Replay complete · ${payload.total} historical daily candles.`); }
      else if (payload.type === 'error') { setStreaming(false); setStreamStatus(payload.message); }
    };
    connection.onerror = () => { setStreaming(false); setStreamStatus('Historical stream could not connect.'); };
    connection.onclose = () => setStreaming(false);
  };
  return <div className="space-y-5">
    <div className="research-panel p-5"><div className="max-w-md"><StockSelect stocks={stocks} symbol={symbol} onChange={setSymbol} /></div></div>
    <ResearchError error={error || query.error} />
    {data && <>
      <section className="research-panel overflow-hidden"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 p-5"><div><span className="research-label">WebSocket historical replay</span><p className="mt-1 text-xs text-slate-500">Streams saved daily candles over a WebSocket to demonstrate live updates.</p></div><button className="research-button-secondary" onClick={toggleStream}>{streaming ? <Pause size={15} /> : <Play size={15} />}{streaming ? 'Pause replay' : 'Start replay'}</button></div>{streamCandles.length ? <Chart data={streamCandles} daily /> : <div className="grid h-36 place-items-center text-sm text-slate-500">{streamStatus}</div>}<p className="border-t border-white/8 p-4 text-xs text-slate-500">{streamStatus} · Historical data ends 30 April 2021; no live feed is connected.</p></section>
      <section className="research-panel grid gap-5 p-5 md:grid-cols-[1fr_auto] md:items-center"><div><div className="flex items-center gap-2 text-indigo-300"><Sparkles size={17} /><span className="research-label">Market regime estimate</span></div><h2 className="mt-3 text-2xl font-semibold">{data.regime.replace('_', ' ')}</h2><p className="mt-2 text-sm text-slate-400">Suggested family: {data.recommended_family} · best-fit algorithm: {data.best_fit_algorithm} · confidence {percent(data.regime_confidence)}</p><p className="mt-2 text-xs text-slate-500">{data.method}</p></div><div className="grid grid-cols-2 gap-3 text-sm"><div className="rounded-xl border border-white/8 p-4"><span className="research-label">Latest close · {dateLabel(data.as_of)}</span><p className="mt-2 font-semibold">{money(data.close)}</p></div><div className="rounded-xl border border-white/8 p-4"><span className="research-label">20-day volatility</span><p className="mt-2 font-semibold">{data.volatility_20d_pct.toFixed(2)}%</p></div></div></section>
      <section className="research-panel overflow-hidden"><div className="border-b border-white/8 p-5"><span className="research-label">13 indicator families · same stock and date</span><p className="mt-1 text-xs text-slate-500">Daily historical rules shown side by side for comparison.</p></div><div className="grid gap-px bg-white/5 sm:grid-cols-2 xl:grid-cols-3">{data.algorithms.map(item => <article key={item.key} className="bg-[#0d1018] p-5"><div className="flex items-start justify-between gap-3"><div><h3 className="font-medium text-slate-100">{item.name}</h3><p className="mt-1 text-[11px] text-slate-500">{item.key.replaceAll('_', ' ')}</p></div><span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold ${signalStyle[item.signal]}`}>{item.signal === 'BUY' ? <ArrowUpRight size={13} /> : item.signal === 'SELL' ? <ArrowDownRight size={13} /> : <Minus size={13} />}{item.signal}</span></div><div className="mt-5 flex items-center justify-between text-xs"><span className="text-slate-500">Indicator score</span><span className="text-slate-300">{percent(item.confidence)}</span></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/5"><div className="h-full rounded-full bg-indigo-300" style={{ width: percent(item.confidence) }} /></div></article>)}</div><p className="border-t border-white/8 p-5 text-xs leading-5 text-slate-500">These are lightweight reference calculations, not the trained minute-candle models or investment advice. The regime classifier uses transparent price/volatility rules and is not a Hugging Face model.</p></section>
    </>}
    {!data && query.isPending && <div className="research-panel grid h-48 place-items-center"><Activity className="animate-pulse text-indigo-300" /></div>}
  </div>;
}
export default function Compare() { return <ResearchShell><CompareWorkspace /></ResearchShell>; }
