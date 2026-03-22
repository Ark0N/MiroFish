"""
Graph memory updater service.
Dynamically updates the knowledge graph with agent activities during simulation.
Replaces zep_graph_memory_updater.py (Zep Cloud → Graphiti + Neo4j).

All logic preserved: AgentActivity dataclass, _describe_* methods,
queue/buffer system, thread safety, batch sending.
"""

import time
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from queue import Queue, Empty

from ..config import Config
from ..utils.logger import get_logger
from ..utils.graphiti_manager import GraphitiManager, run_async
from ..utils.ontology_store import get_entity_types

logger = get_logger('mirofish.graph_memory_updater')


@dataclass
class AgentActivity:
    """Agent activity record (unchanged from Zep version)."""
    platform: str           # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str        # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any]
    round_num: int
    timestamp: str

    def to_episode_text(self) -> str:
        """Convert activity to natural language text for graph ingestion."""
        action_descriptions = {
            "CREATE_POST": self._describe_create_post,
            "LIKE_POST": self._describe_like_post,
            "DISLIKE_POST": self._describe_dislike_post,
            "REPOST": self._describe_repost,
            "QUOTE_POST": self._describe_quote_post,
            "FOLLOW": self._describe_follow,
            "CREATE_COMMENT": self._describe_create_comment,
            "LIKE_COMMENT": self._describe_like_comment,
            "DISLIKE_COMMENT": self._describe_dislike_comment,
            "SEARCH_POSTS": self._describe_search,
            "SEARCH_USER": self._describe_search_user,
            "MUTE": self._describe_mute,
        }

        describe_func = action_descriptions.get(self.action_type, self._describe_generic)
        description = describe_func()
        return f"{self.agent_name}: {description}"

    def _describe_create_post(self) -> str:
        content = self.action_args.get("content", "")
        if content:
            return f"发布了一条帖子：「{content}」"
        return "发布了一条帖子"

    def _describe_like_post(self) -> str:
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        if post_content and post_author:
            return f"点赞了{post_author}的帖子：「{post_content}」"
        elif post_content:
            return f"点赞了一条帖子：「{post_content}」"
        elif post_author:
            return f"点赞了{post_author}的一条帖子"
        return "点赞了一条帖子"

    def _describe_dislike_post(self) -> str:
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        if post_content and post_author:
            return f"踩了{post_author}的帖子：「{post_content}」"
        elif post_content:
            return f"踩了一条帖子：「{post_content}」"
        elif post_author:
            return f"踩了{post_author}的一条帖子"
        return "踩了一条帖子"

    def _describe_repost(self) -> str:
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        if original_content and original_author:
            return f"转发了{original_author}的帖子：「{original_content}」"
        elif original_content:
            return f"转发了一条帖子：「{original_content}」"
        elif original_author:
            return f"转发了{original_author}的一条帖子"
        return "转发了一条帖子"

    def _describe_quote_post(self) -> str:
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        quote_content = self.action_args.get("quote_content", "") or self.action_args.get("content", "")
        base = ""
        if original_content and original_author:
            base = f"引用了{original_author}的帖子「{original_content}」"
        elif original_content:
            base = f"引用了一条帖子「{original_content}」"
        elif original_author:
            base = f"引用了{original_author}的一条帖子"
        else:
            base = "引用了一条帖子"
        if quote_content:
            base += f"，并评论道：「{quote_content}」"
        return base

    def _describe_follow(self) -> str:
        target_user_name = self.action_args.get("target_user_name", "")
        if target_user_name:
            return f"关注了用户「{target_user_name}」"
        return "关注了一个用户"

    def _describe_create_comment(self) -> str:
        content = self.action_args.get("content", "")
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        if content:
            if post_content and post_author:
                return f"在{post_author}的帖子「{post_content}」下评论道：「{content}」"
            elif post_content:
                return f"在帖子「{post_content}」下评论道：「{content}」"
            elif post_author:
                return f"在{post_author}的帖子下评论道：「{content}」"
            return f"评论道：「{content}」"
        return "发表了评论"

    def _describe_like_comment(self) -> str:
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        if comment_content and comment_author:
            return f"点赞了{comment_author}的评论：「{comment_content}」"
        elif comment_content:
            return f"点赞了一条评论：「{comment_content}」"
        elif comment_author:
            return f"点赞了{comment_author}的一条评论"
        return "点赞了一条评论"

    def _describe_dislike_comment(self) -> str:
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        if comment_content and comment_author:
            return f"踩了{comment_author}的评论：「{comment_content}」"
        elif comment_content:
            return f"踩了一条评论：「{comment_content}」"
        elif comment_author:
            return f"踩了{comment_author}的一条评论"
        return "踩了一条评论"

    def _describe_search(self) -> str:
        query = self.action_args.get("query", "") or self.action_args.get("keyword", "")
        return f"搜索了「{query}」" if query else "进行了搜索"

    def _describe_search_user(self) -> str:
        query = self.action_args.get("query", "") or self.action_args.get("username", "")
        return f"搜索了用户「{query}」" if query else "搜索了用户"

    def _describe_mute(self) -> str:
        target_user_name = self.action_args.get("target_user_name", "")
        if target_user_name:
            return f"屏蔽了用户「{target_user_name}」"
        return "屏蔽了一个用户"

    def _describe_generic(self) -> str:
        return f"执行了{self.action_type}操作"


