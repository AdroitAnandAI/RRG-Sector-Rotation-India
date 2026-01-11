"""
Sector definitions for Indian stock market
Stock symbols for different sectors
Tokens will be fetched automatically from scrip master JSON
"""
# Format: {sector_name: [symbol, ...]}

SECTORS = {
    "Banking": [
        "HDFCBANK-EQ",
        "ICICIBANK-EQ",
        "SBIN-EQ",
        "KOTAKBANK-EQ",
        "AXISBANK-EQ",
        "INDUSINDBK-EQ",
        "FEDERALBNK-EQ",
        "PNB-EQ",
        "BANKBARODA-EQ",
        "UNIONBANK-EQ",
    ],
    "IT": [
        "TCS-EQ",
        "INFY-EQ",
        "HCLTECH-EQ",
        "TECHM-EQ",
        "WIPRO-EQ",
        "LTIM-EQ",
        "MPHASIS-EQ",
        "PERSISTENT-EQ",
        "COFORGE-EQ",
        "ZENSARTECH-EQ",
    ],
    "Pharma": [
        "SUNPHARMA-EQ",
        "DRREDDY-EQ",
        "CIPLA-EQ",
        "LUPIN-EQ",
        "TORNTPHARM-EQ",
        "GLENMARK-EQ",
        "ZYDUSLIFE-EQ",
        "DIVISLAB-EQ",
        "AUROPHARMA-EQ",
        "BIOCON-EQ",
    ],
    "Auto": [
        "MARUTI-EQ",
        "M&M-EQ",
        "TATAMOTORS-EQ",
        "BAJAJ-AUTO-EQ",
        "HEROMOTOCO-EQ",
        "EICHERMOT-EQ",
        "ASHOKLEY-EQ",
        "TVSMOTOR-EQ",
        "BHARATFORG-EQ",
        "MRF-EQ",
    ],
    "FMCG": [
        "HINDUNILVR-EQ",
        "ITC-EQ",
        "NESTLEIND-EQ",
        "BRITANNIA-EQ",
        "DABUR-EQ",
        "MARICO-EQ",
        "GODREJCP-EQ",
        "COLPAL-EQ",
        "TATACONSUM-EQ",
        "EMAMILTD-EQ",
    ],
    "Energy": [
        "RELIANCE-EQ",
        "ONGC-EQ",
        "IOC-EQ",
        "BPCL-EQ",
        "HINDPETRO-EQ",
        "GAIL-EQ",
        "ADANIENT-EQ",
        "ADANIGREEN-EQ",
        "TATAPOWER-EQ",
        "NTPC-EQ",
    ],
    "Metals": [
        "TATASTEEL-EQ",
        "JSWSTEEL-EQ",
        "SAIL-EQ",
        "VEDL-EQ",
        "HINDALCO-EQ",
        "NMDC-EQ",
        "NATIONALUM-EQ",
        "HINDZINC-EQ",
        "JINDALSAW-EQ",
        "RATNAMANI-EQ",
    ],
    "Telecom": [
        "BHARTIARTL-EQ",
        "RELIANCE-EQ",
        "IDEA-EQ",
    ],
    "Cement": [
        "ULTRACEMCO-EQ",
        "SHREECEM-EQ",
        "ACC-EQ",
        "AMBUJACEM-EQ",
        "DALMIABHA-EQ",
        "RAMCOCEM-EQ",
        "JKLAKSHMI-EQ",
        "ORIENTCEM-EQ",
    ],
    "Real Estate": [
        "DLF-EQ",
        "GODREJPROP-EQ",
        "OBEROIRLTY-EQ",
        "PRESTIGE-EQ",
        "SOBHA-EQ",
        "BRIGADE-EQ",
        "MAHLIFE-EQ",
        "PHOENIXLTD-EQ",
    ],
    "Finance": [
        "HDFCBANK-EQ",
        "ICICIBANK-EQ",
        "SBIN-EQ",
        "KOTAKBANK-EQ",
        "AXISBANK-EQ",
        "HDFC-EQ",
        "ICICIPRULI-EQ",
        "BAJFINANCE-EQ",
        "SBILIFE-EQ",
        "HDFCLIFE-EQ",
    ],
}

