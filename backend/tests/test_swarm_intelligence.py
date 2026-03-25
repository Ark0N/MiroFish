"""
Tests for swarm intelligence improvements:
- Power-law activity distribution
- Per-agent temperature variation
- Consensus analysis tool
- Sentiment tracking (RoundMetricsTracker)
- Event injection IPC
- Structured predictions
- Follow relationship generation
"""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Power-law activity distribution tests
# ---------------------------------------------------------------------------


class TestPowerLawDistribution:
    """Tests for power-law activity_level redistribution."""

    def _make_agent_config(self, agent_id, activity_level=0.5):
        from app.services.simulation_config_generator import AgentActivityConfig
        return AgentActivityConfig(
            agent_id=agent_id,
            entity_uuid=f"uuid-{agent_id}",
            entity_name=f"Agent_{agent_id}",
            entity_type="Person",
            activity_level=activity_level,
        )

    def _make_generator(self):
        with patch("app.services.simulation_config_generator._is_anthropic_key", return_value=False):
            with patch("app.services.simulation_config_generator.OpenAI"):
                from app.services.simulation_config_generator import SimulationConfigGenerator
                gen = SimulationConfigGenerator.__new__(SimulationConfigGenerator)
                gen.api_key = "test-key"
                gen.base_url = "http://test"
                gen.model_name = "test-model"
                gen._use_anthropic = False
                gen._anthropic_client = None
                gen.client = MagicMock()
                return gen

    def test_empty_list(self):
        gen = self._make_generator()
        result = gen._apply_power_law_distribution([])
        assert result == []

    def test_single_agent(self):
        gen = self._make_generator()
        agents = [self._make_agent_config(0, 0.5)]
        result = gen._apply_power_law_distribution(agents)
        assert len(result) == 1
        assert 0.05 <= result[0].activity_level <= 1.0

    def test_distribution_is_skewed(self):
        """Most agents should have low activity, few should have high."""
        gen = self._make_generator()
        agents = [self._make_agent_config(i, 0.5) for i in range(50)]
        result = gen._apply_power_law_distribution(agents)

        levels = [a.activity_level for a in result]
        high = sum(1 for l in levels if l > 0.7)
        low = sum(1 for l in levels if l < 0.3)
        # In a power-law distribution, low-activity agents should outnumber high-activity
        assert low > high, f"Expected more low-activity agents ({low}) than high ({high})"

    def test_preserves_relative_ranking(self):
        """Agents originally ranked higher should still be ranked higher."""
        gen = self._make_generator()
        agents = [
            self._make_agent_config(0, 0.9),
            self._make_agent_config(1, 0.1),
            self._make_agent_config(2, 0.5),
        ]
        result = gen._apply_power_law_distribution(agents)

        by_id = {a.agent_id: a.activity_level for a in result}
        # Agent 0 had the highest original level, should still be highest
        assert by_id[0] >= by_id[2]
        assert by_id[2] >= by_id[1]

    def test_all_values_in_range(self):
        gen = self._make_generator()
        agents = [self._make_agent_config(i, 0.5) for i in range(20)]
        result = gen._apply_power_law_distribution(agents)
        for a in result:
            assert 0.05 <= a.activity_level <= 1.0, f"Activity {a.activity_level} out of range"


# ---------------------------------------------------------------------------
# Per-agent temperature tests
# ---------------------------------------------------------------------------


class TestAgentTemperature:
    """Tests for per-agent temperature in AgentActivityConfig."""

    def test_temperature_field_exists(self):
        from app.services.simulation_config_generator import AgentActivityConfig
        config = AgentActivityConfig(
            agent_id=0,
            entity_uuid="test",
            entity_name="Test",
            entity_type="Person",
        )
        assert hasattr(config, "temperature")
        assert config.temperature == 0.7  # default

    def test_temperature_custom_value(self):
        from app.services.simulation_config_generator import AgentActivityConfig
        config = AgentActivityConfig(
            agent_id=0,
            entity_uuid="test",
            entity_name="Test",
            entity_type="Student",
            temperature=0.9,
        )
        assert config.temperature == 0.9

    def test_rule_based_temperature_student(self):
        """Students should get high temperature (emotional/impulsive)."""
        from app.services.simulation_config_generator import SimulationConfigGenerator

        gen = SimulationConfigGenerator.__new__(SimulationConfigGenerator)
        entity = MagicMock()
        entity.get_entity_type.return_value = "Student"

        cfg = gen._generate_agent_config_by_rule(entity)
        assert cfg["temperature"] == 0.9

    def test_rule_based_temperature_university(self):
        """Official institutions should get low temperature (formal/measured)."""
        from app.services.simulation_config_generator import SimulationConfigGenerator

        gen = SimulationConfigGenerator.__new__(SimulationConfigGenerator)
        entity = MagicMock()
        entity.get_entity_type.return_value = "University"

        cfg = gen._generate_agent_config_by_rule(entity)
        assert cfg["temperature"] == 0.3

    def test_rule_based_temperature_media(self):
        """Media should get moderate-low temperature."""
        from app.services.simulation_config_generator import SimulationConfigGenerator

        gen = SimulationConfigGenerator.__new__(SimulationConfigGenerator)
        entity = MagicMock()
        entity.get_entity_type.return_value = "MediaOutlet"

        cfg = gen._generate_agent_config_by_rule(entity)
        assert cfg["temperature"] == 0.4


# ---------------------------------------------------------------------------
# Consensus analysis tool tests
# ---------------------------------------------------------------------------


