# Changelog — versão 3.3

## Variabilidade dos agentes

- A execução padrão não usa mais a seed fixa `42`.
- Quando `--seed` é omitido, `main.py` gera uma nova seed e a exibe no terminal.
- Uma seed informada continua reproduzindo exatamente a partida, inclusive a exploração dos agentes.
- Cada jogador possui um gerador pseudoaleatório independente.
- Foram adicionados exploração controlada e desempate aleatório entre ações equivalentes.
- A exploração exclui chamas e células de perigo futuro; bombas aleatórias só são permitidas quando há rota de fuga.

## Perfis comportamentais

- P1: perceptron defensivo, exploração de 5%, fuga para a região mais segura.
- P2: árvore agressiva, exploração de 14%, perseguição e maior frequência de bombas.
- P3: k-NN coletor, exploração de 10%, preferência por itens e caixas.
- P4: MLP territorial, exploração de 8%, preferência pelo centro e controle espacial.
- As configurações estão centralizadas em `players/agent_config.py`.
- A BFS de emergência aceita preferências diferentes para cada perfil e embaralha empates de forma reproduzível.

## Validação

- 20 testes automatizados aprovados.
- Duas execuções com `--seed 4242` produziram resultados e logs de eventos idênticos.
- Duas execuções sem `--seed` geraram seeds, resultados e vencedores diferentes.
- Nenhum timeout, erro de agente ou ação inválida nas partidas de validação.
