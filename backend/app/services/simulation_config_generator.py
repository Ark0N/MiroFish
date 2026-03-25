"""
Intelligent simulation configuration generator
Uses LLM to automatically generate detailed simulation parameters based on requirements, document content, and graph info.
Fully automated, no manual parameter setting needed.

Uses step-by-step generation strategy to avoid failures from generating too much at once:
1. Generate time configuration
2. Generate event configuration
3. Generate agent configs in batches
4. Generate platform configuration
"""

import json
import math
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

from openai import OpenAI

from ..config import Config
from ..utils.llm_client import _is_anthropic_key, create_anthropic_client
from ..utils.logger import get_logger
from .graph_entity_reader import EntityNode, GraphEntityReader

logger = get_logger('mirofish.simulation_config')

# China timezone activity schedule (Beijing time)
CHINA_TIMEZONE_CONFIG = {
    # Late night hours (almost no activity)
    "dead_hours": [0, 1, 2, 3, 4, 5],
    # Morning hours (gradually waking up)
    "morning_hours": [6, 7, 8],
    # Work hours
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    # Evening peak (most active)
    "peak_hours": [19, 20, 21, 22],
    # Night hours (activity declining)
    "night_hours": [23],
    # Activity multipliers
    "activity_multipliers": {
        "dead": 0.05,      # Almost no one in early morning
        "morning": 0.4,    # Morning gradually active
        "work": 0.7,       # Moderate during work hours
        "peak": 1.5,       # Evening peak
        "night": 0.5       # Late night decline
    }
}


@dataclass
class AgentActivityConfig:
    """Single agent activity configuration."""
    agent_id: int
    entity_uuid: str
    entity_name: str
    entity_type: str
    
    # Activity level (0.0-1.0)
    activity_level: float = 0.5  # Overall activity level
    
    # Posting frequency (expected posts per hour)
    posts_per_hour: float = 1.0
    comments_per_hour: float = 2.0
    
    # Active hours (24-hour format, 0-23)
    active_hours: List[int] = field(default_factory=lambda: list(range(8, 23)))
    
    # Response speed (delay to hot events, unit: simulated minutes)
    response_delay_min: int = 5
    response_delay_max: int = 60
    
    # Sentiment bias (-1.0 to 1.0, negative to positive)
    sentiment_bias: float = 0.0
    
    # Stance (attitude toward specific topics)
    stance: str = "neutral"  # supportive, opposing, neutral, observer
    
    # Influence weight (determines probability of their posts being seen by other agents)
    influence_weight: float = 1.0

    # LLM temperature for this agent (higher = more creative/impulsive, lower = more analytical)
    temperature: float = 0.7


@dataclass
class TimeSimulationConfig:
    """Time simulation configuration (based on Chinese timezone activity patterns)."""
    # Total simulation duration (simulated hours)
    total_simulation_hours: int = 72  # Default: simulate 72 hours (3 days)
    
    # Time per round (simulated minutes) - default 60 min (1 hour), accelerated time flow
    minutes_per_round: int = 60
    
    # Agent activation range per hour
    agents_per_hour_min: int = 5
    agents_per_hour_max: int = 20
    
    # Peak hours (19:00-22:00, most active time in Chinese timezone)
    peak_hours: List[int] = field(default_factory=lambda: [19, 20, 21, 22])
    peak_activity_multiplier: float = 1.5
    
    # Off-peak hours (00:00-05:00, almost no activity)
    off_peak_hours: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    off_peak_activity_multiplier: float = 0.05  # Extremely low early morning activity
    
    # Morning hours
    morning_hours: List[int] = field(default_factory=lambda: [6, 7, 8])
    morning_activity_multiplier: float = 0.4
    
    # Work hours
    work_hours: List[int] = field(default_factory=lambda: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18])
    work_activity_multiplier: float = 0.7


@dataclass
class EventConfig:
    """Event configuration."""
    # Initial events (triggered at simulation start)
    initial_posts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Scheduled events (triggered at specific times)
    scheduled_events: List[Dict[str, Any]] = field(default_factory=list)
    
    # Hot topic keywords
    hot_topics: List[str] = field(default_factory=list)
    
    # Narrative direction
    narrative_direction: str = ""


