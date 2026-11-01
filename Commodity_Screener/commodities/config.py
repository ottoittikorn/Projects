"""Project paths and the commodity registry.

The registry is the single place that knows which ticker / page / series id each source uses
for a commodity, and how to convert that source's unit into the commodity's standard unit.
Everything downstream works in the standard unit and never needs to know where data came from.
"""
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
FIGURES_DIR = ROOT / "outputs" / "figures"
TABLES_DIR = ROOT / "outputs" / "tables"

LB_PER_TONNE = 2204.62  # COMEX copper is quoted in USD/lb, LME in USD/tonne


@dataclass(frozen=True)
class SourceSpec:
    id: str             # ticker, Westmetall field, FRED series id or Pink Sheet column
    factor: float = 1.0  # multiply source values by this to get the standard unit


@dataclass(frozen=True)
class Commodity:
    key: str
    name: str
    group: str  # "energy", "precious" or "base"
    unit: str
    sources: dict = field(default_factory=dict)
    screen: bool = True  # False = kept for later phases, not in the screener


_REGISTRY = [
    Commodity("natgas_us", "US natural gas (Henry Hub)", "energy", "USD/MMBtu", {
        "yahoo": SourceSpec("NG=F"),
        "fred": SourceSpec("PNGASUSUSDM"),
        "worldbank": SourceSpec("Natural gas, US"),
    }),
    Commodity("wti", "WTI crude oil", "energy", "USD/bbl", {
        "yahoo": SourceSpec("CL=F"),
        "fred": SourceSpec("POILWTIUSDM"),
        "worldbank": SourceSpec("Crude oil, WTI"),
    }),
    Commodity("brent", "Brent crude oil", "energy", "USD/bbl", {
        "yahoo": SourceSpec("BZ=F"),
        "fred": SourceSpec("POILBREUSDM"),
        "worldbank": SourceSpec("Crude oil, Brent"),
    }),
    # FRED dropped its LBMA gold and silver series in 2022, so the long history is World Bank only.
    Commodity("gold", "Gold", "precious", "USD/oz", {
        "yahoo": SourceSpec("GC=F"),
        "worldbank": SourceSpec("Gold"),
    }),
    Commodity("silver", "Silver", "precious", "USD/oz", {
        "yahoo": SourceSpec("SI=F"),
        "worldbank": SourceSpec("Silver"),
    }),
    Commodity("copper", "Copper", "base", "USD/t", {
        "yahoo": SourceSpec("HG=F", factor=LB_PER_TONNE),
        "lme_cash": SourceSpec("LME_Cu_cash"),
        "lme_3m": SourceSpec("LME_Cu_cash"),  # same Westmetall page, different column
        "fred": SourceSpec("PCOPPUSDM"),
        "worldbank": SourceSpec("Copper"),
    }),
    Commodity("aluminium", "Aluminium", "base", "USD/t", {
        "yahoo": SourceSpec("ALI=F"),
        "lme_cash": SourceSpec("LME_Al_cash"),
        "lme_3m": SourceSpec("LME_Al_cash"),
        "fred": SourceSpec("PALUMUSDM"),
        "worldbank": SourceSpec("Aluminum"),
    }),
    # Later phase (gas spreads / LNG arbitrage): monthly regional gas benchmarks.
    Commodity("natgas_eu", "Europe natural gas (TTF)", "energy", "USD/MMBtu", {
        "fred": SourceSpec("PNGASEUUSDM"),
        "worldbank": SourceSpec("Natural gas, Europe"),
    }, screen=False),
    Commodity("lng_japan", "Japan LNG", "energy", "USD/MMBtu", {
        "fred": SourceSpec("PNGASJPUSDM"),
        "worldbank": SourceSpec("Liquefied natural gas, Japan"),
    }, screen=False),
]

COMMODITIES = {c.key: c for c in _REGISTRY}
SCREENER = [c.key for c in _REGISTRY if c.screen]

# Daily source used by the screener for each commodity. Notebook 01 compares ALI=F and HG=F
# with the LME and explains these choices.
DAILY_SOURCE = {key: "yahoo" for key in SCREENER} | {"aluminium": "lme_3m"}

# Longest monthly history (1960+, includes gold and silver), used for seasonality.
MONTHLY_SOURCE = "worldbank"

# FCA/ESMA maximum retail leverage: 20:1 for gold, 10:1 for other commodities.
# A broker can demand more margin than this, so check the instrument page on Trading 212.
RETAIL_LEVERAGE = {key: 10 for key in SCREENER} | {"gold": 20}

# Fixed colour per commodity, in the validated categorical order (see plots.py).
COLORS = {
    "natgas_us": "#2a78d6", "wti": "#eb6834", "brent": "#1baf7a", "gold": "#eda100",
    "silver": "#e87ba4", "copper": "#008300", "aluminium": "#6250d6",
}
SHORT_NAMES = {
    "natgas_us": "US gas", "wti": "WTI", "brent": "Brent", "gold": "Gold",
    "silver": "Silver", "copper": "Copper", "aluminium": "Aluminium",
}
