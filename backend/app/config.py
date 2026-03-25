"""
Configuration management.
Loads configuration from the project root .env file.
"""

import os
from dotenv import load_dotenv

# Load .env file from project root
# Path: MiroFish/.env (relative to backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # If no .env in project root, try loading environment variables (for production)
    load_dotenv(override=True)


class Config:
    """Flask configuration class."""

    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(32).hex())
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    # JSON configuration - disable ASCII escaping to display non-ASCII characters directly
    JSON_AS_ASCII = False

    # LLM configuration (unified OpenAI format)
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')

    # Neo4j / Graphiti configuration
    NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'mirofish_neo4j')

    # Embeddings for Graphiti semantic search
    # Option 1: Voyage AI (set VOYAGE_API_KEY)
    # Option 2: Local via Ollama or any OpenAI-compatible server (default)
    VOYAGE_API_KEY = os.environ.get('VOYAGE_API_KEY', '')
    EMBEDDER_BASE_URL = os.environ.get('EMBEDDER_BASE_URL', 'http://localhost:11434/v1')
    EMBEDDER_MODEL = os.environ.get('EMBEDDER_MODEL', 'nomic-embed-text')
    EMBEDDER_DIM = int(os.environ.get('EMBEDDER_DIM', '768'))

    # File upload configuration
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}

    # Text processing configuration
    DEFAULT_CHUNK_SIZE = 500  # Default chunk size
    DEFAULT_CHUNK_OVERLAP = 50  # Default overlap size

    # OASIS simulation configuration
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '30'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')

    # OASIS platform available actions
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]

    # CORS configuration
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')

    # Report Agent configuration
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '10'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '3'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    # Pipeline cost budget (USD). Aborts LLM calls when cumulative cost exceeds this limit.
    PIPELINE_BUDGET_LIMIT = float(os.environ.get('PIPELINE_BUDGET_LIMIT', '20.0'))

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY is not configured")
        if not cls.NEO4J_URI:
            errors.append("NEO4J_URI is not configured")
        if not cls.VOYAGE_API_KEY and not cls.EMBEDDER_BASE_URL:
            errors.append("Either VOYAGE_API_KEY or EMBEDDER_BASE_URL must be configured for embeddings")
        return errors
