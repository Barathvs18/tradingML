import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDownRight, ArrowUpRight, Bell, Loader2, Pause, Play, Plus, Wallet } from 'lucide-react';
import ResearchShell, { ResearchError } from '../components/ResearchShell';
import { useResearchStocks } from '../lib/useResearchStocks';
import { dateLabel, money, researchApi } from '../lib/research';
import type { AlertWebhookStatus, Automation, PaperAccount, PaperOrder, PublicApiKey, Strategy, StrategyAlert } from '../lib/research';

function PortfolioLine({ values }: { values: PaperAccount['equity_curve'] }) {
  const path = useMemo(() => {
    if (!values.length) return '';
    const min = Math.min(...values.map(point => point.equity));
    const max = Math.max(...values.map(point => point.equity));
    const span = max - min || 1;
    return values.map((point, index) => `${index ? 'L' : 'M'}${(index / Math.max(1, values.length - 1) * 1000).toFixed(1)},${(210 - (point.equity - min) / span * 190).toFixed(1)}`).join(' ');
  }, [values]);
  const daily = values.slice(-60).map(point => ({ date: point.date, pnl: point.daily_pnl }));
  const weeks = values.reduce< { date: string; pnl: number }[]>((groups, point, index) => {
    const weekIndex = Math.floor(index / 5);
    if (!groups[weekIndex]) groups[weekIndex] = { date: point.date, pnl: 0 };
    groups[weekIndex].pnl += point.daily_pnl;
    return groups;
  }, []).slice(-12);
  const bars = (items: { date: string; pnl: number }[]) => {
    const scale = Math.max(1, ...items.map(item => Math.abs(item.pnl)));
    const step = 1000 / Math.max(1, items.length);
    return items.map((item, index) => {
      const height = Math.max(1, Math.abs(item.pnl) / scale * 82);
      const y = item.pnl >= 0 ? 105 - height : 105;
      return <rect key={`${item.date}-${index}`} x={index * step + 1} y={y} width={Math.max(1, step - 2)} height={height} rx="2" fill={item.pnl >= 0 ? '#6ee7b7' : '#fda4af'} />;
    });
  };
  return <div className="research-panel p-5"><span className="research-label">Portfolio equity · daily</span>{values.length ? <><svg viewBox="0 0 1000 230" className="mt-4 h-52 w-full" role="img" aria-label="Paper portfolio equity curve"><path d={path} fill="none" stroke="#a5b4fc" strokeWidth="4" /></svg><div className="flex justify-between text-[11px] text-slate-500"><span>{dateLabel(values[0].date)}</span><span>{dateLabel(values[values.length - 1].date)}</span></div><div className="mt-6 border-t border-white/8 pt-4"><div className="flex flex-wrap items-center justify-between gap-3"><span className="research-label">Daily P&L · last 60 sessions</span><span className="text-[11px] text-slate-500">Weekly P&L · grouped in 5-session weeks</span></div><svg viewBox="0 0 1000 120" className="mt-3 h-28 w-full" role="img" aria-label="Daily portfolio profit and loss bars"><line x1="0" y1="105" x2="1000" y2="105" stroke="#475569" />{bars(daily)}</svg><div className="mt-4 grid grid-cols-6 gap-2">{weeks.map((week, index) => <div key={`${week.date}-${index}`} className="rounded-lg bg-white/5 p-2 text-center"><p className="text-[9px] text-slate-500">{dateLabel(week.date)}</p><p className={`mt-1 text-[10px] ${week.pnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>{money(week.pnl)}</p></div>)}</div></div></> : <p className="mt-4 text-sm text-slate-500">Equity history appears after the first paper fill.</p>}</div>;
}

function PortfolioWorkspace() {
  const { stocks, symbol, setSymbol, error: stocksError } = useResearchStocks();
  const [selectedDate, setSelectedDate] = useState('');
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY');
  const [orderType, setOrderType] = useState<PaperOrder['order_type']>('market');
  const [quantity, setQuantity] = useState(10);
  const [trigger, setTrigger] = useState(0);
  const [leaderboardOptIn, setLeaderboardOptIn] = useState(false);
  const [strategyId, setStrategyId] = useState('');
  const [intervalMinutes, setIntervalMinutes] = useState(5);
  const [automationQuantity, setAutomationQuantity] = useState(10);
  const [autoTrade, setAutoTrade] = useState(false);
  const [newSecret, setNewSecret] = useState('');
  const [webhookUrl, setWebhookUrl] = useState('');
  const client = useQueryClient();
  const account = useQuery({ queryKey: ['paper-account'], queryFn: async () => (await researchApi.get<PaperAccount>('/app/analysis/paper')).data });
  useEffect(() => { if (account.data) setLeaderboardOptIn(account.data.leaderboard_opt_in); }, [account.data?.leaderboard_opt_in]);
  const dates = useQuery({ queryKey: ['paper-dates', symbol], enabled: !!symbol,
    queryFn: async () => (await researchApi.get<string[]>(`/app/analysis/paper/stocks/${encodeURIComponent(symbol)}/dates`)).data });
  useEffect(() => { if (dates.data?.length && !dates.data.includes(selectedDate)) setSelectedDate(dates.data[Math.floor(dates.data.length * 0.7)]); }, [dates.data, selectedDate]);
  const orders = useMutation({ mutationFn: async () => (await researchApi.post<PaperOrder>('/app/analysis/paper/orders', {
    symbol, as_of: selectedDate, side, order_type: orderType, quantity,
    trigger_price: orderType === 'market' ? null : trigger,
  })).data, onSuccess: () => client.invalidateQueries({ queryKey: ['paper-account'] }) });
  const process = useMutation({ mutationFn: async (id: string) => (await researchApi.post<PaperOrder>(`/app/analysis/paper/orders/${id}/process`, null, { params: { as_of: selectedDate } })).data,
    onSuccess: () => client.invalidateQueries({ queryKey: ['paper-account'] }) });
  const cancel = useMutation({ mutationFn: async (id: string) => researchApi.delete(`/app/analysis/paper/orders/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: ['paper-account'] }) });
  const optIn = useMutation({ mutationFn: async (enabled: boolean) => researchApi.put('/app/analysis/paper/leaderboard-preference', { enabled }) });
  const leaderboard = useQuery({ queryKey: ['paper-leaderboard'], queryFn: async () => (await researchApi.get<{ trader: string; equity: number; total_pnl: number; return_pct: number }[]>('/app/analysis/leaderboard')).data });
  const strategies = useQuery({ queryKey: ['research-strategies'], queryFn: async () => (await researchApi.get<Strategy[]>('/app/analysis/strategies')).data });
  const automations = useQuery({ queryKey: ['research-automations'], queryFn: async () => (await researchApi.get<Automation[]>('/app/analysis/automations')).data });
  const alerts = useQuery({ queryKey: ['research-alerts'], queryFn: async () => (await researchApi.get<StrategyAlert[]>('/app/analysis/alerts')).data });
  const webhookStatus = useQuery({ queryKey: ['alert-webhook-status'], queryFn: async () => (await researchApi.get<AlertWebhookStatus>('/app/analysis/alerts/webhook')).data });
  const apiKeys = useQuery({ queryKey: ['public-api-keys'], queryFn: async () => (await researchApi.get<PublicApiKey[]>('/app/analysis/api-keys')).data });
  useEffect(() => { if (!strategyId && strategies.data?.length) setStrategyId(strategies.data[0].id); }, [strategyId, strategies.data]);
  const createAutomation = useMutation({ mutationFn: async () => researchApi.post('/app/analysis/automations', {
    strategy_id: strategyId, interval_minutes: intervalMinutes, quantity: automationQuantity, auto_trade: autoTrade,
  }), onSuccess: () => client.invalidateQueries({ queryKey: ['research-automations'] }) });
  const toggleAutomation = useMutation({ mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) => researchApi.put(`/app/analysis/automations/${id}`, { enabled }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['research-automations'] }) });
  const deleteAutomation = useMutation({ mutationFn: async (id: string) => researchApi.delete(`/app/analysis/automations/${id}`),
    onSuccess: () => { client.invalidateQueries({ queryKey: ['research-automations'] }); client.invalidateQueries({ queryKey: ['research-alerts'] }); } });
  const readAlert = useMutation({ mutationFn: async (id: string) => researchApi.put(`/app/analysis/alerts/${id}/read`),
    onSuccess: () => client.invalidateQueries({ queryKey: ['research-alerts'] }) });
  const createApiKey = useMutation({ mutationFn: async () => (await researchApi.post<{ id: string; secret: string }>('/app/analysis/api-keys')).data,
    onSuccess: data => { setNewSecret(data.secret); client.invalidateQueries({ queryKey: ['public-api-keys'] }); } });
  const revokeApiKey = useMutation({ mutationFn: async (id: string) => researchApi.delete(`/app/analysis/api-keys/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: ['public-api-keys'] }) });
  const saveWebhook = useMutation({ mutationFn: async () => researchApi.put('/app/analysis/alerts/webhook', { webhook_url: webhookUrl }),
    onSuccess: () => { setWebhookUrl(''); client.invalidateQueries({ queryKey: ['alert-webhook-status'] }); } });
  const removeWebhook = useMutation({ mutationFn: async () => researchApi.delete('/app/analysis/alerts/webhook'),
    onSuccess: () => client.invalidateQueries({ queryKey: ['alert-webhook-status'] }) });
  const error = stocksError || account.error || dates.error || orders.error || process.error || cancel.error || optIn.error || strategies.error || automations.error || alerts.error || apiKeys.error || webhookStatus.error || createAutomation.error || toggleAutomation.error || deleteAutomation.error || readAlert.error || createApiKey.error || revokeApiKey.error || saveWebhook.error || removeWebhook.error;
  const stats = account.data ? [
    { label: 'Total equity', value: money(account.data.equity), sub: `Cash ${money(account.data.cash)}` },
    { label: 'Total P&L', value: `${account.data.total_pnl >= 0 ? '+' : ''}${money(account.data.total_pnl)}`, sub: `${account.data.return_pct.toFixed(2)}% return`, color: account.data.total_pnl >= 0 },
    { label: 'Realized P&L', value: money(account.data.realized_pnl), sub: 'After simulated fees' },
    { label: 'Open holdings', value: account.data.holdings.length.toString(), sub: `${money(account.data.market_value)} market value` },
  ] : [];
  return <div className="space-y-5">
    <ResearchError error={error} />
    {account.isPending ? <div className="grid h-48 place-items-center"><Loader2 className="animate-spin text-indigo-300" /></div> : account.data && <>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{stats.map(item => <div className="research-panel p-5" key={item.label}><span className="research-label">{item.label}</span><p className={`my-3 text-2xl font-semibold ${item.color === undefined ? 'text-white' : item.color ? 'text-emerald-300' : 'text-rose-300'}`}>{item.value}</p><p className="text-xs text-slate-500">{item.sub}</p></div>)}</section>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,.8fr)]">
        <div className="space-y-5"><PortfolioLine values={account.data.equity_curve} />
          <section className="research-panel overflow-hidden"><div className="border-b border-white/8 p-5"><span className="research-label">Open holdings</span></div>{account.data.holdings.length ? <div className="overflow-x-auto"><table className="research-table"><thead><tr><th>Stock</th><th>Qty</th><th>Avg cost</th><th>Last close</th><th>Unrealized P&L</th></tr></thead><tbody>{account.data.holdings.map(item => <tr key={item.symbol}><td>{item.symbol}</td><td>{item.quantity}</td><td>{money(item.average_price)}</td><td>{money(item.last_price)}</td><td className={item.unrealized_pnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}>{money(item.unrealized_pnl)}</td></tr>)}</tbody></table></div> : <p className="p-6 text-sm text-slate-500">No holdings yet. Place a simulated market order to start.</p>}</section>
        </div>
        <section className="research-panel p-5"><div className="mb-5 flex items-center gap-3"><Wallet size={20} className="text-indigo-300" /><div><span className="research-label">Paper order ticket</span><p className="mt-1 text-xs text-slate-500">Historical simulation · no broker connection</p></div></div>
          <form className="space-y-4" onSubmit={event => { event.preventDefault(); orders.mutate(); }}>
            <label className="block"><span className="research-label">Stock</span><select className="research-input mt-2 w-full" value={symbol} onChange={event => setSymbol(event.target.value)}>{stocks.map(stock => <option key={stock.symbol} value={stock.symbol}>{stock.symbol} · {stock.name}</option>)}</select></label>
            <label className="block"><span className="research-label">Historical session</span><input type="date" className="research-input mt-2 w-full" value={selectedDate} min={dates.data?.[0]} max={dates.data?.at(-1)} onChange={event => setSelectedDate(event.target.value)} /></label>
            <div className="grid grid-cols-2 gap-3"><label><span className="research-label">Side</span><select className="research-input mt-2 w-full" value={side} onChange={event => setSide(event.target.value as 'BUY' | 'SELL')}><option>BUY</option><option>SELL</option></select></label><label><span className="research-label">Order type</span><select className="research-input mt-2 w-full" value={orderType} onChange={event => setOrderType(event.target.value as PaperOrder['order_type'])}><option value="market">Market</option><option value="limit">Limit</option><option value="stop_loss">Stop loss</option><option value="take_profit">Take profit</option></select></label></div>
            <label className="block"><span className="research-label">Quantity</span><input type="number" min={1} max={1000000} className="research-input mt-2 w-full" value={quantity} onChange={event => setQuantity(Number(event.target.value))} /></label>
            {orderType !== 'market' && <label className="block"><span className="research-label">Trigger price · INR</span><input type="number" min={0.01} step="any" className="research-input mt-2 w-full" value={trigger} onChange={event => setTrigger(Number(event.target.value))} /></label>}
            <button className="research-button w-full" disabled={orders.isPending || !selectedDate}>{orders.isPending ? <Loader2 size={16} className="animate-spin" /> : <Wallet size={16} />} Place simulated order</button>
          </form>
          <p className="mt-4 text-[11px] leading-5 text-slate-500">Orders use the selected historical candle's OHLC range. Buy orders cannot exceed available cash. Simulated fills include a 10 bps fee.</p>
        </section>
      </div>
      <section className="research-panel overflow-hidden"><div className="border-b border-white/8 p-5"><span className="research-label">Recent orders</span></div>{account.data.orders.length ? <div className="overflow-x-auto"><table className="research-table"><thead><tr><th>Date</th><th>Stock</th><th>Side / type</th><th>Qty</th><th>Status</th><th>Fill</th><th>Action</th></tr></thead><tbody>{account.data.orders.map(order => <tr key={order.id}><td>{dateLabel(order.requested_date)}</td><td>{order.symbol}</td><td>{order.side} · {order.order_type.replace('_', ' ')}</td><td>{order.quantity}</td><td className={order.status === 'filled' ? 'text-emerald-300' : 'text-amber-200'}>{order.status}</td><td>{order.fill_price ? money(order.fill_price) : '—'}</td><td>{order.status === 'pending' ? <div className="flex gap-2"><button className="text-xs text-indigo-300" onClick={() => process.mutate(order.id)} disabled={process.isPending}>Process this date</button><button className="text-xs text-rose-300" onClick={() => cancel.mutate(order.id)} disabled={cancel.isPending}>Cancel</button></div> : '—'}</td></tr>)}</tbody></table></div> : <p className="p-6 text-sm text-slate-500">No paper orders yet.</p>}</section>
      <div className="grid gap-5 lg:grid-cols-2"><section className="research-panel p-5"><label className="flex items-start gap-3"><input type="checkbox" checked={leaderboardOptIn} onChange={event => { setLeaderboardOptIn(event.target.checked); optIn.mutate(event.target.checked); }} /><span><span className="research-label">Opt in to the public leaderboard</span><span className="mt-2 block text-xs leading-5 text-slate-500">Your email and account ID stay private; the board shows a pseudonymous trader alias and simulated return.</span></span></label></section>
        <section className="research-panel overflow-hidden"><div className="border-b border-white/8 p-5"><span className="research-label">Paper trading leaderboard</span></div>{leaderboard.isPending ? <div className="grid h-24 place-items-center"><Loader2 className="animate-spin text-indigo-300" /></div> : leaderboard.data?.length ? <div className="divide-y divide-white/5">{leaderboard.data.map((trader, index) => <div className="flex items-center justify-between p-4 text-sm" key={trader.trader}><span><span className="mr-3 text-slate-500">#{index + 1}</span>{trader.trader}</span><span className={trader.return_pct >= 0 ? 'text-emerald-300' : 'text-rose-300'}>{trader.return_pct >= 0 ? <ArrowUpRight size={14} className="mr-1 inline" /> : <ArrowDownRight size={14} className="mr-1 inline" />}{trader.return_pct.toFixed(2)}%</span></div>)}</div> : <p className="p-5 text-sm text-slate-500">No traders have opted in yet.</p>}</section></div>
      <div className="grid gap-5 lg:grid-cols-2"><section className="research-panel p-5"><div className="flex items-center gap-2"><Play size={16} className="text-indigo-300" /><span className="research-label">Scheduled strategy checks</span></div><p className="mt-2 text-xs leading-5 text-slate-500">Checks for a new cached daily candle at your interval. Optional auto-trading creates paper market orders only.</p>
        {!strategies.data?.length ? <p className="mt-4 text-sm text-amber-200">Create a strategy before scheduling it.</p> : <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={event => { event.preventDefault(); createAutomation.mutate(); }}><label className="sm:col-span-2"><span className="research-label">Saved strategy</span><select className="research-input mt-2 w-full" value={strategyId} onChange={event => setStrategyId(event.target.value)}>{strategies.data.map(item => <option key={item.id} value={item.id}>{item.name} · {item.symbol}</option>)}</select></label><label><span className="research-label">Check every · minutes</span><input type="number" min={1} max={1440} className="research-input mt-2 w-full" value={intervalMinutes} onChange={event => setIntervalMinutes(Number(event.target.value))} /></label><label><span className="research-label">Order quantity</span><input type="number" min={1} max={1000000} className="research-input mt-2 w-full" value={automationQuantity} onChange={event => setAutomationQuantity(Number(event.target.value))} /></label><label className="flex items-center gap-2 text-xs text-slate-400"><input type="checkbox" checked={autoTrade} onChange={event => setAutoTrade(event.target.checked)} /> Enable simulated paper orders</label><div className="sm:text-right"><button className="research-button-secondary" disabled={!strategyId || createAutomation.isPending}>{createAutomation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} Schedule</button></div></form>}
        <div className="mt-4 divide-y divide-white/5">{automations.data?.map(job => <div className="flex flex-wrap items-center justify-between gap-3 py-3" key={job.id}><div><p className="text-sm">{job.strategy_name} · every {job.interval_minutes}m</p><p className="text-[11px] text-slate-500">{job.enabled ? 'Enabled' : 'Paused'} · {job.auto_trade ? 'paper trading on' : 'alerts only'} · last candle {job.last_signal_date || 'not checked'}</p></div><div className="flex gap-3"><button className="text-xs text-indigo-300" onClick={() => toggleAutomation.mutate({ id: job.id, enabled: !job.enabled })}>{job.enabled ? <Pause size={14} /> : <Play size={14} />}</button><button className="text-xs text-rose-300" onClick={() => deleteAutomation.mutate(job.id)}>Delete</button></div></div>)}</div>
      </section><section className="research-panel overflow-hidden"><div className="flex items-center gap-2 border-b border-white/8 p-5"><Bell size={16} className="text-indigo-300" /><span className="research-label">Strategy alerts · in app{webhookStatus.data?.configured ? ` + ${webhookStatus.data.provider}` : ''}</span></div>{alerts.data?.length ? <div className="divide-y divide-white/5">{alerts.data.map(item => <div className="flex items-start justify-between gap-3 p-4" key={item.id}><div><p className={`text-sm ${item.is_read ? 'text-slate-400' : 'text-slate-100'}`}>{item.message}</p><p className="mt-1 text-[11px] text-slate-500">{new Date(item.created_at).toLocaleString()}</p></div>{!item.is_read && <button className="shrink-0 text-xs text-indigo-300" onClick={() => readAlert.mutate(item.id)}>Mark read</button>}</div>)}</div> : <p className="p-5 text-sm text-slate-500">No strategy alerts yet.</p>}<form className="space-y-3 border-t border-white/8 p-4" onSubmit={event => { event.preventDefault(); saveWebhook.mutate(); }}><label className="block"><span className="research-label">Optional Slack or Discord webhook</span><input type="password" autoComplete="off" className="research-input mt-2 w-full text-xs" placeholder="https://hooks.slack.com/services/..." value={webhookUrl} onChange={event => setWebhookUrl(event.target.value)} /></label><div className="flex justify-between"><span className="text-[10px] leading-5 text-slate-600">Only Slack and Discord HTTPS webhook URLs are accepted.</span><div className="flex gap-3"><button type="submit" className="text-xs text-indigo-300" disabled={!webhookUrl || saveWebhook.isPending}>Save webhook</button>{webhookStatus.data?.configured && <button type="button" className="text-xs text-rose-300" onClick={() => removeWebhook.mutate()}>Remove</button>}</div></div></form></section></div>
      <section className="research-panel p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><span className="research-label">Public prediction API</span><p className="mt-1 text-xs text-slate-500">Rate-limited to 60 requests per minute per workspace. Keys are stored hashed and shown once.</p></div><button className="research-button-secondary" onClick={() => createApiKey.mutate()} disabled={createApiKey.isPending || (apiKeys.data?.length ?? 0) >= 3}>{createApiKey.isPending ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />} Create API key</button></div>
        {newSecret && <div className="mt-4 rounded-xl border border-amber-300/20 bg-amber-300/5 p-4"><p className="text-xs text-amber-200">Copy this secret now. It will not be shown again.</p><div className="mt-2 flex gap-2"><input readOnly className="research-input min-w-0 flex-1 font-mono text-xs" value={newSecret} /><button className="research-button-secondary" onClick={() => navigator.clipboard?.writeText(newSecret)}>Copy</button></div></div>}
        <div className="mt-4 divide-y divide-white/5">{apiKeys.data?.map(key => <div className="flex items-center justify-between gap-3 py-3" key={key.id}><div><p className="font-mono text-xs">{key.id}</p><p className="mt-1 text-[11px] text-slate-500">Created {new Date(key.created_at).toLocaleDateString()} · {key.last_used_at ? `last used ${new Date(key.last_used_at).toLocaleString()}` : 'never used'}</p></div><button className="text-xs text-rose-300" onClick={() => revokeApiKey.mutate(key.id)}>Revoke</button></div>)}</div>
        <p className="mt-3 rounded-lg bg-black/20 p-3 font-mono text-[11px] text-slate-400">POST /app/analysis/public/v1/predict · X-API-Key: your_secret</p>
      </section>
    </>}
  </div>;
}

export default function Portfolio() { return <ResearchShell><PortfolioWorkspace /></ResearchShell>; }
