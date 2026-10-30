import axios from 'axios';
import { api } from './api';

// Both workflows share one refresh queue, preventing refresh-token rotation races.
export const researchApi = api;

export type Direction = 'UP' | 'SIDEWAYS' | 'DOWN';
export interface Candle { time: number; open: number; high: number; low: number; close: number; volume: number }
export interface Stock {
  symbol: string; name: string; exchange: string; currency: string; interval: string;
  rows: number; start: string; end: string; analysis_start: string; source: string; model_version: string;
}
export interface Outcome { date: string; close: number; return_pct: number; direction: Direction; correct: boolean; candle: Candle }
export interface Prediction {
  id: string; symbol: string; name: string; as_of: string; horizon: string; close: number;
  direction: Direction; probabilities: Record<Direction, number>; threshold_pct: number;
  model_version: string; training_end: string; history: Candle[]; overlays: Record<string, { time: number; value: number }[]>;
  context: string[]; indicators: { rsi: number; volume_ratio: number; volatility_pct: number };
  outcome_available: boolean; outcome: Outcome | null; created_at: string;
}
export interface Performance {
  symbol: string; name: string; model_version: string; model_type: string; threshold_pct: number;
  source: string; dataset_start: string; dataset_end: string; features: string[];
  accuracy: number; macro_f1: number; baseline_accuracy: number; baseline_class: Direction;
  tracked_predictions: number; tracked_accuracy: number | null; retrain_recommended: boolean;
  confusion_matrix: number[][]; classes: Direction[];
  per_class: { direction: Direction; precision: number; recall: number; f1: number; support: number }[];
  training_samples: number; test_samples: number; gap_samples: number; training_start: string;
  training_end: string; training_outcomes_end: string; test_start: string; test_end: string; large_move_days: number;
}
export type StrategyType = 'sma_crossover' | 'rsi_reversion' | 'rule_chain';
export interface Strategy {
  id: string; name: string; symbol: string; strategy_type: StrategyType;
  parameters: Record<string, unknown>; initial_capital: number;
  transaction_cost_bps: number; created_at: string; published?: boolean; publisher?: string;
}
export interface StrategyBacktest {
  strategy: Strategy; stock_name: string; data_source: string; strategy_label: string;
  initial_capital: number; final_equity: number; total_return_pct: number;
  buy_and_hold_return_pct: number; max_drawdown_pct: number;
  annualized_volatility_pct: number; sharpe_ratio: number; position_changes: number;
  closed_trades: number; win_rate_pct: number;
  transaction_cost_bps: number; start_date: string; end_date: string;
  points: { date: string; equity: number; benchmark: number }[];
}
export interface PaperOrder {
  id: string; symbol: string; side: 'BUY' | 'SELL'; order_type: 'market' | 'limit' | 'stop_loss' | 'take_profit';
  quantity: number; trigger_price: number | null; requested_date: string; status: string;
  fill_price: number | null; realized_pnl: number; created_at: string; filled_at: string | null;
}
export interface PaperAccount {
  starting_balance: number; cash: number; market_value: number; equity: number;
  realized_pnl: number; unrealized_pnl: number; total_pnl: number; return_pct: number;
  leaderboard_opt_in: boolean;
  holdings: { symbol: string; name: string; quantity: number; average_price: number; last_price: number;
    market_value: number; unrealized_pnl: number; realized_pnl: number }[];
  orders: PaperOrder[]; equity_curve: { date: string; equity: number; daily_pnl: number }[];
}
export interface AlgorithmComparison {
  as_of: string; close: number; regime: string; regime_confidence: number;
  recommended_family: string; best_fit_algorithm: string; method: string; volatility_20d_pct: number;
  trend_vs_sma50_pct: number; algorithms: { key: string; name: string; signal: 'BUY' | 'SELL' | 'HOLD'; confidence: number }[];
}
export interface Automation {
  id: string; strategy_id: string; strategy_name: string; symbol: string;
  interval_minutes: number; quantity: number; auto_trade: boolean; enabled: boolean;
  last_checked_at: string | null; last_signal_date: string | null; created_at: string;
}
export interface StrategyAlert { id: string; message: string; details: Record<string, unknown>; is_read: boolean; created_at: string }
export interface AlertWebhookStatus { configured: boolean; provider: 'slack' | 'discord' | null; updated_at: string | null }
export interface PublicApiKey { id: string; created_at: string; last_used_at: string | null }
export const money = (value: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(value);
export const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
export const dateLabel = (value: string) => new Date(`${value}T12:00:00+05:30`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' });
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    return error.response ? 'The request could not be completed. Please try again.' : 'Could not reach the analysis service. Check that it is running and retry.';
  }
  return 'Something went wrong. Please try again.';
}
