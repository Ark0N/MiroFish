"""
RSS feed monitor service.

Manages RSS feed subscriptions per project and checks for new articles.
When new content is detected, extracts text and queues it for graph enrichment.
Feed configurations are stored per project.
"""

import json
import os
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ..config import Config
from ..utils.logger import get_logger
from ..utils.file_utils import atomic_write_json

logger = get_logger('mirofish.rss_monitor')


@dataclass
class FeedConfig:
    """RSS feed subscription configuration."""
    url: str
    name: str = ""
    check_interval_minutes: int = 60
    enabled: bool = True
    last_checked: str = ""
    seen_hashes: List[str] = field(default_factory=list)  # content hashes of seen articles

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "name": self.name,
            "check_interval_minutes": self.check_interval_minutes,
            "enabled": self.enabled,
            "last_checked": self.last_checked,
            "seen_hashes": self.seen_hashes[-100:],  # Keep last 100 hashes
        }


@dataclass
class FeedItem:
    """A single item from an RSS feed."""
    title: str
    url: str
    content: str
    published: str = ""
    content_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content[:500],  # Truncate for summary
            "published": self.published,
            "content_hash": self.content_hash,
        }


class RSSMonitor:
    """Manage RSS feed subscriptions and detect new content."""

    FEEDS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'rss_feeds')

    def add_feed(
        self,
        project_id: str,
        url: str,
        name: str = "",
        check_interval_minutes: int = 60,
    ) -> FeedConfig:
        """Add an RSS feed subscription to a project.

        Args:
            project_id: Project to associate the feed with
            url: RSS feed URL
            name: Human-readable feed name
            check_interval_minutes: How often to check (default 60 min)

        Returns:
            FeedConfig for the added feed
        """
        feeds = self._load_feeds(project_id)

        # Check for duplicate URL
        for f in feeds:
            if f["url"] == url:
                logger.info(f"Feed already exists for project {project_id}: {url}")
                return FeedConfig(**{k: v for k, v in f.items() if k in FeedConfig.__dataclass_fields__})

        feed = FeedConfig(
            url=url,
            name=name or url[:80],
            check_interval_minutes=check_interval_minutes,
        )

        feeds.append(feed.to_dict())
        self._save_feeds(project_id, feeds)
        logger.info(f"Added RSS feed for project {project_id}: {url}")
        return feed

    def remove_feed(self, project_id: str, url: str) -> bool:
        """Remove a feed subscription."""
        feeds = self._load_feeds(project_id)
        original_len = len(feeds)
        feeds = [f for f in feeds if f["url"] != url]
        if len(feeds) < original_len:
            self._save_feeds(project_id, feeds)
            return True
        return False

    def get_feeds(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all feed subscriptions for a project."""
        return self._load_feeds(project_id)

    def check_feed(self, url: str, seen_hashes: List[str]) -> List[FeedItem]:
        """Check an RSS feed for new items.

        Args:
            url: Feed URL to check
            seen_hashes: List of previously seen content hashes

        Returns:
            List of new FeedItems not in seen_hashes
        """
        try:
            import trafilatura

            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                logger.warning(f"Failed to fetch RSS feed: {url}")
                return []

            # Extract text content from the feed page
            text = trafilatura.extract(downloaded, include_comments=False, no_fallback=False)
            if not text:
                return []

            # Create a single feed item from the page content
            content_hash = hashlib.md5(text.encode()).hexdigest()[:16]

            if content_hash in seen_hashes:
                return []

            metadata = trafilatura.extract_metadata(downloaded)
            title = metadata.title if metadata and metadata.title else url[:80]

            return [FeedItem(
                title=title,
                url=url,
                content=text,
                published=datetime.now().isoformat(),
                content_hash=content_hash,
            )]

        except Exception as e:
            logger.error(f"Error checking feed {url}: {e}")
            return []

    def check_all_feeds(self, project_id: str) -> List[FeedItem]:
        """Check all feeds for a project and return new items.

        Updates seen_hashes and last_checked for each feed.

        Returns:
            List of all new FeedItems across all feeds
        """
        feeds = self._load_feeds(project_id)
        all_new_items = []

        for feed_data in feeds:
            if not feed_data.get("enabled", True):
                continue

            url = feed_data["url"]
            seen_hashes = feed_data.get("seen_hashes", [])

            new_items = self.check_feed(url, seen_hashes)

            if new_items:
                # Update seen hashes
                for item in new_items:
                    if item.content_hash and item.content_hash not in seen_hashes:
                        seen_hashes.append(item.content_hash)
                feed_data["seen_hashes"] = seen_hashes[-100:]
                all_new_items.extend(new_items)

            feed_data["last_checked"] = datetime.now().isoformat()

        if all_new_items:
            self._save_feeds(project_id, feeds)

        logger.info(f"Checked {len(feeds)} feeds for project {project_id}, "
                     f"found {len(all_new_items)} new items")
        return all_new_items

    def _load_feeds(self, project_id: str) -> List[Dict[str, Any]]:
        path = os.path.join(self.FEEDS_DIR, f"{project_id}.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save_feeds(self, project_id: str, feeds: List[Dict[str, Any]]) -> None:
        os.makedirs(self.FEEDS_DIR, exist_ok=True)
        path = os.path.join(self.FEEDS_DIR, f"{project_id}.json")
        atomic_write_json(path, feeds)
