import logging
import json
import time

logger = logging.getLogger("predict_engine")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def log_prediction(user_id: str, symbol: str, algorithm: str, duration_ms: float, cache_hit: bool):
    log_data = {
        "event": "prediction",
        "timestamp": int(time.time()),
        "user_id": str(user_id),
        "symbol": symbol,
        "algorithm": algorithm,
        "duration_ms": round(duration_ms, 2),
        "cache_hit": cache_hit
    }
    logger.info(json.dumps(log_data))
