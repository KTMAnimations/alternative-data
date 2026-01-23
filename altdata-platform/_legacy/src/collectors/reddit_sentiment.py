"""Reddit sentiment collector for retail investor signals."""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:
    import praw
    HAS_PRAW = True
except ImportError:
    praw = None
    HAS_PRAW = False

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

from src.collectors.base import BaseCollector, CollectorError
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.sentiment import (
    RedditPost,
    RedditComment,
    SentimentScore,
    TickerMention,
)

logger = logging.getLogger(__name__)


class RedditSentimentCollector(BaseCollector[Dict, Dict]):
    """Collector for Reddit sentiment data.

    Tracks retail investor sentiment from finance-related subreddits.
    """

    SOURCE_NAME = "reddit_sentiment"
    DEFAULT_RATE_LIMIT = 0.5  # 30 requests/minute (Reddit API limit)

    # Finance-focused subreddits
    TRACKED_SUBREDDITS = [
        "wallstreetbets",
        "stocks",
        "investing",
        "options",
        "stockmarket",
        "SecurityAnalysis",
        "ValueInvesting",
        "Daytrading",
        "pennystocks",
        "SPACs",
    ]

    # Ticker pattern for extraction
    TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b|\b([A-Z]{2,5})\b')

    # Common words to exclude from ticker detection
    EXCLUDED_WORDS = {
        "CEO", "CFO", "COO", "CTO", "IPO", "ETF", "SEC", "FDA", "GDP",
        "NYSE", "NASDAQ", "DOW", "HODL", "YOLO", "FOMO", "DD", "IMO",
        "ATH", "ATL", "EPS", "PE", "PB", "ROI", "ROE", "EBITDA",
        "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL",
        "HAS", "HER", "WAS", "ONE", "OUR", "OUT", "DAY", "HAD",
        "EDIT", "UPDATE", "TLDR", "THIS", "THAT", "WHAT", "WHEN",
    }

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None,
        rate_limit: Optional[float] = None,
    ):
        """Initialize the Reddit sentiment collector.

        Args:
            client_id: Reddit API client ID
            client_secret: Reddit API client secret
            user_agent: Reddit API user agent
            rate_limit: Requests per second
        """
        super().__init__(rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT)
        self.client_id = client_id or getattr(settings, 'reddit_client_id', None)
        self.client_secret = client_secret or getattr(settings, 'reddit_client_secret', None)
        self.user_agent = user_agent or getattr(settings, 'reddit_user_agent', 'AltData Platform 1.0')
        self._reddit = None
        self._sentiment_model = None
        self._tokenizer = None

    @property
    def reddit(self):
        """Get or create Reddit instance."""
        if not HAS_PRAW:
            raise CollectorError("praw package not installed. Install with: pip install praw")
        if self._reddit is None:
            if not self.client_id or not self.client_secret:
                raise CollectorError("Reddit API credentials not configured")
            self._reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )
        return self._reddit

    def load_sentiment_model(self):
        """Load FinBERT model for sentiment analysis."""
        if not HAS_TRANSFORMERS:
            logger.warning("transformers not installed, using simple sentiment")
            return

        if self._sentiment_model is None:
            try:
                model_name = "ProsusAI/finbert"
                self._tokenizer = AutoTokenizer.from_pretrained(model_name)
                self._sentiment_model = AutoModelForSequenceClassification.from_pretrained(model_name)
                logger.info("Loaded FinBERT sentiment model")
            except Exception as e:
                logger.warning(f"Could not load FinBERT: {e}, using simple sentiment")

    async def fetch(self) -> List[Dict]:
        """Fetch posts from all tracked subreddits.

        Returns:
            List of post data dicts
        """
        results = []
        for subreddit in self.TRACKED_SUBREDDITS:
            try:
                await self.rate_limiter.wait()
                posts = self.fetch_subreddit_posts(subreddit, limit=100)
                results.extend(posts)
            except Exception as e:
                logger.warning(f"Failed to fetch from r/{subreddit}: {e}")
        return results

    def fetch_subreddit_posts(
        self,
        subreddit: str,
        limit: int = 100,
        time_filter: str = "day",
    ) -> List[Dict]:
        """Fetch top posts from a subreddit.

        Args:
            subreddit: Subreddit name
            limit: Maximum posts to fetch
            time_filter: Time filter (hour, day, week, month, year, all)

        Returns:
            List of post data dicts
        """
        posts = []
        try:
            sub = self.reddit.subreddit(subreddit)
            for post in sub.hot(limit=limit):
                posts.append(self._parse_post(post))
        except Exception as e:
            logger.error(f"Error fetching r/{subreddit}: {e}")
        return posts

    def _parse_post(self, post) -> Dict:
        """Parse a Reddit post submission.

        Args:
            post: PRAW submission object

        Returns:
            Parsed post dict
        """
        text = f"{post.title} {post.selftext or ''}"
        tickers = self.extract_tickers(text)

        return {
            "post_id": post.id,
            "subreddit": post.subreddit.display_name,
            "title": post.title,
            "selftext": post.selftext,
            "author": str(post.author) if post.author else "[deleted]",
            "score": post.score,
            "upvote_ratio": post.upvote_ratio,
            "num_comments": post.num_comments,
            "created_utc": datetime.utcfromtimestamp(post.created_utc),
            "url": post.url,
            "is_self": post.is_self,
            "link_flair_text": post.link_flair_text,
            "mentioned_tickers": tickers,
        }

    def extract_tickers(self, text: str) -> List[str]:
        """Extract stock tickers from text.

        Args:
            text: Text to search

        Returns:
            List of unique tickers found
        """
        tickers = set()
        for match in self.TICKER_PATTERN.finditer(text):
            ticker = match.group(1) or match.group(2)
            if ticker and ticker not in self.EXCLUDED_WORDS:
                tickers.add(ticker)
        return list(tickers)

    def analyze_sentiment_simple(self, text: str) -> Dict:
        """Simple keyword-based sentiment analysis.

        Args:
            text: Text to analyze

        Returns:
            Sentiment result dict
        """
        text_lower = text.lower()

        positive_words = [
            "bullish", "moon", "rocket", "gains", "buy", "calls",
            "profit", "growth", "up", "green", "win", "pump",
            "rally", "surge", "strong", "long", "undervalued",
        ]
        negative_words = [
            "bearish", "crash", "dump", "loss", "sell", "puts",
            "down", "red", "lose", "tank", "drop", "weak",
            "short", "overvalued", "bubble", "scam", "fraud",
        ]

        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)

        total = pos_count + neg_count
        if total == 0:
            return {
                "sentiment_label": "neutral",
                "sentiment_score": 0.0,
                "confidence": 0.5,
                "positive_prob": 0.33,
                "negative_prob": 0.33,
                "neutral_prob": 0.34,
            }

        score = (pos_count - neg_count) / total

        if score > 0.2:
            label = "positive"
        elif score < -0.2:
            label = "negative"
        else:
            label = "neutral"

        return {
            "sentiment_label": label,
            "sentiment_score": score,
            "confidence": abs(score),
            "positive_prob": pos_count / max(total, 1),
            "negative_prob": neg_count / max(total, 1),
            "neutral_prob": 1 - (pos_count + neg_count) / max(total * 2, 1),
        }

    def analyze_sentiment_finbert(self, text: str) -> Dict:
        """Analyze sentiment using FinBERT.

        Args:
            text: Text to analyze

        Returns:
            Sentiment result dict
        """
        if not self._sentiment_model or not self._tokenizer:
            return self.analyze_sentiment_simple(text)

        try:
            # Truncate text to model max length
            inputs = self._tokenizer(
                text[:512],
                return_tensors="pt",
                truncation=True,
                padding=True,
            )

            with torch.no_grad():
                outputs = self._sentiment_model(**inputs)
                probs = torch.softmax(outputs.logits, dim=1)[0]

            # FinBERT outputs: positive, negative, neutral
            labels = ["positive", "negative", "neutral"]
            probs_dict = {label: float(prob) for label, prob in zip(labels, probs)}

            max_label = max(probs_dict, key=probs_dict.get)
            score = probs_dict["positive"] - probs_dict["negative"]

            return {
                "sentiment_label": max_label,
                "sentiment_score": score,
                "confidence": max(probs_dict.values()),
                "positive_prob": probs_dict["positive"],
                "negative_prob": probs_dict["negative"],
                "neutral_prob": probs_dict["neutral"],
                "model_version": "finbert-prosus",
            }

        except Exception as e:
            logger.warning(f"FinBERT analysis failed: {e}")
            return self.analyze_sentiment_simple(text)

    def analyze_sentiment(self, text: str) -> Dict:
        """Analyze sentiment of text.

        Args:
            text: Text to analyze

        Returns:
            Sentiment result dict
        """
        if self._sentiment_model:
            return self.analyze_sentiment_finbert(text)
        return self.analyze_sentiment_simple(text)

    def parse(self, raw_data: List[Dict]) -> List[Dict]:
        """Parse and enrich posts with sentiment.

        Args:
            raw_data: List of raw post dicts

        Returns:
            List of posts with sentiment
        """
        self.load_sentiment_model()

        for post in raw_data:
            text = f"{post['title']} {post.get('selftext', '') or ''}"
            sentiment = self.analyze_sentiment(text)
            post["sentiment"] = sentiment

        return raw_data

    async def store_posts(self, posts: List[Dict]) -> Tuple[int, int]:
        """Store posts and sentiment scores.

        Args:
            posts: List of parsed posts

        Returns:
            Tuple of (posts_stored, sentiments_stored)
        """
        session = SessionLocal()
        posts_count = 0
        sentiments_count = 0

        try:
            for post in posts:
                # Check if post exists
                existing = (
                    session.query(RedditPost)
                    .filter_by(post_id=post["post_id"])
                    .first()
                )

                if existing:
                    # Update scores
                    existing.score = post["score"]
                    existing.num_comments = post["num_comments"]
                else:
                    record = RedditPost(
                        post_id=post["post_id"],
                        subreddit=post["subreddit"],
                        title=post["title"],
                        selftext=post.get("selftext"),
                        author=post.get("author"),
                        score=post.get("score"),
                        upvote_ratio=post.get("upvote_ratio"),
                        num_comments=post.get("num_comments"),
                        created_utc=post["created_utc"],
                        url=post.get("url"),
                        is_self=post.get("is_self"),
                        link_flair_text=post.get("link_flair_text"),
                        mentioned_tickers=post.get("mentioned_tickers"),
                    )
                    session.add(record)
                    posts_count += 1

                # Store sentiment
                if "sentiment" in post:
                    sentiment = post["sentiment"]
                    score_record = SentimentScore(
                        content_type="post",
                        content_id=post["post_id"],
                        subreddit=post["subreddit"],
                        sentiment_label=sentiment.get("sentiment_label"),
                        sentiment_score=sentiment.get("sentiment_score"),
                        confidence=sentiment.get("confidence"),
                        positive_prob=sentiment.get("positive_prob"),
                        negative_prob=sentiment.get("negative_prob"),
                        neutral_prob=sentiment.get("neutral_prob"),
                        model_version=sentiment.get("model_version", "simple"),
                    )
                    session.add(score_record)
                    sentiments_count += 1

                # Store ticker mentions
                for ticker in post.get("mentioned_tickers", []):
                    mention = TickerMention(
                        ticker=ticker,
                        subreddit=post["subreddit"],
                        content_type="post",
                        content_id=post["post_id"],
                        created_utc=post["created_utc"],
                        sentiment_score=post.get("sentiment", {}).get("sentiment_score"),
                        context_text=post["title"][:500],
                    )
                    session.add(mention)

            session.commit()
            logger.info(f"Stored {posts_count} posts, {sentiments_count} sentiment scores")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store posts: {e}")
            raise
        finally:
            session.close()

        return posts_count, sentiments_count

    async def run_collection(self) -> int:
        """Run full collection cycle.

        Returns:
            Number of posts stored
        """
        logger.info("Starting Reddit sentiment collection")

        try:
            raw_data = await self.fetch()
            if raw_data:
                await self.store_raw(raw_data)

            parsed = self.parse(raw_data)
            posts_count, _ = await self.store_posts(parsed)

            logger.info(f"Reddit sentiment collection complete: {posts_count} posts")
            return posts_count

        finally:
            await self.close()
