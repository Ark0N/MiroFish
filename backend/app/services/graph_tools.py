"""
Graph retrieval tools service.
Wraps graph search, node/edge queries for Report Agent.
Replaces zep_tools.py (Zep Cloud → Graphiti + Neo4j).

Core retrieval tools:
1. InsightForge (deep insight retrieval)
2. PanoramaSearch (breadth search)
3. QuickSearch (simple search)
4. InterviewAgents (agent interviews)
"""

import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from graphiti_core.nodes import EntityNode as GraphitiNode, CommunityNode
from graphiti_core.edges import EntityEdge as GraphitiEdge

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..utils.graph_paging import fetch_all_nodes, fetch_all_edges
from ..utils.graphiti_manager import GraphitiManager, run_async

logger = get_logger('mirofish.graph_tools')


@dataclass
class SearchResult:
    """Search result."""
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count
        }

    def to_text(self) -> str:
        text_parts = [f"Search query: {self.query}", f"Found {self.total_count} related items"]
        if self.facts:
            text_parts.append("\n### Related facts:")
            for i, fact in enumerate(self.facts, 1):
                text_parts.append(f"{i}. {fact}")
        return "\n".join(text_parts)


@dataclass
class NodeInfo:
    """Node information."""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes
        }

    def to_text(self) -> str:
        entity_type = next((l for l in self.labels if l not in ["Entity", "Node"]), "Unknown type")
        return f"Entity: {self.name} (type: {entity_type})\nSummary: {self.summary}"


@dataclass
class EdgeInfo:
    """Edge information."""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = None
    target_node_name: Optional[str] = None
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at
        }

    def to_text(self, include_temporal: bool = False) -> str:
        source = self.source_node_name or self.source_node_uuid[:8]
        target = self.target_node_name or self.target_node_uuid[:8]
        base_text = f"Relationship: {source} --[{self.name}]--> {target}\nFact: {self.fact}"
        if include_temporal:
            valid_at = self.valid_at or "unknown"
            invalid_at = self.invalid_at or "present"
            base_text += f"\nValid period: {valid_at} - {invalid_at}"
            if self.expired_at:
                base_text += f" (expired: {self.expired_at})"
        return base_text

    @property
    def is_expired(self) -> bool:
        return self.expired_at is not None

    @property
    def is_invalid(self) -> bool:
        return self.invalid_at is not None


@dataclass
class InsightForgeResult:
    """Deep insight retrieval result."""
    query: str
    simulation_requirement: str
    sub_queries: List[str]
    semantic_facts: List[str] = field(default_factory=list)
    entity_insights: List[Dict[str, Any]] = field(default_factory=list)
    relationship_chains: List[str] = field(default_factory=list)
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": self.sub_queries,
            "semantic_facts": self.semantic_facts,
            "entity_insights": self.entity_insights,
            "relationship_chains": self.relationship_chains,
            "total_facts": self.total_facts,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships
        }

    def to_text(self) -> str:
        text_parts = [
            f"## Deep Predictive Analysis",
            f"Analysis query: {self.query}",
            f"Prediction scenario: {self.simulation_requirement}",
            f"\n### Prediction Data Statistics",
            f"- Related prediction facts: {self.total_facts}",
            f"- Entities involved: {self.total_entities}",
            f"- Relationship chains: {self.total_relationships}"
        ]
        if self.sub_queries:
            text_parts.append(f"\n### Sub-questions Analyzed")
            for i, sq in enumerate(self.sub_queries, 1):
                text_parts.append(f"{i}. {sq}")
        if self.semantic_facts:
            text_parts.append(f"\n### [Key Facts] (cite these in the report)")
            for i, fact in enumerate(self.semantic_facts, 1):
                text_parts.append(f'{i}. "{fact}"')
        if self.entity_insights:
            text_parts.append(f"\n### [Core Entities]")
            for entity in self.entity_insights:
                text_parts.append(f"- **{entity.get('name', 'Unknown')}** ({entity.get('type', 'Entity')})")
                if entity.get('summary'):
                    text_parts.append(f'  Summary: "{entity.get("summary")}"')
                if entity.get('related_facts'):
                    text_parts.append(f"  Related facts: {len(entity.get('related_facts', []))}")
        if self.relationship_chains:
            text_parts.append(f"\n### [Relationship Chains]")
            for chain in self.relationship_chains:
                text_parts.append(f"- {chain}")
        return "\n".join(text_parts)


@dataclass
class PanoramaResult:
    """Breadth search result."""
    query: str
    all_nodes: List[NodeInfo] = field(default_factory=list)
    all_edges: List[EdgeInfo] = field(default_factory=list)
    active_facts: List[str] = field(default_factory=list)
    historical_facts: List[str] = field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0
    communities: List[Dict[str, Any]] = field(default_factory=list)  # Community/cluster info from graph

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "all_nodes": [n.to_dict() for n in self.all_nodes],
            "all_edges": [e.to_dict() for e in self.all_edges],
            "active_facts": self.active_facts,
            "historical_facts": self.historical_facts,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "active_count": self.active_count,
            "historical_count": self.historical_count,
            "communities": self.communities
        }

    def to_text(self) -> str:
        text_parts = [
            f"## Breadth Search Results (Future Panoramic View)",
            f"Query: {self.query}",
            f"\n### Statistics",
            f"- Total nodes: {self.total_nodes}",
            f"- Total edges: {self.total_edges}",
            f"- Current active facts: {self.active_count}",
            f"- Historical/expired facts: {self.historical_count}"
        ]
        if self.active_facts:
            text_parts.append(f"\n### [Current Active Facts] (simulation results)")
            for i, fact in enumerate(self.active_facts, 1):
                text_parts.append(f'{i}. "{fact}"')
        if self.historical_facts:
            text_parts.append(f"\n### [Historical/Expired Facts] (evolution records)")
            for i, fact in enumerate(self.historical_facts, 1):
                text_parts.append(f'{i}. "{fact}"')
        if self.all_nodes:
            text_parts.append(f"\n### [Entities Involved]")
            for node in self.all_nodes:
                entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "Entity")
                text_parts.append(f"- **{node.name}** ({entity_type})")
        if self.communities:
            text_parts.append(f"\n### [Communities/Clusters] ({len(self.communities)} detected)")
            for i, comm in enumerate(self.communities, 1):
                text_parts.append(f"**{i}. {comm.get('name', 'Unnamed')}** ({comm.get('member_count', 0)} members)")
                if comm.get('summary'):
                    text_parts.append(f"   Summary: {comm['summary']}")
        return "\n".join(text_parts)


