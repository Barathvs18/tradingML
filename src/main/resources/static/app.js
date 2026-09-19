let chart = null;
let candleSeries = null;
let replayInterval = null;

function initChart() {
    const chartContainer = document.getElementById('tvchart');
    chart = LightweightCharts.createChart(chartContainer, {
        layout: {
            background: { type: 'solid', color: '#0d0f14' },
            textColor: '#d1d4dc',
        },
        grid: {
            vertLines: { color: '#2a2e39' },
            horzLines: { color: '#2a2e39' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        timeScale: {
            timeVisible: true,
            secondsVisible: false,
        },
    });

    candleSeries = chart.addCandlestickSeries({
        upColor: '#089981',
        downColor: '#f23645',
        borderDownColor: '#f23645',
        borderUpColor: '#089981',
        wickDownColor: '#f23645',
        wickUpColor: '#089981',
    });

    window.addEventListener('resize', () => {
        chart.applyOptions({ 
            width: chartContainer.clientWidth, 
            height: chartContainer.clientHeight 
        });
    });
}

document.getElementById('btn-simulate').addEventListener('click', async () => {
    const dateVal = document.getElementById('simDate').value;
    if (!dateVal) return;

    // Reset UI
    if (replayInterval) clearInterval(replayInterval);
    document.getElementById('btn-simulate').innerText = "Loading Data...";
    candleSeries.setData([]);

    // Fetch data strictly between 07:30:00 and 14:14:00
    const startIso = `${dateVal}T07:30:00`;
    const endIso = `${dateVal}T14:14:00`;

    const url = `/api/v1/history/data?symbol=SPY&start=${startIso}&end=${endIso}`;
    
    try {
        // Add a 15-second timeout in case the database is busy ingesting the 1.5M row CSV
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);

        const res = await fetch(url, { signal: controller.signal });
        clearTimeout(timeoutId);
        
        const data = await res.json();

        if (!data || data.length === 0) {
            alert("No data found for this date. Try another date like 2008-01-22.");
            document.getElementById('btn-simulate').innerText = "Simulate Day";
            return;
        }

        // Format data for chart
        const formattedData = data.map(d => ({
            time: new Date(d.timestamp + "Z").getTime() / 1000,
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close,
            originalTime: d.timestamp
        })).sort((a, b) => a.time - b.time);

        // Pre-load the first few candles so the chart has a starting viewport
        const initialCandles = formattedData.slice(0, 10);
        let currentIndex = 10;
        
        if (initialCandles.length > 0) {
            candleSeries.setData(initialCandles);
            updateClock(initialCandles[initialCandles.length - 1].originalTime);
            chart.timeScale().fitContent();
        }

        document.getElementById('btn-simulate').innerText = "Playing Simulation...";

        // Play the rest of the day minute-by-minute
        replayInterval = setInterval(() => {
            if (currentIndex >= formattedData.length) {
                clearInterval(replayInterval);
                document.getElementById('btn-simulate').innerText = "Simulation Complete";
                return;
            }

            const candle = formattedData[currentIndex];
            
            // Append candle to chart
            candleSeries.update(candle);
            
            // Update clock
            updateClock(candle.originalTime);
            
            currentIndex++;
        }, 100); // 100ms per minute -> super smooth fast playback!

    } catch (e) {
        console.error(e);
        if (e.name === 'AbortError') {
            alert("The backend took too long to respond. It is likely still busy ingesting the 1.5 Million row CSV file into the database! Please check your terminal to see if it says 'Data ingestion complete!' before trying again.");
        } else {
            alert("Failed to fetch history data.");
        }
        document.getElementById('btn-simulate').innerText = "Simulate Day";
    }
});

function updateClock(isoString) {
    const d = new Date(isoString);
    document.getElementById('clock-date').innerText = d.toLocaleDateString();
    document.getElementById('clock-time').innerText = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Run init
initChart();
