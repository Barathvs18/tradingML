"""Simple long-only daily strategies with signals applied on the next session."""

import numpy as np
import pandas as pd


def _indicators(frame: pd.DataFrame) -> pd.DataFrame:
    close = frame["close"].astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    rsi = rsi.mask((loss == 0) & (gain > 0), 100).mask((loss == 0) & (gain == 0), 50)
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    return pd.DataFrame({"close": close, "rsi_14": rsi, "macd_line": macd,
                         "macd_signal": macd.ewm(span=9, adjust=False).mean(),
                         "sma_5": close.rolling(5).mean(), "sma_20": close.rolling(20).mean(),
                         "sma_50": close.rolling(50).mean()}, index=frame.index)


def _condition(indicators: pd.DataFrame, condition: dict) -> pd.Series:
    left = indicators[condition["left"]]
    right = indicators[condition["right"]] if condition.get("right") else float(condition["value"])
    operator = condition["operator"]
    if operator == "<":
        return left < right
    if operator == ">":
        return left > right
    if operator == "crosses_above":
        return (left > right) & (left.shift(1) <= (right.shift(1) if isinstance(right, pd.Series) else right))
    if operator == "crosses_below":
        return (left < right) & (left.shift(1) >= (right.shift(1) if isinstance(right, pd.Series) else right))
    raise ValueError("Unsupported strategy condition operator.")


def _rule_chain(frame: pd.DataFrame, parameters: dict) -> tuple[pd.Series, str]:
    indicators = _indicators(frame)
    def combine(conditions: list[dict], logic: str) -> pd.Series:
        values = [_condition(indicators, item).fillna(False) for item in conditions]
        result = values[0]
        for item in values[1:]:
            result = result & item if logic == "AND" else result | item
        return result
    entries = combine(parameters["entry_conditions"], parameters["entry_logic"])
    exits = combine(parameters["exit_conditions"], parameters["exit_logic"])
    state = 0.0
    signals = []
    for enter, exit_ in zip(entries, exits):
        if state == 0 and enter:
            state = 1.0
        elif state == 1 and exit_:
            state = 0.0
        signals.append(state)
    description = f"Entry: {parameters['entry_logic']} · Exit: {parameters['exit_logic']}"
    return pd.Series(signals, index=frame.index, dtype=float), description


def current_target(frame: pd.DataFrame, kind: str, parameters: dict) -> int:
    if kind == "sma_crossover":
        close = frame["close"].astype(float)
        return int(close.rolling(int(parameters["short_window"])).mean().iloc[-1] >
                    close.rolling(int(parameters["long_window"])).mean().iloc[-1])
    if kind == "rsi_reversion":
        close = frame["close"].astype(float)
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
        rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
        rsi = rsi.mask((loss == 0) & (gain > 0), 100).mask((loss == 0) & (gain == 0), 50)
        state = 0
        for value in rsi:
            if pd.notna(value):
                if value <= int(parameters["oversold"]):
                    state = 1
                elif value >= int(parameters["overbought"]):
                    state = 0
        return state
    if kind == "rule_chain":
        signal, _ = _rule_chain(frame, parameters)
        return int(signal.iloc[-1])
    raise ValueError("Unsupported automated strategy type.")


