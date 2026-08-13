# Arquivos dos quatro jogadores — modelos de IA

Cada jogador é carregado em um processo independente e possui um arquivo próprio:

- `player_1.py`: perceptron linear **defensivo**, exploração de 5%;
- `player_2.py`: árvore de decisão **agressiva**, exploração de 14%;
- `player_3.py`: classificador k-NN **coletor**, exploração de 10%;
- `player_4.py`: rede neural MLP **territorial**, exploração de 8%.

O método que define a ação é `Agent.decide(observation)` dentro de cada arquivo.
O retorno deve ser `WAIT`, `UP`, `DOWN`, `LEFT`, `RIGHT` ou `BOMB`.

`ai_utils.py` contém percepção, atributos, perigo, exploração segura e busca de
rotas. A decisão final continua separada dentro de cada `player_N.py`.
`agent_config.py` centraliza somente o nome do perfil, a taxa de exploração e a
preferência de fuga.

Cada agente possui seu próprio gerador pseudoaleatório derivado da seed da
partida e do identificador do jogador. Assim, `python main.py` produz partidas
variadas, enquanto `python main.py --seed 42` continua totalmente reproduzível.

A execução padrão carrega os quatro modelos automaticamente.