@dataclass
class AgentInterview:
    """Single agent interview result."""
    agent_name: str
    agent_role: str
    agent_bio: str
    question: str
    response: str
    key_quotes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "agent_bio": self.agent_bio,
            "question": self.question,
            "response": self.response,
            "key_quotes": self.key_quotes
        }

    def to_text(self) -> str:
        text = f"**{self.agent_name}** ({self.agent_role})\n"
        text += f"_Bio: {self.agent_bio}_\n\n"
        text += f"**Q:** {self.question}\n\n"
        text += f"**A:** {self.response}\n"
        if self.key_quotes:
            text += "\n**Key Quotes:**\n"
            for quote in self.key_quotes:
                clean_quote = quote.replace('\u201c', '').replace('\u201d', '').replace('"', '')
                clean_quote = clean_quote.replace('\u300c', '').replace('\u300d', '')
                clean_quote = clean_quote.strip()
                while clean_quote and clean_quote[0] in '，,；;：:、。！？\n\r\t ':
                    clean_quote = clean_quote[1:]
                skip = False
                for d in '123456789':
                    if f'\u95ee\u9898{d}' in clean_quote:
                        skip = True
                        break
                if skip:
                    continue
                if len(clean_quote) > 150:
                    dot_pos = clean_quote.find('\u3002', 80)
                    if dot_pos > 0:
                        clean_quote = clean_quote[:dot_pos + 1]
                    else:
                        clean_quote = clean_quote[:147] + "..."
                if clean_quote and len(clean_quote) >= 10:
                    text += f'> "{clean_quote}"\n'
        return text


@dataclass
class InterviewResult:
    """Interview result containing multiple agent interviews."""
    interview_topic: str
    interview_questions: List[str]
    selected_agents: List[Dict[str, Any]] = field(default_factory=list)
    interviews: List[AgentInterview] = field(default_factory=list)
    selection_reasoning: str = ""
    summary: str = ""
    total_agents: int = 0
    interviewed_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_topic": self.interview_topic,
            "interview_questions": self.interview_questions,
            "selected_agents": self.selected_agents,
            "interviews": [i.to_dict() for i in self.interviews],
            "selection_reasoning": self.selection_reasoning,
            "summary": self.summary,
            "total_agents": self.total_agents,
            "interviewed_count": self.interviewed_count
        }

    def to_text(self) -> str:
        text_parts = [
            "## In-Depth Interview Report",
            f"**Interview Topic:** {self.interview_topic}",
            f"**Interviewed:** {self.interviewed_count} / {self.total_agents} simulation agents",
            "\n### Interview Subject Selection Reasoning",
            self.selection_reasoning or "(auto-selected)",
            "\n---",
            "\n### Interview Transcripts",
        ]
        if self.interviews:
            for i, interview in enumerate(self.interviews, 1):
                text_parts.append(f"\n#### Interview #{i}: {interview.agent_name}")
                text_parts.append(interview.to_text())
                text_parts.append("\n---")
        else:
            text_parts.append("(no interview records)\n\n---")
        text_parts.append("\n### Interview Summary and Key Viewpoints")
        text_parts.append(self.summary or "(no summary)")
        return "\n".join(text_parts)


@dataclass
class ConsensusStrength:
    """Weighted consensus strength score with sub-components."""
    diversity_score: float  # 0-1: how many agent behavior types are in the dominant faction
    conviction_score: float  # 0-1: average abs sentiment magnitude of agents
    stability_score: float  # 0-1: how stable was sentiment direction across rounds
    weighted_score: float  # 0-1: composite (diversity * 0.3 + conviction * 0.3 + stability * 0.4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diversity_score": round(self.diversity_score, 3),
            "conviction_score": round(self.conviction_score, 3),
            "stability_score": round(self.stability_score, 3),
            "weighted_score": round(self.weighted_score, 3),
        }


@dataclass
class ConsensusResult:
    """Result from consensus analysis tool."""
    query: str
    total_agents_analyzed: int
    stance_distribution: Dict[str, int]  # e.g., {"supportive": 15, "opposing": 8, "neutral": 12}
    sentiment_summary: Dict[str, Any]  # avg sentiment, positive/negative/neutral counts
    key_factions: List[Dict[str, Any]]  # groups of agents with similar views
    agreement_score: float  # 0.0 (complete disagreement) to 1.0 (full consensus)
    top_themes: List[str]  # most discussed themes
    representative_quotes: List[Dict[str, str]]  # {"agent": name, "quote": content, "stance": stance}
    consensus_strength: Optional[ConsensusStrength] = None  # weighted consensus strength

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "total_agents_analyzed": self.total_agents_analyzed,
            "stance_distribution": self.stance_distribution,
            "sentiment_summary": self.sentiment_summary,
            "key_factions": self.key_factions,
            "agreement_score": self.agreement_score,
            "top_themes": self.top_themes,
            "representative_quotes": self.representative_quotes,
            "consensus_strength": self.consensus_strength.to_dict() if self.consensus_strength else None
        }

    def to_text(self) -> str:
        text_parts = [
            "## Consensus Analysis",
            f"Query: {self.query}",
            f"Total agents analyzed: {self.total_agents_analyzed}",
            f"Agreement score: {self.agreement_score} (0=complete disagreement, 1=full consensus)",
            "\n### Stance Distribution",
        ]
        for stance, count in self.stance_distribution.items():
            pct = round(count / self.total_agents_analyzed * 100, 1) if self.total_agents_analyzed > 0 else 0
            text_parts.append(f"- {stance}: {count} agents ({pct}%)")

        text_parts.append("\n### Sentiment Summary")
        text_parts.append(f"- Average sentiment: {self.sentiment_summary.get('average', 0)}")
        text_parts.append(f"- Positive agents: {self.sentiment_summary.get('positive_agents', 0)}")
        text_parts.append(f"- Negative agents: {self.sentiment_summary.get('negative_agents', 0)}")
        text_parts.append(f"- Neutral agents: {self.sentiment_summary.get('neutral_agents', 0)}")

        if self.sentiment_summary.get("trajectory"):
            text_parts.append("\n### Sentiment Trajectory")
            for t in self.sentiment_summary["trajectory"]:
                text_parts.append(
                    f"- Round {t.get('round', '?')} ({t.get('platform', '?')}): "
                    f"avg_sentiment={t.get('avg_sentiment', 0)}, posts={t.get('content_posts', 0)}"
                )

        if self.key_factions:
            text_parts.append("\n### Identified Factions")
            for faction in self.key_factions:
                text_parts.append(
                    f"- **{faction['stance']}** faction: {faction['count']} agents "
                    f"(avg sentiment: {faction.get('avg_sentiment', 'N/A')})"
                )
                members = faction.get("members", [])
                if members:
                    text_parts.append(f"  Members: {', '.join(members[:10])}")

        if self.top_themes:
            text_parts.append("\n### Top Discussed Themes")
            for i, theme in enumerate(self.top_themes, 1):
                text_parts.append(f"{i}. {theme}")

        if self.representative_quotes:
            text_parts.append("\n### Representative Quotes")
            for rq in self.representative_quotes:
                text_parts.append(f'- **{rq["agent"]}** ({rq["stance"]}): "{rq["quote"]}"')

        if self.consensus_strength:
            cs = self.consensus_strength
            text_parts.append("\n### Consensus Strength")
            text_parts.append(f"- **Weighted Score**: {cs.weighted_score:.3f} (0=weak, 1=strong)")
            text_parts.append(f"- Agent diversity: {cs.diversity_score:.3f} (behavioral type spread in dominant faction)")
            text_parts.append(f"- Conviction intensity: {cs.conviction_score:.3f} (average sentiment magnitude)")
            text_parts.append(f"- Temporal stability: {cs.stability_score:.3f} (consistency across rounds)")

        return "\n".join(text_parts)