class TestConsensusAnalysis:
    """Tests for the ConsensusAnalysis tool in graph_tools."""

    def _create_actions_file(self, tmpdir, platform, actions):
        """Create a mock actions.jsonl file."""
        platform_dir = os.path.join(tmpdir, platform)
        os.makedirs(platform_dir, exist_ok=True)
        filepath = os.path.join(platform_dir, "actions.jsonl")
        with open(filepath, "w", encoding="utf-8") as f:
            for action in actions:
                f.write(json.dumps(action, ensure_ascii=False) + "\n")
        return filepath

    def _make_service(self):
        from app.services.graph_tools import GraphToolsService
        service = GraphToolsService.__new__(GraphToolsService)
        service.graph_id = "test-graph"
        service.simulation_id = "test-sim"
        return service

    def test_empty_simulation_dir(self):
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = service.consensus_analysis("test topic", tmpdir)
            assert result.total_agents_analyzed == 0
            assert result.agreement_score == 0.0

    def test_single_agent_posts(self):
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_actions_file(tmpdir, "twitter", [
                {"action_type": "CREATE_POST", "agent_name": "alice", "content": "This is great and wonderful"},
                {"action_type": "CREATE_POST", "agent_name": "alice", "content": "I love this excellent progress"},
            ])
            result = service.consensus_analysis("test", tmpdir)
            assert result.total_agents_analyzed == 1
            assert result.agreement_score == 1.0  # Only one agent = full "consensus"

    def test_mixed_sentiment_agents(self):
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_actions_file(tmpdir, "twitter", [
                {"action_type": "CREATE_POST", "agent_name": "alice", "content": "This is great and wonderful progress"},
                {"action_type": "CREATE_POST", "agent_name": "bob", "content": "This is terrible and awful crisis"},
                {"action_type": "CREATE_POST", "agent_name": "charlie", "content": "Just sharing some information today"},
            ])
            result = service.consensus_analysis("test", tmpdir)
            assert result.total_agents_analyzed == 3
            assert result.stance_distribution["supportive"] >= 1
            assert result.stance_distribution["opposing"] >= 1
            assert result.agreement_score < 1.0  # Not full consensus

    def test_non_content_actions_ignored(self):
        """LIKE_POST and DO_NOTHING should not count as content."""
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_actions_file(tmpdir, "twitter", [
                {"action_type": "LIKE_POST", "agent_name": "alice", "content": ""},
                {"action_type": "DO_NOTHING", "agent_name": "bob"},
                {"action_type": "CREATE_POST", "agent_name": "charlie", "content": "Only real post"},
            ])
            result = service.consensus_analysis("test", tmpdir)
            assert result.total_agents_analyzed == 1  # Only charlie has content

    def test_cross_platform(self):
        """Should read from both twitter and reddit directories."""
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_actions_file(tmpdir, "twitter", [
                {"action_type": "CREATE_POST", "agent_name": "alice", "content": "Great support progress"},
            ])
            self._create_actions_file(tmpdir, "reddit", [
                {"action_type": "CREATE_POST", "agent_name": "bob", "content": "Terrible crisis problem"},
            ])
            result = service.consensus_analysis("test", tmpdir)
            assert result.total_agents_analyzed == 2

    def test_result_has_factions(self):
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_actions_file(tmpdir, "twitter", [
                {"action_type": "CREATE_POST", "agent_name": "alice", "content": "Great wonderful excellent love"},
                {"action_type": "CREATE_POST", "agent_name": "bob", "content": "Terrible awful hate crisis corrupt"},
            ])
            result = service.consensus_analysis("test", tmpdir)
            assert len(result.key_factions) >= 2

    def test_result_has_themes(self):
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_actions_file(tmpdir, "twitter", [
                {"action_type": "CREATE_POST", "agent_name": "alice", "content": "housing prices rising rapidly"},
                {"action_type": "CREATE_POST", "agent_name": "bob", "content": "housing crisis worsening daily"},
                {"action_type": "CREATE_POST", "agent_name": "charlie", "content": "housing market needs reform"},
            ])
            result = service.consensus_analysis("test", tmpdir)
            assert "housing" in result.top_themes

    def test_representative_quotes(self):
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_actions_file(tmpdir, "twitter", [
                {"action_type": "CREATE_POST", "agent_name": "alice", "content": "This is absolutely great progress for everyone"},
            ])
            result = service.consensus_analysis("test", tmpdir)
            assert len(result.representative_quotes) >= 1
            assert result.representative_quotes[0]["agent"] == "alice"


# ---------------------------------------------------------------------------
# Consensus Strength tests
# ---------------------------------------------------------------------------