@dataclass
class PlatformConfig:
    """Platform-specific configuration."""
    platform: str  # twitter or reddit
    
    # Recommendation algorithm weights
    recency_weight: float = 0.4  # Time recency
    popularity_weight: float = 0.3  # Popularity
    relevance_weight: float = 0.3  # Relevance
    
    # Viral threshold (interactions needed to trigger spread)
    viral_threshold: int = 10
    
    # Echo chamber effect strength (degree of similar viewpoint clustering)
    echo_chamber_strength: float = 0.5


@dataclass
class SimulationParameters:
    """Complete simulation parameter configuration."""
    # Basic information
    simulation_id: str
    project_id: str
    graph_id: str
    simulation_requirement: str
    
    # Time configuration
    time_config: TimeSimulationConfig = field(default_factory=TimeSimulationConfig)
    
    # Agent configuration list
    agent_configs: List[AgentActivityConfig] = field(default_factory=list)
    
    # Event configuration
    event_config: EventConfig = field(default_factory=EventConfig)
    
    # Platform configuration
    twitter_config: Optional[PlatformConfig] = None
    reddit_config: Optional[PlatformConfig] = None
    
    # LLM configuration
    llm_model: str = ""
    llm_base_url: str = ""
    
    # Generation metadata
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generation_reasoning: str = ""  # LLM's reasoning explanation
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        time_dict = asdict(self.time_config)
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "time_config": time_dict,
            "agent_configs": [asdict(a) for a in self.agent_configs],
            "event_config": asdict(self.event_config),
            "twitter_config": asdict(self.twitter_config) if self.twitter_config else None,
            "reddit_config": asdict(self.reddit_config) if self.reddit_config else None,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "generated_at": self.generated_at,
            "generation_reasoning": self.generation_reasoning,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class SimulationConfigGenerator:
    """
    Intelligent simulation configuration generator
    
    Uses LLM to analyze simulation requirements, document content, and graph entity info
    to automatically generate optimal simulation parameter configuration
    
    Uses step-by-step generation strategy:
    1. Generate time and event config (lightweight)
    2. Generate agent configs in batches (10-20 per batch)
    3. Generate platform config
    """
    
    # Maximum context character count
    MAX_CONTEXT_LENGTH = 50000
    # Agents per batch
    AGENTS_PER_BATCH = 15
    
    # Context truncation length per step (characters)
    TIME_CONFIG_CONTEXT_LENGTH = 10000   # Time configuration
    EVENT_CONFIG_CONTEXT_LENGTH = 8000   # Event configuration
    ENTITY_SUMMARY_LENGTH = 300          # Entity summary
    AGENT_SUMMARY_LENGTH = 300           # Entity summary in agent config
    ENTITIES_PER_TYPE_DISPLAY = 20       # Number of entities to display per type
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")
        
        self._use_anthropic = _is_anthropic_key(self.api_key)
        if self._use_anthropic:
            self._anthropic_client = create_anthropic_client(self.api_key, self.base_url)
            self.client = None
        else:
            self._anthropic_client = None
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
    
    def generate_config(
        self,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> SimulationParameters:
        """
        Intelligently generate complete simulation configuration (step-by-step)
        
        Args:
            simulation_id: Simulation ID
            project_id: Project ID
            graph_id: Graph ID
            simulation_requirement: Simulation requirement description
            document_text: Original document content
            entities: Filtered entity list
            enable_twitter: Whether to enable Twitter
            enable_reddit: Whether to enable Reddit
            progress_callback: Progress callback function(current_step, total_steps, message)
            
        Returns:
            SimulationParameters: Complete simulation parameters
        """
        logger.info(f"Starting intelligent simulation config generation: simulation_id={simulation_id}, entities={len(entities)}")
        
        # Calculate total steps
        num_batches = math.ceil(len(entities) / self.AGENTS_PER_BATCH)
        total_steps = 3 + num_batches  # Time config + event config + N agent batches + platform config
        current_step = 0
        
        def report_progress(step: int, message: str):
            nonlocal current_step
            current_step = step
            if progress_callback:
                progress_callback(step, total_steps, message)
            logger.info(f"[{step}/{total_steps}] {message}")
        
        # 1. Build base context info
        context = self._build_context(
            simulation_requirement=simulation_requirement,
            document_text=document_text,
            entities=entities
        )
        
        reasoning_parts = []
        
        # ========== Step 1: Generate time config ==========
        report_progress(1, "Generating time config...")
        num_entities = len(entities)
        time_config_result = self._generate_time_config(context, num_entities)
        time_config = self._parse_time_config(time_config_result, num_entities)
        reasoning_parts.append(f"Time config: {time_config_result.get('reasoning', 'success')}")
        
        # ========== Step 2: Generate event config ==========
        report_progress(2, "Generating event config and hot topics...")
        event_config_result = self._generate_event_config(context, simulation_requirement, entities)
        event_config = self._parse_event_config(event_config_result)
        reasoning_parts.append(f"Event config: {event_config_result.get('reasoning', 'success')}")
        
        # ========== Step 3-N: Generate agent configs in batches ==========
        all_agent_configs = []
        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.AGENTS_PER_BATCH
            end_idx = min(start_idx + self.AGENTS_PER_BATCH, len(entities))
            batch_entities = entities[start_idx:end_idx]
            
            report_progress(
                3 + batch_idx,
                f"Generating agent configs ({start_idx + 1}-{end_idx}/{len(entities)})..."
            )
            
            batch_configs = self._generate_agent_configs_batch(
                context=context,
                entities=batch_entities,
                start_idx=start_idx,
                simulation_requirement=simulation_requirement
            )
            all_agent_configs.extend(batch_configs)
        
        reasoning_parts.append(f"Agent configs: successfully generated {len(all_agent_configs)}")

        # Apply power-law distribution for realistic social media activity patterns
        all_agent_configs = self._apply_power_law_distribution(all_agent_configs)

        # ========== Assign publisher agents to initial posts ==========
        logger.info("Assigning suitable publisher agents to initial posts...")
        event_config = self._assign_initial_post_agents(event_config, all_agent_configs)
        assigned_count = len([p for p in event_config.initial_posts if p.get("poster_agent_id") is not None])
        reasoning_parts.append(f"Initial post assignment: {assigned_count} posts assigned to publishers")
        
        # ========== Final step: Generate platform config ==========
        report_progress(total_steps, "Generating platform config...")
        twitter_config = None
        reddit_config = None
        
        if enable_twitter:
            twitter_config = PlatformConfig(
                platform="twitter",
                recency_weight=0.4,
                popularity_weight=0.3,
                relevance_weight=0.3,
                viral_threshold=10,
                echo_chamber_strength=0.5
            )
        
        if enable_reddit:
            reddit_config = PlatformConfig(
                platform="reddit",
                recency_weight=0.3,
                popularity_weight=0.4,
                relevance_weight=0.3,
                viral_threshold=15,
                echo_chamber_strength=0.6
            )
        
        # Build final parameters
        params = SimulationParameters(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            time_config=time_config,
            agent_configs=all_agent_configs,
            event_config=event_config,
            twitter_config=twitter_config,
            reddit_config=reddit_config,
            llm_model=self.model_name,
            llm_base_url=self.base_url,
            generation_reasoning=" | ".join(reasoning_parts)
        )
        
        logger.info(f"Simulation config generation completed: {len(params.agent_configs)} agent configs")
        
        return params
    
    def _build_context(
        self,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode]
    ) -> str:
        """Build LLM context, truncated to max length."""
        
        # Entity summary
        entity_summary = self._summarize_entities(entities)
        
        # Build context
        context_parts = [
            f"## Simulation Requirement\n{simulation_requirement}",
            f"\n## Entity Information ({len(entities)})\n{entity_summary}",
        ]
        
        current_length = sum(len(p) for p in context_parts)
        remaining_length = self.MAX_CONTEXT_LENGTH - current_length - 500  # Leave 500 char buffer
        
        if remaining_length > 0 and document_text:
            doc_text = document_text[:remaining_length]
            if len(document_text) > remaining_length:
                doc_text += "\n...(document truncated)"
            context_parts.append(f"\n## Original Document Content\n{doc_text}")
        
        return "\n".join(context_parts)
    
    def _summarize_entities(self, entities: List[EntityNode]) -> str:
        """Generate entity summary."""
        lines = []
        
        # Group by type
        by_type: Dict[str, List[EntityNode]] = {}
        for e in entities:
            t = e.get_entity_type() or "Unknown"
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(e)
        
        for entity_type, type_entities in by_type.items():
            lines.append(f"\n### {entity_type} ({len(type_entities)})")
            # Use configured display count and summary length
            display_count = self.ENTITIES_PER_TYPE_DISPLAY
            summary_len = self.ENTITY_SUMMARY_LENGTH
            for e in type_entities[:display_count]:
                summary_preview = (e.summary[:summary_len] + "...") if len(e.summary) > summary_len else e.summary
                lines.append(f"- {e.name}: {summary_preview}")
            if len(type_entities) > display_count:
                lines.append(f"  ... plus {len(type_entities) - display_count} ")
        
        return "\n".join(lines)
    
    def _call_llm_with_retry(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """LLM call with retry and JSON repair logic."""
        import re
        
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                temp = 0.7 - (attempt * 0.1)

                if self._use_anthropic:
                    json_hint = "\n\nIMPORTANT: Respond with valid JSON only. No markdown, no code blocks."
                    resp = self._anthropic_client.messages.create(
                        model=self.model_name,
                        system=system_prompt + json_hint,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temp,
                        max_tokens=8192,
                    )
                    if not resp.content:
                        raise ValueError("Empty response from API")
                    content = resp.content[0].text
                    # Strip closed think tags
                    content = re.sub(r'<think>[\s\S]*?</think>', '', content, flags=re.DOTALL).strip()
                    # Also strip unclosed think tags (truncated output)
                    content = re.sub(r'<think>[\s\S]*$', '', content, flags=re.DOTALL).strip()
                    if resp.stop_reason == "content_filter":
                        raise ValueError("Response was filtered by content safety policy")
                    finish_reason = "length" if resp.stop_reason == "max_tokens" else "stop"
                else:
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"},
                        temperature=temp,
                    )
                    content = response.choices[0].message.content
                    finish_reason = response.choices[0].finish_reason

                # Check if truncated
                if finish_reason == 'length':
                    logger.warning(f"LLM output truncated (attempt {attempt+1})")
                    content = self._fix_truncated_json(content)
                
                # Try to parse JSON
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parse failed (attempt {attempt+1}): {str(e)[:80]}")
                    
                    # Try to fix JSON
                    fixed = self._try_fix_config_json(content)
                    if fixed:
                        return fixed
                    
                    last_error = e
                    
            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(2 * (attempt + 1))
        
        raise last_error or Exception("LLM call failed")
    
    def _fix_truncated_json(self, content: str) -> str:
        """Fix truncated JSON."""
        content = content.strip()
        
        # Count unclosed brackets
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # Check for unclosed strings
        if content and content[-1] not in '",}]':
            content += '"'
        
        # Close brackets
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_config_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Try to fix config JSON."""
        import re
        
        # Fix truncation cases
        content = self._fix_truncated_json(content)
        
        # Extract JSON portion
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # Remove newlines in strings
            def fix_string(match):
                s = match.group(0)
                s = s.replace('\n', ' ').replace('\r', ' ')
                s = re.sub(r'\s+', ' ', s)
                return s
            
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string, json_str)
            
            try:
                return json.loads(json_str)
            except:
                # Try removing all control characters
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                json_str = re.sub(r'\s+', ' ', json_str)
                try:
                    return json.loads(json_str)
                except:
                    pass
        
        return None
    
    def _generate_time_config(self, context: str, num_entities: int) -> Dict[str, Any]:
        """Generate time configuration."""
        # Use configured context truncation length
        context_truncated = context[:self.TIME_CONFIG_CONTEXT_LENGTH]
        
        # Calculate max allowed value (80% of agent count)
        max_agents_allowed = max(1, int(num_entities * 0.9))
        
        prompt = f"""Based on the following simulation requirements, generate time simulation configuration.

