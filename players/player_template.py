from __future__ import annotations


class Agent:
    """Modelo mínimo para a entrega individual de um aluno.

    Renomeie este arquivo e implemente um modelo de IA no método ``decide``.
    O agente recebe apenas uma cópia serializável do estado da partida.
    """

    def __init__(self, player_id: int = 0, seed: int = 0) -> None:
        self.player_id = player_id
        self.seed = seed

    def decide(self, observation: dict) -> str:
        # Substitua pela inferência do modelo desenvolvido pelo aluno.
        # Retornos válidos: WAIT, UP, DOWN, LEFT, RIGHT ou BOMB.
        return "WAIT"