class GraphMemoryUpdater:
    """
    Graph memory updater.

    Monitors simulation action logs, batches agent activities by platform,
    and sends them to the Graphiti knowledge graph.
    """

    BATCH_SIZE = 5
    PLATFORM_DISPLAY_NAMES = {
        'twitter': '世界1',
        'reddit': '世界2',
    }
    SEND_INTERVAL = 0.5
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self, graph_id: str):
        self.graph_id = graph_id

        self._activity_queue: Queue = Queue()
        self._platform_buffers: Dict[str, List[AgentActivity]] = {
            'twitter': [],
            'reddit': [],
        }
        self._buffer_lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

        self._counter_lock = threading.Lock()
        self._total_activities = 0
        self._total_sent = 0
        self._total_items_sent = 0
        self._failed_count = 0
        self._skipped_count = 0

        logger.info(f"GraphMemoryUpdater initialized: graph_id={graph_id}, batch_size={self.BATCH_SIZE}")

    def _get_platform_display_name(self, platform: str) -> str:
        return self.PLATFORM_DISPLAY_NAMES.get(platform.lower(), platform)

    def start(self):
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name=f"GraphMemoryUpdater-{self.graph_id[:8]}"
        )
        self._worker_thread.start()
        logger.info(f"GraphMemoryUpdater started: graph_id={self.graph_id}")

    def stop(self):
        self._running = False
        self._flush_remaining()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
        with self._counter_lock:
            total_act = self._total_activities
            total_sent = self._total_sent
            total_items = self._total_items_sent
            failed = self._failed_count
            skipped = self._skipped_count
        logger.info(f"GraphMemoryUpdater stopped: graph_id={self.graph_id}, "
                   f"total_activities={total_act}, "
                   f"batches_sent={total_sent}, "
                   f"items_sent={total_items}, "
                   f"failed={failed}, "
                   f"skipped={skipped}")

    def add_activity(self, activity: AgentActivity):
        if activity.action_type == "DO_NOTHING":
            with self._counter_lock:
                self._skipped_count += 1
            return
        self._activity_queue.put(activity)
        with self._counter_lock:
            self._total_activities += 1
        logger.debug(f"Added activity to graph queue: {activity.agent_name} - {activity.action_type}")

    def add_activity_from_dict(self, data: Dict[str, Any], platform: str):
        if "event_type" in data:
            return
        activity = AgentActivity(
            platform=platform,
            agent_id=data.get("agent_id", 0),
            agent_name=data.get("agent_name", ""),
            action_type=data.get("action_type", ""),
            action_args=data.get("action_args", {}),
            round_num=data.get("round", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )
        self.add_activity(activity)

    def _worker_loop(self):
        while self._running or not self._activity_queue.empty():
            try:
                try:
                    activity = self._activity_queue.get(timeout=1)
                    platform = activity.platform.lower()
                    with self._buffer_lock:
                        if platform not in self._platform_buffers:
                            self._platform_buffers[platform] = []
                        self._platform_buffers[platform].append(activity)
                        if len(self._platform_buffers[platform]) >= self.BATCH_SIZE:
                            batch = self._platform_buffers[platform][:self.BATCH_SIZE]
                            self._platform_buffers[platform] = self._platform_buffers[platform][self.BATCH_SIZE:]
                            self._send_batch_activities(batch, platform)
                            time.sleep(self.SEND_INTERVAL)
                except Empty:
                    pass
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                time.sleep(1)

    def _send_batch_activities(self, activities: List[AgentActivity], platform: str):
        if not activities:
            return

        episode_texts = [activity.to_episode_text() for activity in activities]
        combined_text = "\n".join(episode_texts)

        for attempt in range(self.MAX_RETRIES):
            try:
                graphiti = GraphitiManager.get_instance()
                entity_types = get_entity_types(self.graph_id)

                run_async(graphiti.add_episode(
                    name="sim_activity",
                    episode_body=combined_text,
                    source_description=f"MiroFish simulation ({platform})",
                    reference_time=datetime.now(),
                    source="text",
                    group_id=self.graph_id,
                    entity_types=entity_types,
                ))

                with self._counter_lock:
                    self._total_sent += 1
                    self._total_items_sent += len(activities)
                display_name = self._get_platform_display_name(platform)
                logger.info(f"Sent batch of {len(activities)} {display_name} activities to graph {self.graph_id}")
                logger.debug(f"Batch preview: {combined_text[:200]}...")
                return

            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"Batch send failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"Batch send failed after {self.MAX_RETRIES} attempts: {e}")
                    with self._counter_lock:
                        self._failed_count += 1

    def _flush_remaining(self):
        while not self._activity_queue.empty():
            try:
                activity = self._activity_queue.get_nowait()
                platform = activity.platform.lower()
                with self._buffer_lock:
                    if platform not in self._platform_buffers:
                        self._platform_buffers[platform] = []
                    self._platform_buffers[platform].append(activity)
            except Empty:
                break

        with self._buffer_lock:
            for platform, buffer in self._platform_buffers.items():
                if buffer:
                    display_name = self._get_platform_display_name(platform)
                    logger.info(f"Sending remaining {len(buffer)} {display_name} activities")
                    self._send_batch_activities(buffer, platform)
            for platform in self._platform_buffers:
                self._platform_buffers[platform] = []

    def get_stats(self) -> Dict[str, Any]:
        with self._buffer_lock:
            buffer_sizes = {p: len(b) for p, b in self._platform_buffers.items()}
        with self._counter_lock:
            total_activities = self._total_activities
            total_sent = self._total_sent
            total_items_sent = self._total_items_sent
            failed_count = self._failed_count
            skipped_count = self._skipped_count
        return {
            "graph_id": self.graph_id,
            "batch_size": self.BATCH_SIZE,
            "total_activities": total_activities,
            "batches_sent": total_sent,
            "items_sent": total_items_sent,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "queue_size": self._activity_queue.qsize(),
            "buffer_sizes": buffer_sizes,
            "running": self._running,
        }


class GraphMemoryManager:
    """Manages multiple simulation graph memory updaters."""

    _updaters: Dict[str, GraphMemoryUpdater] = {}
    _lock = threading.Lock()

    @classmethod
    def create_updater(cls, simulation_id: str, graph_id: str) -> GraphMemoryUpdater:
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
            updater = GraphMemoryUpdater(graph_id)
            updater.start()
            cls._updaters[simulation_id] = updater
            logger.info(f"Created graph memory updater: simulation_id={simulation_id}, graph_id={graph_id}")
            return updater

    @classmethod
    def get_updater(cls, simulation_id: str) -> Optional[GraphMemoryUpdater]:
        return cls._updaters.get(simulation_id)

    @classmethod
    def stop_updater(cls, simulation_id: str):
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
                del cls._updaters[simulation_id]
                logger.info(f"Stopped graph memory updater: simulation_id={simulation_id}")

    _stop_all_done = False

    @classmethod
    def stop_all(cls):
        if cls._stop_all_done:
            return
        cls._stop_all_done = True
        with cls._lock:
            if cls._updaters:
                for simulation_id, updater in list(cls._updaters.items()):
                    try:
                        updater.stop()
                    except Exception as e:
                        logger.error(f"Failed to stop updater: simulation_id={simulation_id}, error={e}")
                cls._updaters.clear()
            logger.info("Stopped all graph memory updaters")

    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        return {
            sim_id: updater.get_stats()
            for sim_id, updater in cls._updaters.items()
        }
