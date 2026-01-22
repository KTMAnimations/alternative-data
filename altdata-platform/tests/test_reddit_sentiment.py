"""Tests for Reddit sentiment data collection and factors."""

import sys
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

# Mock praw and transformers before importing collector
sys.modules['praw'] = MagicMock()
sys.modules['transformers'] = MagicMock()
sys.modules['torch'] = MagicMock()

from src.collectors.reddit_sentiment import RedditSentimentCollector
from src.models.sentiment import (
    RedditPost,
    RedditComment,
    SentimentScore,
    SubredditSentimentDaily,
    TickerMention,
    TickerSentimentDaily,
)
from src.transformations.factors.sentiment_factors import (
    calc_ticker_sentiment,
    calc_ticker_mention_velocity,
    calc_sentiment_momentum,
    calc_wsb_sentiment,
    calc_retail_attention_index,
    calc_sentiment_dispersion,
    TickerSentiment,
    MentionVelocity,
    SentimentMomentum,
    WSBSentiment,
    RetailAttentionIndex,
    SentimentDispersion,
)


# =============================================================================
# Sentiment Model Tests
# =============================================================================

class TestSentimentModels:
    """Test sentiment database models."""

    def test_reddit_post_model(self):
        """Test RedditPost model creation."""
        post = RedditPost(
            post_id="abc123",
            subreddit="wallstreetbets",
            title="TSLA to the moon!",
            selftext="Buy calls",
            author="diamond_hands",
            score=1500,
            upvote_ratio=0.92,
            num_comments=350,
            created_utc=datetime.utcnow(),
            mentioned_tickers=["TSLA"],
        )
        assert post.post_id == "abc123"
        assert post.subreddit == "wallstreetbets"
        assert "TSLA" in post.mentioned_tickers

    def test_reddit_comment_model(self):
        """Test RedditComment model creation."""
        comment = RedditComment(
            comment_id="xyz789",
            post_id="abc123",
            subreddit="stocks",
            body="I'm bullish on this stock",
            author="trader123",
            score=50,
            created_utc=datetime.utcnow(),
        )
        assert comment.comment_id == "xyz789"
        assert comment.score == 50

    def test_sentiment_score_model(self):
        """Test SentimentScore model creation."""
        score = SentimentScore(
            content_type="post",
            content_id="abc123",
            subreddit="wallstreetbets",
            sentiment_label="positive",
            sentiment_score=0.85,
            confidence=0.92,
            positive_prob=0.85,
            negative_prob=0.05,
            neutral_prob=0.10,
            model_version="finbert-prosus",
        )
        assert score.sentiment_label == "positive"
        assert score.sentiment_score == 0.85
        assert score.model_version == "finbert-prosus"

    def test_subreddit_sentiment_daily_model(self):
        """Test SubredditSentimentDaily model creation."""
        daily = SubredditSentimentDaily(
            subreddit="wallstreetbets",
            date=date.today(),
            post_count=500,
            comment_count=15000,
            avg_sentiment=0.15,
            positive_ratio=0.45,
            negative_ratio=0.30,
            neutral_ratio=0.25,
        )
        assert daily.post_count == 500
        assert daily.avg_sentiment == 0.15

    def test_ticker_mention_model(self):
        """Test TickerMention model creation."""
        mention = TickerMention(
            ticker="GME",
            subreddit="wallstreetbets",
            content_type="post",
            content_id="abc123",
            created_utc=datetime.utcnow(),
            sentiment_score=0.75,
            context_text="GME is going to squeeze!",
        )
        assert mention.ticker == "GME"
        assert mention.sentiment_score == 0.75

    def test_ticker_sentiment_daily_model(self):
        """Test TickerSentimentDaily model creation."""
        daily = TickerSentimentDaily(
            ticker="AAPL",
            date=date.today(),
            mention_count=250,
            post_mentions=50,
            comment_mentions=200,
            avg_sentiment=0.35,
            positive_mentions=125,
            negative_mentions=50,
            neutral_mentions=75,
        )
        assert daily.mention_count == 250
        assert daily.avg_sentiment == 0.35


# =============================================================================
# Reddit Sentiment Collector Tests
# =============================================================================