class TestConsensusStrength:
    """Tests for the weighted consensus strength scoring."""

    def _make_service(self):
        from app.services.graph_tools import GraphToolsService
        service = GraphToolsService.__new__(GraphToolsService)
        service.graph_id = "test-graph"
        service.simulation_id = "test-sim"
        return service

    def _create_actions_file(self, base_dir, platform, actions):
        platform_dir = os.path.join(base_dir, platform)
        os.makedirs(platform_dir, exist_ok=True)
        path = os.path.join(platform_dir, "actions.jsonl")
        with open(path, 'w') as f:
            for a in actions:
                f.write(json.dumps(a) + '\n')

    def _create_metrics_file(self, base_dir, platform, rounds):
        platform_dir = os.path.join(base_dir, platform)
        os.makedirs(platform_dir, exist_ok=True)
        path = os.path.join(platform_dir, "round_metrics.jsonl")
        with open(path, 'w') as f:
            for r in rounds:
                f.write(json.dumps(r) + '\n')

    def test_consensus_strength_present_in_result(self):
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_actions_file(tmpdir, "twitter", [
                {"action_type": "CREATE_POST", "agent_name": "alice", "content": "great progress"},
            ])
            result = service.consensus_analysis("test", tmpdir)
            assert result.consensus_strength is not None
            assert 0.0 <= result.consensus_strength.weighted_score <= 1.0

    def test_high_conviction_score(self):
        """Agents with strong sentiments should yield high conviction."""
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_actions_file(tmpdir, "twitter", [
                {"action_type": "CREATE_POST", "agent_name": "a1", "content": "great excellent wonderful love progress"},
                {"action_type": "CREATE_POST", "agent_name": "a2", "content": "terrible awful crisis danger hate"},
            ])
            result = service.consensus_analysis("test", tmpdir)
            assert result.consensus_strength.conviction_score > 0.3

    def test_low_conviction_score(self):
        """Agents with neutral posts should yield low conviction."""
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_actions_file(tmpdir, "twitter", [
                {"action_type": "CREATE_POST", "agent_name": "a1", "content": "just sharing information today"},
                {"action_type": "CREATE_POST", "agent_name": "a2", "content": "another neutral observation"},
            ])
            result = service.consensus_analysis("test", tmpdir)
            assert result.consensus_strength.conviction_score < 0.3

    def test_stability_with_consistent_trajectory(self):
        """Stable sentiment direction across rounds should yield high stability."""
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_actions_file(tmpdir, "twitter", [
                {"action_type": "CREATE_POST", "agent_name": "a1", "content": "great progress"},
            ])
            self._create_metrics_file(tmpdir, "twitter", [
                {"round": 1, "sentiment": {"average": 0.3}, "content_posts": 5},
                {"round": 2, "sentiment": {"average": 0.4}, "content_posts": 6},
                {"round": 3, "sentiment": {"average": 0.5}, "content_posts": 4},
            ])
            result = service.consensus_analysis("test", tmpdir)
            assert result.consensus_strength.stability_score >= 0.8

    def test_stability_with_flipflopping_trajectory(self):
        """Rapidly changing sentiment direction should yield low stability."""
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_actions_file(tmpdir, "twitter", [
                {"action_type": "CREATE_POST", "agent_name": "a1", "content": "great progress"},
            ])
            self._create_metrics_file(tmpdir, "twitter", [
                {"round": 1, "sentiment": {"average": 0.5}, "content_posts": 5},
                {"round": 2, "sentiment": {"average": -0.5}, "content_posts": 6},
                {"round": 3, "sentiment": {"average": 0.5}, "content_posts": 4},
                {"round": 4, "sentiment": {"average": -0.5}, "content_posts": 3},
            ])
            result = service.consensus_analysis("test", tmpdir)
            assert result.consensus_strength.stability_score < 0.5

    def test_diversity_with_varied_agent_types(self):
        """Multiple agent behavior types in dominant faction should raise diversity."""
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create agents with different action patterns but same sentiment
            self._create_actions_file(tmpdir, "twitter", [
                # Creator: mostly creates posts
                {"action_type": "CREATE_POST", "agent_name": "creator1", "content": "great wonderful excellent"},
                {"action_type": "CREATE_POST", "agent_name": "creator1", "content": "amazing progress love it"},
                {"action_type": "CREATE_POST", "agent_name": "creator1", "content": "positive great news"},
                # Engager: mostly comments
                {"action_type": "CREATE_COMMENT", "agent_name": "engager1", "content": "I agree this is great"},
                {"action_type": "CREATE_COMMENT", "agent_name": "engager1", "content": "excellent support progress"},
                {"action_type": "LIKE_POST", "agent_name": "engager1", "content": ""},
                # Lurker: mostly likes
                {"action_type": "LIKE_POST", "agent_name": "lurker1", "content": ""},
                {"action_type": "LIKE_POST", "agent_name": "lurker1", "content": ""},
                {"action_type": "CREATE_POST", "agent_name": "lurker1", "content": "good stuff hope for more"},
            ])
            result = service.consensus_analysis("test", tmpdir)
            # At least some diversity should be detected
            assert result.consensus_strength.diversity_score > 0.0

    def test_to_dict_in_result(self):
        """consensus_strength should serialize properly in ConsensusResult.to_dict()."""
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_actions_file(tmpdir, "twitter", [
                {"action_type": "CREATE_POST", "agent_name": "a1", "content": "great progress"},
            ])
            result = service.consensus_analysis("test", tmpdir)
            d = result.to_dict()
            assert "consensus_strength" in d
            assert d["consensus_strength"] is not None
            assert "weighted_score" in d["consensus_strength"]
            assert "diversity_score" in d["consensus_strength"]
            assert "conviction_score" in d["consensus_strength"]
            assert "stability_score" in d["consensus_strength"]

    def test_to_text_includes_strength(self):
        """to_text should include consensus strength section."""
        service = self._make_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_actions_file(tmpdir, "twitter", [
                {"action_type": "CREATE_POST", "agent_name": "a1", "content": "great progress"},
            ])
            result = service.consensus_analysis("test", tmpdir)
            text = result.to_text()
            assert "Consensus Strength" in text
            assert "Weighted Score" in text


# ---------------------------------------------------------------------------
# Time-decay relevance scoring tests
# ---------------------------------------------------------------------------


class TestTimeDecayScoring:
    """Tests for time-decay recency-weighted search ranking."""

    def _get_cls(self):
        from app.services.graph_tools import GraphToolsService
        return GraphToolsService

    def test_empty_edges_returns_empty(self):
        cls = self._get_cls()
        result = cls._apply_time_decay([])
        assert result == []

    def test_recent_edges_rank_higher(self):
        from datetime import datetime, timedelta
        now = datetime.now()
        recent = (now - timedelta(days=1)).isoformat()
        old = (now - timedelta(days=60)).isoformat()

        edges = [
            {"fact": "old fact", "created_at": old},
            {"fact": "recent fact", "created_at": recent},
        ]
        result = self._get_cls()._apply_time_decay(edges)
        assert result[0]["fact"] == "recent fact"
        assert result[1]["fact"] == "old fact"
        assert result[0]["recency_score"] > result[1]["recency_score"]

    def test_valid_at_preferred_over_created_at(self):
        from datetime import datetime, timedelta
        now = datetime.now()
        old_created = (now - timedelta(days=100)).isoformat()
        recent_valid = (now - timedelta(days=2)).isoformat()

        edges = [
            {"fact": "fact", "created_at": old_created, "valid_at": recent_valid},
        ]
        result = self._get_cls()._apply_time_decay(edges)
        # Should use valid_at (2 days ago) not created_at (100 days ago)
        assert result[0]["recency_score"] > 0.8

    def test_undated_edges_get_neutral_score(self):
        edges = [
            {"fact": "no date"},
            {"fact": "also no date", "created_at": None},
        ]
        result = self._get_cls()._apply_time_decay(edges)
        assert all(e["recency_score"] == 0.5 for e in result)

    def test_dated_before_undated(self):
        from datetime import datetime, timedelta
        now = datetime.now()
        recent = (now - timedelta(days=1)).isoformat()

        edges = [
            {"fact": "undated"},
            {"fact": "dated", "created_at": recent},
        ]
        result = self._get_cls()._apply_time_decay(edges)
        # Dated edges should come before undated
        assert result[0]["fact"] == "dated"
        assert result[1]["fact"] == "undated"

    def test_half_life_decay(self):
        """After half_life_days, score should be approximately 0.5."""
        from datetime import datetime, timedelta
        now = datetime.now()
        half_life = 30.0
        at_half_life = (now - timedelta(days=half_life)).isoformat()

        edges = [{"fact": "half-life", "created_at": at_half_life}]
        result = self._get_cls()._apply_time_decay(edges, decay_half_life_days=half_life)
        assert 0.45 <= result[0]["recency_score"] <= 0.55

    def test_preserves_edge_fields(self):
        from datetime import datetime
        edges = [{"fact": "test", "uuid": "abc", "name": "edge1", "created_at": datetime.now().isoformat()}]
        result = self._get_cls()._apply_time_decay(edges)
        assert result[0]["uuid"] == "abc"
        assert result[0]["name"] == "edge1"
        assert "recency_score" in result[0]


