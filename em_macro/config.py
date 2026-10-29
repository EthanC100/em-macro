"""Static configuration: countries, series identifiers, sample split."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"            # cached downloads (gitignored)
PROC = ROOT / "data" / "processed"     # cleaned daily / monthly panels
EVENTS = ROOT / "data" / "events"      # event calendars
RESULTS = ROOT / "results"

START = "2005-01-01"
FIT_END = "2021-12-31"     # estimation sample: 2005-2021
TEST_START = "2022-01-01"  # hold-out: 2022 onward, evaluated once

COUNTRIES = ["BR", "MX", "ZA", "TR", "ID", "PL"]
NAMES = {"BR": "Brazil", "MX": "Mexico", "ZA": "South Africa",
         "TR": "Turkey", "ID": "Indonesia", "PL": "Poland"}
ISO3 = {"BR": "BRA", "MX": "MEX", "ZA": "ZAF", "TR": "TUR", "ID": "IDN", "PL": "POL"}
CCY = {"BR": "BRL", "MX": "MXN", "ZA": "ZAR", "TR": "TRY", "ID": "IDR", "PL": "PLN"}

# Spot FX, local currency per USD.  Primary source per country; the others are
# downloaded as cross-checks for the coverage report.
FX_PRIMARY = {
    "BR": ("fred", "DEXBZUS"),   # FRB H.10 noon NY buying rate
    "MX": ("fred", "DEXMXUS"),
    "ZA": ("fred", "DEXSFUS"),
    "TR": ("yahoo", "TRY=X"),    # not in H.10
    "ID": ("yahoo", "IDR=X"),
    "PL": ("yahoo", "PLN=X"),
}
FX_CHECK = {
    "BR": ("bcb_sgs", 1),            # PTAX sell
    "MX": ("banxico", "SF43718"),    # FIX
    "ZA": ("sarb", "EXCX135D"),      # SARB rand per USD
    "TR": None,
    "ID": None,
    "PL": ("nbp", "usd"),            # NBP table A mid fixing
}

# US / global controls
GLOBAL = {
    "US10Y": ("fred", "DGS10"),
    "VIX": ("fred", "VIXCLS"),
    "DXY": ("yahoo", "DX-Y.NYB"),         # ICE US dollar index
    "USD_BROAD": ("fred", "DTWEXBGS"),    # Fed broad dollar index (2006+), cross-check
    "US_FF": ("fred", "DFF"),             # effective fed funds
}

# BIS central bank policy rates (daily), WS_CBPOL
BIS_POLICY = {"BR": "BR", "MX": "MX", "ZA": "ZA", "TR": "TR", "ID": "ID", "PL": "PL", "US": "US"}

# Monthly long-term government bond yields (OECD MEI via FRED), used only as a
# level cross-check / monthly fallback
FRED_LT_MONTHLY = {"MX": "IRLTLT01MXM156N", "ZA": "IRLTLT01ZAM156N", "PL": "IRLTLT01PLM156N"}

# Banxico SIE (public JSON behind the SIE web charts, no token needed)
BANXICO_MBONO_7_10 = {"days": "SF45430", "clean": "SF45454", "dirty": "SF45455", "coupon": "SF45478"}
BANXICO_TIIE28 = "SF43783"
SARB_10Y = "CMJD004A"       # daily average yield, govt bonds 10y and longer
SARB_JIBAR3M = "MMRD403A"
BCB_CDI = 12                # SGS: CDI daily rate, % per day
TESOURO_URL = ("https://www.tesourotransparente.gov.br/ckan/dataset/"
               "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
               "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv")