class TestRedditSentimentCollector:
    """Test Reddit sentiment collector."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        collector = RedditSentimentCollector()
        assert collector.SOURCE_NAME == "reddit_sentiment"

    def test_tracked_subreddits(self):
        """Test tracked subreddits configuration."""
        collector = RedditSentimentCollector()
        assert "wallstreetbets" in collector.TRACKED_SUBREDDITS
        assert "stocks" in collector.TRACKED_SUBREDDITS
        assert "investing" in collector.TRACKED_SUBREDDITS

    def test_extract_tickers_with_dollar_sign(self):
        """Test ticker extraction with $ prefix."""
        collector = RedditSentimentCollector()
        text = "Just bought $TSLA and $AAPL calls!"
        tickers = collector.extract_tickers(text)
        assert "TSLA" in tickers
        assert "AAPL" in tickers

    def test_extract_tickers_without_dollar_sign(self):
        """Test ticker extraction without $ prefix."""
        collector = RedditSentimentCollector()
        text = "NVDA earnings looking good, might buy AMD too"
        tickers = collector.extract_tickers(text)
        assert "NVDA" in tickers
        assert "AMD" in tickers

    def test_extract_tickers_excludes_common_words(self):
        """Test that common words are excluded from tickers."""
        collector = RedditSentimentCollector()
        text = "The CEO said IPO is coming. YOLO on GME!"
        tickers = collector.extract_tickers(text)
        assert "CEO" not in tickers
        assert "IPO" not in tickers
        assert "YOLO" not in tickers
        assert "GME" in tickers

    def test_extract_tickers_handles_lowercase(self):
        """Test ticker extraction ignores lowercase."""
        collector = RedditSentimentCollector()
        text = "i think tsla is good but TSLA better"
        tickers = collector.extract_tickers(text)
        # Should only find uppercase TSLA
        assert "TSLA" in tickers
        assert len([t for t in tickers if t == "TSLA"]) == 1

    def test_analyze_sentiment_simple_positive(self):
        """Test simple sentiment analysis - positive."""
        collector = RedditSentimentCollector()
        text = "Super bullish on this! Moon rocket gains incoming! 🚀"
        result = collector.analyze_sentiment_simple(text)
        assert result["sentiment_label"] == "positive"
        assert result["sentiment_score"] > 0

    def test_analyze_sentiment_simple_negative(self):
        """Test simple sentiment analysis - negative."""
        collector = RedditSentimentCollector()
        text = "This is a crash waiting to happen. Bearish, sell everything!"
        result = collector.analyze_sentiment_simple(text)
        assert result["sentiment_label"] == "negative"
        assert result["sentiment_score"] < 0

    def test_analyze_sentiment_simple_neutral(self):
        """Test simple sentiment analysis - neutral."""
        collector = RedditSentimentCollector()
        text = "The company released their quarterly report today."
        result = collector.analyze_sentiment_simple(text)
        assert result["sentiment_label"] == "neutral"
        assert result["confidence"] <= 0.5

    def test_parse_post(self):
        """Test parsing a Reddit post."""
        collector = RedditSentimentCollector()

        # Create mock post
        mock_post = MagicMock()
        mock_post.id = "test123"
        mock_post.subreddit.display_name = "wallstreetbets"
        mock_post.title = "TSLA calls printing!"
        mock_post.selftext = "Bought 10 contracts"
        mock_post.author = "trader123"
        mock_post.score = 500
        mock_post.upvote_ratio = 0.85
        mock_post.num_comments = 100
        mock_post.created_utc = 1700000000
        mock_post.url = "https://reddit.com/..."
        mock_post.is_self = True
        mock_post.link_flair_text = "YOLO"

        parsed = collector._parse_post(mock_post)

        assert parsed["post_id"] == "test123"
        assert parsed["subreddit"] == "wallstreetbets"
        assert "TSLA" in parsed["mentioned_tickers"]
        assert parsed["score"] == 500

    def test_excluded_words_comprehensive(self):
        """Test that all common words are properly excluded."""
        collector = RedditSentimentCollector()
        excluded = collector.EXCLUDED_WORDS

        # Check important exclusions
        assert "THE" in excluded
        assert "CEO" in excluded
        assert "ETF" in excluded
        assert "HODL" in excluded
        assert "FOMO" in excluded


# =============================================================================
# Sentiment Factor Calculation Tests
# =============================================================================

class TestSentimentFactorCalculations:
    """Test sentiment factor calculation functions."""

    @patch("src.transformations.factors.sentiment_factors.SessionLocal")
    def test_calc_ticker_sentiment(self, mock_session_local):
        """Test ticker sentiment calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.return_value = 0.45

        result = calc_ticker_sentiment("TSLA", date(2024, 6, 15))

        assert result == 0.45
        mock_session.close.assert_called_once()

    @patch("src.transformations.factors.sentiment_factors.SessionLocal")
    def test_calc_ticker_sentiment_no_data(self, mock_session_local):
        """Test ticker sentiment returns None when no data."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_session.query.return_value.filter.return_value.scalar.return_value = None

        result = calc_ticker_sentiment("UNKNOWN", date(2024, 6, 15))

        assert result is None

    @patch("src.transformations.factors.sentiment_factors.SessionLocal")
    def test_calc_ticker_mention_velocity(self, mock_session_local):
        """Test mention velocity calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Short window: 10 mentions in 1 day, Long window: 35 mentions in 7 days
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [10, 35]

        result = calc_ticker_mention_velocity("GME", date(2024, 6, 15))

        # short_rate = 10/1 = 10, long_rate = 35/7 = 5
        # velocity = 10/5 = 2.0
        assert result == 2.0

    @patch("src.transformations.factors.sentiment_factors.SessionLocal")
    def test_calc_sentiment_momentum(self, mock_session_local):
        """Test sentiment momentum calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Short avg: 0.6, Long avg: 0.3
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [0.6, 0.3]

        result = calc_sentiment_momentum("AAPL", date(2024, 6, 15))

        # Momentum = 0.6 - 0.3 = 0.3
        assert result == 0.3

    @patch("src.transformations.factors.sentiment_factors.SessionLocal")
    def test_calc_wsb_sentiment(self, mock_session_local):
        """Test WSB sentiment calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.return_value = 0.25

        result = calc_wsb_sentiment(date(2024, 6, 15))

        assert result == 0.25

    @patch("src.transformations.factors.sentiment_factors.SessionLocal")
    def test_calc_retail_attention_index(self, mock_session_local):
        """Test retail attention index calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Post count: 100, Total score: 50000, Total comments: 10000
        mock_session.query.return_value.filter.return_value.scalar.return_value = 100
        mock_session.query.return_value.filter.return_value.first.return_value = (50000, 10000)

        result = calc_retail_attention_index(date(2024, 6, 15))

        assert result is not None
        assert result > 0

    @patch("src.transformations.factors.sentiment_factors.SessionLocal")
    def test_calc_sentiment_dispersion(self, mock_session_local):
        """Test sentiment dispersion calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Mock sentiment scores: mixed opinions
        mock_session.query.return_value.filter.return_value.all.return_value = [
            (0.8,), (-0.5,), (0.3,), (-0.2,), (0.6,)
        ]

        result = calc_sentiment_dispersion("NVDA", date(2024, 6, 15))

        assert result is not None
        assert result > 0  # Should have dispersion

    @patch("src.transformations.factors.sentiment_factors.SessionLocal")
    def test_calc_sentiment_dispersion_insufficient_data(self, mock_session_local):
        """Test dispersion returns None with insufficient data."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_session.query.return_value.filter.return_value.all.return_value = [(0.5,), (0.3,)]

        result = calc_sentiment_dispersion("RARE", date(2024, 6, 15))

        assert result is None


# =============================================================================
# Sentiment Factor Class Tests
# =============================================================================

class TestSentimentFactorClasses:
    """Test sentiment factor classes."""

    def test_ticker_sentiment_factor(self):
        """Test TickerSentiment factor class."""
        factor = TickerSentiment()
        assert factor.FACTOR_NAME == "ticker_sentiment"
        assert factor.CATEGORY == "sentiment"
        assert factor.ENTITY_TYPE == "ticker"

    def test_mention_velocity_factor(self):
        """Test MentionVelocity factor class."""
        factor = MentionVelocity()
        assert factor.FACTOR_NAME == "mention_velocity"
        assert "velocity" in factor.FACTOR_DESCRIPTION.lower()

    def test_sentiment_momentum_factor(self):
        """Test SentimentMomentum factor class."""
        factor = SentimentMomentum()
        assert factor.FACTOR_NAME == "sentiment_momentum"
        assert factor.LOOKBACK_DAYS == 14

    def test_wsb_sentiment_factor(self):
        """Test WSBSentiment factor class."""
        factor = WSBSentiment()
        assert factor.FACTOR_NAME == "wsb_sentiment"
        assert factor.ENTITY_TYPE == "market"

    def test_retail_attention_index_factor(self):
        """Test RetailAttentionIndex factor class."""
        factor = RetailAttentionIndex()
        assert factor.FACTOR_NAME == "retail_attention_index"
        assert factor.ENTITY_TYPE == "market"

    def test_sentiment_dispersion_factor(self):
        """Test SentimentDispersion factor class."""
        factor = SentimentDispersion()
        assert factor.FACTOR_NAME == "sentiment_dispersion"
        assert "disagreement" in factor.FACTOR_DESCRIPTION.lower()

    @patch("src.transformations.factors.sentiment_factors.calc_ticker_sentiment")
    def test_ticker_sentiment_compute(self, mock_calc):
        """Test TickerSentiment compute method."""
        mock_calc.return_value = 0.65

        factor = TickerSentiment()
        result = factor.compute("AAPL", datetime(2024, 6, 15))

        assert result == 0.65
        mock_calc.assert_called_once()

    @patch("src.transformations.factors.sentiment_factors.calc_wsb_sentiment")
    def test_wsb_sentiment_compute(self, mock_calc):
        """Test WSBSentiment compute method."""
        mock_calc.return_value = 0.15

        factor = WSBSentiment()
        result = factor.compute("market", datetime(2024, 6, 15))

        assert result == 0.15


# =============================================================================
# Factor Registry Tests
# =============================================================================

class TestSentimentFactorRegistry:
    """Test sentiment factors in registry."""

    def test_sentiment_factors_registered(self):
        """Test that all sentiment factors are registered."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        registered_ids = [f["id"] for f in registered]

        sentiment_factors = [
            "ticker_sentiment",
            "mention_velocity",
            "sentiment_momentum",
            "wsb_sentiment",
            "retail_attention_index",
            "sentiment_dispersion",
        ]

        for factor in sentiment_factors:
            assert factor in registered_ids, f"{factor} not registered"

    def test_sentiment_factors_category(self):
        """Test sentiment factors have correct category."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        sentiment_factors = [f for f in registered if f["category"] == "sentiment"]

        assert len(sentiment_factors) >= 6
