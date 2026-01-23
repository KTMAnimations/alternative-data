"""Database models for movie box office data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, Integer, BigInteger,
    Index, ForeignKey, Date, Numeric
)

from src.models.database import Base


class BoxOfficeDaily(Base):
    """Daily movie box office data.

    Daily theatrical revenue from major distributors.
    Mapped to studio tickers for entertainment sector analysis.
    """
    __tablename__ = "box_office_daily"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)

    # Movie identification
    movie_title = Column(String(500), nullable=False)
    movie_id = Column(String(50))  # External ID if available

    # Distributor/studio
    distributor = Column(String(200))
    distributor_ticker = Column(String(20), index=True)  # Mapped ticker

    # Box office metrics
    daily_gross = Column(Numeric(15, 2))  # Daily revenue
    cumulative_gross = Column(Numeric(15, 2))  # Total to date
    theater_count = Column(Integer)
    per_theater_avg = Column(Numeric(10, 2))
    days_in_release = Column(Integer)

    # Rankings
    daily_rank = Column(Integer)
    is_new_release = Column(String(5))  # Yes/No

    # Lineage
    raw_data_id = Column(BigInteger, ForeignKey("raw_data_catalog.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_boxoffice_date_movie", "date", "movie_title"),
        Index("ix_boxoffice_distributor", "distributor_ticker", "date"),
    )


# Studio to ticker mapping
STUDIO_TICKER_MAP = {
    "Walt Disney Studios": "DIS",
    "Disney": "DIS",
    "Marvel Studios": "DIS",
    "Pixar": "DIS",
    "Lucasfilm": "DIS",
    "20th Century Studios": "DIS",
    "Warner Bros.": "WBD",
    "Warner Bros": "WBD",
    "New Line Cinema": "WBD",
    "DC Studios": "WBD",
    "Paramount Pictures": "PARA",
    "Paramount": "PARA",
    "Universal Pictures": "CMCSA",
    "Universal": "CMCSA",
    "Focus Features": "CMCSA",
    "DreamWorks Animation": "CMCSA",
    "Sony Pictures": "SONY",
    "Sony": "SONY",
    "Columbia Pictures": "SONY",
    "TriStar Pictures": "SONY",
    "Lionsgate": "LGF.A",
    "Lions Gate": "LGF.A",
    "Summit Entertainment": "LGF.A",
    "A24": None,  # Private
    "Amazon Studios": "AMZN",
    "Apple TV+": "AAPL",
    "Apple": "AAPL",
    "Netflix": "NFLX",
    "MGM": "AMZN",  # Amazon acquired MGM
}
