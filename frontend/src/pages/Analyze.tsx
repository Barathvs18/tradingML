import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, BrainCircuit, CalendarDays, CheckCircle2, Eye, Loader2, Minus, TrendingUp } from 'lucide-react';
import Chart from '../components/Chart';
import ResearchShell, { DirectionBadge, ResearchError, StockSelect } from '../components/ResearchShell';
import { useResearchStocks } from '../lib/useResearchStocks';
import { dateLabel, money, percent, researchApi } from '../lib/research';
import type { Direction, Outcome, Prediction } from '../lib/research';

function AnalyzeWorkspace() {
  const { stocks, symbol, setSymbol, stock, error: stockError, isPending } = useResearchStocks();
  const [selectedDate, setSelectedDate] = useState('');
  const [savedPrediction, setPrediction] = useState<Prediction | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const client = useQueryClient();
  const dates = useQuery({ queryKey: ['research-dates', symbol, stock?.model_version], enabled: !!symbol, queryFn: async () => (await researchApi.get<string[]>(`/app/analysis/stocks/${encodeURIComponent(symbol)}/dates`)).data });
  const analysisDate = dates.data?.includes(selectedDate) ? selectedDate : dates.data?.[1] || dates.data?.[0] || '';
  const prediction = savedPrediction?.symbol === symbol && savedPrediction.model_version === stock?.model_version && savedPrediction.as_of === analysisDate ? savedPrediction : null;
  const analyze = useMutation({ mutationFn: async () => (await researchApi.post<Prediction>('/app/analysis/predict', { symbol, as_of: analysisDate })).data,
    onSuccess: data => { setPrediction(data); setOutcome(null); client.invalidateQueries({ queryKey: ['research-history'] }); } });
  const reveal = useMutation({ mutationFn: async () => (await researchApi.post<{ available: boolean; outcome: Outcome | null }>(`/app/analysis/history/${prediction!.id}/reveal`)).data,
    onSuccess: data => { setOutcome(data.outcome); client.invalidateQueries({ queryKey: ['research-history'] }); } });
  const busy = analyze.isPending || reveal.isPending;
  const changeSymbol = (value: string) => { setSymbol(value); setSelectedDate(''); setPrediction(null); setOutcome(null); analyze.reset(); reveal.reset(); };
  const changeDate = (value: string) => { setSelectedDate(value); setPrediction(null); setOutcome(null); analyze.reset(); reveal.reset(); };
  const probabilities: Direction[] = ['UP', 'SIDEWAYS', 'DOWN'];
  const colors = { UP: '#6ee7b7', SIDEWAYS: '#fcd34d', DOWN: '#fda4af' };
  return <div className="space-y-5">
    <div className="research-panel grid gap-5 p-5 md:grid-cols-[1.2fr_1fr_auto] md:items-end">
      <StockSelect stocks={stocks} symbol={symbol} onChange={changeSymbol} disabled={busy} />
      <label><span className="research-label">Analyze after market close · IST</span><select aria-label="Analysis date" className="research-input mt-2 w-full" value={analysisDate} disabled={!dates.data?.length || busy} onChange={event => changeDate(event.target.value)}>{!dates.data?.length && <option value="">{dates.isPending && symbol ? 'Loading trading dates…' : 'No trading dates'}</option>}{dates.data?.map(value => <option key={value} value={value}>{dateLabel(value)}</option>)}</select></label>
      <button className="research-button h-[46px] px-7" disabled={!analysisDate || busy || !stock} onClick={() => analyze.mutate()}>{analyze.isPending ? <Loader2 size={17} className="animate-spin" /> : <BrainCircuit size={17} />} {analyze.isPending ? 'Analyzing…' : 'Analyze session'}<ArrowRight size={16} /></button>
    </div>
    <ResearchError error={stockError || dates.error || analyze.error || reveal.error} />
    {!isPending && !stocks.length && !stockError && <div className="research-panel p-12 text-center"><CalendarDays className="mx-auto mb-4 text-indigo-300" size={32} /><h2 className="text-xl font-semibold">Your first dataset starts here</h2><p className="mx-auto mt-3 max-w-md text-sm leading-6 text-slate-400">Use Import CSV to add an Indian stock with at least 300 daily sessions. We will train a model and reserve later dates for comparison.</p></div>}
    {stock && <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-slate-500"><span>{stock.rows.toLocaleString()} daily sessions · {dateLabel(stock.start)} – {dateLabel(stock.end)}</span><span>Analysis dates start after training · This dataset is historical</span></div>}
    {stock && <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_350px]">
      <section className="research-panel min-w-0 overflow-hidden">
        <div className="flex flex-wrap justify-between gap-3 border-b border-white/8 p-5"><div><div className="research-label">Price history</div><h2 className="mt-1 text-lg font-semibold">{stock.symbol} <span className="text-sm font-normal text-slate-500">NSE · 1D</span></h2></div>{prediction && <div className="text-right"><span className="text-xl font-semibold">{money(prediction.close)}</span><p className="mt-1 text-xs text-slate-500">Close · {dateLabel(prediction.as_of)}</p></div>}</div>
        {prediction ? <Chart data={prediction.history} predictedData={outcome ? [outcome.candle] : []} overlays={prediction.overlays} daily /> : <div className="flex h-[400px] flex-col items-center justify-center gap-4 p-8 text-center"><div className="grid h-16 w-16 place-items-center rounded-2xl border border-indigo-300/15 bg-indigo-300/5"><TrendingUp className="text-indigo-300" size={28} /></div><h3 className="text-lg font-medium">What did the market look like?</h3><p className="max-w-sm text-sm leading-6 text-slate-500">Choose a session and run the model. The chart will show only prices available at that point.</p></div>}
        <div className="flex flex-wrap gap-5 border-t border-white/8 px-5 py-3 text-xs text-slate-500"><span><span className="mr-2 inline-block h-2 w-2 rounded-full bg-indigo-400" />20-session moving average</span>{outcome && <span><span className="mr-2 inline-block h-2 w-2 rounded-full bg-emerald-300/50" />Revealed actual next-session candle</span>}</div>
      </section>
      <section className="research-panel flex flex-col p-5">
        <div className="flex items-center justify-between"><span className="research-label">AI direction estimate</span><span className="rounded-full border border-white/10 px-2 py-1 text-[10px] text-slate-400">Next session</span></div>
        {prediction ? <>
          <div className="my-5"><DirectionBadge value={prediction.direction} /><h3 className="mt-3 text-xl font-semibold">{prediction.direction === 'UP' ? 'An upward lean.' : prediction.direction === 'DOWN' ? 'A downward lean.' : 'A quieter session.'}</h3><p className="mt-2 text-xs leading-5 text-slate-500">Up: above +{prediction.threshold_pct}%. Down: below −{prediction.threshold_pct}%. Sideways: between these close-to-close changes.</p></div>
          <div className="space-y-4">{probabilities.map(label => <div key={label}><div className="mb-1.5 flex justify-between text-xs"><span className="text-slate-400">{label === 'UP' ? 'Up' : label === 'DOWN' ? 'Down' : 'Sideways'}</span><span style={{ color: colors[label] }}>{percent(prediction.probabilities[label])}</span></div><div className="h-1.5 overflow-hidden rounded-full bg-white/5"><div className="h-full rounded-full" style={{ width: percent(prediction.probabilities[label]), background: colors[label] }} /></div></div>)}</div>
          <div className="my-5 border-t border-white/8 pt-4"><span className="research-label">Indicator context</span><ul className="mt-3 space-y-3">{prediction.context.map(text => <li key={text} className="flex gap-2 text-xs leading-5 text-slate-400"><Minus size={13} className="mt-1 shrink-0 text-indigo-300" />{text}</li>)}</ul><p className="mt-3 text-[11px] leading-5 text-slate-500">These describe the inputs, rather than prove why the model chose this direction.</p></div>
          <button className="research-button-secondary mt-auto w-full" disabled={busy || !prediction.outcome_available || !!outcome} onClick={() => reveal.mutate()}>{reveal.isPending ? <Loader2 size={16} className="animate-spin" /> : outcome ? <CheckCircle2 size={16} /> : <Eye size={16} />}{outcome ? 'Actual outcome revealed' : prediction.outcome_available ? 'Reveal actual next session' : 'No later candle in dataset'}</button>
          <p className="mt-3 text-center text-[10px] text-slate-500">Model trained through {dateLabel(prediction.training_end)}</p>
        </> : <div className="flex flex-1 flex-col items-center justify-center gap-3 py-12 text-center"><BrainCircuit size={30} className="text-slate-600" /><p className="text-sm text-slate-500">Your analysis will appear here.</p><p className="max-w-[230px] text-xs leading-5 text-slate-600">One model, three possible directions, and an honest comparison.</p></div>}
      </section>
    </div>}
    {outcome && prediction && <section className={`research-panel grid gap-5 p-5 sm:grid-cols-[1fr_auto] ${outcome.correct ? 'border-emerald-400/20' : 'border-amber-400/20'}`}><div><span className="research-label">What actually happened · {dateLabel(outcome.date)}</span><div className="mt-3 flex flex-wrap items-center gap-3"><DirectionBadge value={outcome.direction} /><span className="text-xl font-semibold">{money(outcome.close)}</span><span className={outcome.return_pct >= 0 ? 'text-emerald-300' : 'text-rose-300'}>{outcome.return_pct > 0 ? '+' : ''}{outcome.return_pct.toFixed(2)}%</span></div></div><div className="self-center text-sm"><span className={outcome.correct ? 'text-emerald-300' : 'text-amber-200'}>{outcome.correct ? 'Direction matched' : 'Direction did not match'}</span><p className="mt-2 text-xs text-slate-500">A single result does not measure model quality.</p></div></section>}
  </div>;
}

export default function Analyze() { return <ResearchShell><AnalyzeWorkspace /></ResearchShell>; }