class GraphToolsService:
    """
    Graph retrieval tools service.

    Core tools:
    1. insight_forge - Deep insight retrieval
    2. panorama_search - Breadth search
    3. quick_search - Simple search
    4. interview_agents - Agent interviews
    5. consensus_analysis - Consensus/disagreement analysis across agents

    Foundation tools:
    - search_graph, get_all_nodes, get_all_edges, get_node_detail,
      get_node_edges, get_entities_by_type, get_entity_summary
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 2.0

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._llm_client = llm_client
        logger.info("GraphToolsService initialized")

    @property
    def llm(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def _call_with_retry(self, func, operation_name: str, max_retries: int = None):
        max_retries = max_retries or self.MAX_RETRIES
        last_exception = None
        delay = self.RETRY_DELAY
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Graph {operation_name} attempt {attempt + 1} failed: {str(e)[:100]}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"Graph {operation_name} failed after {max_retries} attempts: {str(e)}")
        raise last_exception

    def search_graph(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Semantic search on the knowledge graph.

        Uses Graphiti's hybrid search. Falls back to local keyword matching
        if the search API fails.
        """
        logger.info(f"Graph search: graph_id={graph_id}, query={query[:50]}...")

        try:
            graphiti = GraphitiManager.get_instance()

            search_results = self._call_with_retry(
                func=lambda: run_async(graphiti.search(
                    query=query,
                    group_ids=[graph_id],
                    num_results=limit
                )),
                operation_name=f"graph search (graph={graph_id})"
            )

            facts = []
            edges = []

            # Graphiti search returns list[EntityEdge]
            for edge in search_results:
                if edge.fact:
                    facts.append(edge.fact)
                edges.append({
                    "uuid": edge.uuid,
                    "name": edge.name or "",
                    "fact": edge.fact or "",
                    "source_node_uuid": edge.source_node_uuid,
                    "target_node_uuid": edge.target_node_uuid,
                })

            logger.info(f"Search complete: found {len(facts)} related facts")

            return SearchResult(
                facts=facts,
                edges=edges,
                nodes=[],
                query=query,
                total_count=len(facts)
            )

        except Exception as e:
            logger.warning(f"Graph Search API failed, falling back to local search: {str(e)}")
            return self._local_search(graph_id, query, limit, scope)

    def _local_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """Local keyword matching search (fallback)."""
        logger.info(f"Using local search: query={query[:30]}...")

        facts = []
        edges_result = []
        nodes_result = []

        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]

        def match_score(text: str) -> int:
            if not text:
                return 0
            text_lower = text.lower()
            if query_lower in text_lower:
                return 100
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 10
            return score

        try:
            if scope in ["edges", "both"]:
                all_edges = self.get_all_edges(graph_id)
                scored_edges = []
                for edge in all_edges:
                    score = match_score(edge.fact) + match_score(edge.name)
                    if score > 0:
                        scored_edges.append((score, edge))
                scored_edges.sort(key=lambda x: x[0], reverse=True)
                for score, edge in scored_edges[:limit]:
                    if edge.fact:
                        facts.append(edge.fact)
                    edges_result.append({
                        "uuid": edge.uuid,
                        "name": edge.name,
                        "fact": edge.fact,
                        "source_node_uuid": edge.source_node_uuid,
                        "target_node_uuid": edge.target_node_uuid,
                    })

            if scope in ["nodes", "both"]:
                all_nodes = self.get_all_nodes(graph_id)
                scored_nodes = []
                for node in all_nodes:
                    score = match_score(node.name) + match_score(node.summary)
                    if score > 0:
                        scored_nodes.append((score, node))
                scored_nodes.sort(key=lambda x: x[0], reverse=True)
                for score, node in scored_nodes[:limit]:
                    nodes_result.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "labels": node.labels,
                        "summary": node.summary,
                    })
                    if node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")

            logger.info(f"Local search complete: found {len(facts)} related facts")

        except Exception as e:
            logger.error(f"Local search failed: {str(e)}")

        return SearchResult(
            facts=facts,
            edges=edges_result,
            nodes=nodes_result,
            query=query,
            total_count=len(facts)
        )

    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """Get all nodes in the graph."""
        logger.info(f"Fetching all nodes for graph {graph_id}...")
        nodes = fetch_all_nodes(graph_id)
        result = []
        for node in nodes:
            result.append(NodeInfo(
                uuid=node.uuid,
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            ))
        logger.info(f"Fetched {len(result)} nodes")
        return result

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        """Get all edges in the graph (with temporal info)."""
        logger.info(f"Fetching all edges for graph {graph_id}...")
        edges = fetch_all_edges(graph_id)
        result = []
        for edge in edges:
            edge_info = EdgeInfo(
                uuid=edge.uuid,
                name=edge.name or "",
                fact=edge.fact or "",
                source_node_uuid=edge.source_node_uuid or "",
                target_node_uuid=edge.target_node_uuid or ""
            )
            if include_temporal:
                edge_info.created_at = str(edge.created_at) if edge.created_at else None
                edge_info.valid_at = str(edge.valid_at) if edge.valid_at else None
                edge_info.invalid_at = str(edge.invalid_at) if edge.invalid_at else None
                edge_info.expired_at = str(edge.expired_at) if edge.expired_at else None
            result.append(edge_info)
        logger.info(f"Fetched {len(result)} edges")
        return result

    def get_node_detail(self, node_uuid: str) -> Optional[NodeInfo]:
        """Get detailed info for a single node."""
        logger.info(f"Fetching node detail: {node_uuid[:8]}...")
        try:
            graphiti = GraphitiManager.get_instance()
            driver = graphiti.driver

            # Get edges for node, which confirms it exists
            edges = self._call_with_retry(
                func=lambda: run_async(
                    GraphitiEdge.get_by_node_uuid(driver, node_uuid)
                ),
                operation_name=f"get node detail (uuid={node_uuid[:8]}...)"
            )

            # We need to find the node itself. Try to get it from a known group.
            # Since we have edges, we can confirm the node exists. But we need the node data.
            # Use a broader search approach - query all nodes and find by UUID
            # This is less efficient but reliable for this use case
            return None  # Will be populated when called from methods that already have nodes
        except Exception as e:
            logger.error(f"Failed to get node detail: {str(e)}")
            return None

    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        """Get all edges related to a node."""
        logger.info(f"Fetching edges for node {node_uuid[:8]}...")
        try:
            all_edges = self.get_all_edges(graph_id)
            result = []
            for edge in all_edges:
                if edge.source_node_uuid == node_uuid or edge.target_node_uuid == node_uuid:
                    result.append(edge)
            logger.info(f"Found {len(result)} edges for node")
            return result
        except Exception as e:
            logger.warning(f"Failed to get node edges: {str(e)}")
            return []

    def get_entities_by_type(self, graph_id: str, entity_type: str) -> List[NodeInfo]:
        """Get entities by type."""
        logger.info(f"Fetching entities of type {entity_type}...")
        all_nodes = self.get_all_nodes(graph_id)
        filtered = [node for node in all_nodes if entity_type in node.labels]
        logger.info(f"Found {len(filtered)} entities of type {entity_type}")
        return filtered

    def get_entity_summary(self, graph_id: str, entity_name: str) -> Dict[str, Any]:
        """Get relationship summary for an entity."""
        logger.info(f"Fetching entity summary for {entity_name}...")
        search_result = self.search_graph(graph_id=graph_id, query=entity_name, limit=20)
        all_nodes = self.get_all_nodes(graph_id)
        entity_node = None
        for node in all_nodes:
            if node.name.lower() == entity_name.lower():
                entity_node = node
                break
        related_edges = []
        if entity_node:
            related_edges = self.get_node_edges(graph_id, entity_node.uuid)
        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else None,
            "related_facts": search_result.facts,
            "related_edges": [e.to_dict() for e in related_edges],
            "total_relations": len(related_edges)
        }

    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        """Get graph statistics."""
        logger.info(f"Fetching graph statistics for {graph_id}...")
        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)
        entity_types = {}
        for node in nodes:
            for label in node.labels:
                if label not in ["Entity", "Node"]:
                    entity_types[label] = entity_types.get(label, 0) + 1
        relation_types = {}
        for edge in edges:
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1
        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types
        }

    def get_simulation_context(self, graph_id: str, simulation_requirement: str, limit: int = 30) -> Dict[str, Any]:
        """Get simulation-related context."""
        logger.info(f"Fetching simulation context: {simulation_requirement[:50]}...")
        search_result = self.search_graph(graph_id=graph_id, query=simulation_requirement, limit=limit)
        stats = self.get_graph_statistics(graph_id)
        all_nodes = self.get_all_nodes(graph_id)
        entities = []
        for node in all_nodes:
            custom_labels = [l for l in node.labels if l not in ["Entity", "Node"]]
            if custom_labels:
                entities.append({
                    "name": node.name,
                    "type": custom_labels[0],
                    "summary": node.summary
                })
        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": search_result.facts,
            "graph_statistics": stats,
            "entities": entities[:limit],
            "total_entities": len(entities)
        }

    # ========== Core retrieval tools ==========

    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5
    ) -> InsightForgeResult:
        """InsightForge - Deep insight retrieval."""
        logger.info(f"InsightForge: {query[:50]}...")

        result = InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=[]
        )

        sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries
        )
        result.sub_queries = sub_queries
        logger.info(f"Generated {len(sub_queries)} sub-queries")

        all_facts = []
        all_edges = []
        seen_facts = set()

        for sub_query in sub_queries:
            search_result = self.search_graph(graph_id=graph_id, query=sub_query, limit=15, scope="edges")
            for fact in search_result.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)
            all_edges.extend(search_result.edges)

        main_search = self.search_graph(graph_id=graph_id, query=query, limit=20, scope="edges")
        for fact in main_search.facts:
            if fact not in seen_facts:
                all_facts.append(fact)
                seen_facts.add(fact)

        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)

        # Extract related entity UUIDs from edges
        entity_uuids = set()
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                if source_uuid:
                    entity_uuids.add(source_uuid)
                if target_uuid:
                    entity_uuids.add(target_uuid)

        # Get all nodes for this graph and index by UUID
        all_nodes = self.get_all_nodes(graph_id)
        all_nodes_map = {n.uuid: n for n in all_nodes}

        entity_insights = []
        node_map = {}

        for uuid_val in entity_uuids:
            if not uuid_val:
                continue
            node = all_nodes_map.get(uuid_val)
            if node:
                node_map[uuid_val] = node
                entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "Entity")
                related_facts = [f for f in all_facts if node.name.lower() in f.lower()]
                entity_insights.append({
                    "uuid": node.uuid,
                    "name": node.name,
                    "type": entity_type,
                    "summary": node.summary,
                    "related_facts": related_facts
                })

        result.entity_insights = entity_insights
        result.total_entities = len(entity_insights)

        # Build relationship chains
        relationship_chains = []
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                relation_name = edge_data.get('name', '')
                source_name = node_map.get(source_uuid, NodeInfo('', '', [], '', {})).name or source_uuid[:8]
                target_name = node_map.get(target_uuid, NodeInfo('', '', [], '', {})).name or target_uuid[:8]
                chain = f"{source_name} --[{relation_name}]--> {target_name}"
                if chain not in relationship_chains:
                    relationship_chains.append(chain)

        result.relationship_chains = relationship_chains
        result.total_relationships = len(relationship_chains)

        logger.info(f"InsightForge complete: {result.total_facts} facts, {result.total_entities} entities, {result.total_relationships} relationships")
        return result

    def _generate_sub_queries(self, query: str, simulation_requirement: str,
                              report_context: str = "", max_queries: int = 5) -> List[str]:
        """Generate sub-queries using LLM."""
        system_prompt = """You are a professional question analysis expert. Your task is to break down a complex question into multiple sub-questions that can be independently observed in the simulated world.

Requirements:
1. Each sub-question should be specific enough to find related agent behavior or events in the simulated world
2. Sub-questions should cover different dimensions of the original question (e.g., who, what, why, how, when, where)
3. Sub-questions should be relevant to the simulation scenario
4. Return in JSON format: {"sub_queries": ["sub-question 1", "sub-question 2", ...]}"""

        user_prompt = f"""Simulation requirement background:
{simulation_requirement}

{f"Report context:{report_context[:500]}" if report_context else ""}

Please break down the following question into {max_queries} sub-questions:
{query}

Return the sub-question list in JSON format."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            sub_queries = response.get("sub_queries", [])
            return [str(sq) for sq in sub_queries[:max_queries]]
        except Exception as e:
            logger.warning(f"Failed to generate sub-queries: {str(e)}, using defaults")
            return [
                query,
                f"Main participants in {query}",
                f"Causes and impacts of {query}",
                f"Development process of {query}"
            ][:max_queries]

    def panorama_search(self, graph_id: str, query: str,
                        include_expired: bool = True, limit: int = 50) -> PanoramaResult:
        """PanoramaSearch - Breadth search."""
        logger.info(f"PanoramaSearch: {query[:50]}...")

        result = PanoramaResult(query=query)

        all_nodes = self.get_all_nodes(graph_id)
        node_map = {n.uuid: n for n in all_nodes}
        result.all_nodes = all_nodes
        result.total_nodes = len(all_nodes)

        all_edges = self.get_all_edges(graph_id, include_temporal=True)
        result.all_edges = all_edges
        result.total_edges = len(all_edges)

        active_facts = []
        historical_facts = []

        for edge in all_edges:
            if not edge.fact:
                continue
            source_name = node_map.get(edge.source_node_uuid, NodeInfo('', '', [], '', {})).name or edge.source_node_uuid[:8]
            target_name = node_map.get(edge.target_node_uuid, NodeInfo('', '', [], '', {})).name or edge.target_node_uuid[:8]
            is_historical = edge.is_expired or edge.is_invalid
            if is_historical:
                valid_at = edge.valid_at or "unknown"
                invalid_at = edge.invalid_at or edge.expired_at or "unknown"
                fact_with_time = f"[{valid_at} - {invalid_at}] {edge.fact}"
                historical_facts.append(fact_with_time)
            else:
                active_facts.append(edge.fact)

        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]

        def relevance_score(fact: str) -> int:
            fact_lower = fact.lower()
            score = 0
            if query_lower in fact_lower:
                score += 100
            for kw in keywords:
                if kw in fact_lower:
                    score += 10
            return score

        active_facts.sort(key=relevance_score, reverse=True)
        historical_facts.sort(key=relevance_score, reverse=True)

        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)

        # Fetch community data from graph
        communities = []
        try:
            graphiti = GraphitiManager.get_instance()
            community_nodes = run_async(CommunityNode.get_by_group_ids(graphiti.driver, [graph_id]))
            for comm in community_nodes[:10]:  # Top 10 communities
                # Count members via HAS_MEMBER edges
                member_count = 0
                try:
                    records, _, _ = run_async(graphiti.driver.execute_query(
                        "MATCH (c:Community {uuid: $uuid})-[:HAS_MEMBER]->(e:Entity) RETURN count(e) AS cnt",
                        uuid=comm.uuid,
                        database_="neo4j",
                    ))
                    if records:
                        member_count = records[0]['cnt']
                except Exception:
                    pass
                communities.append({
                    "name": comm.name or "unnamed",
                    "summary": comm.summary or "",
                    "member_count": member_count,
                    "uuid": comm.uuid,
                })
        except Exception as e:
            logger.warning(f"Community fetch failed (non-fatal): {e}")

        result.communities = communities

        logger.info(f"PanoramaSearch complete: {result.active_count} active, {result.historical_count} historical, {len(communities)} communities")
        return result

    def quick_search(self, graph_id: str, query: str, limit: int = 10) -> SearchResult:
        """QuickSearch - Simple search."""
        logger.info(f"QuickSearch: {query[:50]}...")
        result = self.search_graph(graph_id=graph_id, query=query, limit=limit, scope="edges")
        logger.info(f"QuickSearch complete: {result.total_count} results")
        return result

    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: List[str] = None
    ) -> InterviewResult:
        """InterviewAgents - Deep interview with simulation agents."""
        from .simulation_runner import SimulationRunner

        logger.info(f"InterviewAgents: {interview_requirement[:50]}...")

        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or []
        )

        profiles = self._load_agent_profiles(simulation_id)
        if not profiles:
            logger.warning(f"No profiles found for simulation {simulation_id}")
            result.summary = "No agent profile files found for interview"
            return result

        result.total_agents = len(profiles)
        logger.info(f"Loaded {len(profiles)} agent profiles")

        selected_agents, selected_indices, selection_reasoning = self._select_agents_for_interview(
            profiles=profiles,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents
        )

        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning
        logger.info(f"Selected {len(selected_agents)} agents: {selected_indices}")

        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents
            )
            logger.info(f"Generated {len(result.interview_questions)} interview questions")

        combined_prompt = "\n".join([f"{i+1}. {q}" for i, q in enumerate(result.interview_questions)])

        INTERVIEW_PROMPT_PREFIX = (
            "You are being interviewed. Drawing on your persona, all past memories and actions, "
            "answer the following questions directly in plain text.\n"
            "Response requirements:\n"
            "1. Answer directly in natural language, do not call any tools\n"
            "2. Do not return JSON format or tool call format\n"
            "3. Do not use Markdown headings (such as #, ##, ###)\n"
            "4. Answer each question by number, starting each answer with \"Question X:\" (X is the question number)\n"
            "5. Separate each answer with a blank line\n"
            "6. Answers should be substantive, at least 2-3 sentences per question\n\n"
        )
        optimized_prompt = f"{INTERVIEW_PROMPT_PREFIX}{combined_prompt}"

        try:
            interviews_request = []
            for agent_idx in selected_indices:
                interviews_request.append({
                    "agent_id": agent_idx,
                    "prompt": optimized_prompt
                })

            logger.info(f"Calling batch interview API: {len(interviews_request)} agents")

            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=None,
                timeout=180.0
            )

            logger.info(f"Interview API returned: {api_result.get('interviews_count', 0)} results")

            if not api_result.get("success", False):
                error_msg = api_result.get("error", "Unknown error")
                logger.warning(f"Interview API failed: {error_msg}")
                result.summary = f"Interview API call failed: {error_msg}. Please check OASIS simulation environment status."
                return result

            api_data = api_result.get("result", {})
            results_dict = api_data.get("results", {}) if isinstance(api_data, dict) else {}

            for i, agent_idx in enumerate(selected_indices):
                agent = selected_agents[i]
                agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
                agent_role = agent.get("profession", "unknown")
                agent_bio = agent.get("bio", "")

                twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_result = results_dict.get(f"reddit_{agent_idx}", {})

                twitter_response = twitter_result.get("response", "")
                reddit_response = reddit_result.get("response", "")

                twitter_response = self._clean_tool_call_response(twitter_response)
                reddit_response = self._clean_tool_call_response(reddit_response)

                twitter_text = twitter_response if twitter_response else "(no response from this platform)"
                reddit_text = reddit_response if reddit_response else "(no response from this platform)"
                response_text = f"[Twitter Response]\n{twitter_text}\n\n[Reddit Response]\n{reddit_text}"

                import re
                combined_responses = f"{twitter_response} {reddit_response}"

                clean_text = re.sub(r'#{1,6}\s+', '', combined_responses)
                clean_text = re.sub(r'\{[^}]*tool_name[^}]*\}', '', clean_text)
                clean_text = re.sub(r'[*_`|>~\-]{2,}', '', clean_text)
                clean_text = re.sub(r'(?:Question|问题)\d+[：:]\s*', '', clean_text)
                clean_text = re.sub(r'【[^】]+】', '', clean_text)

                sentences = re.split(r'[。！？]', clean_text)
                meaningful = [
                    s.strip() for s in sentences
                    if 20 <= len(s.strip()) <= 150
                    and not re.match(r'^[\s\W，,；;：:、]+', s.strip())
                    and not s.strip().startswith(('{', 'Question', '问题'))
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + "。" for s in meaningful[:3]]

                if not key_quotes:
                    paired = re.findall(r'\u201c([^\u201c\u201d]{15,100})\u201d', clean_text)
                    paired += re.findall(r'\u300c([^\u300c\u300d]{15,100})\u300d', clean_text)
                    key_quotes = [q for q in paired if not re.match(r'^[，,；;：:、]', q)][:3]

                interview = AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000],
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5]
                )
                result.interviews.append(interview)

            result.interviewed_count = len(result.interviews)

        except ValueError as e:
            logger.warning(f"Interview API failed (env not running?): {e}")
            result.summary = f"Interview failed: {str(e)}. Simulation environment may be closed. Please ensure the OASIS environment is running."
            return result
        except Exception as e:
            logger.error(f"Interview API error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            result.summary = f"Error during interview: {str(e)}"
            return result

        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement
            )

        logger.info(f"InterviewAgents complete: interviewed {result.interviewed_count} agents")
        return result

    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        """Clean JSON tool call wrapping from agent responses."""
        if not response or not response.strip().startswith('{'):
            return response
        text = response.strip()
        if 'tool_name' not in text[:80]:
            return response
        import re as _re
        try:
            data = json.loads(text)
            if isinstance(data, dict) and 'arguments' in data:
                for key in ('content', 'text', 'body', 'message', 'reply'):
                    if key in data['arguments']:
                        return str(data['arguments'][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = _re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace('\\n', '\n').replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        """Load agent profiles for a simulation."""
        import os
        import csv

        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )

        profiles = []

        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_profile_path):
            try:
                with open(reddit_profile_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                logger.info(f"Loaded {len(profiles)} profiles from reddit_profiles.json")
                return profiles
            except Exception as e:
                logger.warning(f"Failed to read reddit_profiles.json: {e}")

        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_profile_path):
            try:
                with open(twitter_profile_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        profiles.append({
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": "unknown"
                        })
                logger.info(f"Loaded {len(profiles)} profiles from twitter_profiles.csv")
                return profiles
            except Exception as e:
                logger.warning(f"Failed to read twitter_profiles.csv: {e}")

        return profiles

    def _select_agents_for_interview(self, profiles: List[Dict[str, Any]],
                                     interview_requirement: str,
                                     simulation_requirement: str,
                                     max_agents: int) -> tuple:
        """Select agents for interview using LLM."""
        agent_summaries = []
        for i, profile in enumerate(profiles):
            summary = {
                "index": i,
                "name": profile.get("realname", profile.get("username", f"Agent_{i}")),
                "profession": profile.get("profession", "unknown"),
                "bio": profile.get("bio", "")[:200],
                "interested_topics": profile.get("interested_topics", [])
            }
            agent_summaries.append(summary)

        system_prompt = """You are a professional interview planning expert. Your task is to select the most suitable interview subjects from the simulation agent list based on the interview requirements.

