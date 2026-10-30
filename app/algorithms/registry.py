from app.algorithms.impl.linear_regression_slope import LinearRegressionSlopeAlgo
from app.algorithms.impl.supertrend import SuperTrendAlgo
from app.algorithms.impl.macd import MACDAlgo
from app.algorithms.impl.adx import ADXAlgo
from app.algorithms.impl.bollinger_bands import BollingerBandsAlgo
from app.algorithms.impl.rsi import RSIAlgo
from app.algorithms.impl.atr import ATRAlgo
from app.algorithms.impl.doji import DojiAlgo
from app.algorithms.impl.hammer import HammerAlgo
from app.algorithms.impl.shooting_star import ShootingStarAlgo
from app.algorithms.impl.marubozu import MarubozuAlgo
from app.algorithms.impl.renko import RenkoAlgo
from app.algorithms.impl.pivot_points import PivotPointsAlgo

ALGORITHMS = {
    "linear_regression_slope": {
        "key": "linear_regression_slope",
        "name": "Linear Regression Slope",
        "category": "Trend & Momentum",
        "description": "Calculates the slope of the linear regression line to determine trend direction.",
        "lookback_minutes": 60,
        "default_params": {"period": 14},
        "class": LinearRegressionSlopeAlgo
    },
    "supertrend": {
        "key": "supertrend",
        "name": "SuperTrend",
        "category": "Trend & Momentum",
        "description": "A trend-following indicator based on Average True Range (ATR).",
        "lookback_minutes": 100,
        "default_params": {"period": 7, "multiplier": 3.0},
        "class": SuperTrendAlgo
    },
    "macd": {
        "key": "macd",
        "name": "MACD",
        "category": "Trend & Momentum",
        "description": "Moving Average Convergence Divergence.",
        "lookback_minutes": 200,
        "default_params": {"fast": 12, "slow": 26, "signal": 9},
        "class": MACDAlgo
    },
    "adx": {
        "key": "adx",
        "name": "Average Directional Index (ADX)",
        "category": "Trend & Momentum",
        "description": "Measures the strength of a trend.",
        "lookback_minutes": 100,
        "default_params": {"period": 14},
        "class": ADXAlgo
    },
    "bollinger_bands": {
        "key": "bollinger_bands",
        "name": "Bollinger Bands",
        "category": "Mean-Reversion & Volatility",
        "description": "Measures volatility using standard deviations from a moving average.",
        "lookback_minutes": 100,
        "default_params": {"period": 20, "std_dev": 2.0},
        "class": BollingerBandsAlgo
    },
    "rsi": {
        "key": "rsi",
        "name": "Relative Strength Index (RSI)",
        "category": "Mean-Reversion & Volatility",
        "description": "Momentum oscillator measuring the speed and change of price movements.",
        "lookback_minutes": 100,
        "default_params": {"period": 14},
        "class": RSIAlgo
    },
    "atr": {
        "key": "atr",
        "name": "Average True Range (ATR)",
        "category": "Mean-Reversion & Volatility",
        "description": "Measures market volatility.",
        "lookback_minutes": 100,
        "default_params": {"period": 14},
        "class": ATRAlgo
    },
    "doji": {
        "key": "doji",
        "name": "Doji Pattern",
        "category": "Pattern Recognition",
        "description": "Identifies Doji candlestick patterns signaling indecision.",
        "lookback_minutes": 10,
        "default_params": {},
        "class": DojiAlgo
    },
    "hammer": {
        "key": "hammer",
        "name": "Hammer Pattern",
        "category": "Pattern Recognition",
        "description": "Identifies bullish reversal Hammer patterns.",
        "lookback_minutes": 10,
        "default_params": {},
        "class": HammerAlgo
    },
    "shooting_star": {
        "key": "shooting_star",
        "name": "Shooting Star Pattern",
        "category": "Pattern Recognition",
        "description": "Identifies bearish reversal Shooting Star patterns.",
        "lookback_minutes": 10,
        "default_params": {},
        "class": ShootingStarAlgo
    },
    "marubozu": {
        "key": "marubozu",
        "name": "Marubozu Pattern",
        "category": "Pattern Recognition",
        "description": "Identifies Marubozu patterns signaling strong momentum.",
        "lookback_minutes": 10,
        "default_params": {},
        "class": MarubozuAlgo
    },
    "renko": {
        "key": "renko",
        "name": "Renko Bricks",
        "category": "Charting & Support/Resistance",
        "description": "Filters out noise by focusing purely on price movement.",
        "lookback_minutes": 300,
        "default_params": {"brick_size": 10},
        "class": RenkoAlgo
    },
    "pivot_points": {
        "key": "pivot_points",
        "name": "Pivot Points",
        "category": "Charting & Support/Resistance",
        "description": "Calculates support and resistance levels based on previous periods.",
        "lookback_minutes": 375,
        "default_params": {},
        "class": PivotPointsAlgo,
        "source": "reference"
    }
}

# Add default "source" to all reference algorithms
for key in ALGORITHMS:
    ALGORITHMS[key]["source"] = "reference"

def load_manifest_registry():
    """Overrides the reference algorithms with pretrained manifest ones."""
    from app.algorithms.pretrained import MANIFEST_CONFIG, PretrainedAlgorithm
    
    algos = MANIFEST_CONFIG.get("algorithms", {})
    for key, config in algos.items():
        if key in ALGORITHMS:
            ALGORITHMS[key]["source"] = "pretrained"
            ALGORITHMS[key]["class"] = PretrainedAlgorithm
            ALGORITHMS[key]["pretrained_config"] = config
            ALGORITHMS[key]["lookback_minutes"] = config.get("lookback_minutes", ALGORITHMS[key]["lookback_minutes"])
        else:
            ALGORITHMS[key] = {
                "key": key,
                "name": config.get("name", f"Pretrained {key}"),
                "category": config.get("category", "Custom Models"),
                "description": f"Pretrained model ({config.get('framework')})",
                "lookback_minutes": config.get("lookback_minutes", 60),
                "default_params": {},
                "class": PretrainedAlgorithm,
                "pretrained_config": config,
                "source": "pretrained"
            }