{context_truncated}

## Task
Please generate time configuration JSON.

### Basic Principles (for reference only, adjust flexibly based on specific events and participant groups):
- User base follows Chinese timezone activity patterns (Beijing time)
- 00:00-05:00 almost no activity (activity coefficient 0.05)
- 06:00-08:00 gradually active (activity coefficient 0.4)
- 09:00-18:00 moderately active (activity coefficient 0.7)
- 19:00-22:00 peak hours (activity coefficient 1.5)
- After 23:00 activity declines (activity coefficient 0.5)
- General pattern: low early morning, increasing morning, moderate work hours, evening peak
- **Important**: Example values below are for reference only; adjust based on event nature and participant characteristics
  - Example: Student peak may be 21:00-23:00; media active all day; official agencies only during work hours
  - Example: Breaking news may cause late-night discussions, off_peak_hours can be shortened

### Return JSON format (no markdown)

Example:
{{
    "total_simulation_hours": 72,
    "minutes_per_round": 60,
    "agents_per_hour_min": 5,
    "agents_per_hour_max": 50,
    "peak_hours": [19, 20, 21, 22],
    "off_peak_hours": [0, 1, 2, 3, 4, 5],
    "morning_hours": [6, 7, 8],
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    "reasoning": "Time configuration explanation for this event"
}}

