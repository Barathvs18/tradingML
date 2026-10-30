import { useEffect, useRef } from 'react';
import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
} from 'lightweight-charts';

interface ChartProps {
  data: any[];
  predictedData?: any[];
  overlays?: Record<string, any[]>;
  markers?: any[];
  daily?: boolean;
}

export default function Chart({ data, predictedData = [], overlays = {}, markers = [], daily = false }: ChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const predictedSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const overlaySeriesMap = useRef<Record<string, ISeriesApi<"Line">>>({});

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: '#111522' },
        textColor: '#cbd5e1',
      },
      grid: {
        vertLines: { color: 'rgba(148, 163, 184, 0.12)' },
        horzLines: { color: 'rgba(148, 163, 184, 0.12)' },
      },
      timeScale: {
        timeVisible: !daily,
        secondsVisible: false,
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
    });
    
    chartRef.current = chart;
    overlaySeriesMap.current = {};

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });
    seriesRef.current = candlestickSeries;
    markersRef.current = createSeriesMarkers(candlestickSeries);

    const predictedSeries = chart.addSeries(CandlestickSeries, {
      upColor: 'rgba(34, 197, 94, 0.4)',
      downColor: 'rgba(239, 68, 68, 0.4)',
      borderVisible: false,
      wickUpColor: 'rgba(34, 197, 94, 0.4)',
      wickDownColor: 'rgba(239, 68, 68, 0.4)',
    });
    predictedSeriesRef.current = predictedSeries;

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    const observer = new ResizeObserver(handleResize);
    observer.observe(chartContainerRef.current);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      predictedSeriesRef.current = null;
      markersRef.current = null;
      overlaySeriesMap.current = {};
    };
  }, [daily]);

  useEffect(() => {
    if (!seriesRef.current || !data) return;
    
    // Sort and format data
    const sortedData = [...data].sort((a, b) => a.time - b.time);
    seriesRef.current.setData(sortedData);
    if (daily) chartRef.current?.timeScale().fitContent();

    if (markers.length > 0) {
      markersRef.current?.setMarkers(markers.map(m => ({
        time: m.time,
        position: m.position,
        color: m.position === 'aboveBar' ? '#ef4444' : '#22c55e',
        shape: m.position === 'aboveBar' ? 'arrowDown' : 'arrowUp',
        text: m.label
      })));
    } else {
      markersRef.current?.setMarkers([]);
    }
  }, [data, markers, daily]);

  useEffect(() => {
    if (!predictedSeriesRef.current || !predictedData) return;
    const sorted = [...predictedData].sort((a, b) => a.time - b.time);
    predictedSeriesRef.current.setData(sorted);
    if (daily && sorted.length) chartRef.current?.timeScale().fitContent();
  }, [predictedData, daily]);

  useEffect(() => {
    if (!chartRef.current) return;
    const chart = chartRef.current;

    // Clear old overlays not in current props
    Object.keys(overlaySeriesMap.current).forEach(key => {
      if (!overlays[key]) {
        chart.removeSeries(overlaySeriesMap.current[key]);
        delete overlaySeriesMap.current[key];
      }
    });

    // Add or update overlays
    const colors = ['#3b82f6', '#eab308', '#a855f7', '#ec4899'];
    let colorIdx = 0;

    Object.keys(overlays).forEach(key => {
      if (!overlaySeriesMap.current[key]) {
        const lineSeries = chart.addSeries(LineSeries, {
          color: colors[colorIdx % colors.length],
          lineWidth: 2,
        });
        overlaySeriesMap.current[key] = lineSeries;
      }
      
      const sorted = [...overlays[key]].sort((a, b) => a.time - b.time);
      overlaySeriesMap.current[key].setData(sorted);
      colorIdx++;
    });
    
  }, [overlays]);

  return <div ref={chartContainerRef} className="w-full h-[400px]" />;
}
