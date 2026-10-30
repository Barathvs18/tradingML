import os
import yaml
import importlib.util
from typing import Dict, Any
import pandas as pd
from app.algorithms.base import BaseAlgorithm, AlgoResult
from app.core.config import settings

# Global registries for models and scalers
LOADED_MODELS: Dict[str, Any] = {}
LOADED_SCALERS: Dict[str, Any] = {}
MANIFEST_CONFIG: Dict[str, Any] = {}

def load_manifest() -> Dict[str, Any]:
    manifest_path = os.path.join(settings.MODELS_DIR, "manifest.yaml")
    if not os.path.exists(manifest_path):
        return {}
    with open(manifest_path, "r") as f:
        return yaml.safe_load(f) or {}

def _load_pickle(filepath: str):
    import pickle
    with open(filepath, "rb") as f:
        return pickle.load(f)

def load_all_pretrained():
    """Loads all models defined in manifest.yaml into memory."""
    global LOADED_MODELS, LOADED_SCALERS, MANIFEST_CONFIG
    
    MANIFEST_CONFIG = load_manifest()
    algos = MANIFEST_CONFIG.get("algorithms", {})
    
    for key, config in algos.items():
        model_file = config.get("file")
        scaler_file = config.get("scaler_file")
        framework = config.get("framework")
        
        if not model_file or not framework:
            continue
            
        model_path = os.path.join(settings.MODELS_DIR, model_file)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file {model_path} not found for {key}")
            
        # Load Model
        if framework == "sklearn" or framework == "xgboost":
            LOADED_MODELS[key] = _load_pickle(model_path)
        elif framework == "tensorflow":
            import tensorflow as tf
            LOADED_MODELS[key] = tf.keras.models.load_model(model_path)
        elif framework == "torch":
            import torch
            LOADED_MODELS[key] = torch.load(model_path)
        elif framework == "python_script":
            # Dynamic import
            spec = importlib.util.spec_from_file_location(f"custom_{key}", model_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not hasattr(mod, "main"):
                raise ValueError(f"Python script {model_path} must define a 'main(df)' function.")
            LOADED_MODELS[key] = mod.main
        else:
            raise ValueError(f"Unknown framework: {framework} for {key}")
            
        # Load Scaler
        if scaler_file:
            scaler_path = os.path.join(settings.MODELS_DIR, scaler_file)
            if not os.path.exists(scaler_path):
                raise FileNotFoundError(f"Scaler file {scaler_path} not found for {key}")
            LOADED_SCALERS[key] = _load_pickle(scaler_path)

class PretrainedAlgorithm(BaseAlgorithm):
    def __init__(self, key: str, config: Dict[str, Any]):
        self.key = key
        self.config = config
        self.lookback_minutes = config.get("lookback_minutes", 60)
        self.features = config.get("features", [])
        self.framework = config.get("framework")
        self.output_mapping = config.get("output_mapping", {})
        
        # Verify model was loaded
        if key not in LOADED_MODELS:
            raise ValueError(f"Model for {key} was not loaded into memory.")
            
    def run(self, df: pd.DataFrame, params: dict) -> AlgoResult:
        model = LOADED_MODELS[self.key]
        scaler = LOADED_SCALERS.get(self.key)
        
        if self.framework == "python_script":
            # Direct passthrough to custom script
            return model(df)
            
        # Feature Extraction
        for feat in self.features:
            if feat not in df.columns:
                # If feature is not a raw column, it might require computation 
                # (e.g. rsi_14). In a robust system, we would dynamically calculate TA features here.
                # For Phase 5, we assume either raw columns or the user handles it in a pipeline.
                raise ValueError(f"Required model feature is unavailable: {feat}")
                
        # Use the latest row's features
        latest_features = df[self.features].iloc[-1:].copy()
        
        # Scale if necessary
        if scaler:
            scaled = scaler.transform(latest_features)
            latest_features = pd.DataFrame(scaled, columns=self.features)
            
        # Predict
        if self.framework == "sklearn" or self.framework == "xgboost":
            pred = model.predict(latest_features)[0]
        elif self.framework == "tensorflow":
            pred = model.predict(latest_features.values, verbose=0)[0]
            # Convert single value tensor/array to scalar if needed
            if hasattr(pred, "item"): pred = pred.item()
            elif isinstance(pred, (list, tuple)): pred = pred[0]
        elif self.framework == "torch":
            import torch
            with torch.no_grad():
                tensor_input = torch.tensor(latest_features.values, dtype=torch.float32)
                pred = model(tensor_input).item()
        
        # Map output
        signal = "HOLD"
        reason = f"Pretrained {self.framework} model prediction: {pred}"
        
        # If output_mapping is defined, use it
        if self.output_mapping:
            # Try exact match, or round if it's float
            mapped = self.output_mapping.get(pred) or self.output_mapping.get(round(pred))
            if mapped:
                signal = mapped
        else:
            # Fallback heuristic
            if pred > 0.5: signal = "BUY"
            elif pred < -0.5: signal = "SELL"
            
        # ATR logic for overlays/markers reused from Phase 3 reference if needed, 
        # but for pretrained we just return the signal.
        return AlgoResult(
            signal=signal,
            confidence=0.8, # Placeholder
            reason=reason,
            overlays={},
            markers=[]
        )
