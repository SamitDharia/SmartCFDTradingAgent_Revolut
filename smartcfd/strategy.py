from abc import ABC, abstractmethod
import logging
from typing import List, Dict, Any, Tuple
from pathlib import Path
import joblib
import pandas as pd
from datetime import datetime, timedelta

from smartcfd.alpaca_client import AlpacaClient
from smartcfd.data_loader import DataLoader, is_data_stale, has_data_gaps, has_anomalous_data, _parse_interval
from alpaca.data.timeframe import TimeFrame
from .indicators import create_features as calculate_indicators
from .config import load_config
from .portfolio import PortfolioManager

log = logging.getLogger("strategy")

class Strategy(ABC):
    """
    Abstract base class for a trading strategy.
    """
    @abstractmethod
    def evaluate(self, portfolio_manager: PortfolioManager, watch_list: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, pd.DataFrame]]:
        """
        Evaluate the strategy and return a list of proposed actions and the data used.
        
        :param portfolio_manager: An instance of PortfolioManager to access portfolio state.
        :param watch_list: A list of symbols to evaluate.
        :return: A tuple containing:
                 - A list of dictionaries, each representing a proposed action.
                 - A dictionary mapping symbols to the DataFrame of historical data used.
        """
        pass

class DryRunStrategy(Strategy):
    """
    A simple strategy that logs the account information and proposes no actions.
    This is useful for verifying that the strategy evaluation pipeline is working.
    """
    def evaluate(self, portfolio_manager: PortfolioManager, watch_list: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, pd.DataFrame]]:
        log.info("strategy.dry_run.evaluate")
        try:
            log.info("strategy.dry_run.watching", extra={"extra": {"symbols": watch_list}})
            
            actions = [
                {"action": "log", "symbol": symbol, "decision": "hold", "reason": "dry_run"}
                for symbol in watch_list
            ]
            # Return empty data dictionary as no data was fetched
            return actions, {}
        except Exception as e:
            log.error("strategy.dry_run.fail", extra={"extra": {"error": repr(e)}})
            return [], {}

