from __future__ import annotations

"""Perfis comportamentais dos quatro agentes didáticos.

Os parâmetros ficam centralizados para facilitar a demonstração em sala, mas a
lógica de cada modelo continua implementada em ``player_1.py`` a
``player_4.py``.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentProfile:
    name: str
    exploration_rate: float
    escape_preference: str


PLAYER_PROFILES = {
    1: AgentProfile("defensivo", 0.05, "safest"),
    2: AgentProfile("agressivo", 0.14, "aggressive"),
    3: AgentProfile("coletor", 0.10, "collector"),
    4: AgentProfile("territorial", 0.08, "territorial"),
}