Field descriptions:
- total_simulation_hours (int): Total simulation duration, 24-168 hours, shorter for breaking events, longer for ongoing topics
- minutes_per_round (int): Duration per round, 30-120 minutes, recommended 60 minutes
- agents_per_hour_min (int): Minimum agents activated per hour (range: 1-{max_agents_allowed})
- agents_per_hour_max (int): Maximum agents activated per hour (range: 1-{max_agents_allowed})
- peak_hours (int array): Peak hours, adjust based on event participant groups
- off_peak_hours (int array): Off-peak hours, usually late night/early morning
- morning_hours (int array): Morning hours
- work_hours (int array): Work hours
- reasoning (string): Brief explanation of why this configuration was chosen"""

        system_prompt = "You are a social media simulation expert. Return pure JSON format. Time configuration should follow Chinese timezone activity patterns."
        
        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"Time configLLM生成失败: {e}, using default config")
            return self._get_default_time_config(num_entities)
    
    def _get_default_time_config(self, num_entities: int) -> Dict[str, Any]:
        """获取默认Time config（中国人作息）"""
        return {
            "total_simulation_hours": 72,
            "minutes_per_round": 60,  # 1 hour per round, accelerated time flow
            "agents_per_hour_min": max(1, num_entities // 15),
            "agents_per_hour_max": max(5, num_entities // 5),
            "peak_hours": [19, 20, 21, 22],
            "off_peak_hours": [0, 1, 2, 3, 4, 5],
            "morning_hours": [6, 7, 8],
            "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            "reasoning": "Using default Chinese timezone activity config (1 hour per round)"
        }
    
    def _parse_time_config(self, result: Dict[str, Any], num_entities: int) -> TimeSimulationConfig:
        """Parse time config result and validate agents_per_hour does not exceed total agent count"""
        # Get raw values
        agents_per_hour_min = result.get("agents_per_hour_min", max(1, num_entities // 15))
        agents_per_hour_max = result.get("agents_per_hour_max", max(5, num_entities // 5))
        
        # Validate and correct: ensure does not exceed total agent count
        if agents_per_hour_min > num_entities:
            logger.warning(f"agents_per_hour_min ({agents_per_hour_min}) exceeds total agent count ({num_entities})，corrected")
            agents_per_hour_min = max(1, num_entities // 10)
        
        if agents_per_hour_max > num_entities:
            logger.warning(f"agents_per_hour_max ({agents_per_hour_max}) exceeds total agent count ({num_entities})，corrected")
            agents_per_hour_max = max(agents_per_hour_min + 1, num_entities // 2)
        
        # Ensure min < max
        if agents_per_hour_min >= agents_per_hour_max:
            agents_per_hour_min = max(1, agents_per_hour_max // 2)
            logger.warning(f"agents_per_hour_min >= max，corrected为 {agents_per_hour_min}")
        
        return TimeSimulationConfig(
            total_simulation_hours=result.get("total_simulation_hours", 72),
            minutes_per_round=result.get("minutes_per_round", 60),  # Default 1 hour per round
            agents_per_hour_min=agents_per_hour_min,
            agents_per_hour_max=agents_per_hour_max,
            peak_hours=result.get("peak_hours", [19, 20, 21, 22]),
            off_peak_hours=result.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
            off_peak_activity_multiplier=0.05,  # Almost no one in early morning
            morning_hours=result.get("morning_hours", [6, 7, 8]),
            morning_activity_multiplier=0.4,
            work_hours=result.get("work_hours", list(range(9, 19))),
            work_activity_multiplier=0.7,
            peak_activity_multiplier=1.5
        )
    
    def _generate_event_config(
        self, 
        context: str, 
        simulation_requirement: str,
        entities: List[EntityNode]
    ) -> Dict[str, Any]:
        """生成Event config"""
        
        # Get available entity types list for LLM reference
        entity_types_available = list(set(
            e.get_entity_type() or "Unknown" for e in entities
        ))
        
        # List representative entity names per type
        type_examples = {}
        for e in entities:
            etype = e.get_entity_type() or "Unknown"
            if etype not in type_examples:
                type_examples[etype] = []
            if len(type_examples[etype]) < 3:
                type_examples[etype].append(e.name)
        
        type_info = "\n".join([
            f"- {t}: {', '.join(examples)}" 
            for t, examples in type_examples.items()
        ])
        
        # Use configured context truncation length
        context_truncated = context[:self.EVENT_CONFIG_CONTEXT_LENGTH]
        
        prompt = f"""基于以下Simulation requirement，生成Event config。