class InferenceStrategy(Strategy):
    """
    A strategy that uses a trained model to make trading decisions.
    """
    def __init__(self, model_path: str = "models/model.joblib"):
        self.model_path = Path(model_path)
        self.model = self.load_model()
        # Load data integrity check settings from config
        app_config = load_config()
        self.max_data_staleness_minutes = app_config.max_data_staleness_minutes
        self.trade_interval_str = app_config.trade_interval

    def load_model(self) -> object | None:
        """Loads the model from the specified path."""
        if self.model_path and self.model_path.exists():
            try:
                model = joblib.load(self.model_path)
                log.info(f"strategy.inference.model_loaded", extra={"extra": {"model_path": str(self.model_path)}})
                return model
            except Exception as e:
                log.error(f"strategy.inference.model_load_fail", extra={"extra": {"error": repr(e)}})
                return None
        else:
            log.warning(f"strategy.inference.no_model_found", extra={"extra": {"path": str(self.model_path)}})
            return None

    def evaluate(self, portfolio_manager: PortfolioManager, watch_list: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, pd.DataFrame]]:
        if not self.model:
            log.warning("strategy.inference.evaluate.no_model", extra={"extra": {"reason": "Model not loaded."}})
            actions = [{"action": "log", "symbol": symbol, "decision": "hold", "reason": "no_model"} for symbol in watch_list]
            return actions, {}
        
        all_actions = []
        all_historical_data = {}
        
        for symbol in watch_list:
            log.info("strategy.inference.evaluate.start", extra={"extra": {"symbol": symbol}})
            
            try:
                # 1. Fetch live market data for the symbol.
                data_loader = DataLoader(api_base=portfolio_manager.client.api_base)
                # Fetch more data for gap check
                data = data_loader.get_market_data([symbol], self.trade_interval_str, limit=200)
                
                # Store data in a dictionary to return
                all_historical_data[symbol] = data

                if data is None or data.empty:
                    log.warning("strategy.inference.evaluate.no_data", extra={"extra": {"symbol": symbol}})
                    action = {"action": "log", "symbol": symbol, "decision": "hold", "reason": "no_data"}
                    all_actions.append(action)
                    continue

                # 2. Perform data integrity checks
                if is_data_stale(data, self.max_data_staleness_minutes):
                    log.warning(
                        "strategy.inference.evaluate.data_stale",
                        extra={"extra": {"symbol": symbol, "max_staleness_minutes": self.max_data_staleness_minutes}},
                    )
                    action = {"action": "log", "symbol": symbol, "decision": "hold", "reason": "data_stale"}
                    all_actions.append(action)
                    continue
                
                trade_interval_tf = _parse_interval(self.trade_interval_str)
                if has_data_gaps(data, trade_interval_tf):
                    log.warning(
                        "strategy.inference.evaluate.data_gaps",
                        extra={"extra": {"symbol": symbol, "interval": self.trade_interval_str}},
                    )
                    action = {"action": "log", "symbol": symbol, "decision": "hold", "reason": "data_gaps_detected"}
                    all_actions.append(action)
                    continue

                if has_anomalous_data(data):
                    log.warning(
                        "strategy.inference.evaluate.anomalous_data",
                        extra={"extra": {"symbol": symbol}},
                    )
                    action = {"action": "log", "symbol": symbol, "decision": "hold", "reason": "anomalous_data_detected"}
                    all_actions.append(action)
                    continue

                # 3. Calculate features from the data.
                log.info("strategy.inference.evaluate.calculating_features", extra={"extra": {"symbol": symbol}})
                features = calculate_indicators(data)
                if features.empty:
                    log.warning("strategy.inference.evaluate.no_features", extra={"extra": {"symbol": symbol}})
                    action = {"action": "log", "symbol": symbol, "decision": "hold", "reason": "feature_calculation_failed"}
                    all_actions.append(action)
                    continue

                # 4. Make a prediction using the model.
                latest_features = features.iloc[-1:]
                
                # Ensure the feature names match what the model was trained on
                model_features = self.model.get_booster().feature_names
                latest_features_aligned = latest_features[model_features]

                prediction = self.model.predict(latest_features_aligned)[0]
                try:
                    prediction_proba = self.model.predict_proba(latest_features_aligned)[0]
                    prediction_proba_serializable = [float(p) for p in prediction_proba]
                except AttributeError:
                    prediction_proba_serializable = None
                
                # 5. Translate the prediction into an action, checking for existing positions.
                
                # Check if a position already exists for this symbol
                if symbol in portfolio_manager.positions:
                    log.info(
                        "strategy.inference.evaluate.position_exists",
                        extra={"extra": {"symbol": symbol, "reason": "Holding due to existing position."}}
                    )
                    action_item = {"action": "log", "symbol": symbol, "decision": "hold", "reason": "position_exists"}
                elif prediction == 1:
                    decision = "buy"
                    action_item = {"action": "buy", "symbol": symbol, "decision": decision}
                elif prediction == 2:
                    decision = "sell"
                    action_item = {"action": "sell", "symbol": symbol, "decision": decision}
                else:
                    decision = "hold" # Simplified: only act on buy signals
                    action_item = {"action": "log", "symbol": symbol, "decision": "hold", "reason": "model_hold"}
                
                # Log the decision and key data
                log_extra = {
                    "symbol": symbol,
                    "prediction": int(prediction),
                    "decision": action_item.get("decision", "hold"),
                    "prediction_proba": prediction_proba_serializable,
                    "features": latest_features_aligned.to_dict(orient='records')[0]
                }
                log.info("strategy.inference.evaluate.prediction", extra={"extra": log_extra})
                all_actions.append(action_item)
            
            except Exception:
                log.error(
                    "strategy.inference.evaluate.fail",
                    extra={"extra": {"symbol": symbol}},
                    exc_info=True
                )
                action = {"action": "log", "symbol": symbol, "decision": "hold", "reason": "evaluation_exception"}
                all_actions.append(action)

        return all_actions, all_historical_data


def get_strategy_by_name(name: str) -> Strategy:
    """
    A simple factory to get a strategy instance by name.
    """
    if name == "dry_run":
        return DryRunStrategy()
    elif name == "inference":
        return InferenceStrategy()
    # Add other strategies here
    # elif name == "moving_average_crossover":
    #     return MovingAverageCrossoverStrategy()
    else:
        raise ValueError(f"Unknown strategy: {name}")
