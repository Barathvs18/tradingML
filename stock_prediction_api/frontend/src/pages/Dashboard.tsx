import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../lib/api';
import Chart from '../components/Chart';
import { Search, Loader2, CandlestickChart, Crosshair, Settings2, Star, Plus } from 'lucide-react';

export default function Dashboard() {
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedSymbol, setSelectedSymbol] = useState('spy_data');
  const [selectedAlgo, setSelectedAlgo] = useState('spy_next_return');
  const [selectedDate, setSelectedDate] = useState('');
  const [selectedTime, setSelectedTime] = useState('13:59');
  const [horizon, setHorizon] = useState(15);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchTerm), 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const { data: searchResults } = useQuery({
    queryKey: ['stocks', debouncedSearch],
    queryFn: async () => {
      const res = await api.get('/app/stocks', { params: { search: debouncedSearch, limit: 10 } });
      return res.data.items;
    }
  });

  const { data: algos } = useQuery({
    queryKey: ['algorithms'],
    queryFn: async () => {
      const res = await api.get('/app/algorithms');
      return res.data;
    }
  });

  const { data: tradingDays = [] } = useQuery({
    queryKey: ['trading-days', selectedSymbol],
    queryFn: async () => (await api.get(`/app/stocks/${selectedSymbol}/trading-days`)).data,
  });

  const analysisDate = tradingDays.includes(selectedDate) ? selectedDate : tradingDays[0] || '';

  const predictMutation = useMutation({
    mutationFn: async () => {
      const res = await api.post('/app/predict', {
        symbol: selectedSymbol,
        algorithm: selectedAlgo,
        // This naïve value is explicitly interpreted as America/New_York by the API.
        as_of: analysisDate ? `${analysisDate}T${selectedTime}:00` : undefined,
        horizon,
      });
      return { data: res.data, cached: res.headers['x-cache'] === 'HIT' };
    }
  });

  const prediction = predictMutation.data?.data;

  return (
    <div className="mx-3 mb-3 mt-3 flex h-[calc(100vh-85px)] min-h-[620px] overflow-hidden rounded-2xl glass">
      <aside className="hidden w-12 shrink-0 border-r border-white/8 py-4 lg:flex flex-col items-center gap-5 text-slate-500"><Crosshair size={17}/><CandlestickChart size={17}/><Star size={17}/><Settings2 size={17}/></aside>
      <div className="grid min-w-0 flex-1 grid-cols-1 lg:grid-cols-[245px_minmax(0,1fr)_275px]">
      {/* Left Panel */}
      <div className="bg-black/10 p-4 border-r border-white/8 flex flex-col gap-5">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Symbol search</h3>
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search stocks..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 pl-9 pr-3 focus:outline-none focus:border-primary"
            />
          </div>
          {searchResults && searchResults.length > 0 && searchTerm && (
            <div className="mt-2 bg-slate-800 border border-slate-700 rounded-md max-h-40 overflow-y-auto">
              {searchResults.map((s: any) => (
                <div 
                  key={s.symbol}
                  onClick={() => { setSelectedSymbol(s.symbol); setSelectedDate(''); setSearchTerm(''); }}
                  className="px-3 py-2 hover:bg-slate-700 cursor-pointer text-sm"
                >
                  {s.symbol} - {s.name}
                </div>
              ))}
            </div>
          )}
          <div className="mt-2 text-sm text-slate-400">Selected: <span className="text-white font-bold">{selectedSymbol}</span></div>
        </div>

        <div>
          <h3 className="text-lg font-semibold mb-3">Algorithm</h3>
          <select 
            value={selectedAlgo}
            onChange={e => setSelectedAlgo(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 px-3 focus:outline-none focus:border-primary"
          >
            {algos?.map((group: any) => (
              <optgroup key={group.category} label={group.category}>
                {group.algorithms.map((a: any) => (
                  <option key={a.key} value={a.key}>{a.name}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Analysis date</h3>
          <input type="date" list="dashboard-trading-days" value={analysisDate} onChange={e => setSelectedDate(e.target.value)} className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 px-3 focus:outline-none focus:border-primary" />
          <datalist id="dashboard-trading-days">{tradingDays.map((day: string) => <option key={day} value={day} />)}</datalist>
          <p className="mt-2 text-xs text-slate-500">Choose any trading date from the selected dataset.</p>
        </div>

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Analysis time (ET)</h3>
          <input type="time" min="07:30" max="13:59" step="60" value={selectedTime} onChange={e => setSelectedTime(e.target.value)} className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 px-3 focus:outline-none focus:border-primary" />
          <p className="mt-2 text-xs text-slate-500">Available data: 07:30 to 13:59 Eastern Time.</p>
        </div>

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Forecast tenure</h3>
          <select value={horizon} onChange={e => setHorizon(Number(e.target.value))} className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 px-3 focus:outline-none focus:border-primary">
            {[1, 5, 15, 30, 60, 120, 240].map(minutes => <option key={minutes} value={minutes}>Next {minutes} minute{minutes === 1 ? '' : 's'}</option>)}
          </select>
        </div>

        <button 
          onClick={() => predictMutation.mutate()}
          disabled={predictMutation.isPending}
          className="premium-button mt-auto rounded-xl py-2.5 text-sm font-medium text-white transition-all flex justify-center items-center gap-2 disabled:opacity-50"
        >
          {predictMutation.isPending && <Loader2 className="animate-spin h-5 w-5" />}
          Analyze date & forecast
        </button>
        {predictMutation.isError && (
          <div className="text-danger text-sm mt-2 text-center">
            {/* @ts-ignore */}
            {predictMutation.error?.response?.data?.detail || "Prediction failed"}
          </div>
        )}
      </div>

      {/* Center Panel */}
      <div className="min-w-0 bg-black/5 flex flex-col">
        <div className="flex h-11 shrink-0 items-center gap-3 border-b border-[#2a2e39] px-4 text-sm"><Star size={16} className="text-slate-500"/><b>{selectedSymbol.toUpperCase()}</b><span className="text-slate-500">NYSE · 1m</span><span className="ml-auto text-xs text-slate-400">Indicators</span><Plus size={16}/></div>
        <div className="flex h-9 shrink-0 items-center gap-4 border-b border-[#2a2e39] px-4 text-xs text-slate-400"><span className="text-white">1m</span><span>5m</span><span>15m</span><span>1h</span><span>1D</span><span className="ml-auto">Auto</span></div>
        <div className="flex-1 bg-[#111522]/40 overflow-hidden">
          {prediction ? (
            <Chart 
              data={prediction.history} 
              predictedData={prediction.predicted_candles}
              overlays={prediction.prediction.overlays}
              markers={prediction.prediction.markers}
            />
          ) : (
            <div className="h-full flex flex-col items-center justify-center gap-3 text-slate-500">
              <CandlestickChart size={34} className="text-[#2962ff]"/><span>Select a symbol, model and run analysis</span>
            </div>
          )}
        </div>
        {prediction && (
          <p className="text-xs text-slate-500 mt-3 text-center">{prediction.disclaimer}</p>
        )}
      </div>

      {/* Right Panel */}
      <div className="bg-black/10 border-l border-white/8 p-4 flex flex-col gap-4">
        <div className="flex items-center justify-between border-b border-[#2a2e39] pb-3"><h3 className="text-sm font-semibold">Watchlist</h3><Plus size={16} className="text-slate-400"/></div>
        <div className="grid grid-cols-3 text-[10px] uppercase text-slate-500"><span>Symbol</span><span className="text-right">Last</span><span className="text-right">Change</span></div>
        <div className="grid grid-cols-3 text-xs"><b>{selectedSymbol.toUpperCase()}</b><span className="text-right">—</span><span className="text-right text-slate-500">—</span></div>
        <h3 className="text-sm font-semibold mt-3 border-b border-[#2a2e39] pb-3">Model analysis</h3>
        
        {!prediction ? (
          <div className="text-slate-500 text-sm italic">No prediction run yet.</div>
        ) : (
          <>
            <div className="flex justify-between items-center bg-slate-800 p-3 rounded-lg border border-slate-700">
              <span className="text-slate-400">Signal</span>
              <span className={`px-3 py-1 rounded-full text-sm font-bold ${
                prediction.prediction.signal === 'BUY' ? 'bg-success/20 text-success' : 
                prediction.prediction.signal === 'SELL' ? 'bg-danger/20 text-danger' : 
                'bg-slate-700 text-slate-300'
              }`}>
                {prediction.prediction.signal}
              </span>
            </div>

            <div className="bg-slate-800 p-3 rounded-lg border border-slate-700">
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-400">Confidence</span>
                <span>{(prediction.prediction.confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div 
                  className="bg-primary h-2 rounded-full" 
                  style={{ width: `${prediction.prediction.confidence * 100}%` }}
                ></div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-800 p-3 rounded-lg border border-slate-700"><span className="block text-xs text-slate-400">Analysis point</span><span className="text-sm font-medium">{selectedDate} {selectedTime} ET</span></div>
              <div className="bg-slate-800 p-3 rounded-lg border border-slate-700"><span className="block text-xs text-slate-400">Forecast tenure</span><span className="text-sm font-medium">{prediction.predicted_candles.length} min</span></div>
            </div>

            {prediction.predicted_candles.length > 0 && <div className="bg-slate-800 p-3 rounded-lg border border-slate-700"><span className="block text-xs text-slate-400">Projected price at end of tenure</span><span className="text-lg font-semibold">${prediction.predicted_candles[prediction.predicted_candles.length - 1].close.toFixed(2)}</span></div>}

            <div className="bg-slate-800 p-3 rounded-lg border border-slate-700">
              <span className="text-slate-400 block text-sm mb-1">Reason</span>
              <p className="text-sm">{prediction.prediction.reason}</p>
            </div>

            {(prediction.prediction.target_price || prediction.prediction.stop_loss) && (
              <div className="grid grid-cols-2 gap-3 mt-2">
                {prediction.prediction.target_price && (
                  <div className="bg-slate-800 p-3 rounded-lg border border-slate-700">
                    <span className="text-slate-400 text-xs block">Target</span>
                    <span className="font-bold text-success">₹{prediction.prediction.target_price.toFixed(2)}</span>
                  </div>
                )}
                {prediction.prediction.stop_loss && (
                  <div className="bg-slate-800 p-3 rounded-lg border border-slate-700">
                    <span className="text-slate-400 text-xs block">Stop Loss</span>
                    <span className="font-bold text-danger">₹{prediction.prediction.stop_loss.toFixed(2)}</span>
                  </div>
                )}
              </div>
            )}
            
            <div className="mt-auto pt-4 border-t border-slate-700">
              <div className="text-xs text-slate-400 flex justify-between">
                <span>Cached: {predictMutation.data?.cached ? 'Yes' : 'No'}</span>
                <span>As of: {new Date(prediction.as_of).toLocaleTimeString()}</span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
    </div>
  );
}