Simulation requirement: {simulation_requirement}

{context_truncated}

## Available Entity Types and Examples
{type_info}

## 任务
请生成Event configJSON：
- 提取热点话题关键词
- 描述舆论发展方向
- 设计初始帖子内容，**每帖子必须指定 poster_type（发布者类型）**
- Design 2-3 scheduled events that inject new developments at different simulation stages (e.g., round 5: official response, round 15: media investigation reveals new facts)

**Important**: poster_type must be selected from the "Available Entity Types" above, so initial posts can be assigned to suitable agents.
Example: Official statements should be published by Official/University type, news by MediaOutlet, student opinions by Student.

Return JSON format (no markdown):
{{
    "hot_topics": ["keyword1", "keyword2", ...],
    "narrative_direction": "<narrative development direction>",
    "initial_posts": [
        {{"content": "post content", "poster_type": "entity type (must be from available types)"}},
        ...
    ],
    "scheduled_events": [
        {{"round": <round number>, "content": "event description/post content", "poster_type": "entity type"}},
        ...
    ],
    "reasoning": "<brief explanation>"
}}"""

        system_prompt = "You are a public opinion analysis expert. Return pure JSON format. Note that poster_type must exactly match available entity types."
        
        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"Event configLLM生成失败: {e}, using default config")
            return {
                "hot_topics": [],
                "narrative_direction": "",
                "initial_posts": [],
                "reasoning": "using default config"
            }
    
    def _parse_event_config(self, result: Dict[str, Any]) -> EventConfig:
        """解析Event config结果"""
        return EventConfig(
            initial_posts=result.get("initial_posts", []),
            scheduled_events=result.get("scheduled_events", []),
            hot_topics=result.get("hot_topics", []),
            narrative_direction=result.get("narrative_direction", "")
        )
    
    def _assign_initial_post_agents(
        self,
        event_config: EventConfig,
        agent_configs: List[AgentActivityConfig]
    ) -> EventConfig:
        """
        为Initial post assignment合适的发布者 Agent
        
        根据每帖子的 poster_type Match the most suitable agent_id
        """
        if not event_config.initial_posts:
            return event_config
        
        # Build agent index by entity type
        agents_by_type: Dict[str, List[AgentActivityConfig]] = {}
        for agent in agent_configs:
            etype = agent.entity_type.lower()
            if etype not in agents_by_type:
                agents_by_type[etype] = []
            agents_by_type[etype].append(agent)
        
        # Type alias mapping (handles different formats LLM may output)
        type_aliases = {
            "official": ["official", "university", "governmentagency", "government"],
            "university": ["university", "official"],
            "mediaoutlet": ["mediaoutlet", "media"],
            "student": ["student", "person"],
            "professor": ["professor", "expert", "teacher"],
            "alumni": ["alumni", "person"],
            "organization": ["organization", "ngo", "company", "group"],
            "person": ["person", "student", "alumni"],
        }
        
        # 记录每种类型已使用的 agent 索引，避免重复使用同一 agent
        used_indices: Dict[str, int] = {}
        
        updated_posts = []
        for post in event_config.initial_posts:
            poster_type = post.get("poster_type", "").lower()
            content = post.get("content", "")
            
            # Try to find a matching agent
            matched_agent_id = None
            
            # 1. Direct match
            if poster_type in agents_by_type:
                agents = agents_by_type[poster_type]
                idx = used_indices.get(poster_type, 0) % len(agents)
                matched_agent_id = agents[idx].agent_id
                used_indices[poster_type] = idx + 1
            else:
                # 2. Match using aliases
                for alias_key, aliases in type_aliases.items():
                    if poster_type in aliases or alias_key == poster_type:
                        for alias in aliases:
                            if alias in agents_by_type:
                                agents = agents_by_type[alias]
                                idx = used_indices.get(alias, 0) % len(agents)
                                matched_agent_id = agents[idx].agent_id
                                used_indices[alias] = idx + 1
                                break
                    if matched_agent_id is not None:
                        break
            
            # 3. If still not found, use agent with highest influence
            if matched_agent_id is None:
                logger.warning(f"No agent found for type '{poster_type}' , using agent with highest influence")
                if agent_configs:
                    # Sort by influence, select highest
                    sorted_agents = sorted(agent_configs, key=lambda a: a.influence_weight, reverse=True)
                    matched_agent_id = sorted_agents[0].agent_id
                else:
                    matched_agent_id = 0
            
            updated_posts.append({
                "content": content,
                "poster_type": post.get("poster_type", "Unknown"),
                "poster_agent_id": matched_agent_id
            })
            
            logger.info(f"Initial post assignment: poster_type='{poster_type}' -> agent_id={matched_agent_id}")
        
        event_config.initial_posts = updated_posts
        return event_config
    
    def _generate_agent_configs_batch(
        self,
        context: str,
        entities: List[EntityNode],
        start_idx: int,
        simulation_requirement: str
    ) -> List[AgentActivityConfig]:
        """分批Generating agent configs"""
        
        # Build entity info (using configured summary length)
        entity_list = []
        summary_len = self.AGENT_SUMMARY_LENGTH
        for i, e in enumerate(entities):
            entity_list.append({
                "agent_id": start_idx + i,
                "entity_name": e.name,
                "entity_type": e.get_entity_type() or "Unknown",
                "summary": e.summary[:summary_len] if e.summary else ""
            })
        
        prompt = f"""基于以下信息，为每实体生成社交媒体活动配置。

