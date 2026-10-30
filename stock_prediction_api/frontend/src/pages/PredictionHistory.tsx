import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ArrowRight, Eye, History, Loader2 } from 'lucide-react';
import ResearchShell, { DirectionBadge, ResearchError } from '../components/ResearchShell';
import { dateLabel, money, percent, researchApi } from '../lib/research';
import type { Prediction } from '../lib/research';

function HistoryWorkspace() {
  const client = useQueryClient();
  const history = useQuery({ queryKey: ['research-history'], queryFn: async () => (await researchApi.get<Prediction[]>('/app/analysis/history')).data });
  const reveal = useMutation({ mutationFn: async (id: string) => researchApi.post(`/app/analysis/history/${id}/reveal`), onSuccess: () => client.invalidateQueries({ queryKey: ['research-history'] }) });
  const items = history.data || [];
  const revealed = items.filter(item => item.outcome);
  const matched = revealed.filter(item => item.outcome?.correct).length;
  return <div className="space-y-5">
    <div className="grid gap-4 sm:grid-cols-3">{[{ label: 'Saved analyses', value: items.length, detail: 'Most recent 100' }, { label: 'Outcomes revealed', value: revealed.length, detail: 'Compare estimates with actual prices' }, { label: 'Directions matched', value: `${matched} / ${revealed.length}`, detail: 'Your selected sessions; not the holdout score' }].map(stat => <div key={stat.label} className="research-panel p-5"><span className="research-label">{stat.label}</span><p className="my-3 text-3xl font-semibold">{stat.value}</p><p className="text-xs text-slate-500">{stat.detail}</p></div>)}</div>
    <ResearchError error={history.error || reveal.error} />
    <section className="research-panel overflow-hidden"><div className="flex flex-wrap justify-between gap-3 border-b border-white/8 p-5"><div><h2 className="text-lg font-semibold">A record of your research</h2><p className="mt-2 text-xs text-slate-500">Each estimate keeps its original model version and outcome, even after a new import.</p></div><Link className="research-button-secondary" to="/analyze">New analysis <ArrowRight size={14} /></Link></div>
      {history.isPending ? <div className="grid h-52 place-items-center"><Loader2 className="animate-spin text-indigo-300" /></div> : !items.length ? <div className="flex flex-col items-center gap-4 py-16 text-center"><History className="text-slate-600" size={30} /><h3 className="font-medium">Every comparison starts with a question.</h3><p className="text-sm text-slate-500">Run your first analysis to start building a history.</p></div> : <div className="overflow-x-auto"><table className="research-table min-w-[820px]"><thead><tr><th>Stock / session</th><th>Estimated direction</th><th>Model probability</th><th>Actual outcome</th><th>Comparison</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td><span className="font-medium text-white">{item.symbol}</span><span className="mt-1 block text-xs text-slate-500">{dateLabel(item.as_of)} · {money(item.close)}</span><span className="mt-1 block font-mono text-[9px] text-slate-600" title={item.model_version}>{item.model_version}</span></td><td><DirectionBadge value={item.direction} /></td><td>{percent(item.probabilities[item.direction])}<span className="mt-1 block text-[10px] text-slate-600">Estimate, not accuracy</span></td><td>{item.outcome ? <><DirectionBadge value={item.outcome.direction} /><span className="mt-2 block text-xs text-slate-500">{dateLabel(item.outcome.date)} · {item.outcome.return_pct > 0 ? '+' : ''}{item.outcome.return_pct.toFixed(2)}%</span></> : <span className="text-xs text-slate-500">{item.outcome_available ? 'Hidden until you reveal it' : 'No later candle available'}</span>}</td><td>{item.outcome ? <span className={`text-xs ${item.outcome.correct ? 'text-emerald-300' : 'text-amber-200'}`}>{item.outcome.correct ? 'Matched' : 'Did not match'}</span> : <button className="research-button-secondary text-xs" disabled={!item.outcome_available || reveal.isPending} onClick={() => reveal.mutate(item.id)}>{reveal.isPending && reveal.variables === item.id ? <Loader2 size={13} className="animate-spin" /> : <Eye size={13} />} Reveal</button>}</td></tr>)}</tbody></table></div>}
    </section>
  </div>;
}

export default function PredictionHistory() { return <ResearchShell><HistoryWorkspace /></ResearchShell>; }
