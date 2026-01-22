"""Database models for Reddit sentiment data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, Integer, BigInteger,
    Index, JSON, Text, Date, Boolean
)

from src.models.database import Base


class RedditPost(Base):
    """Reddit posts from tracked subreddits."""
    __tablename__ = "reddit_posts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    post_id = Column(String(20), nullable=False, unique=True, index=True)
    subreddit = Column(String(100), nullable=False, index=True)
    title = Column(Text, nullable=False)
    selftext = Column(Text)
    author = Column(String(100))
    score = Column(Integer)
    upvote_ratio = Column(Float)
    num_comments = Column(Integer)
    created_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    url = Column(Text)
    is_self = Column(Boolean)
    link_flair_text = Column(String(100))
    fetched_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Extracted entities
    mentioned_tickers = Column(JSON)  # List of tickers mentioned
    mentioned_companies = Column(JSON)  # List of company names

    __table_args__ = (
        Index("ix_reddit_post_sub_created", "subreddit", "created_utc"),
    )


class RedditComment(Base):
    """Reddit comments from tracked posts."""
    __tablename__ = "reddit_comments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    comment_id = Column(String(20), nullable=False, unique=True, index=True)
    post_id = Column(String(20), nullable=False, index=True)
    subreddit = Column(String(100), nullable=False, index=True)
    body = Column(Text, nullable=False)
    author = Column(String(100))
    score = Column(Integer)
    created_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    parent_id = Column(String(20))
    is_submitter = Column(Boolean)
    fetched_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_reddit_comment_post", "post_id"),
        Index("ix_reddit_comment_sub_created", "subreddit", "created_utc"),
    )


class SentimentScore(Base):
    """Sentiment scores for Reddit content."""
    __tablename__ = "sentiment_scores"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    content_type = Column(String(20), nullable=False)  # 'post' or 'comment'
    content_id = Column(String(20), nullable=False, index=True)
    subreddit = Column(String(100), index=True)

    # Sentiment scores
    sentiment_label = Column(String(20))  # positive, negative, neutral
    sentiment_score = Column(Float)  # -1 to 1
    confidence = Column(Float)  # 0 to 1

    # FinBERT specific
    positive_prob = Column(Float)
    negative_prob = Column(Float)
    neutral_prob = Column(Float)

    model_version = Column(String(50))
    analyzed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_sentiment_content", "content_type", "content_id"),
        Index("ix_sentiment_sub", "subreddit"),
    )


class SubredditSentimentDaily(Base):
    """Daily aggregated sentiment by subreddit."""
    __tablename__ = "subreddit_sentiment_daily"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    subreddit = Column(String(100), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    # Aggregated metrics
    post_count = Column(Integer)
    comment_count = Column(Integer)
    total_score = Column(Integer)
    avg_upvote_ratio = Column(Float)

    # Sentiment aggregates
    avg_sentiment = Column(Float)  # -1 to 1
    positive_ratio = Column(Float)  # % of positive posts
    negative_ratio = Column(Float)  # % of negative posts
    neutral_ratio = Column(Float)  # % of neutral posts

    # Volume-weighted sentiment
    weighted_sentiment = Column(Float)

    computed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_sub_sent_daily_sub_date", "subreddit", "date"),
    )


class TickerMention(Base):
    """Ticker mentions extracted from Reddit."""
    __tablename__ = "ticker_mentions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    subreddit = Column(String(100), nullable=False, index=True)
    content_type = Column(String(20), nullable=False)  # 'post' or 'comment'
    content_id = Column(String(20), nullable=False)
    created_utc = Column(DateTime(timezone=True), nullable=False, index=True)

    # Sentiment at mention
    sentiment_score = Column(Float)
    context_text = Column(Text)  # Surrounding text

    __table_args__ = (
        Index("ix_ticker_mention_ticker_date", "ticker", "created_utc"),
        Index("ix_ticker_mention_sub", "subreddit"),
    )


class TickerSentimentDaily(Base):
    """Daily aggregated sentiment by ticker."""
    __tablename__ = "ticker_sentiment_daily"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    # Mention counts
    mention_count = Column(Integer)
    post_mentions = Column(Integer)
    comment_mentions = Column(Integer)

    # Sentiment
    avg_sentiment = Column(Float)
    positive_mentions = Column(Integer)
    negative_mentions = Column(Integer)
    neutral_mentions = Column(Integer)

    # Source subreddits
    top_subreddits = Column(JSON)  # List of {subreddit: count}

    computed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_ticker_sent_daily_ticker_date", "ticker", "date"),
    )
