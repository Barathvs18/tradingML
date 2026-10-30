from dataclasses import dataclass

@dataclass
class Stock:
    symbol: str
    name: str
    exchange: str
