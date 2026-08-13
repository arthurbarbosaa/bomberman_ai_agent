# Changelog — versão 3.2

## Quatro jogadores com modelos de IA distintos

- P1 implementa um perceptron linear para pontuar ações.
- P2 implementa uma árvore de decisão simbólica.
- P3 implementa um classificador k-NN com protótipos didáticos.
- P4 implementa uma rede neural MLP `12-6-1` com ativação ReLU.
- Cada modelo permanece em seu próprio arquivo `players/player_N.py`.
- `players/ai_utils.py` centraliza apenas a extração de atributos e a busca de fuga.
- Foi adicionada fuga emergencial por busca em largura para células ameaçadas.
- Os modelos não exigem bibliotecas de machine learning ou treinamento externo.
- A execução padrão continua iniciando P1, P2, P3 e P4.
- Foram validadas partidas completas em múltiplas seeds sem timeout, erro ou ação inválida.
