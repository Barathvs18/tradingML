import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Activity, ArrowDownRight, ArrowUpRight, Loader2, Play, Plus, Trash2 } from 'lucide-react';
import ResearchShell, { ResearchError } from '../components/ResearchShell';
import { useResearchStocks } from '../lib/useResearchStocks';
import { dateLabel, money, researchApi } from '../lib/research';
import type { Strategy, StrategyBacktest, StrategyType } from '../lib/research';

function EquityChart({ points }: { points: StrategyBacktest['points'] }) {
  const paths = useMemo(() => {
    if (!points.length) return null;
    const values = points.flatMap(point => [point.equity, point.benchmark]);
    const low = Math.min(...values);
    const high = Math.max(...values);
    const span = high - low || 1;
    const pathFor = (key: 'equity' | 'benchmark') => points.map((point, index) => {
      const x = points.length === 1 ? 0 : index / (points.length - 1) * 1000;
      const y = 220 - (point[key] - low) / span * 200;
      return `${index ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    return { strategy: pathFor('equity'), benchmark: pathFor('benchmark') };
  }, [points]);
  if (!paths) return null;
  return <div className="research-panel p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><span className="research-label">Historical equity curve</span><p className="mt-1 text-xs text-slate-500">Strategy compared with buying and holding the same stock</p></div><div className="flex gap-4 text-xs"><span className="text-indigo-300">● Strategy</span><span className="text-slate-400">● Buy and hold</span></div></div>
    <div className="mt-5 overflow-hidden"><svg viewBox="0 0 1000 240" role="img" aria-label="Backtest equity curve" className="h-56 w-full"><path d={paths.benchmark} fill="none" stroke="#94a3b8" strokeWidth="3" strokeDasharray="8 7" /><path d={paths.strategy} fill="none" stroke="#a5b4fc" strokeWidth="4" /></svg></div>
    <div className="flex justify-between text-[11px] text-slate-500"><span>{dateLabel(points[0].date)}</span><span>{dateLabel(points[points.length - 1].date)}</span></div>
  </div>;
}

function StrategiesWorkspace() {
  const { stocks, symbol, setSymbol, error: stockError } = useResearchStocks();
  const [name, setName] = useState('My historical strategy');
  const [kind, setKind] = useState<StrategyType>('sma_crossover');
  const [shortWindow, setShortWindow] = useState(10);
  const [longWindow, setLongWindow] = useState(30);
  const [oversold, setOversold] = useState(30);
  const [overbought, setOverbought] = useState(70);
  const [entryLogic, setEntryLogic] = useState<'AND' | 'OR'>('AND');
  const [exitLogic, setExitLogic] = useState<'AND' | 'OR'>('OR');
  const [capital, setCapital] = useState(100000);
  const [costBps, setCostBps] = useState(10);
  const [result, setResult] = useState<StrategyBacktest | null>(null);
  const client = useQueryClient();
  const saved = useQuery({ queryKey: ['research-strategies'], queryFn: async () => (await researchApi.get<Strategy[]>('/app/analysis/strategies')).data });
  const marketplace = useQuery({ queryKey: ['research-marketplace'], queryFn: async () => (await researchApi.get<Strategy[]>('/app/analysis/marketplace')).data });
  const create = useMutation({ mutationFn: async () => {
    const parameters = kind === 'sma_crossover' ? { short_window: shortWindow, long_window: longWindow }
      : kind === 'rsi_reversion' ? { oversold, overbought }
        : { entry_logic: entryLogic, exit_logic: exitLogic,
          entry_conditions: [{ left: 'rsi_14', operator: '<', value: oversold }, { left: 'macd_line', operator: 'crosses_above', right: 'macd_signal' }],
          exit_conditions: [{ left: 'rsi_14', operator: '>', value: overbought }, { left: 'macd_line', operator: 'crosses_below', right: 'macd_signal' }] };
    return (await researchApi.post<Strategy>('/app/analysis/strategies', {
      name, symbol, strategy_type: kind, parameters, initial_capital: capital, transaction_cost_bps: costBps,
    })).data;
  }, onSuccess: () => { setResult(null); client.invalidateQueries({ queryKey: ['research-strategies'] }); } });
  const backtest = useMutation({ mutationFn: async (id: string) => (await researchApi.post<StrategyBacktest>(`/app/analysis/strategies/${id}/backtest`)).data,
    onSuccess: data => setResult(data) });
  const remove = useMutation({ mutationFn: async (id: string) => researchApi.delete(`/app/analysis/strategies/${id}`),
    onSuccess: () => { client.invalidateQueries({ queryKey: ['research-strategies'] }); setResult(null); } });
  const publish = useMutation({ mutationFn: async ({ id, published }: { id: string; published: boolean }) => researchApi.put(`/app/analysis/strategies/${id}/publish`, { published }),
    onSuccess: () => { client.invalidateQueries({ queryKey: ['research-strategies'] }); client.invalidateQueries({ queryKey: ['research-marketplace'] }); } });
  const clone = useMutation({ mutationFn: async (id: string) => researchApi.post(`/app/analysis/marketplace/${id}/clone`),
    onSuccess: () => client.invalidateQueries({ queryKey: ['research-strategies'] }) });
  const error = stockError || saved.error || marketplace.error || create.error || backtest.error || remove.error || publish.error || clone.error;
  return <div className="space-y-5">
    <section className="research-panel p-5 sm:p-6">
      <div className="mb-5 flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-xl bg-indigo-300/10 text-indigo-300"><Activity size={20} /></div><div><span className="research-label">Create a historical strategy</span><p className="mt-1 text-xs text-slate-500">Save a simple rule, then replay it on the selected stock's daily history.</p></div></div>
      <form className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" onSubmit={event => { event.preventDefault(); create.mutate(); }}>
        <label><span className="research-label">Strategy name</span><input className="research-input mt-2 w-full" required maxLength={60} value={name} onChange={event => setName(event.target.value)} /></label>
        <label><span className="research-label">Historical stock</span><select className="research-input mt-2 w-full" value={symbol} onChange={event => setSymbol(event.target.value)} disabled={!stocks.length}>{stocks.map(stock => <option key={stock.symbol} value={stock.symbol}>{stock.symbol} · {stock.name}</option>)}</select></label>
        <label><span className="research-label">Rule type</span><select className="research-input mt-2 w-full" value={kind} onChange={event => setKind(event.target.value as StrategyType)}><option value="sma_crossover">Moving average trend</option><option value="rsi_reversion">RSI mean reversion</option><option value="rule_chain">Chain RSI + MACD rules</option></select></label>
        {kind === 'sma_crossover' ? <>
          <label><span className="research-label">Short average · sessions</span><input type="number" min={2} max={100} className="research-input mt-2 w-full" value={shortWindow} onChange={event => setShortWindow(Number(event.target.value))} /></label>
          <label><span className="research-label">Long average · sessions</span><input type="number" min={3} max={250} className="research-input mt-2 w-full" value={longWindow} onChange={event => setLongWindow(Number(event.target.value))} /></label>
        </> : kind === 'rsi_reversion' ? <>
          <label><span className="research-label">Buy when RSI is at or below</span><input type="number" min={5} max={45} className="research-input mt-2 w-full" value={oversold} onChange={event => setOversold(Number(event.target.value))} /></label>
          <label><span className="research-label">Exit when RSI is at or above</span><input type="number" min={55} max={95} className="research-input mt-2 w-full" value={overbought} onChange={event => setOverbought(Number(event.target.value))} /></label>
        </> : <>
          <label><span className="research-label">Entry join</span><select className="research-input mt-2 w-full" value={entryLogic} onChange={event => setEntryLogic(event.target.value as 'AND' | 'OR')}><option>AND</option><option>OR</option></select></label>
          <label><span className="research-label">Exit join</span><select className="research-input mt-2 w-full" value={exitLogic} onChange={event => setExitLogic(event.target.value as 'AND' | 'OR')}><option>OR</option><option>AND</option></select></label>
          <label><span className="research-label">RSI entry threshold</span><input type="number" min={5} max={45} className="research-input mt-2 w-full" value={oversold} onChange={event => setOversold(Number(event.target.value))} /></label>
          <label><span className="research-label">RSI exit threshold</span><input type="number" min={55} max={95} className="research-input mt-2 w-full" value={overbought} onChange={event => setOverbought(Number(event.target.value))} /></label>
        </>}
        <label><span className="research-label">Starting virtual capital · INR</span><input type="number" min={1000} max={1000000000} step={1000} className="research-input mt-2 w-full" value={capital} onChange={event => setCapital(Number(event.target.value))} /></label>
        <label><span className="research-label">Estimated transaction cost · bps</span><input type="number" min={0} max={100} step={1} className="research-input mt-2 w-full" value={costBps} onChange={event => setCostBps(Number(event.target.value))} /></label>
        <div className="flex items-end"><button className="research-button w-full" type="submit" disabled={create.isPending || !symbol}>{create.isPending ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />} Save strategy</button></div>
      </form>
      <p className="mt-4 text-xs leading-5 text-slate-500">Rule chains combine RSI threshold checks with MACD line/signal crossovers using your AND/OR choices. Long-only simulation; close-based rules apply from the next session. Results exclude taxes, slippage and corporate-action adjustments.</p>
    </section>
    <ResearchError error={error} />
    <section className="research-panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/8 p-5"><div><span className="research-label">Your saved strategies</span><p className="mt-1 text-xs text-slate-500">Only you can view or delete strategies saved in this workspace.</p></div><span className="text-xs text-slate-500">{saved.data?.length ?? 0} saved</span></div>
      {saved.isPending ? <div className="grid h-32 place-items-center"><Loader2 className="animate-spin text-indigo-300" /></div> : !saved.data?.length ? <p className="p-8 text-center text-sm text-slate-500">Create your first strategy above to run a historical backtest.</p> : <div className="divide-y divide-white/5">{saved.data.map(strategy => <div key={strategy.id} className="flex flex-wrap items-center justify-between gap-4 p-5"><div className="min-w-[200px] flex-1"><h3 className="font-medium text-slate-100">{strategy.name}</h3><p className="mt-1 text-xs text-slate-500">{strategy.symbol} · {strategy.strategy_type === 'sma_crossover' ? `${strategy.parameters.short_window}/${strategy.parameters.long_window} session averages` : strategy.strategy_type === 'rsi_reversion' ? `RSI buy ${strategy.parameters.oversold}, exit ${strategy.parameters.overbought}` : `RSI + MACD · entry ${strategy.parameters.entry_logic}, exit ${strategy.parameters.exit_logic}`} · {money(strategy.initial_capital)} start</p></div><div className="flex flex-wrap gap-2"><button className="research-button-secondary" onClick={() => backtest.mutate(strategy.id)} disabled={backtest.isPending}>{backtest.isPending && backtest.variables === strategy.id ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />} Run backtest</button><button className="research-button-secondary" onClick={() => publish.mutate({ id: strategy.id, published: !strategy.published })} disabled={publish.isPending}>{strategy.published ? 'Unpublish' : 'Publish'}</button><button className="research-button-secondary" aria-label={`Delete ${strategy.name}`} onClick={() => remove.mutate(strategy.id)} disabled={remove.isPending}><Trash2 size={15} /></button></div></div>)}</div>}
    </section>
    <section className="research-panel overflow-hidden"><div className="border-b border-white/8 p-5"><span className="research-label">Strategy marketplace</span><p className="mt-1 text-xs text-slate-500">Public strategies show pseudonymous creators. Cloning copies rules into your private workspace.</p></div>{marketplace.isPending ? <div className="grid h-24 place-items-center"><Loader2 className="animate-spin text-indigo-300" /></div> : marketplace.data?.length ? <div className="divide-y divide-white/5">{marketplace.data.map(item => <div className="flex flex-wrap items-center justify-between gap-3 p-5" key={item.id}><div><h3 className="font-medium">{item.name}</h3><p className="mt-1 text-xs text-slate-500">{item.symbol} · {item.publisher} · {item.strategy_type.replace('_', ' ')}</p></div><button className="research-button-secondary" onClick={() => clone.mutate(item.id)} disabled={clone.isPending}>Clone strategy</button></div>)}</div> : <p className="p-6 text-sm text-slate-500">No published strategies yet.</p>}</section>
    {result && <>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[
        { label: 'Strategy return', value: `${result.total_return_pct > 0 ? '+' : ''}${result.total_return_pct.toFixed(2)}%`, detail: `${money(result.final_equity)} ending equity`, good: result.total_return_pct >= 0 },
        { label: 'Buy and hold', value: `${result.buy_and_hold_return_pct > 0 ? '+' : ''}${result.buy_and_hold_return_pct.toFixed(2)}%`, detail: 'Same stock and date range' },
        { label: 'Maximum drawdown', value: `${result.max_drawdown_pct.toFixed(2)}%`, detail: 'Largest peak-to-trough decline' },
        { label: 'Win rate', value: `${result.win_rate_pct.toFixed(1)}%`, detail: `${result.closed_trades} completed trades` },
        { label: 'Sharpe ratio', value: result.sharpe_ratio.toFixed(2), detail: `${result.position_changes} position changes · vol ${result.annualized_volatility_pct.toFixed(1)}%` },
      ].map(card => <div className="research-panel p-5" key={card.label}><span className="research-label">{card.label}</span><p className={`my-3 text-2xl font-semibold ${card.good === undefined ? 'text-white' : card.good ? 'text-emerald-300' : 'text-rose-300'}`}>{card.value}</p><p className="text-xs text-slate-500">{card.detail}</p></div>)}</section>
      <EquityChart points={result.points} />
      <section className="research-panel flex flex-wrap items-center justify-between gap-3 p-5 text-xs text-slate-400"><div><span className="research-label">Backtest period</span><p className="mt-2">{dateLabel(result.start_date)} – {dateLabel(result.end_date)} · {result.stock_name}</p></div><div className="flex items-center gap-2"><ArrowUpRight size={15} className="text-indigo-300" /> Strategy return is historical and simulated.</div><div className="flex items-center gap-2"><ArrowDownRight size={15} className="text-slate-500" /> No live orders are sent.</div></section>
    </>}
  </div>;
}

export default function Strategies() { return <ResearchShell><StrategiesWorkspace /></ResearchShell>; }
