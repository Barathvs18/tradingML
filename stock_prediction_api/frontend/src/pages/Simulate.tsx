import { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';
import Chart from '../components/Chart';
import { Play, Pause, SkipForward } from 'lucide-react';
import { initialWallet, openPosition, closePosition, unrealized } from '../lib/simulator';
import type { Candle } from '../lib/research';

interface AlgorithmGroup { category: string; algorithms: { key: string; name: string; lookback_minutes: number }[] }

export default function Simulate() {
  const [symbol, setSymbol] = useState('spy_data');
  const [tradingDays, setTradingDays] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState('');
  const [viewMode, setViewMode] = useState<'full' | 'replay'>('replay');
  const [loadError, setLoadError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [allCandles, setAllCandles] = useState<Candle[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1000);
  const [wallet, setWallet] = useState(initialWallet);
  const { capital, position, entryPrice, realizedPnl } = wallet;
  const [tradeQty, setTradeQty] = useState(10);
  const [autoTrade, setAutoTrade] = useState(false);
  const [selectedAlgo, setSelectedAlgo] = useState('supertrend');
  const [algos, setAlgos] = useState<AlgorithmGroup[]>([]);
  const loadGeneration = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    api.get<string[]>(`/app/stocks/${encodeURIComponent(symbol)}/trading-days`, { signal: controller.signal }).then(({ data }) => {
      setTradingDays(data); setSelectedDate(data[0] || '');
    }).catch(error => { if (!controller.signal.aborted) setLoadError(error.response?.data?.detail || 'Could not load this symbol.'); });
    return () => controller.abort();
  }, [symbol]);

  useEffect(() => {
    const controller = new AbortController();
    api.get<AlgorithmGroup[]>('/app/algorithms', { signal: controller.signal }).then(({ data }) => setAlgos(data))
      .catch(() => { if (!controller.signal.aborted) setLoadError('Could not load the algorithms.'); });
    return () => controller.abort();
  }, []);

  const changeSymbol = (value: string) => {
    loadGeneration.current += 1;
    setSymbol(value); setTradingDays([]); setSelectedDate(''); setAllCandles([]); setCurrentIndex(0);
    setWallet(initialWallet()); setIsPlaying(false); setIsLoading(false); setLoadError('');
  };

  const loadDay = async (date = selectedDate) => {
    if (!date) return;
    const generation = ++loadGeneration.current;
    setIsPlaying(false); setLoadError(''); setIsLoading(true);
    const start = new Date(date); start.setUTCHours(0, 0, 0, 0);
    const end = new Date(date); end.setUTCHours(23, 59, 59, 999);
    try {
      const { data } = await api.get<Candle[]>(`/app/stocks/${encodeURIComponent(symbol)}/candles`, {
        params: { from: start.toISOString(), to: end.toISOString(), interval: '1m' },
      });
      if (generation !== loadGeneration.current) return;
      if (!data.length) throw new Error('No candles were found for this date.');
      setAllCandles(data); setCurrentIndex(viewMode === 'full' ? data.length : Math.min(60, data.length));
      setWallet(initialWallet());
    } catch (error: any) {
      if (generation === loadGeneration.current) {
        setAllCandles([]); setLoadError(error.response?.data?.detail || error.message || 'Unable to load this session.');
      }
    } finally { if (generation === loadGeneration.current) setIsLoading(false); }
  };

  const visibleCandles = viewMode === 'full' ? allCandles : allCandles.slice(0, currentIndex);
  const currentCandle = visibleCandles[visibleCandles.length - 1];
  const unrealizedPnl = currentCandle ? unrealized(wallet, currentCandle.close) : 0;
  const totalEquity = capital + realizedPnl + unrealizedPnl;
  const handleBuy = () => { if (currentCandle) setWallet(previous => openPosition(previous, 'BUY', tradeQty, currentCandle.close)); };
  const handleSell = () => { if (currentCandle) setWallet(previous => openPosition(previous, 'SELL', tradeQty, currentCandle.close)); };
  const handleSquareOff = () => { if (currentCandle) setWallet(previous => closePosition(previous, currentCandle.close)); };
  const stepForward = () => {
    const next = Math.min(currentIndex + 1, allCandles.length);
    setCurrentIndex(next);
    if (next === allCandles.length && next > 0) {
      setWallet(previous => closePosition(previous, allCandles[next - 1].close)); setIsPlaying(false);
    }
  };

  useEffect(() => {
    if (!isPlaying || currentIndex >= allCandles.length || viewMode !== 'replay') return;
    const controller = new AbortController();
    // Auto-trade calls stay under the server's ten predictions per minute.
    const timer = setTimeout(async () => {
      const candle = allCandles[currentIndex - 1];
      const lookback = algos.flatMap(group => group.algorithms).find(algo => algo.key === selectedAlgo)?.lookback_minutes ?? 100;
      if (autoTrade && currentIndex % 5 === 0 && currentIndex >= lookback && candle) {
        try {
          const { data } = await api.post('/app/predict', {
            symbol, algorithm: selectedAlgo, as_of: new Date(candle.time * 1000).toISOString(), horizon: 1,
          }, { signal: controller.signal });
          if (controller.signal.aborted) return;
          if (data.prediction.signal === 'BUY' || data.prediction.signal === 'SELL') {
            setWallet(previous => openPosition(previous, data.prediction.signal, tradeQty, candle.close));
          }
        } catch (error: any) {
          if (controller.signal.aborted) return;
          setLoadError(error.response?.data?.detail || 'Auto-trade could not get a signal. Playback paused.');
          setIsPlaying(false); return;
        }
      }
      if (controller.signal.aborted) return;
      const next = currentIndex + 1;
      setCurrentIndex(next);
      if (next === allCandles.length) {
        setWallet(previous => closePosition(previous, allCandles[next - 1].close)); setIsPlaying(false);
      }
    }, autoTrade ? Math.max(speed, 1300) : speed);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [isPlaying, currentIndex, allCandles, viewMode, speed, autoTrade, selectedAlgo, tradeQty, symbol, algos]);

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Top Bar */}
      <div className="bg-surface p-4 rounded-xl border border-slate-700 flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Symbol</label>
          <input 
            type="text" 
            value={symbol} 
            onChange={e => changeSymbol(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-md py-1 px-3 w-32" 
          />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Trading Day</label>
          <input
            type="date"
            list="dataset-trading-days"
            value={selectedDate} 
            onChange={e => {
              setSelectedDate(e.target.value);
              loadDay(e.target.value);
            }}
            className="bg-slate-800 border border-slate-700 rounded-md py-1 px-3"
          />
          <datalist id="dataset-trading-days">
            {tradingDays.map(d => <option key={d} value={d} />)}
          </datalist>
        </div>
        <button onClick={() => loadDay()} disabled={isLoading || !selectedDate} className="bg-primary hover:bg-blue-600 px-4 py-1.5 rounded-md font-medium disabled:opacity-50">{isLoading ? 'Loading…' : 'Load day'}</button>
        <div className="flex rounded-md border border-slate-700 overflow-hidden text-sm">
          <button onClick={() => { setViewMode('full'); setCurrentIndex(allCandles.length); setWallet(initialWallet()); setIsPlaying(false); }} className={`px-3 py-1.5 ${viewMode === 'full' ? 'bg-primary text-white' : 'bg-slate-800 text-slate-400'}`}>Full session</button>
          <button onClick={() => { setViewMode('replay'); setCurrentIndex(Math.min(60, allCandles.length)); setWallet(initialWallet()); setIsPlaying(false); }} className={`px-3 py-1.5 ${viewMode === 'replay' ? 'bg-primary text-white' : 'bg-slate-800 text-slate-400'}`}>Replay</button>
        </div>
        
        <div className="w-px h-8 bg-slate-700 mx-2"></div>
        
        {/* Playback Controls */}
        <button aria-label={isPlaying ? 'Pause replay' : 'Play replay'} onClick={() => setIsPlaying(!isPlaying)} disabled={viewMode === 'full' || allCandles.length===0 || currentIndex >= allCandles.length} className="bg-slate-700 hover:bg-slate-600 p-2 rounded-full disabled:opacity-40">
          {isPlaying ? <Pause size={18} /> : <Play size={18} />}
        </button>
        <button aria-label="Next candle" onClick={stepForward} disabled={viewMode === 'full' || isPlaying || allCandles.length===0 || currentIndex >= allCandles.length} className="bg-slate-700 hover:bg-slate-600 p-2 rounded-full disabled:opacity-40">
          <SkipForward size={18} />
        </button>
        <div>
          <select value={speed} onChange={e => setSpeed(Number(e.target.value))} className="bg-slate-800 border border-slate-700 rounded-md py-1 px-2 text-sm">
            <option value={1000}>1x Speed</option>
            <option value={200}>5x Speed</option>
            <option value={50}>20x Speed</option>
          </select>
        </div>
        
        <div className="w-px h-8 bg-slate-700 mx-2"></div>
        
        {/* Auto Trade */}
        <div className="flex items-center gap-2">
          <input type="checkbox" checked={autoTrade} onChange={e => setAutoTrade(e.target.checked)} id="auto" />
          <label htmlFor="auto" className="text-sm font-medium">Auto-Trade</label>
        </div>
        {autoTrade && (
          <select value={selectedAlgo} onChange={e=>setSelectedAlgo(e.target.value)} className="bg-slate-800 border border-slate-700 rounded-md py-1 px-2 text-sm">
             {algos.map((group: any) => group.algorithms.map((a: any) => <option key={a.key} value={a.key}>{a.name}</option>))}
          </select>
        )}
      </div>
      {tradingDays.length > 0 && <p className="text-xs text-slate-500">Dataset dates: {tradingDays[tradingDays.length - 1]} to {tradingDays[0]} · {tradingDays.length.toLocaleString()} trading days.</p>}
      {loadError && <p className="rounded-md border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{loadError}</p>}

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-4 min-h-0">
        {/* Chart */}
        <div className="lg:col-span-3 bg-surface p-4 rounded-xl border border-slate-700 flex flex-col">
          <h3 className="font-semibold mb-2 flex justify-between">
            <span>{viewMode === 'full' ? 'Full trading session' : 'Replay simulation'} · {selectedDate || 'Select a date'}</span>
            <span className="text-slate-400 font-normal">
              {currentCandle ? new Date(currentCandle.time*1000).toLocaleTimeString() : '--:--'}
            </span>
          </h3>
          <div className="flex-1 border border-slate-700 rounded-lg overflow-hidden bg-slate-800/50">
             <Chart data={visibleCandles} />
          </div>
        </div>

        {/* Wallet & Trading */}
        <div className="bg-surface p-4 rounded-xl border border-slate-700 flex flex-col gap-6">
          <div>
            <h3 className="font-bold text-xl mb-4">Virtual Wallet</h3>
            <div className="space-y-3">
              <div className="flex justify-between bg-slate-800 p-3 rounded-lg border border-slate-700">
                <span className="text-slate-400">Total Equity</span>
                <span className="font-bold">₹{totalEquity.toFixed(2)}</span>
              </div>
              <div className="flex justify-between bg-slate-800 p-3 rounded-lg border border-slate-700">
                <span className="text-slate-400">Realized P&L</span>
                <span className={`font-bold ${realizedPnl > 0 ? 'text-success' : realizedPnl < 0 ? 'text-danger' : ''}`}>
                  ₹{realizedPnl.toFixed(2)}
                </span>
              </div>
            </div>
          </div>

          <div>
            <h3 className="font-semibold mb-3">Current Position</h3>
            {position === 0 ? (
              <div className="bg-slate-800 p-4 rounded-lg border border-slate-700 text-center text-slate-400">
                No open positions
              </div>
            ) : (
              <div className="bg-slate-800 p-4 rounded-lg border border-slate-700 border-l-4 border-l-primary space-y-2">
                <div className="flex justify-between">
                  <span className="font-bold">{position > 0 ? 'LONG' : 'SHORT'}</span>
                  <span>{Math.abs(position)} Qty</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Entry</span>
                  <span>₹{entryPrice.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Unrealized P&L</span>
                  <span className={`font-bold ${unrealizedPnl > 0 ? 'text-success' : 'text-danger'}`}>
                    ₹{unrealizedPnl.toFixed(2)}
                  </span>
                </div>
                <button 
                  onClick={handleSquareOff}
                  className="w-full mt-2 bg-slate-700 hover:bg-slate-600 py-1.5 rounded-md font-medium transition-colors"
                >
                  Square Off
                </button>
              </div>
            )}
          </div>

          <div className="mt-auto">
            <h3 className="font-semibold mb-3">Trade Execution</h3>
            <div className="flex gap-2 mb-3">
              <input 
                type="number" 
                value={tradeQty} 
                onChange={e => setTradeQty(Number(e.target.value))}
                className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 px-3 focus:outline-none" 
              />
              <span className="py-2 text-slate-400">Qty</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <button 
                onClick={handleBuy}
                disabled={!currentCandle || position > 0 || !Number.isInteger(tradeQty) || tradeQty <= 0 || tradeQty * currentCandle.close > totalEquity}
                className="bg-success/20 text-success hover:bg-success/30 font-bold py-3 rounded-lg transition-colors disabled:opacity-50"
              >
                BUY
              </button>
              <button 
                onClick={handleSell}
                disabled={!currentCandle || position < 0 || !Number.isInteger(tradeQty) || tradeQty <= 0 || tradeQty * currentCandle.close > totalEquity}
                className="bg-danger/20 text-danger hover:bg-danger/30 font-bold py-3 rounded-lg transition-colors disabled:opacity-50"
              >
                SELL
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
