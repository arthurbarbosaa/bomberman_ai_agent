# Alterações da versão 3.1

- A execução padrão passou de dois para quatro jogadores.
- `python main.py` carrega automaticamente `player_1.py`, `player_2.py`, `player_3.py` e `player_4.py`.
- Cada arquivo de jogador agora declara explicitamente seu próprio método `Agent.decide()`.
- Os quatro agentes continuam sendo executados em processos independentes.
- Adicionado teste para impedir regressão para apenas dois jogadores.
- README atualizado com a execução padrão de quatro participantes.