Simulation requirement: {simulation_requirement}

## Entity List
```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

## 任务
为每实体生成活动配置，注意：
- **时间符合中国人作息**：凌晨0-5点几乎不活动，晚间19-22点最活跃
- **官方机构**（University/GovernmentAgency）：活跃度低(0.1-0.3)，工作时间(9-17)活动，响应慢(60-240分钟)，影响力高(2.5-3.0)
- **媒体**（MediaOutlet）：活跃度中(0.4-0.6)，全天活动(8-23)，响应快(5-30分钟)，影响力高(2.0-2.5)
- **人**（Student/Person/Alumni）：活跃度高(0.6-0.9)，主要晚间活动(18-23)，响应快(1-15分钟)，影响力低(0.8-1.2)
- **公众人物/专家**：活跃度中(0.4-0.6)，影响力中高(1.5-2.0)

Return JSON format (no markdown):
{{
    "agent_configs": [
        {{
            "agent_id": <必须与输入一致>,
            "activity_level": <0.0-1.0>,
            "posts_per_hour": <发帖频率>,
            "comments_per_hour": <评论频率>,
            "active_hours": [<活跃小时列表，考虑中国人作息>],
            "response_delay_min": <最小响应延迟分钟>,
            "response_delay_max": <最大响应延迟分钟>,
            "sentiment_bias": <-1.0到1.0>,
            "stance": "<supportive/opposing/neutral/observer>",
            "influence_weight": <影响力权重>,
            "temperature": <0.3-1.0, lower for analytical/official agents, higher for emotional/impulsive agents>
        }},
        ...
    ]
}}"""

        system_prompt = "You are a social media behavior analysis expert. Return pure JSON, configuration should follow Chinese timezone activity patterns."
        
        try:
            result = self._call_llm_with_retry(prompt, system_prompt)
            llm_configs = {cfg["agent_id"]: cfg for cfg in result.get("agent_configs", [])}
        except Exception as e:
            logger.warning(f"Agent config batch LLM generation failed: {e}, falling back to rule-based generation")
            llm_configs = {}
        
        # Build AgentActivityConfig objects
        configs = []
        for i, entity in enumerate(entities):
            agent_id = start_idx + i
            cfg = llm_configs.get(agent_id, {})
            
            # 如果LLM没有生成，falling back to rule-based generation
            if not cfg:
                cfg = self._generate_agent_config_by_rule(entity)
            
            config = AgentActivityConfig(
                agent_id=agent_id,
                entity_uuid=entity.uuid,
                entity_name=entity.name,
                entity_type=entity.get_entity_type() or "Unknown",
                activity_level=cfg.get("activity_level", 0.5),
                posts_per_hour=cfg.get("posts_per_hour", 0.5),
                comments_per_hour=cfg.get("comments_per_hour", 1.0),
                active_hours=cfg.get("active_hours", list(range(9, 23))),
                response_delay_min=cfg.get("response_delay_min", 5),
                response_delay_max=cfg.get("response_delay_max", 60),
                sentiment_bias=cfg.get("sentiment_bias", 0.0),
                stance=cfg.get("stance", "neutral"),
                influence_weight=cfg.get("influence_weight", 1.0),
                temperature=cfg.get("temperature", 0.7),
            )
            configs.append(config)
        
        return configs
    
    def _apply_power_law_distribution(self, agent_configs: List[AgentActivityConfig]) -> List[AgentActivityConfig]:
        """Apply power-law distribution to activity levels for realistic social media patterns.

        Real social media follows the 90-9-1 rule: 1% create most content, 9% contribute
        occasionally, 90% are lurkers. We use a Pareto-like redistribution.
        """
        import random

        if not agent_configs:
            return agent_configs

        n = len(agent_configs)
        # Generate power-law distributed values (Pareto with alpha=1.5)
        # Higher alpha = more skewed (more lurkers)
        alpha = 1.5
        raw_values = sorted(
            [random.paretovariate(alpha) for _ in range(n)],
            reverse=True
        )

        # Normalize to 0.05-1.0 range (minimum 0.05 so lurkers still occasionally act)
        max_val = max(raw_values) if raw_values else 1.0
        min_val = min(raw_values) if raw_values else 0.0
        range_val = max_val - min_val if max_val != min_val else 1.0

        normalized = [0.05 + 0.95 * (v - min_val) / range_val for v in raw_values]

        # Sort agents by their current activity_level (descending) to preserve relative ranking
        sorted_agents = sorted(agent_configs, key=lambda a: a.activity_level, reverse=True)

        for agent, new_level in zip(sorted_agents, normalized):
            agent.activity_level = round(new_level, 3)

        # Log distribution stats
        levels = [a.activity_level for a in agent_configs]
        high_activity = sum(1 for l in levels if l > 0.7)
        mid_activity = sum(1 for l in levels if 0.3 <= l <= 0.7)
        low_activity = sum(1 for l in levels if l < 0.3)
        logger.info(f"Power-law activity distribution applied: {high_activity} high, {mid_activity} mid, {low_activity} low activity agents")

        return agent_configs

    def _generate_agent_config_by_rule(self, entity: EntityNode) -> Dict[str, Any]:
        """基于规则生成单Agent配置（中国人作息）"""
        entity_type = (entity.get_entity_type() or "Unknown").lower()
        
        if entity_type in ["university", "governmentagency", "ngo"]:
            # Official institutions: work hours activity, low frequency, high influence
            return {
                "activity_level": 0.2,
                "posts_per_hour": 0.1,
                "comments_per_hour": 0.05,
                "active_hours": list(range(9, 18)),  # 9:00-17:59
                "response_delay_min": 60,
                "response_delay_max": 240,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 3.0,
                "temperature": 0.3,
            }
        elif entity_type in ["mediaoutlet"]:
            # Media: all day activity, medium frequency, high influence
            return {
                "activity_level": 0.5,
                "posts_per_hour": 0.8,
                "comments_per_hour": 0.3,
                "active_hours": list(range(7, 24)),  # 7:00-23:59
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "observer",
                "influence_weight": 2.5,
                "temperature": 0.4,
            }
        elif entity_type in ["professor", "expert", "official"]:
            # 专家/教授：工作+晚间活动，中等频率
            return {
                "activity_level": 0.4,
                "posts_per_hour": 0.3,
                "comments_per_hour": 0.5,
                "active_hours": list(range(8, 22)),  # 8:00-21:59
                "response_delay_min": 15,
                "response_delay_max": 90,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 2.0,
                "temperature": 0.4,
            }
        elif entity_type in ["student"]:
            # 学生：晚间为主，高频率
            return {
                "activity_level": 0.8,
                "posts_per_hour": 0.6,
                "comments_per_hour": 1.5,
                "active_hours": [8, 9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # 上午+晚间
                "response_delay_min": 1,
                "response_delay_max": 15,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 0.8,
                "temperature": 0.9,
            }
        elif entity_type in ["alumni"]:
            # 校友：晚间为主
            return {
                "activity_level": 0.6,
                "posts_per_hour": 0.4,
                "comments_per_hour": 0.8,
                "active_hours": [12, 13, 19, 20, 21, 22, 23],  # 午休+晚间
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0,
                "temperature": 0.7,
            }
        else:
            # 普通人：晚间高峰
            return {
                "activity_level": 0.7,
                "posts_per_hour": 0.5,
                "comments_per_hour": 1.2,
                "active_hours": [9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # 白天+晚间
                "response_delay_min": 2,
                "response_delay_max": 20,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0,
                "temperature": 0.7,
            }
    