# ---------------------------------------------------------------------------
# RoundMetricsTracker tests
# ---------------------------------------------------------------------------


class TestRoundMetricsTracker:
    """Tests for per-round sentiment/metrics tracking."""

    def _make_tracker(self, tmpdir):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from action_logger import RoundMetricsTracker
        return RoundMetricsTracker(tmpdir)

    def test_empty_round(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._make_tracker(tmpdir)
            metrics = tracker.flush_round(round_num=1, platform="twitter", total_agents=10, active_agents=0)
            assert metrics["round"] == 1
            assert metrics["total_actions"] == 0
            assert metrics["participation_rate"] == 0.0

    def test_positive_sentiment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._make_tracker(tmpdir)
            tracker.add_action({"action_type": "CREATE_POST", "content": "This is great and wonderful"})
            tracker.add_action({"action_type": "CREATE_POST", "content": "Excellent progress, love it"})
            metrics = tracker.flush_round(round_num=1, platform="twitter", total_agents=10, active_agents=2)
            assert metrics["sentiment"]["positive"] >= 1
            assert metrics["sentiment"]["average"] > 0

    def test_negative_sentiment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._make_tracker(tmpdir)
            tracker.add_action({"action_type": "CREATE_POST", "content": "Terrible crisis, awful problem"})
            metrics = tracker.flush_round(round_num=1, platform="twitter", total_agents=10, active_agents=1)
            assert metrics["sentiment"]["negative"] >= 1
            assert metrics["sentiment"]["average"] < 0

    def test_action_counts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._make_tracker(tmpdir)
            tracker.add_action({"action_type": "CREATE_POST", "content": "hello"})
            tracker.add_action({"action_type": "LIKE_POST", "content": ""})
            tracker.add_action({"action_type": "LIKE_POST", "content": ""})
            tracker.add_action({"action_type": "REPOST", "content": ""})
            metrics = tracker.flush_round(round_num=1, platform="twitter", total_agents=10, active_agents=4)
            assert metrics["action_counts"]["CREATE_POST"] == 1
            assert metrics["action_counts"]["LIKE_POST"] == 2
            assert metrics["action_counts"]["REPOST"] == 1
            assert metrics["engagement"]["likes"] == 2
            assert metrics["engagement"]["reposts"] == 1

    def test_metrics_file_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._make_tracker(tmpdir)
            tracker.add_action({"action_type": "CREATE_POST", "content": "test"})
            tracker.flush_round(round_num=1, platform="twitter", total_agents=5, active_agents=1)

            metrics_file = os.path.join(tmpdir, "round_metrics.jsonl")
            assert os.path.exists(metrics_file)
            with open(metrics_file, "r") as f:
                lines = f.readlines()
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["round"] == 1

    def test_multiple_rounds_append(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._make_tracker(tmpdir)

            tracker.add_action({"action_type": "CREATE_POST", "content": "round 1"})
            tracker.flush_round(1, "twitter", 10, 1)

            tracker.add_action({"action_type": "CREATE_POST", "content": "round 2"})
            tracker.flush_round(2, "twitter", 10, 1)

            metrics_file = os.path.join(tmpdir, "round_metrics.jsonl")
            with open(metrics_file, "r") as f:
                lines = f.readlines()
            assert len(lines) == 2

    def test_buffer_clears_after_flush(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._make_tracker(tmpdir)
            tracker.add_action({"action_type": "CREATE_POST", "content": "test"})
            tracker.flush_round(1, "twitter", 10, 1)

            # Second flush with no new actions should show 0
            metrics = tracker.flush_round(2, "twitter", 10, 0)
            assert metrics["total_actions"] == 0

    def test_participation_rate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._make_tracker(tmpdir)
            metrics = tracker.flush_round(1, "twitter", total_agents=20, active_agents=10)
            assert metrics["participation_rate"] == 0.5


# ---------------------------------------------------------------------------
# Faction detection tests
# ---------------------------------------------------------------------------


class TestFactionDetection:
    """Tests for per-round faction detection in RoundMetricsTracker."""

    def _make_tracker(self, tmpdir):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from action_logger import RoundMetricsTracker
        return RoundMetricsTracker(tmpdir)

    def test_factions_present_in_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._make_tracker(tmpdir)
            tracker.add_action({"action_type": "CREATE_POST", "agent_name": "alice", "content": "great progress love"})
            tracker.add_action({"action_type": "CREATE_POST", "agent_name": "bob", "content": "terrible crisis awful"})
            metrics = tracker.flush_round(1, "twitter", 10, 2)
            assert "factions" in metrics
            assert "supportive" in metrics["factions"]
            assert "opposing" in metrics["factions"]
            assert "neutral" in metrics["factions"]

    def test_faction_counts_correct(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._make_tracker(tmpdir)
            tracker.add_action({"action_type": "CREATE_POST", "agent_name": "alice", "content": "great wonderful excellent"})
            tracker.add_action({"action_type": "CREATE_POST", "agent_name": "bob", "content": "terrible awful hate"})
            tracker.add_action({"action_type": "CREATE_POST", "agent_name": "charlie", "content": "just sharing info today"})
            metrics = tracker.flush_round(1, "twitter", 10, 3)
            assert metrics["factions"]["supportive"]["count"] >= 1
            assert metrics["factions"]["opposing"]["count"] >= 1

    def test_faction_members_listed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._make_tracker(tmpdir)
            tracker.add_action({"action_type": "CREATE_POST", "agent_name": "alice", "content": "great progress love it"})
            metrics = tracker.flush_round(1, "twitter", 10, 1)
            supportive = metrics["factions"]["supportive"]
            assert "alice" in supportive["members"]

    def test_faction_metrics_file_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._make_tracker(tmpdir)
            tracker.add_action({"action_type": "CREATE_POST", "agent_name": "a", "content": "great"})
            tracker.flush_round(1, "twitter", 10, 1)

            faction_file = os.path.join(tmpdir, "faction_metrics.jsonl")
            assert os.path.exists(faction_file)
            with open(faction_file) as f:
                data = json.loads(f.readline())
            assert data["round"] == 1
            assert "factions" in data

    def test_empty_round_has_empty_factions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._make_tracker(tmpdir)
            metrics = tracker.flush_round(1, "twitter", 10, 0)
            assert metrics["factions"]["supportive"]["count"] == 0
            assert metrics["factions"]["opposing"]["count"] == 0
            assert metrics["factions"]["neutral"]["count"] == 0


# ---------------------------------------------------------------------------
# Event injection IPC tests
# ---------------------------------------------------------------------------


class TestEventInjectionIPC:
    """Tests for INJECT_EVENT command type in IPC."""

    def test_inject_event_command_type_exists(self):
        from app.services.simulation_ipc import CommandType
        assert hasattr(CommandType, "INJECT_EVENT")

    def test_send_inject_event_method_exists(self):
        from app.services.simulation_ipc import SimulationIPCClient
        assert hasattr(SimulationIPCClient, "send_inject_event")

    def test_send_inject_event_creates_command(self):
        from app.services.simulation_ipc import SimulationIPCClient, CommandType
        with tempfile.TemporaryDirectory() as tmpdir:
            client = SimulationIPCClient(tmpdir)
            # Patch send_command to capture the call
            with patch.object(client, "send_command", return_value={"status": "ok"}) as mock_send:
                result = client.send_inject_event(
                    agent_id=5,
                    content="Breaking news!",
                    platform="twitter",
                    timeout=30
                )
                mock_send.assert_called_once_with(
                    command_type=CommandType.INJECT_EVENT,
                    args={
                        "agent_id": 5,
                        "content": "Breaking news!",
                        "platform": "twitter"
                    },
                    timeout=30
                )


# ---------------------------------------------------------------------------
# Follow relationship generation tests
# ---------------------------------------------------------------------------


class TestFollowRelationships:
    """Tests for follow-based feed filtering via generated follow relationships."""

    def _make_entity(self, uuid, name, entity_type, related_edges=None, related_nodes=None):
        from app.services.graph_entity_reader import EntityNode
        entity = EntityNode.__new__(EntityNode)
        entity.uuid = uuid
        entity.name = name
        entity.summary = f"A {entity_type} named {name}"
        entity.attributes = {}
        entity.related_edges = related_edges or []
        entity.related_nodes = related_nodes or []
        entity._labels = [entity_type]
        return entity

    def _make_profile(self, user_id, uuid, entity_type):
        from app.services.oasis_profile_generator import OasisAgentProfile
        return OasisAgentProfile(
            user_id=user_id,
            user_name=f"user_{user_id}",
            name=f"Agent {user_id}",
            bio="Test bio",
            persona="Test persona",
            source_entity_uuid=uuid,
            source_entity_type=entity_type,
        )

    def _make_generator(self):
        from app.services.oasis_profile_generator import OasisProfileGenerator
        gen = OasisProfileGenerator.__new__(OasisProfileGenerator)
        gen._follow_map = {}
        return gen

    def test_empty_profiles(self):
        gen = self._make_generator()
        result = gen._generate_follow_relationships([], [])
        assert result == {}

    def test_high_influence_follows(self):
        """Everyone should follow media/university accounts."""
        gen = self._make_generator()
        profiles = [
            self._make_profile(0, "u0", "Student"),
            self._make_profile(1, "u1", "MediaOutlet"),
            self._make_profile(2, "u2", "Person"),
        ]
        entities = [
            self._make_entity("u0", "Student1", "Student"),
            self._make_entity("u1", "CNN", "MediaOutlet"),
            self._make_entity("u2", "Person1", "Person"),
        ]
        result = gen._generate_follow_relationships(profiles, entities)

        # Student and Person should follow MediaOutlet
        assert 1 in result[0], "Student should follow MediaOutlet"
        assert 1 in result[2], "Person should follow MediaOutlet"
        # MediaOutlet should not follow itself
        assert 1 not in result[1]

    def test_relationship_based_follows(self):
        """Entities connected by edges should follow each other."""
        gen = self._make_generator()
        profiles = [
            self._make_profile(0, "u0", "Student"),
            self._make_profile(1, "u1", "University"),
        ]
        entities = [
            self._make_entity("u0", "Alice", "Student", related_edges=[
                {"target_node_uuid": "u1", "direction": "outgoing", "edge_name": "STUDIES_AT"}
            ]),
            self._make_entity("u1", "MIT", "University"),
        ]
        result = gen._generate_follow_relationships(profiles, entities)

        # Student should follow University (from edge)
        assert 1 in result[0]
        # University should follow Student (bidirectional)
        assert 0 in result[1]

    def test_same_type_clustering(self):
        """Agents of same type should follow each other (up to 5)."""
        gen = self._make_generator()
        profiles = [self._make_profile(i, f"u{i}", "Student") for i in range(8)]
        entities = [self._make_entity(f"u{i}", f"Student{i}", "Student") for i in range(8)]
        result = gen._generate_follow_relationships(profiles, entities)

        # Each student should follow some other students
        for uid in range(8):
            same_type_follows = [f for f in result[uid] if f != uid]
            assert len(same_type_follows) >= 1, f"Agent {uid} should follow at least one same-type peer"


# ---------------------------------------------------------------------------
# Contrarian agent injection tests
# ---------------------------------------------------------------------------


class TestContrarianAgentInjection:
    """Tests for Devil's Advocate contrarian agent injection."""

    def _make_generator(self):
        from app.services.oasis_profile_generator import OasisProfileGenerator
        gen = OasisProfileGenerator.__new__(OasisProfileGenerator)
        gen._follow_map = {}
        return gen

    def _make_profiles(self, count):
        from app.services.oasis_profile_generator import OasisAgentProfile
        return [
            OasisAgentProfile(
                user_id=i,
                user_name=f"user_{i}",
                name=f"Agent {i}",
                bio="Test bio",
                persona="Test persona",
                interested_topics=["politics", "economy"],
            )
            for i in range(count)
        ]

    def test_no_contrarians_for_small_groups(self):
        """Groups with fewer than 5 agents get no contrarians."""
        gen = self._make_generator()
        profiles = self._make_profiles(3)
        result = gen._inject_contrarian_agents(profiles)
        assert len(result) == 0

    def test_contrarians_injected_for_medium_groups(self):
        """Groups with 5+ agents get at least 1 contrarian."""
        gen = self._make_generator()
        profiles = self._make_profiles(10)
        result = gen._inject_contrarian_agents(profiles)
        assert len(result) >= 1
        assert all(p.is_contrarian for p in result)

    def test_contrarian_count_proportional(self):
        """5-10% of agents should be contrarians."""
        gen = self._make_generator()
        profiles = self._make_profiles(100)
        result = gen._inject_contrarian_agents(profiles)
        assert 3 <= len(result) <= 12  # 5-10% of 100 ≈ 5-10, with rounding

    def test_contrarian_profiles_valid(self):
        """Contrarian profiles should have all required fields."""
        gen = self._make_generator()
        profiles = self._make_profiles(20)
        result = gen._inject_contrarian_agents(profiles)
        for p in result:
            assert p.is_contrarian is True
            assert p.name
            assert p.bio
            assert p.persona
            assert p.user_name.startswith("contrarian_")
            assert p.user_id > max(pr.user_id for pr in profiles)

    def test_contrarian_personas_mention_challenging(self):
        """Contrarian personas should contain challenge/opposition language."""
        gen = self._make_generator()
        profiles = self._make_profiles(20)
        result = gen._inject_contrarian_agents(profiles)
        for p in result:
            persona_lower = p.persona.lower()
            assert any(word in persona_lower for word in
                       ["challenge", "opposing", "counter", "skeptic", "devil"]), \
                f"Contrarian persona should mention challenging behavior: {p.persona[:100]}"

    def test_contrarian_inherits_topics(self):
        """Contrarian agents should pick up topics from existing profiles."""
        gen = self._make_generator()
        profiles = self._make_profiles(10)
        result = gen._inject_contrarian_agents(profiles)
        assert len(result) >= 1
        # Topics should be non-empty since existing profiles have topics
        assert len(result[0].interested_topics) > 0

    def test_empty_profiles_returns_empty(self):
        gen = self._make_generator()
        result = gen._inject_contrarian_agents([])
        assert result == []


# ---------------------------------------------------------------------------
# Scheduled events in config tests
# ---------------------------------------------------------------------------


class TestScheduledEvents:
    """Tests for scheduled events in EventConfig."""

    def test_event_config_has_scheduled_events(self):
        from app.services.simulation_config_generator import EventConfig
        config = EventConfig(
            initial_posts=[],
            scheduled_events=[
                {"round": 5, "content": "Breaking news!", "poster_type": "MediaOutlet"},
                {"round": 15, "content": "Official response", "poster_type": "University"},
            ],
            hot_topics=["test"],
            narrative_direction="test direction"
        )
        assert len(config.scheduled_events) == 2
        assert config.scheduled_events[0]["round"] == 5

    def test_parse_event_config_passes_scheduled_events(self):
        from app.services.simulation_config_generator import SimulationConfigGenerator
        gen = SimulationConfigGenerator.__new__(SimulationConfigGenerator)

        result = {
            "hot_topics": ["topic1"],
            "narrative_direction": "direction",
            "initial_posts": [],
            "scheduled_events": [
                {"round": 10, "content": "Mid-sim event", "poster_type": "MediaOutlet"}
            ],
        }
        event_config = gen._parse_event_config(result)
        assert len(event_config.scheduled_events) == 1
        assert event_config.scheduled_events[0]["round"] == 10


# ---------------------------------------------------------------------------
# Event cascade tests
# ---------------------------------------------------------------------------


class TestEventCascades:
    """Tests for temporal event cascade generation."""

    def _make_generator(self):
        from app.services.simulation_config_generator import SimulationConfigGenerator
        gen = SimulationConfigGenerator.__new__(SimulationConfigGenerator)
        return gen

    def _make_entity(self, name, entity_type):
        entity = MagicMock()
        entity.name = name
        entity.get_entity_type.return_value = entity_type
        return entity

    def test_empty_events_returns_empty(self):
        gen = self._make_generator()
        result = gen._generate_event_cascades([], [], 30)
        assert result == []

    def test_generates_cascades_from_events(self):
        gen = self._make_generator()
        events = [
            {"round": 5, "content": "Official government announcement on new policy", "poster_type": "Official"},
        ]
        entities = [self._make_entity("Gov", "Official"), self._make_entity("CNN", "MediaOutlet")]
        result = gen._generate_event_cascades(events, entities, max_rounds=30)
        assert len(result) >= 1
        # Cascades should be at rounds after the trigger
        for c in result:
            assert c["round"] > 5
            assert c["is_cascade"] is True
            assert c["trigger_round"] == 5

    def test_cascades_respect_max_rounds(self):
        gen = self._make_generator()
        events = [{"round": 8, "content": "Crisis event", "poster_type": "Person"}]
        entities = [self._make_entity("Alice", "Person")]
        result = gen._generate_event_cascades(events, entities, max_rounds=9)
        # Only delay=2 cascade fits (round 10 is at round 10, exceeds 9)
        for c in result:
            assert c["round"] <= 9

    def test_no_duplicate_rounds(self):
        gen = self._make_generator()
        events = [
            {"round": 5, "content": "Event A", "poster_type": "Person"},
            {"round": 7, "content": "Event B", "poster_type": "Person"},  # round 7 = cascade of A at +2
        ]
        entities = [self._make_entity("Alice", "Person")]
        result = gen._generate_event_cascades(events, entities, max_rounds=30)
        # Should not generate cascade at round 7 since Event B is already there
        cascade_rounds = [c["round"] for c in result]
        assert 7 not in cascade_rounds

    def test_crisis_event_generates_crisis_cascades(self):
        gen = self._make_generator()
        events = [{"round": 3, "content": "Major crisis and emergency declared", "poster_type": "Official"}]
        entities = [self._make_entity("Gov", "Official"), self._make_entity("CNN", "MediaOutlet")]
        result = gen._generate_event_cascades(events, entities, max_rounds=30)
        # Crisis cascades should mention "emergency" or "response"
        assert any("response" in c["content"].lower() or "assessment" in c["content"].lower() for c in result)

    def test_cascade_has_required_fields(self):
        gen = self._make_generator()
        events = [{"round": 5, "content": "Test event", "poster_type": "Person"}]
        entities = [self._make_entity("Alice", "Person")]
        result = gen._generate_event_cascades(events, entities, max_rounds=30)
        for c in result:
            assert "round" in c
            assert "content" in c
            assert "poster_type" in c
            assert "is_cascade" in c
            assert "trigger_round" in c


# ---------------------------------------------------------------------------
# Multi-wave simulation tests
# ---------------------------------------------------------------------------


class TestMultiWaveManager:
    """Tests for multi-wave simulation orchestration."""

    def _make_manager(self, tmp_path):
        from app.services.multi_wave import MultiWaveManager
        mgr = MultiWaveManager()
        mgr.SERIES_DIR = str(tmp_path / "wave_series")
        os.makedirs(mgr.SERIES_DIR, exist_ok=True)
        return mgr

    def test_create_series(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        config = mgr.create_series("proj_1", "graph_1")
        assert config.series_id.startswith("series_")
        assert config.project_id == "proj_1"
        assert config.graph_id == "graph_1"
        assert len(config.waves) == 0

    def test_add_wave(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        config = mgr.create_series("proj_1", "graph_1")
        wave = mgr.add_wave(config.series_id, "sim_1", [{"round": 5, "content": "event"}])
        assert wave.wave_number == 1
        assert wave.simulation_id == "sim_1"
        assert len(wave.injected_events) == 1

    def test_multiple_waves(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        config = mgr.create_series("proj_1", "graph_1")
        mgr.add_wave(config.series_id, "sim_1")
        mgr.add_wave(config.series_id, "sim_2")
        loaded = mgr.get_series(config.series_id)
        assert len(loaded.waves) == 2
        assert loaded.waves[0].wave_number == 1
        assert loaded.waves[1].wave_number == 2

    def test_extract_sentiment_snapshot(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        # Create mock action logs
        sim_dir = tmp_path / "sim_output"
        twitter_dir = sim_dir / "twitter"
        twitter_dir.mkdir(parents=True)
        actions = [
            {"action_type": "CREATE_POST", "agent_name": "alice", "content": "great excellent love progress"},
            {"action_type": "CREATE_POST", "agent_name": "bob", "content": "terrible awful crisis danger"},
            {"action_type": "CREATE_POST", "agent_name": "charlie", "content": "just some information here"},
        ]
        with open(twitter_dir / "actions.jsonl", "w") as f:
            for a in actions:
                f.write(json.dumps(a) + "\n")

        snapshot = mgr.extract_sentiment_snapshot(str(sim_dir))
        assert "alice" in snapshot
        assert "bob" in snapshot
        assert snapshot["alice"] > 0  # positive
        assert snapshot["bob"] < 0  # negative

    def test_extract_empty_dir(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        snapshot = mgr.extract_sentiment_snapshot(str(tmp_path))
        assert snapshot == {}

    def test_generate_wave_events_with_snapshot(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        snapshot = {"alice": 0.5, "bob": 0.3, "charlie": 0.4}
        events = mgr.generate_wave_events(snapshot, "New policy announced")
        assert len(events) >= 2
        assert events[0]["is_wave_transition"] is True
        assert "positive" in events[0]["content"].lower()
        assert events[1]["content"] == "New policy announced"

    def test_generate_wave_events_negative(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        snapshot = {"alice": -0.5, "bob": -0.3}
        events = mgr.generate_wave_events(snapshot, "")
        assert len(events) >= 1
        assert "concern" in events[0]["content"].lower() or "opposition" in events[0]["content"].lower()

    def test_generate_wave_events_empty(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        events = mgr.generate_wave_events({}, "")
        assert events == []

    def test_update_wave_status(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        config = mgr.create_series("proj_1", "graph_1")
        mgr.add_wave(config.series_id, "sim_1")
        mgr.update_wave_status(config.series_id, 1, "completed", {"alice": 0.5})
        loaded = mgr.get_series(config.series_id)
        assert loaded.waves[0].status == "completed"
        assert loaded.waves[0].sentiment_snapshot["alice"] == 0.5

    def test_get_nonexistent_series(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        assert mgr.get_series("nonexistent") is None

    def test_series_roundtrip(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        config = mgr.create_series("proj_x", "graph_x")
        mgr.add_wave(config.series_id, "sim_a", [{"round": 3, "content": "test"}])
        mgr.update_wave_status(config.series_id, 1, "completed")

        loaded = mgr.get_series(config.series_id)
        assert loaded.project_id == "proj_x"
        assert loaded.waves[0].simulation_id == "sim_a"
        assert loaded.waves[0].status == "completed"
        d = loaded.to_dict()
        assert d["series_id"] == config.series_id


# ---------------------------------------------------------------------------
# Config defaults tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Cost tracker tests
# ---------------------------------------------------------------------------


class TestCostTracker:
    """Tests for centralized LLM cost tracking and budget enforcement."""

    def _get_tracker(self):
        from app.utils.cost_tracker import CostTracker
        CostTracker._reset_instance()
        tracker = CostTracker.get_instance()
        tracker.reset("test-run")
        return tracker

    def test_singleton(self):
        from app.utils.cost_tracker import CostTracker
        CostTracker._reset_instance()
        t1 = CostTracker.get_instance()
        t2 = CostTracker.get_instance()
        assert t1 is t2

    def test_reset_clears_state(self):
        tracker = self._get_tracker()
        tracker.record_usage(1000, 500, model="claude-haiku-4-5-20251001", phase="test")
        tracker.reset("new-run")
        s = tracker.get_summary()
        assert s["total_api_calls"] == 0
        assert s["total_cost_usd"] == 0.0
        assert s["run_id"] == "new-run"

    def test_record_usage_accumulates(self):
        tracker = self._get_tracker()
        tracker.record_usage(1000, 500, model="claude-haiku-4-5-20251001", phase="test1")
        tracker.record_usage(2000, 1000, model="claude-haiku-4-5-20251001", phase="test2")
        s = tracker.get_summary()
        assert s["total_input_tokens"] == 3000
        assert s["total_output_tokens"] == 1500
        assert s["total_api_calls"] == 2

    def test_cost_calculation_haiku(self):
        tracker = self._get_tracker()
        # Haiku: $1/MTok input, $5/MTok output
        cost = tracker.record_usage(1_000_000, 1_000_000, model="claude-haiku-4-5-20251001", phase="test")
        assert abs(cost - 6.0) < 0.01  # $1 input + $5 output

    def test_cost_calculation_opus(self):
        tracker = self._get_tracker()
        # Opus: $15/MTok input, $75/MTok output
        cost = tracker.record_usage(1_000_000, 1_000_000, model="claude-opus-4-20250514", phase="test")
        assert abs(cost - 90.0) < 0.01  # $15 input + $75 output

    def test_budget_exceeded_raises(self):
        from app.utils.cost_tracker import BudgetExceededError
        tracker = self._get_tracker()
        tracker._budget_limit = 1.0  # $1 limit
        # Record enough to exceed: 1M tokens of Haiku output = $5
        tracker.record_usage(0, 1_000_000, model="claude-haiku-4-5-20251001", phase="test")
        with pytest.raises(BudgetExceededError) as exc_info:
            tracker.check_budget("test_phase")
        assert exc_info.value.current_cost >= 1.0
        assert "budget exceeded" in str(exc_info.value).lower()

    def test_budget_not_exceeded(self):
        tracker = self._get_tracker()
        tracker._budget_limit = 100.0
        tracker.record_usage(1000, 500, model="claude-haiku-4-5-20251001", phase="test")
        tracker.check_budget("test")  # Should not raise

    def test_cost_by_phase(self):
        tracker = self._get_tracker()
        tracker.record_usage(1000, 500, model="claude-haiku-4-5-20251001", phase="ontology")
        tracker.record_usage(2000, 1000, model="claude-haiku-4-5-20251001", phase="profiles")
        s = tracker.get_summary()
        assert "ontology" in s["cost_by_phase"]
        assert "profiles" in s["cost_by_phase"]
        assert s["cost_by_phase"]["profiles"] > s["cost_by_phase"]["ontology"]

    def test_remaining_budget(self):
        tracker = self._get_tracker()
        tracker._budget_limit = 20.0
        initial = tracker.remaining_budget
        assert initial == 20.0
        tracker.record_usage(1_000_000, 0, model="claude-haiku-4-5-20251001", phase="test")
        assert tracker.remaining_budget < 20.0
        assert tracker.remaining_budget == pytest.approx(19.0, abs=0.01)

    def test_unknown_model_uses_fallback(self):
        tracker = self._get_tracker()
        # Unknown model should use Haiku-class fallback pricing
        cost = tracker.record_usage(1_000_000, 0, model="some-unknown-model", phase="test")
        assert abs(cost - 1.0) < 0.01  # $1/MTok input fallback

    def test_zero_tokens_no_op(self):
        tracker = self._get_tracker()
        cost = tracker.record_usage(0, 0, phase="test")
        assert cost == 0.0
        assert tracker.get_summary()["total_api_calls"] == 0

    def test_default_budget_limit(self):
        with patch.dict(os.environ, {}, clear=False):
            env = os.environ.copy()
            env.pop("PIPELINE_BUDGET_LIMIT", None)
            with patch.dict(os.environ, env, clear=True):
                import importlib
                import app.config
                importlib.reload(app.config)
                assert app.config.Config.PIPELINE_BUDGET_LIMIT == 20.0


class TestConfigDefaults:
    """Tests for updated config defaults."""

    def test_default_max_rounds(self):
        with patch.dict(os.environ, {}, clear=False):
            # Remove the env var if set so we get the code default
            env = os.environ.copy()
            env.pop("OASIS_DEFAULT_MAX_ROUNDS", None)
            with patch.dict(os.environ, env, clear=True):
                # Re-import to get fresh defaults
                import importlib
                import app.config
                importlib.reload(app.config)
                assert app.config.Config.OASIS_DEFAULT_MAX_ROUNDS == 30

    def test_default_max_tool_calls(self):
        with patch.dict(os.environ, {}, clear=False):
            env = os.environ.copy()
            env.pop("REPORT_AGENT_MAX_TOOL_CALLS", None)
            with patch.dict(os.environ, env, clear=True):
                import importlib
                import app.config
                importlib.reload(app.config)
                assert app.config.Config.REPORT_AGENT_MAX_TOOL_CALLS == 10

    def test_default_max_reflection_rounds(self):
        with patch.dict(os.environ, {}, clear=False):
            env = os.environ.copy()
            env.pop("REPORT_AGENT_MAX_REFLECTION_ROUNDS", None)
            with patch.dict(os.environ, env, clear=True):
                import importlib
                import app.config
                importlib.reload(app.config)
                assert app.config.Config.REPORT_AGENT_MAX_REFLECTION_ROUNDS == 3
