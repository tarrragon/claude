#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6.0",
#     "click>=8.0",
# ]
# ///
"""
Dispatch Recommender - Agent 派發建議演算法

根據 Ticket 狀態和 registry 推薦合適的 agent。
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
import yaml

from ticket_system.lib.registry_loader import load_registry


REGISTRY_PATH = Path(__file__).parent.parent.parent / "agents" / "registry.yaml"

# 評分常數
MAX_SCORE = 60  # artifact_match(40) + phase_match(20)


class DispatchRecommender:
    """派發建議引擎"""
    
    def __init__(self, registry_path: Path = REGISTRY_PATH):
        self.registry = load_registry(registry_path)
        self.agents = self.registry.get("agents", {}) if self.registry else {}
    def recommend(
        self,
        ticket_id: str,
        artifact_type: str,
        tdd_phase: str = None,
        top_n: int = 5
    ) -> List[Tuple[str, float, str]]:
        """
        推薦合適的 agent
        
        返回：[(agent_name, score, reason), ...]
        """
        if not self.agents:
            return []
        
        candidates = []
        
        for agent_name, config in self.agents.items():
            score, reason = self._calculate_score(
                agent_name, config, artifact_type, tdd_phase
            )
            if score > 0:
                candidates.append((agent_name, score, reason))
        
        # 按分數排序
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_n]
    
    def _calculate_score(
        self,
        agent_name: str,
        config: Dict[str, Any],
        artifact_type: str,
        tdd_phase: str = None
    ) -> Tuple[float, str]:
        """
        計算 agent 的推薦分數

        評分公式：
        total = artifact_match_score(40) + phase_match_score(20)
        最高分：60
        """
        score = 0.0
        reason_parts = []
        
        # 1. Artifact Type 匹配（40 分）
        accepts = config.get("accepts", [])
        artifact_matches = [a for a in accepts if a.get("artifact_type") == artifact_type]
        artifact_score = 40.0 * (len(artifact_matches) / max(len(accepts), 1))
        if artifact_score > 0:
            score += artifact_score
            reason_parts.append(f"artifact match: {artifact_score:.0f}")
        
        # 2. TDD Phase 匹配（20 分）
        if tdd_phase:
            tdd_phases = config.get("tdd_phases", [])
            if tdd_phase in tdd_phases:
                score += 20.0
                reason_parts.append("phase match: 20")

        reason = ", ".join(reason_parts) if reason_parts else "no match"
        return score, reason


def format_recommendation(
    candidates: List[Tuple[str, float, str]],
    ticket_id: str,
    artifact_type: str,
    tdd_phase: str = None
) -> str:
    """格式化推薦結果"""
    lines = [
        f"\n{'='*60}",
        f"Dispatch Recommendation: {ticket_id}",
        f"Artifact Type: {artifact_type}",
    ]
    
    if tdd_phase:
        lines.append(f"TDD Phase: {tdd_phase}")
    
    lines.append(f"{'='*60}\n")
    
    if not candidates:
        lines.append("No suitable agents found.\n")
        return "\n".join(lines)
    
    for idx, (agent_name, score, reason) in enumerate(candidates, 1):
        lines.append(f"{idx}. {agent_name}")
        lines.append(f"   Score: {score:.1f}/{MAX_SCORE}")
        lines.append(f"   Reason: {reason}\n")
    
    return "\n".join(lines)


def main():
    """CLI 主程式"""
    if len(sys.argv) < 3:
        print("Usage: dispatch_recommender.py <ticket-id> <artifact-type> [tdd-phase]")
        return 1
    
    ticket_id = sys.argv[1]
    artifact_type = sys.argv[2]
    tdd_phase = sys.argv[3] if len(sys.argv) > 3 else None
    
    recommender = DispatchRecommender()
    candidates = recommender.recommend(ticket_id, artifact_type, tdd_phase)
    
    output = format_recommendation(candidates, ticket_id, artifact_type, tdd_phase)
    print(output)
    
    return 0 if candidates else 1


if __name__ == "__main__":
    sys.exit(main())