def run_backtest(frame: pd.DataFrame, kind: str, parameters: dict, initial_capital: float,
                 transaction_cost_bps: float) -> dict:
    close = frame["close"].astype(float)
    if kind == "rule_chain":
        signal, label = _rule_chain(frame, parameters)
    elif kind == "sma_crossover":
        short_window = int(parameters["short_window"])
        long_window = int(parameters["long_window"])
        if not 2 <= short_window < long_window <= 250:
            raise ValueError("SMA windows must satisfy 2 <= short < long <= 250.")
        short_average = close.rolling(short_window, min_periods=short_window).mean()
        long_average = close.rolling(long_window, min_periods=long_window).mean()
        signal = (short_average > long_average).astype(float).where(long_average.notna(), 0.0)
        label = f"{short_window}/{long_window} session moving average crossover"
    elif kind == "rsi_reversion":
        oversold = int(parameters["oversold"])
        overbought = int(parameters["overbought"])
        if not 5 <= oversold <= 45 or not 55 <= overbought <= 95 or oversold >= overbought:
            raise ValueError("RSI levels must have oversold 5-45 below overbought 55-95.")
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
        rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
        rsi = rsi.mask((loss == 0) & (gain > 0), 100).mask((loss == 0) & (gain == 0), 50)
        state = 0.0
        signals = []
        for value in rsi:
            if pd.notna(value):
                if value <= oversold:
                    state = 1.0
                elif value >= overbought:
                    state = 0.0
            signals.append(state)
        signal = pd.Series(signals, index=frame.index, dtype=float)
        label = f"RSI(14) buy at {oversold}, exit at {overbought}"
    else:
        raise ValueError("Choose a supported strategy type.")

    # A close-based signal from session t first earns the return of session t+1.
    exposure = signal.shift(1).fillna(0.0)
    daily_return = close.pct_change(fill_method=None).fillna(0.0)
    turnover = exposure.diff().abs()
    turnover.iloc[0] = abs(float(exposure.iloc[0]))
    net_returns = exposure * daily_return - turnover * (transaction_cost_bps / 10_000)
    # Close any remaining long position at the final close.
    if len(net_returns) and exposure.iloc[-1] > 0:
        net_returns.iloc[-1] -= transaction_cost_bps / 10_000
    equity = initial_capital * (1 + net_returns).cumprod()
    benchmark = initial_capital * (1 + daily_return).cumprod()
    drawdown = equity / equity.cummax().clip(lower=initial_capital) - 1
    volatility = float(net_returns.std(ddof=1) * np.sqrt(252)) if len(net_returns) > 1 else 0.0
    mean_return = float(net_returns.mean())
    standard_deviation = float(net_returns.std(ddof=1)) if len(net_returns) > 1 else 0.0
    positions_changed = int((turnover > 0).sum())
    trade_returns = []
    active_trade_return = None
    for position, period_return in zip(exposure, net_returns):
        if position > 0 and active_trade_return is None:
            active_trade_return = 1.0
        if position > 0 and active_trade_return is not None:
            active_trade_return *= 1 + float(period_return)
        elif active_trade_return is not None:
            active_trade_return *= 1 + float(period_return)  # include the simulated exit fee
            trade_returns.append(active_trade_return - 1)
            active_trade_return = None
    if active_trade_return is not None:
        trade_returns.append(active_trade_return - 1)
    points = [{"date": str(frame.iloc[index]["date"]), "equity": round(float(equity.iloc[index]), 2),
               "benchmark": round(float(benchmark.iloc[index]), 2)}
              for index in range(0, len(frame), max(1, len(frame) // 1200))]
    if len(frame) and (not points or points[-1]["date"] != str(frame.iloc[-1]["date"])):
        points.append({"date": str(frame.iloc[-1]["date"]), "equity": round(float(equity.iloc[-1]), 2),
                       "benchmark": round(float(benchmark.iloc[-1]), 2)})
    return {
        "strategy_label": label,
        "initial_capital": float(initial_capital),
        "final_equity": round(float(equity.iloc[-1]), 2),
        "total_return_pct": round((float(equity.iloc[-1]) / initial_capital - 1) * 100, 3),
        "buy_and_hold_return_pct": round((float(benchmark.iloc[-1]) / initial_capital - 1) * 100, 3),
        "max_drawdown_pct": round(float(drawdown.min()) * 100, 3),
        "annualized_volatility_pct": round(volatility * 100, 3),
        "sharpe_ratio": round(mean_return / standard_deviation * np.sqrt(252), 3) if standard_deviation else 0.0,
        "position_changes": positions_changed,
        "closed_trades": len(trade_returns),
        "win_rate_pct": round(sum(value > 0 for value in trade_returns) / len(trade_returns) * 100, 2) if trade_returns else 0.0,
        "transaction_cost_bps": float(transaction_cost_bps),
        "start_date": str(frame.iloc[0]["date"]),
        "end_date": str(frame.iloc[-1]["date"]),
        "points": points,
    }


def compare_indicators(frame: pd.DataFrame) -> dict:
    """Evaluate the app's 13 reference indicator families on the latest daily bar."""
    data = frame.reset_index(drop=True)
    values = _indicators(data)
    last = data.iloc[-1]
    close = float(last["close"])
    rsi = float(values["rsi_14"].iloc[-1])
    macd = values["macd_line"]
    macd_signal = values["macd_signal"]
    sma20 = values["sma_20"]
    sma50 = values["sma_50"]
    ret = data["close"].pct_change(fill_method=None)
    latest_volatility = ret.rolling(20).std().iloc[-1]
    volatility = float(latest_volatility) if pd.notna(latest_volatility) else 0.0
    high_low = (data["high"] - data["low"]).astype(float)
    previous_close = data["close"].shift(1)
    tr = pd.concat([high_low, (data["high"] - previous_close).abs(), (data["low"] - previous_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    up_move = data["high"].diff()
    down_move = -data["low"].diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    plus_di = 100 * plus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / 14, adjust=False).mean()
    midpoint = (data["high"] + data["low"]) / 2
    basic_upper = midpoint + 3 * atr
    basic_lower = midpoint - 3 * atr
    supertrend = 1
    final_upper = float(basic_upper.iloc[0])
    final_lower = float(basic_lower.iloc[0])
    for index in range(1, len(data)):
        current_upper = float(basic_upper.iloc[index])
        current_lower = float(basic_lower.iloc[index])
        prior_close = float(data["close"].iloc[index - 1])
        final_upper = current_upper if current_upper < final_upper or prior_close > final_upper else final_upper
        final_lower = current_lower if current_lower > final_lower or prior_close < final_lower else final_lower
        current_close = float(data["close"].iloc[index])
        if current_close > final_upper:
            supertrend = 1
        elif current_close < final_lower:
            supertrend = -1
    band_std = data["close"].rolling(20).std()
    lower = sma20 - 2 * band_std
    upper = sma20 + 2 * band_std
    slope = float(np.polyfit(np.arange(20), data["close"].tail(20), 1)[0]) if len(data) >= 20 else 0.0
    candle_range = max(float(last["high"] - last["low"]), 1e-9)
    body = abs(close - float(last["open"]))
    lower_wick = min(close, float(last["open"])) - float(last["low"])
    upper_wick = float(last["high"]) - max(close, float(last["open"]))

    specs = [
        ("linear_regression_slope", "Linear regression slope", "BUY" if slope > 0 else "SELL", min(abs(slope) / max(close * 0.001, 1e-9), 1.0)),
        ("supertrend", "SuperTrend", "BUY" if supertrend > 0 else "SELL", min(abs(close - (final_lower if supertrend > 0 else final_upper)) / max(close * 0.01, 1e-9), 1.0)),
        ("macd", "MACD", "BUY" if macd.iloc[-1] >= macd_signal.iloc[-1] else "SELL", min(abs(float(macd.iloc[-1] - macd_signal.iloc[-1])) / max(close * 0.01, 1e-9), 1.0)),
        ("adx", "ADX", "BUY" if plus_di.iloc[-1] > minus_di.iloc[-1] else "SELL" if plus_di.iloc[-1] < minus_di.iloc[-1] else "HOLD", min(float(adx.iloc[-1]) / 50, 1.0) if pd.notna(adx.iloc[-1]) else 0.0),
        ("bollinger_bands", "Bollinger Bands", "BUY" if close < lower.iloc[-1] else "SELL" if close > upper.iloc[-1] else "HOLD", min(abs(close - float(sma20.iloc[-1])) / max(float(band_std.iloc[-1] or 0), 1e-9) / 2, 1.0)),
        ("rsi", "RSI", "BUY" if rsi < 30 else "SELL" if rsi > 70 else "HOLD", min(abs(rsi - 50) / 50, 1.0)),
        ("atr", "ATR volatility", "HOLD", min(float(atr.iloc[-1]) / max(close, 1e-9) * 20, 1.0)),
        ("doji", "Doji pattern", "HOLD", 1 - min(body / candle_range, 1.0) if body / candle_range < 0.1 else 0.0),
        ("hammer", "Hammer pattern", "BUY" if lower_wick >= body * 2 and upper_wick <= max(body, candle_range * 0.1) else "HOLD", min(lower_wick / candle_range, 1.0)),
        ("shooting_star", "Shooting star", "SELL" if upper_wick >= body * 2 and lower_wick <= max(body, candle_range * 0.1) else "HOLD", min(upper_wick / candle_range, 1.0)),
        ("marubozu", "Marubozu", "BUY" if close > float(last["open"]) and body / candle_range > 0.9 else "SELL" if close < float(last["open"]) and body / candle_range > 0.9 else "HOLD", body / candle_range),
        ("renko", "Renko direction", "BUY" if close - float(data.iloc[-2]["close"]) > float(atr.iloc[-1]) * 0.5 else "SELL" if close - float(data.iloc[-2]["close"]) < -float(atr.iloc[-1]) * 0.5 else "HOLD", min(abs(close - float(data.iloc[-2]["close"])) / max(float(atr.iloc[-1]), 1e-9), 1.0)),
        ("pivot_points", "Pivot points", "BUY" if close > 2 * ((float(data.iloc[-2]["high"]) + float(data.iloc[-2]["low"]) + float(data.iloc[-2]["close"])) / 3) - float(data.iloc[-2]["low"]) else "SELL" if close < 2 * ((float(data.iloc[-2]["high"]) + float(data.iloc[-2]["low"]) + float(data.iloc[-2]["close"])) / 3) - float(data.iloc[-2]["high"]) else "HOLD", min(abs(close / max(float(data.iloc[-2]["close"]), 1e-9) - 1) * 20, 1.0)),
    ]
    results = [{"key": key, "name": name, "signal": signal,
                "confidence": round(0.5 + 0.5 * max(0.0, min(float(confidence), 1.0)), 3)}
               for key, name, signal, confidence in specs]
    trend = close / float(sma50.iloc[-1]) - 1 if pd.notna(sma50.iloc[-1]) else 0.0
    if volatility >= 0.04:
        regime, recommendation, best_fit = "high_volatility", "ATR / volatility controls", "atr"
        regime_confidence = min(0.55 + volatility * 5, 0.95)
    elif trend >= 0.025:
        regime, recommendation, best_fit = "uptrend", "MACD or SuperTrend", "supertrend"
        regime_confidence = min(0.55 + abs(trend) * 5, 0.95)
    elif trend <= -0.025:
        regime, recommendation, best_fit = "downtrend", "MACD or SuperTrend", "supertrend"
        regime_confidence = min(0.55 + abs(trend) * 5, 0.95)
    else:
        regime, recommendation, best_fit = "range_bound", "RSI or Bollinger Bands", "rsi"
        regime_confidence = 0.6
    return {"as_of": str(last["date"]), "close": close, "regime": regime,
            "regime_confidence": round(regime_confidence, 3), "recommended_family": recommendation,
            "best_fit_algorithm": best_fit,
            "method": "Heuristic regime estimate; confidence is not a calibrated probability.",
            "volatility_20d_pct": round(volatility * 100, 3), "trend_vs_sma50_pct": round(trend * 100, 3),
            "algorithms": results}