# Sub-sectors for each major sector
SUB_SECTORS = {
    # Banking sub-sectors
    "Private Banks": [
        "HDFCBANK-EQ",
        "ICICIBANK-EQ",
        "KOTAKBANK-EQ",
        "AXISBANK-EQ",
        "INDUSINDBK-EQ",
        "FEDERALBNK-EQ",
        "YESBANK-EQ",
        "IDFCFIRSTB-EQ",
    ],
    "PSU Banks": [
        "SBIN-EQ",
        "PNB-EQ",
        "BANKBARODA-EQ",
        "UNIONBANK-EQ",
        "CANBK-EQ",
        "INDIANB-EQ",
        "CENTRALBK-EQ",
        "IOB-EQ",
    ],
    # IT sub-sectors
    "IT Services": [
        "TCS-EQ",
        "INFY-EQ",
        "HCLTECH-EQ",
        "TECHM-EQ",
        "WIPRO-EQ",
        "LTIM-EQ",
        "MPHASIS-EQ",
        "PERSISTENT-EQ",
    ],
    "IT Products": [
        "COFORGE-EQ",
        "ZENSARTECH-EQ",
        "MINDTREE-EQ",
        "LTI-EQ",
    ],
    # Pharma sub-sectors
    "Pharma - Large Cap": [
        "SUNPHARMA-EQ",
        "DRREDDY-EQ",
        "CIPLA-EQ",
        "LUPIN-EQ",
        "TORNTPHARM-EQ",
    ],
    "Pharma - Mid Cap": [
        "GLENMARK-EQ",
        "ZYDUSLIFE-EQ",
        "DIVISLAB-EQ",
        "AUROPHARMA-EQ",
        "BIOCON-EQ",
    ],
    # Auto sub-sectors
    "Passenger Vehicles": [
        "MARUTI-EQ",
        "M&M-EQ",
        "TATAMOTORS-EQ",
        "BAJAJ-AUTO-EQ",
    ],
    "Two Wheelers": [
        "HEROMOTOCO-EQ",
        "EICHERMOT-EQ",
        "TVSMOTOR-EQ",
        "BAJAJ-AUTO-EQ",
    ],
    "Auto Ancillaries": [
        "ASHOKLEY-EQ",
        "BHARATFORG-EQ",
        "MRF-EQ",
        "APOLLOTYRE-EQ",
    ],
    # FMCG sub-sectors
    "FMCG - Personal Care": [
        "HINDUNILVR-EQ",
        "DABUR-EQ",
        "MARICO-EQ",
        "GODREJCP-EQ",
        "COLPAL-EQ",
    ],
    "FMCG - Food & Beverages": [
        "ITC-EQ",
        "NESTLEIND-EQ",
        "BRITANNIA-EQ",
        "TATACONSUM-EQ",
        "EMAMILTD-EQ",
    ],
    # Energy sub-sectors
    "Oil & Gas - Refining": [
        "RELIANCE-EQ",
        "IOC-EQ",
        "BPCL-EQ",
        "HINDPETRO-EQ",
    ],
    "Oil & Gas - Exploration": [
        "ONGC-EQ",
        "GAIL-EQ",
        "OIL-EQ",
    ],
    "Power": [
        "TATAPOWER-EQ",
        "NTPC-EQ",
        "ADANIENT-EQ",
        "ADANIGREEN-EQ",
    ],
    # Metals sub-sectors
    "Steel": [
        "TATASTEEL-EQ",
        "JSWSTEEL-EQ",
        "SAIL-EQ",
        "JINDALSTEL-EQ",
    ],
    "Non-Ferrous Metals": [
        "VEDL-EQ",
        "HINDALCO-EQ",
        "HINDZINC-EQ",
        "NATIONALUM-EQ",
    ],
    "Mining": [
        "NMDC-EQ",
        "COALINDIA-EQ",
    ],
    # Finance sub-sectors
    "Finance - Private Banks": [
        "HDFCBANK-EQ",
        "ICICIBANK-EQ",
        "KOTAKBANK-EQ",
        "AXISBANK-EQ",
    ],
    "Finance - PSU Banks": [
        "SBIN-EQ",
        "PNB-EQ",
        "BANKBARODA-EQ",
        "UNIONBANK-EQ",
    ],
    "Finance - NBFCs": [
        "BAJFINANCE-EQ",
        "HDFC-EQ",
        "M&MFIN-EQ",
        "POWERGRID-EQ",
    ],
    "Finance - Insurance": [
        "SBILIFE-EQ",
        "HDFCLIFE-EQ",
        "ICICIPRULI-EQ",
        "LICI-EQ",
    ],
}

# Benchmark indices
# Format: {name: symbol}
# Tokens will be fetched automatically from scrip master JSON or use hardcoded fallback
# Note: Benchmarks may not have -EQ suffix in scrip master, so we try both formats
BENCHMARKS = {
    "NIFTY 50": "Nifty 50",  # Token: 99926000
    "NIFTY BANK": "Nifty Bank",  # Token: 99926009
    "NIFTY IT": "Nifty IT",  # Token: 99926008
    "NIFTY PHARMA": "Nifty Pharma",  # Token: 99926023
    "NIFTY AUTO": "Nifty Auto",  # Token: 99926029
    "NIFTY FMCG": "Nifty FMCG",  # Token: 99926021
    "NIFTY ENERGY": "Nifty Energy",  # Token: 99926020
    "NIFTY METAL": "Nifty Metal",  # Token: 99926030
}

