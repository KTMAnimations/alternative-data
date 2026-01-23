"""Studio to stock ticker mapping for box office data."""

from typing import Optional


# Primary studio mappings with variations
STUDIO_TICKER_MAP: dict[str, str] = {
    # Disney and subsidiaries
    "Disney": "DIS",
    "Walt Disney": "DIS",
    "Walt Disney Studios": "DIS",
    "Walt Disney Pictures": "DIS",
    "Buena Vista": "DIS",
    "Buena Vista Pictures": "DIS",
    "Marvel": "DIS",
    "Marvel Studios": "DIS",
    "Lucasfilm": "DIS",
    "Pixar": "DIS",
    "20th Century": "DIS",
    "20th Century Studios": "DIS",
    "20th Century Fox": "DIS",
    "Searchlight": "DIS",
    "Searchlight Pictures": "DIS",
    "Fox Searchlight": "DIS",
    # Warner Bros Discovery
    "Warner Bros": "WBD",
    "Warner Bros.": "WBD",
    "Warner Bros. Pictures": "WBD",
    "Warner": "WBD",
    "WB": "WBD",
    "New Line": "WBD",
    "New Line Cinema": "WBD",
    "HBO Films": "WBD",
    "Castle Rock": "WBD",
    # Paramount (part of Paramount Global)
    "Paramount": "PARA",
    "Paramount Pictures": "PARA",
    "Paramount Vantage": "PARA",
    "Miramax": "PARA",
    # Universal (Comcast/NBCUniversal)
    "Universal": "CMCSA",
    "Universal Pictures": "CMCSA",
    "Universal Studios": "CMCSA",
    "Focus": "CMCSA",
    "Focus Features": "CMCSA",
    "DreamWorks": "CMCSA",
    "DreamWorks Animation": "CMCSA",
    "Illumination": "CMCSA",
    "Working Title": "CMCSA",
    # Sony Pictures
    "Sony": "SONY",
    "Sony Pictures": "SONY",
    "Sony Pictures Releasing": "SONY",
    "Columbia": "SONY",
    "Columbia Pictures": "SONY",
    "TriStar": "SONY",
    "TriStar Pictures": "SONY",
    "Screen Gems": "SONY",
    "Sony Pictures Classics": "SONY",
}

# Primary tickers for box office analysis
PRIMARY_TICKERS = ["DIS", "WBD", "PARA", "CMCSA", "SONY"]

# Canonical studio names for each ticker
TICKER_TO_STUDIO: dict[str, str] = {
    "DIS": "Disney",
    "WBD": "Warner Bros",
    "PARA": "Paramount",
    "CMCSA": "Universal",
    "SONY": "Sony Pictures",
}


def get_ticker_for_studio(studio_name: str) -> Optional[str]:
    """Map a studio/distributor name to its stock ticker.

    Args:
        studio_name: The distributor name from box office data

    Returns:
        Stock ticker symbol or None if no mapping found
    """
    if not studio_name:
        return None

    # Direct match
    if studio_name in STUDIO_TICKER_MAP:
        return STUDIO_TICKER_MAP[studio_name]

    # Case-insensitive match
    studio_lower = studio_name.lower()
    for key, ticker in STUDIO_TICKER_MAP.items():
        if key.lower() == studio_lower:
            return ticker

    # Partial match (studio name contains key)
    for key, ticker in STUDIO_TICKER_MAP.items():
        if key.lower() in studio_lower or studio_lower in key.lower():
            return ticker

    return None


def get_studio_for_ticker(ticker: str) -> Optional[str]:
    """Get canonical studio name for a ticker.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Canonical studio name or None if ticker not found
    """
    return TICKER_TO_STUDIO.get(ticker.upper())


def is_major_studio(studio_name: str) -> bool:
    """Check if a studio is one of the major tracked studios.

    Args:
        studio_name: The distributor name from box office data

    Returns:
        True if this is a major studio we track
    """
    return get_ticker_for_studio(studio_name) is not None
