"""
Batch URL ingestion service with rate limiting.

Handles large batches of URLs (100+) with internal rate limiting,
progress tracking, and partial failure recovery.
"""

import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from ..utils.logger import get_logger

logger = get_logger('mirofish.batch_ingester')


@dataclass
class IngestionResult:
    """Result of a single URL ingestion attempt."""
    url: str
    success: bool
    title: str = ""
    text_length: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "success": self.success,
            "title": self.title,
            "text_length": self.text_length,
            "error": self.error,
        }


@dataclass
class BatchProgress:
    """Progress state for a batch ingestion."""
    total: int
    completed: int = 0
    succeeded: int = 0
    failed: int = 0
    current_url: str = ""
    status: str = "pending"  # pending, running, completed, failed
    results: List[IngestionResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "completed": self.completed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "current_url": self.current_url,
            "status": self.status,
            "progress_pct": round(self.completed / self.total * 100, 1) if self.total > 0 else 0,
        }


class BatchIngester:
    """Process large batches of URLs with rate limiting and progress tracking."""

    def __init__(
        self,
        rate_limit_per_second: float = 2.0,
        max_retries: int = 2,
    ):
        """
        Args:
            rate_limit_per_second: Maximum URLs to fetch per second
            max_retries: Number of retries per failed URL
        """
        self.min_interval = 1.0 / rate_limit_per_second
        self.max_retries = max_retries

    def ingest_batch(
        self,
        urls: List[str],
        progress_callback: Optional[Callable[[BatchProgress], None]] = None,
    ) -> BatchProgress:
        """Ingest a batch of URLs with rate limiting.

        Args:
            urls: List of URLs to process
            progress_callback: Optional callback for progress updates

        Returns:
            BatchProgress with results for each URL
        """
        from ..utils.url_extractor import extract_text_from_url

        progress = BatchProgress(total=len(urls), status="running")

        if progress_callback:
            progress_callback(progress)

        for i, url in enumerate(urls):
            progress.current_url = url

            result = self._ingest_with_retry(url, extract_text_from_url)

            progress.results.append(result)
            progress.completed += 1
            if result.success:
                progress.succeeded += 1
            else:
                progress.failed += 1

            if progress_callback:
                progress_callback(progress)

            # Rate limiting (skip for last URL)
            if i < len(urls) - 1:
                time.sleep(self.min_interval)

        progress.status = "completed"
        progress.current_url = ""

        if progress_callback:
            progress_callback(progress)

        logger.info(f"Batch ingestion complete: {progress.succeeded}/{progress.total} succeeded")
        return progress

    def _ingest_with_retry(self, url: str, extract_fn) -> IngestionResult:
        """Attempt to ingest a URL with retries."""
        last_error = None

        for attempt in range(1 + self.max_retries):
            try:
                result = extract_fn(url)
                if result["success"]:
                    return IngestionResult(
                        url=url,
                        success=True,
                        title=result.get("title", ""),
                        text_length=len(result.get("text", "")),
                    )
                last_error = result.get("error", "Unknown error")
            except Exception as e:
                last_error = str(e)

            if attempt < self.max_retries:
                time.sleep(0.5 * (attempt + 1))  # Brief backoff

        return IngestionResult(
            url=url,
            success=False,
            error=last_error,
        )

    def get_successful_texts(self, progress: BatchProgress) -> List[Dict[str, Any]]:
        """Extract texts from successful ingestion results.

        Note: This requires re-fetching since BatchProgress only stores metadata.
        For efficiency in production, texts should be stored during ingestion.
        """
        return [
            {"url": r.url, "title": r.title}
            for r in progress.results
            if r.success
        ]
