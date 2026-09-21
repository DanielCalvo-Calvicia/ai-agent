"""What one LLM call was billed, from the price files in config/ (USD per 1M tokens)."""
import json
import os
from typing import Dict, Optional, Tuple

CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config')
PRICE_FILES = ("gemini_models.json", "other_models.json")


def load_prices(config_dir: str = CONFIG_DIR) -> Dict[str, Tuple[float, float]]:
    """model id -> (input price, output price). A missing file just gives fewer models."""
    prices: Dict[str, Tuple[float, float]] = {}
    for name in PRICE_FILES:
        try:
            with open(os.path.join(config_dir, name), "r", encoding="utf-8") as f:
                for model in json.load(f)["models"]:
                    prices[model["id"]] = (float(model["input"]), float(model["output"]))
        except (OSError, ValueError, KeyError):
            continue
    return prices


def billed_output_tokens(prompt: int, completion: int, total: int) -> int:
    """Answered tokens plus hidden thinking. Google reports thinking only in the total (total - sent - answered)."""
    return max(completion, total - prompt)


def cost_usd(prices: Dict[str, Tuple[float, float]], model: str, prompt: int, completion: int, total: int) -> Optional[float]:
    """None when the model has no price in the files."""
    if model not in prices:
        return None
    price_in, price_out = prices[model]
    return (prompt * price_in + billed_output_tokens(prompt, completion, total) * price_out) / 1e6