Selection criteria:
1. Agent's identity/profession is relevant to the interview topic
2. Agent may hold unique or valuable viewpoints
3. Select diverse perspectives (e.g., supporters, opponents, neutral parties, professionals, etc.)
4. Prioritize roles directly related to the event

Return in JSON format:
{
    "selected_indices": [list of selected agent indices],
    "reasoning": "explanation of selection reasoning"
}"""

        user_prompt = f"""Interview requirement:
{interview_requirement}

Simulation background:
{simulation_requirement if simulation_requirement else "not provided"}

Available agent list ({len(agent_summaries)} agents):
{json.dumps(agent_summaries, ensure_ascii=False, indent=2)}

Please select up to {max_agents} agents most suitable for interview, and explain the selection reasoning."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            selected_indices = response.get("selected_indices", [])[:max_agents]
            reasoning = response.get("reasoning", "Automatically selected based on relevance")
            selected_agents = []
            valid_indices = []
            for idx in selected_indices:
                if 0 <= idx < len(profiles):
                    selected_agents.append(profiles[idx])
                    valid_indices.append(idx)
            return selected_agents, valid_indices, reasoning
        except Exception as e:
            logger.warning(f"LLM agent selection failed, using defaults: {e}")
            selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return selected, indices, "Using default selection strategy"

    def _generate_interview_questions(self, interview_requirement: str,
                                      simulation_requirement: str,
                                      selected_agents: List[Dict[str, Any]]) -> List[str]:
        """Generate interview questions using LLM."""
        agent_roles = [a.get("profession", "unknown") for a in selected_agents]

        system_prompt = """You are a professional journalist/interviewer. Based on the interview requirements, generate 3-5 in-depth interview questions.

Question requirements:
1. Open-ended questions that encourage detailed answers
2. Different roles may give different answers
3. Cover multiple dimensions such as facts, opinions, feelings
4. Natural language, like a real interview
5. Keep each question concise, under 50 words
6. Ask directly, without background explanations or prefixes

Return in JSON format: {"questions": ["question 1", "question 2", ...]}"""

        user_prompt = f"""Interview requirement: {interview_requirement}

Simulation background: {simulation_requirement if simulation_requirement else "not provided"}

Interviewee roles: {', '.join(agent_roles)}

Please generate 3-5 interview questions."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5
            )
            return response.get("questions", [f"What are your views on {interview_requirement}?"])
        except Exception as e:
            logger.warning(f"Failed to generate interview questions: {e}")
            return [
                f"What is your perspective on {interview_requirement}?",
                "How does this matter affect you or the group you represent?",
                "How do you think this issue should be resolved or improved?"
            ]

    def _generate_interview_summary(self, interviews: List[AgentInterview],
                                    interview_requirement: str) -> str:
        """Generate interview summary using LLM."""
        if not interviews:
            return "No interviews completed"

        interview_texts = []
        for interview in interviews:
            interview_texts.append(f"[{interview.agent_name} ({interview.agent_role})]\n{interview.response[:500]}")

        system_prompt = """You are a professional news editor. Based on multiple interviewees' responses, generate an interview summary.

