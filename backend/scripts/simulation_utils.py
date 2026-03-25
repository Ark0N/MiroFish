"""
OASIS simulation script shared utilities module

Provides shared infrastructure for the three simulation scripts (Twitter, Reddit, parallel):
- UnicodeFormatter: Log formatter that converts Unicode escape sequences to readable characters
- MaxTokensWarningFilter: Filters camel-ai max_tokens log warnings
- setup_oasis_logging(): Configure OASIS logging to fixed files
- create_model(): Create LLM model (supports Anthropic detection and Boost config)
- setup_signal_handlers(): Signal handlers for graceful shutdown
- IPCHandlerBase: IPC command handler base class (poll/response/status/interview result query)
- CommandType: IPC command type constants
- IPC directory/file name constants
"""

import json
import logging
import os
import re
import signal
import sqlite3
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional


# ============================================================
# Logging utilities
# ============================================================

class UnicodeFormatter(logging.Formatter):
    """Custom formatter that converts Unicode escape sequences to readable characters."""

    UNICODE_ESCAPE_PATTERN = re.compile(r'\\u([0-9a-fA-F]{4})')

    def format(self, record):
        result = super().format(record)

        def replace_unicode(match):
            try:
                return chr(int(match.group(1), 16))
            except (ValueError, OverflowError):
                return match.group(0)

        return self.UNICODE_ESCAPE_PATTERN.sub(replace_unicode, result)


class MaxTokensWarningFilter(logging.Filter):
    """Filter out camel-ai max_tokens warnings (we intentionally don't set max_tokens, letting the model decide)."""

    def filter(self, record):
        if "max_tokens" in record.getMessage() and "Invalid or missing" in record.getMessage():
            return False
        return True


def install_max_tokens_filter():
    """Add filter immediately at module load time, ensuring it takes effect before camel code runs."""
    logging.getLogger().addFilter(MaxTokensWarningFilter())


def setup_oasis_logging(log_dir: str):
    """Configure OASIS logging with fixed-name log files."""
    os.makedirs(log_dir, exist_ok=True)

    # Clean up old log files
    for f in os.listdir(log_dir):
        old_log = os.path.join(log_dir, f)
        if os.path.isfile(old_log) and f.endswith('.log'):
            try:
                os.remove(old_log)
            except OSError:
                pass

    formatter = UnicodeFormatter("%(levelname)s - %(asctime)s - %(name)s - %(message)s")

    loggers_config = {
        "social.agent": os.path.join(log_dir, "social.agent.log"),
        "social.twitter": os.path.join(log_dir, "social.twitter.log"),
        "social.rec": os.path.join(log_dir, "social.rec.log"),
        "oasis.env": os.path.join(log_dir, "oasis.env.log"),
        "table": os.path.join(log_dir, "table.log"),
    }

    for logger_name, log_file in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.propagate = False


# ============================================================
# LLM model creation
# ============================================================

def create_model(config: Dict[str, Any], use_boost: bool = False):
    """
    创建LLM模型

    支持双 LLM 配置，用于Parallel simulation时提速：
    - 通用配置：LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
    - 加速配置（可选）：LLM_BOOST_API_KEY, LLM_BOOST_BASE_URL, LLM_BOOST_MODEL_NAME

    如果配置了加速 LLM，Parallel simulation时可以让不同平台使用不同的 API 服务商，提高并发能力。

    Args:
        config: Simulation config字典
        use_boost: 是否使用加速 LLM 配置（如果可用）
    """
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType

    # Check是否有加速配置
    boost_api_key = os.environ.get("LLM_BOOST_API_KEY", "")
    boost_base_url = os.environ.get("LLM_BOOST_BASE_URL", "")
    boost_model = os.environ.get("LLM_BOOST_MODEL_NAME", "")
    has_boost_config = bool(boost_api_key)

    # 根据参数和配置情况选择使用哪个 LLM
    if use_boost and has_boost_config:
        llm_api_key = boost_api_key
        llm_base_url = boost_base_url
        llm_model = boost_model or os.environ.get("LLM_MODEL_NAME", "")
        config_label = "[加速LLM]"
    else:
        llm_api_key = os.environ.get("LLM_API_KEY", "")
        llm_base_url = os.environ.get("LLM_BASE_URL", "")
        llm_model = os.environ.get("LLM_MODEL_NAME", "")
        config_label = "[通用LLM]"

    # 如果 .env 中没有模型名，则使用 config 作为备用
    if not llm_model:
        llm_model = config.get("llm_model", "gpt-4o-mini")

    # Detect Anthropic API keys (sk-ant-) and use native ANTHROPIC platform
    is_anthropic = llm_api_key.startswith("sk-ant-") or "anthropic" in (llm_base_url or "").lower()

    if is_anthropic:
        os.environ["ANTHROPIC_API_KEY"] = llm_api_key
        print(f"{config_label} [Anthropic] model={llm_model}...")
        return ModelFactory.create(
            model_platform=ModelPlatformType.ANTHROPIC,
            model_type=llm_model,
        )

    # Configure camel-ai 所需的环境变量 (OpenAI-compatible)
    if llm_api_key:
        os.environ["OPENAI_API_KEY"] = llm_api_key

    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("缺少 API Key 配置，请在项目根目录 .env 文件中设置 LLM_API_KEY")

    if llm_base_url:
        os.environ["OPENAI_API_BASE_URL"] = llm_base_url

    print(f"{config_label} model={llm_model}, base_url={llm_base_url[:40] if llm_base_url else '默认'}...")

    return ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI,
        model_type=llm_model,
    )


