import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BarChart3, BrainCircuit, ShieldCheck } from 'lucide-react';

const candleSeries = [
  { open: 68, close: 72, high: 74, low: 66 },
  { open: 72, close: 70, high: 73, low: 66 },
  { open: 70, close: 75, high: 77, low: 68 },
  { open: 75, close: 73, high: 76, low: 69 },
  { open: 73, close: 79, high: 80, low: 71 },
  { open: 79, close: 78, high: 82, low: 74 },
  { open: 78, close: 82, high: 84, low: 75 },
  { open: 82, close: 86, high: 88, low: 80 },
  { open: 86, close: 84, high: 87, low: 79 },
  { open: 84, close: 88, high: 90, low: 82 },
  { open: 88, close: 91, high: 92, low: 84 },
  { open: 91, close: 89, high: 93, low: 86 },
  { open: 89, close: 94, high: 95, low: 87 },
  { open: 94, close: 92, high: 96, low: 90 },
  { open: 92, close: 97, high: 98, low: 90 },
  { open: 97, close: 96, high: 99, low: 93 },
];

function InteractiveGraph() {
  const [hovered, setHovered] = useState<number | null>(null);

  const width = 560;
  const height = 290;
  const paddingX = 28;
  const paddingY = 18;
  const minPrice = Math.min(...candleSeries.flatMap(c => [c.low, c.open, c.close]));
  const maxPrice = Math.max(...candleSeries.flatMap(c => [c.high, c.open, c.close]));
  const chartHeight = height - paddingY * 2;
  const chartWidth = width - paddingX * 2;

  const toY = (value: number) => height - paddingY - ((value - minPrice) / (maxPrice - minPrice || 1)) * chartHeight;
  const candleWidth = 12;

  const linePoints = candleSeries.map((candle, index) => {
    const x = paddingX + (index / (candleSeries.length - 1)) * chartWidth;
    const y = toY((candle.open + candle.close) / 2);
    return `${x},${y}`;
  }).join(' ');

  const areaPath = `M ${paddingX},${height - paddingY} L ${candleSeries.map((candle, index) => {
    const x = paddingX + (index / (candleSeries.length - 1)) * chartWidth;
    const y = toY((candle.open + candle.close) / 2);
    return `${x} ${y}`;
  }).join(' L ')} L ${width - paddingX},${height - paddingY} Z`;

  return (
    <div
      className="group relative h-[290px] w-[500px] max-w-[110vw] transition-all duration-300 ease-out sm:h-[360px] sm:w-[620px]"
      style={{
        transform: 'perspective(1800px) rotateX(0deg) rotateY(-30deg) rotateZ(0deg)',
        transformOrigin: 'center center',
      }}
    >
      <div className="absolute inset-4 rounded-[30px] border border-white/10 bg-white/[0.02] shadow-[0_18px_40px_rgba(255,255,255,0.04)]" />
      <div className="absolute inset-0 translate-x-1 translate-y-1 rounded-[28px] border border-white/8 bg-black/25" />

      <div className="absolute inset-0 rounded-[28px] border border-white/12 bg-[rgba(17,17,17,0.72)] p-5 shadow-[0_30px_80px_rgba(15,23,42,0.7)] backdrop-blur-2xl transition-all duration-300 group-hover:shadow-[0_35px_90px_rgba(148,163,184,0.22)] group-hover:scale-[1.01]">
        <div className="mb-5 flex items-center justify-between text-[10px] uppercase tracking-[0.18em] text-zinc-400">
          <span>Illustration · sample values, not market data</span>
          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-zinc-200">Daily research</span>
        </div>

        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="h-[calc(100%-32px)] w-full overflow-visible transition-transform duration-300 group-hover:scale-[1.01]"
          role="img"
          aria-label="Interactive market candle chart"
          onMouseLeave={() => setHovered(null)}
        >
          {[55, 105, 155, 205, 255].map(y => (
            <line key={y} x1="0" x2={width} y1={y} y2={y} stroke="rgba(255,255,255,.09)" />
          ))}
          {[40, 120, 200, 280, 360, 440, 520].map(x => (
            <line key={x} x1={x} x2={x} y1="0" y2={height} stroke="rgba(255,255,255,.06)" />
          ))}

          <path d={areaPath} fill="rgba(255,255,255,.04)" />
          <polyline
            points={linePoints}
            fill="none"
            stroke="rgba(255,255,255,0.8)"
            strokeWidth="2.2"
            strokeLinejoin="round"
            strokeLinecap="round"
          />

          {candleSeries.map((candle, i) => {
            const x = paddingX + (i / (candleSeries.length - 1)) * chartWidth;
            const yOpen = toY(candle.open);
            const yClose = toY(candle.close);
            const yHigh = toY(candle.high);
            const yLow = toY(candle.low);
            const up = candle.close >= candle.open;
            const rectY = Math.min(yOpen, yClose);
            const rectHeight = Math.max(8, Math.abs(yClose - yOpen));
            const isActive = hovered === i;

            return (
              <g
                key={i}
                onMouseEnter={() => setHovered(i)}
                className="cursor-crosshair transition-all duration-200"
              >
                <line
                  x1={x}
                  x2={x}
                  y1={yHigh}
                  y2={yLow}
                  stroke={up ? 'rgba(74, 222, 128, 0.9)' : 'rgba(248, 113, 113, 0.9)'}
                  strokeWidth={isActive ? '2.2' : '1.6'}
                  opacity={isActive ? 1 : 0.9}
                />
                <rect
                  x={x - candleWidth / 2}
                  y={rectY}
                  width={candleWidth}
                  height={rectHeight}
                  rx={2}
                  fill={up ? 'rgba(74, 222, 128, 0.8)' : 'rgba(248, 113, 113, 0.8)'}
                  stroke={up ? 'rgba(134, 239, 172, 0.9)' : 'rgba(254, 178, 178, 0.9)'}
                  strokeWidth={isActive ? 1.5 : 0.8}
                  opacity={isActive ? 1 : 0.9}
                  transform={isActive ? `translate(0, ${-1})` : undefined}
                  style={{ filter: isActive ? 'drop-shadow(0 0 8px rgba(255,255,255,0.35))' : 'none' }}
                />
                {isActive && (
                  <>
                    <line x1={x} x2={x} y1="0" y2={height} stroke="rgba(255,255,255,.35)" strokeDasharray="4 4" />
                    <text x={Math.min(x + 10, 470)} y={Math.max(yHigh - 10, 16)} fill="white" fontSize="11">
                      {((candle.close + candle.open) / 2).toFixed(1)}
                    </text>
                  </>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

export default function Landing() {
  const features = [{ icon: BarChart3, title: 'Indian stock history', text: 'Explore daily NSE prices in rupees, after each market close.' }, { icon: BrainCircuit, title: 'AI direction estimates', text: 'Estimate up, down or sideways for the next trading session.' }, { icon: ShieldCheck, title: 'See the actual outcome', text: 'Reveal the next candle and compare with results on unseen data.' }];
  return (
    <main className="min-h-[calc(100vh-82px)] overflow-hidden px-6 pb-16 pt-16 sm:px-10 lg:px-16">
      <section className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[.9fr_1.1fr]">
        <div>
          <h1 className="max-w-xl text-5xl font-semibold leading-[1.03] tracking-tight text-white sm:text-6xl">
            Read the market.<br />
            <span className="text-zinc-400">Run the model.</span>
          </h1>
          <p className="mt-6 max-w-lg text-base leading-7 text-zinc-400">
            A focused workspace for Indian stocks. Explore historical prices, estimate the next trading session, and compare the model with what actually happened.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/analyze" className="premium-button inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-medium">
              Open market lab <ArrowRight size={16} />
            </Link>
            <Link to="/login" className="glass-subtle rounded-xl px-5 py-3 text-sm font-medium text-zinc-200 transition hover:bg-white/10">
              Sign in
            </Link>
          </div>
          <div className="mt-10 flex gap-7 text-xs text-zinc-500">
            <span>Reliance · TCS · Infosys</span>
            <span>Daily NSE data through 2021</span>
            <span>Educational use</span>
          </div>
        </div>

        <div className="flex min-h-[400px] items-center justify-center lg:justify-end">
          <InteractiveGraph />
        </div>
      </section>

      <section className="mx-auto mt-16 grid max-w-6xl gap-3 sm:grid-cols-3">
        {features.map(({ icon: Icon, title, text }) => (
          <article key={title} className="glass-subtle rounded-2xl p-5">
            <Icon size={19} className="mb-4 text-zinc-300" />
            <h2 className="text-sm font-medium text-white">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-zinc-400">{text}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