Summary requirements:
1. Extract key viewpoints from all parties
2. Identify consensus and disagreements
3. Highlight valuable quotes
4. Be objective and neutral, without favoring any side
5. Keep within 1000 words

Format constraints (must follow):
- Use plain text paragraphs, separate sections with blank lines
- Do not use Markdown headings (such as #, ##, ###)
- Do not use dividers (such as ---, ***)
- Use quotation marks when citing interviewees
- You may use **bold** to mark keywords, but do not use other Markdown syntax"""

        user_prompt = f"""Interview topic: {interview_requirement}

Interview content:
{"".join(interview_texts)}

Please generate an interview summary."""

        try:
            summary = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            return summary
        except Exception as e:
            logger.warning(f"Failed to generate interview summary: {e}")
            return f"Interviewed {len(interviews)} respondents, including: " + ", ".join([i.agent_name for i in interviews])

    def _compute_consensus_strength(
        self,
        agent_sentiments: Dict[str, float],
        stance_dist: Dict[str, int],
        trajectory: List[Dict],
        all_posts: List[Dict],
        simulation_dir: str
    ) -> ConsensusStrength:
        """Compute weighted consensus strength from diversity, conviction, and stability.

        Diversity: how many behavioral types (Creator/Engager/Lurker/Influencer inferred
        from action patterns) are in the dominant faction. Higher diversity = stronger signal.

        Conviction: average absolute sentiment magnitude across all agents. Strong opinions
        (positive or negative) indicate higher conviction.

        Stability: how consistent the sentiment direction is across rounds. Computed from
        trajectory data — if sentiment sign stays the same across rounds, stability is high.
        """
        import os as _os
        import math

        # --- Diversity score ---
        # Infer agent behavior types from action logs
        agent_action_counts = {}  # agent -> {creates, likes, reposts, comments}
        for platform in ["twitter", "reddit"]:
            actions_file = _os.path.join(simulation_dir, platform, "actions.jsonl")
            if not _os.path.exists(actions_file):
                continue
            try:
                with open(actions_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            action = json.loads(line)
                            agent = action.get("agent_name", action.get("user_name", ""))
                            atype = action.get("action_type", "")
                            if agent not in agent_action_counts:
                                agent_action_counts[agent] = {"creates": 0, "likes": 0, "reposts": 0, "comments": 0}
                            if atype in ("CREATE_POST",):
                                agent_action_counts[agent]["creates"] += 1
                            elif atype in ("LIKE_POST", "LIKE_COMMENT"):
                                agent_action_counts[agent]["likes"] += 1
                            elif atype in ("REPOST",):
                                agent_action_counts[agent]["reposts"] += 1
                            elif atype in ("CREATE_COMMENT", "QUOTE_POST"):
                                agent_action_counts[agent]["comments"] += 1
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

        # Classify agents into behavioral types
        def classify_agent(counts):
            total = sum(counts.values())
            if total == 0:
                return "lurker"
            create_ratio = counts["creates"] / total
            comment_ratio = counts["comments"] / total
            like_ratio = counts["likes"] / total
            if create_ratio > 0.4:
                return "creator"
            elif comment_ratio > 0.3:
                return "engager"
            elif like_ratio > 0.5:
                return "lurker"
            else:
                return "influencer"

        agent_types = {agent: classify_agent(c) for agent, c in agent_action_counts.items()}

        # Find dominant stance
        dominant_stance = max(stance_dist, key=stance_dist.get) if stance_dist else "neutral"

        # Count unique types in dominant faction
        dominant_types = set()
        for agent, avg_sent in agent_sentiments.items():
            in_dominant = (
                (dominant_stance == "supportive" and avg_sent > 0.15) or
                (dominant_stance == "opposing" and avg_sent < -0.15) or
                (dominant_stance == "neutral" and -0.15 <= avg_sent <= 0.15)
            )
            if in_dominant and agent in agent_types:
                dominant_types.add(agent_types[agent])

        # 4 possible types, so diversity = unique_types / 4
        diversity_score = len(dominant_types) / 4.0 if dominant_types else 0.0

        # --- Conviction score ---
        # Average absolute sentiment across all agents
        if agent_sentiments:
            abs_sentiments = [abs(s) for s in agent_sentiments.values()]
            conviction_score = min(sum(abs_sentiments) / len(abs_sentiments) / 0.5, 1.0)
        else:
            conviction_score = 0.0

        # --- Stability score ---
        # Check if sentiment direction is consistent across rounds
        if trajectory and len(trajectory) >= 2:
            signs = []
            for t in trajectory:
                s = t.get("avg_sentiment", 0)
                if s > 0.05:
                    signs.append(1)
                elif s < -0.05:
                    signs.append(-1)
                else:
                    signs.append(0)

            # Count direction changes
            changes = sum(1 for i in range(1, len(signs)) if signs[i] != signs[i-1])
            max_changes = len(signs) - 1
            stability_score = 1.0 - (changes / max_changes) if max_changes > 0 else 1.0
        else:
            # No trajectory data, default to moderate stability
            stability_score = 0.5

        # --- Weighted composite ---
        weighted_score = (
            diversity_score * 0.3 +
            conviction_score * 0.3 +
            stability_score * 0.4
        )

        return ConsensusStrength(
            diversity_score=diversity_score,
            conviction_score=conviction_score,
            stability_score=stability_score,
            weighted_score=weighted_score
        )

    def consensus_analysis(self, query: str, simulation_dir: str) -> ConsensusResult:
        """Analyze agreement/disagreement patterns across simulation agents.

        Reads simulation action logs (actions.jsonl) and round metrics to compute:
        - Stance distribution across agents
        - Sentiment clustering
        - Faction identification (groups with similar views)
        - Agreement score

        Args:
            query: The topic/question to analyze consensus around
            simulation_dir: Path to simulation output directory
        """
        import os as _os

        all_posts = []
        agent_stances = {}  # agent_name -> list of sentiments

        # Read action logs from both platforms
        for platform in ["twitter", "reddit"]:
            actions_file = _os.path.join(simulation_dir, platform, "actions.jsonl")
            if not _os.path.exists(actions_file):
                continue

            try:
                with open(actions_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            action = json.loads(line)
                            action_type = action.get("action_type", "")
                            if action_type in ("CREATE_POST", "CREATE_COMMENT", "QUOTE_POST"):
                                agent_name = action.get("agent_name", action.get("user_name", "unknown"))
                                content = action.get("content", action.get("action_args", {}).get("content", ""))
                                if content:
                                    all_posts.append({"agent": agent_name, "content": str(content), "platform": platform})
                                    if agent_name not in agent_stances:
                                        agent_stances[agent_name] = []
                                    agent_stances[agent_name].append(str(content))
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

        # Simple keyword-based sentiment analysis per post
        positive_keywords = {"good", "great", "support", "agree", "happy", "love", "excellent", "hope", "thank", "progress", "solution", "positive", "improvement", "benefit"}
        negative_keywords = {"bad", "terrible", "oppose", "disagree", "angry", "hate", "awful", "crisis", "fail", "problem", "scandal", "corrupt", "outrage", "concern", "danger", "risk", "worried"}

        agent_sentiments = {}
        for agent, posts in agent_stances.items():
            scores = []
            for post in posts:
                lower_post = post.lower()
                pos = sum(1 for w in positive_keywords if w in lower_post)
                neg = sum(1 for w in negative_keywords if w in lower_post)
                total = pos + neg
                score = (pos - neg) / total if total > 0 else 0.0
                scores.append(score)
            avg = sum(scores) / len(scores) if scores else 0.0
            agent_sentiments[agent] = avg

        # Classify stances
        stance_dist = {"supportive": 0, "opposing": 0, "neutral": 0}
        for agent, avg_sent in agent_sentiments.items():
            if avg_sent > 0.15:
                stance_dist["supportive"] += 1
            elif avg_sent < -0.15:
                stance_dist["opposing"] += 1
            else:
                stance_dist["neutral"] += 1

        total_agents = len(agent_sentiments)

        # Compute agreement score (1.0 = all same stance, 0.0 = evenly split)
        if total_agents > 0:
            max_faction = max(stance_dist.values())
            agreement_score = max_faction / total_agents
        else:
            agreement_score = 0.0

        # Identify factions
        factions = []
        for stance_name in ["supportive", "opposing", "neutral"]:
            members = []
            for agent, avg_sent in agent_sentiments.items():
                if stance_name == "supportive" and avg_sent > 0.15:
                    members.append(agent)
                elif stance_name == "opposing" and avg_sent < -0.15:
                    members.append(agent)
                elif stance_name == "neutral" and -0.15 <= avg_sent <= 0.15:
                    members.append(agent)
            if members:
                factions.append({
                    "stance": stance_name,
                    "count": len(members),
                    "members": members[:10],  # Top 10 members
                    "avg_sentiment": round(sum(agent_sentiments[m] for m in members) / len(members), 3)
                })

        # Extract top themes (most common words in posts, excluding stopwords)
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
                     "do", "does", "did", "will", "would", "shall", "should", "may", "might", "can", "could",
                     "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
                     "my", "your", "his", "its", "our", "their", "this", "that", "these", "those",
                     "in", "on", "at", "to", "for", "of", "with", "by", "from", "as", "into", "through",
                     "and", "but", "or", "not", "no", "so", "if", "when", "what", "which", "who", "how",
                     "all", "each", "every", "both", "few", "more", "most", "other", "some", "such",
                     "than", "too", "very", "just", "about", "above", "after", "before", "between",
                     "same", "also", "only", "own", "then", "there", "here", "now", "up", "out", "over"}
        word_counts = {}
        query_lower = query.lower()
        for post in all_posts:
            words = post["content"].lower().split()
            for word in words:
                word = ''.join(c for c in word if c.isalnum())
                if word and len(word) > 2 and word not in stopwords:
                    word_counts[word] = word_counts.get(word, 0) + 1
        top_themes = sorted(word_counts, key=word_counts.get, reverse=True)[:15]

        # Get representative quotes (one per faction)
        representative_quotes = []
        for faction in factions:
            if faction["members"]:
                agent = faction["members"][0]
                posts_for_agent = agent_stances.get(agent, [])
                if posts_for_agent:
                    # Pick the longest post as most representative
                    best_post = max(posts_for_agent, key=len)
                    representative_quotes.append({
                        "agent": agent,
                        "quote": best_post[:500],
                        "stance": faction["stance"]
                    })

        # Sentiment summary
        all_sentiments = list(agent_sentiments.values())
        sentiment_summary = {
            "average": round(sum(all_sentiments) / len(all_sentiments), 3) if all_sentiments else 0.0,
            "positive_agents": stance_dist["supportive"],
            "negative_agents": stance_dist["opposing"],
            "neutral_agents": stance_dist["neutral"],
        }

        # Also read round metrics if available for trajectory info
        trajectory = []
        for platform in ["twitter", "reddit"]:
            metrics_file = _os.path.join(simulation_dir, platform, "round_metrics.jsonl")
            if _os.path.exists(metrics_file):
                try:
                    with open(metrics_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    m = json.loads(line)
                                    trajectory.append({
                                        "round": m.get("round"),
                                        "platform": platform,
                                        "avg_sentiment": m.get("sentiment", {}).get("average", 0),
                                        "content_posts": m.get("content_posts", 0)
                                    })
                                except json.JSONDecodeError:
                                    continue
                except Exception:
                    continue

        if trajectory:
            sentiment_summary["trajectory"] = trajectory

        # Compute consensus strength (diversity, conviction, stability)
        consensus_strength = self._compute_consensus_strength(
            agent_sentiments=agent_sentiments,
            stance_dist=stance_dist,
            trajectory=trajectory,
            all_posts=all_posts,
            simulation_dir=simulation_dir
        )

        return ConsensusResult(
            query=query,
            total_agents_analyzed=total_agents,
            stance_distribution=stance_dist,
            sentiment_summary=sentiment_summary,
            key_factions=factions,
            agreement_score=round(agreement_score, 3),
            top_themes=top_themes,
            representative_quotes=representative_quotes,
            consensus_strength=consensus_strength
        )