# ============================================================
# Signal handling for graceful shutdown
# ============================================================

def setup_signal_handlers(shutdown_event_ref, cleanup_done_ref):
    """
    设置Signal handling器，确保收到 SIGTERM/SIGINT 时能够正确退出
    让程序有机会正常清理资源（关闭Database、环境等）

    Args:
        shutdown_event_ref: 一个可调用对象，返回当前的 shutdown asyncio.Event（或 None）
        cleanup_done_ref: 一个包含单个 bool 元素的列表 [False]，用于跟踪清理状态
    """
    def signal_handler(signum, frame):
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        print(f"\n收到 {sig_name} 信号，正在退出...")
        if not cleanup_done_ref[0]:
            cleanup_done_ref[0] = True
            event = shutdown_event_ref()
            if event:
                event.set()
        else:
            # 重复Received signal才强制退出
            print("强制退出...")
            sys.exit(1)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


# ============================================================
# IPC constants and base class
# ============================================================

IPC_COMMANDS_DIR = "ipc_commands"
IPC_RESPONSES_DIR = "ipc_responses"
ENV_STATUS_FILE = "env_status.json"


class CommandType:
    """命令类型常量"""
    INTERVIEW = "interview"
    BATCH_INTERVIEW = "batch_interview"
    CLOSE_ENV = "close_env"
    INJECT_EVENT = "inject_event"


class IPCHandlerBase:
    """
    IPCCommand handling基类

    提供 poll_command、send_response、update_status 以及
    _get_interview_result 等通用方法。子类只需实现 handle_interview、
    handle_batch_interview 以及可选地重写 update_status / process_commands。
    """

    def __init__(self, simulation_dir: str):
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, IPC_COMMANDS_DIR)
        self.responses_dir = os.path.join(simulation_dir, IPC_RESPONSES_DIR)
        self.status_file = os.path.join(simulation_dir, ENV_STATUS_FILE)
        self._running = True

        # 确保目录存在
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)

    def update_status(self, status: str):
        """更新Environment status"""
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump({
                "status": status,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)

    def poll_command(self) -> Optional[Dict[str, Any]]:
        """轮询获取待Processing command"""
        if not os.path.exists(self.commands_dir):
            return None

        # 获取命令文件（按时间排序）
        command_files = []
        for filename in os.listdir(self.commands_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.commands_dir, filename)
                command_files.append((filepath, os.path.getmtime(filepath)))

        command_files.sort(key=lambda x: x[1])

        for filepath, _ in command_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

        return None

    def send_response(self, command_id: str, status: str, result: Dict = None, error: str = None):
        """发送响应"""
        response = {
            "command_id": command_id,
            "status": status,
            "result": result,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }

        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response, f, ensure_ascii=False, indent=2)

        # 删除命令文件
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass

    def _get_interview_result(self, agent_id: int, db_name: str) -> Dict[str, Any]:
        """
        从Database获取最新的Interview结果

        Args:
            agent_id: Agent ID
            db_name: Database文件名（如 "twitter_simulation.db"）
        """
        from oasis import ActionType

        db_path = os.path.join(self.simulation_dir, db_name)

        result = {
            "agent_id": agent_id,
            "response": None,
            "timestamp": None
        }

        if not os.path.exists(db_path):
            return result

        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = ? AND user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (ActionType.INTERVIEW.value, agent_id))

                row = cursor.fetchone()
                if row:
                    user_id, info_json, created_at = row
                    try:
                        info = json.loads(info_json) if info_json else {}
                        result["response"] = info.get("response", info)
                        result["timestamp"] = created_at
                    except json.JSONDecodeError:
                        result["response"] = info_json

        except Exception as e:
            print(f"  读取Interview结果failed: {e}")

        return result

    async def process_commands(self) -> bool:
        """
        处理所有待Processing command

        Returns:
            True 表示继续运行，False 表示应该退出
        """
        command = self.poll_command()
        if not command:
            return True

        command_id = command.get("command_id")
        command_type = command.get("command_type")
        args = command.get("args", {})

        print(f"\n收到IPC命令: {command_type}, id={command_id}")

        if command_type == CommandType.INTERVIEW:
            await self.handle_interview(command_id, args)
            return True

        elif command_type == CommandType.BATCH_INTERVIEW:
            await self.handle_batch_interview(command_id, args)
            return True

        elif command_type == CommandType.INJECT_EVENT:
            await self.handle_inject_event(command_id, args)
            return True

        elif command_type == CommandType.CLOSE_ENV:
            print("收到Closing environment命令")
            self.send_response(command_id, "completed", result={"message": "环境即将关闭"})
            return False

        else:
            self.send_response(command_id, "failed", error=f"未知命令类型: {command_type}")
            return True

    async def handle_interview(self, command_id: str, args: Dict[str, Any]) -> bool:
        """处理单个AgentInterview command - 子类必须实现"""
        raise NotImplementedError

    async def handle_batch_interview(self, command_id: str, args: Dict[str, Any]) -> bool:
        """处理批量Interview command - 子类必须实现"""
        raise NotImplementedError

    async def handle_inject_event(self, command_id: str, args: Dict[str, Any]) -> bool:
        """处理事件注入命令 - 子类必须实现"""
        raise NotImplementedError
