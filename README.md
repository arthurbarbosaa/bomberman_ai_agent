# Bomberman AI Arena — versão 3.3

Projeto didático para uma disciplina de Inteligência Artificial. Cada aluno entrega um agente em um arquivo Python próprio, e os agentes disputam partidas de Bomberman em uma arena procedural. O desempenho no torneio pode compor a nota da atividade.

A versão 3.3 incorpora as ideias úteis do projeto de referência enviado: **spritesheets direcionais**, animação contínua e **um módulo independente por jogador**. Além disso, os quatro jogadores padrão agora utilizam quatro modelos de IA distintos e didáticos: perceptron linear, árvore de decisão, k-NN e rede neural MLP. O motor anterior foi preservado porque oferece arena aleatória, regras reproduzíveis, isolamento dos agentes, timeout de decisão e testes automatizados.

## Variabilidade e reprodutibilidade

- `python main.py` gera automaticamente uma nova seed e, portanto, uma nova partida.
- `python main.py --seed 42` reproduz mapa, itens e escolhas estocásticas.
- cada agente possui um gerador pseudoaleatório independente derivado da seed da partida e do identificador do jogador;
- os quatro modelos usam taxas de exploração e objetivos comportamentais diferentes;
- empates entre ações equivalentes são resolvidos aleatoriamente, mas permanecem reproduzíveis quando a seed é fixa.

## Correção central: lógica e animação separadas

A posição usada para colisões e dano é sempre uma coordenada inteira da grade. A posição interpolada do sprite existe apenas no renderizador.

Cada tick segue esta ordem:

```text
1. Receber as decisões dos agentes
2. Aplicar a maldição aos comandos
3. Resolver simultaneamente os movimentos
4. Atualizar a passagem das bombas
5. Colocar novas bombas
6. Coletar itens e transmitir a maldição
7. Resolver explosões e reações em cadeia
8. Aplicar dano e fechamento da arena
9. Registrar os eventos do tick
10. Animar a transição entre o estado anterior e o posterior
```

O renderizador divide visualmente o tick em duas fases:

- primeiro, o personagem chega à posição lógica resolvida;
- depois, aparecem explosões, caixas destruídas e eliminações.

Assim, um jogador nunca desaparece enquanto seu sprite ainda parece estar em outra célula. Uma eliminação causada por bomba registra:

```json
{
  "type": "player_eliminated",
  "player": 1,
  "killer": 0,
  "reason": "bomb_blast",
  "position": [5, 5],
  "bomb_id": 7,
  "bomb_position": [4, 5],
  "flame_created_tick": 126,
  "tick": 126,
  "event_id": 418
}
```

## Requisitos implementados

1. **Arena aleatória e reproduzível:** o mapa é gerado por `seed`, com paredes, pilares e caixas destrutíveis.
2. **Área inicial segura:** cada spawn possui dois corredores em L, permitindo escapar da primeira bomba.
3. **Itens:** aumento de bombas, alcance, velocidade, escudo e maldição.
4. **Timeout da partida:** após o tempo configurado, anéis da arena tornam-se paredes letais.
5. **Debuff `CURSE`:** todos os comandos são permutados, inclusive `BOMB` e `WAIT`, sem pontos fixos.
6. **Transmissão da maldição:** o debuff passa para um adversário em contato ortogonal.
7. **Bombas sólidas:** ninguém atravessa bombas. O dono pode apenas sair da bomba recém-colocada.
8. **Agentes independentes:** cada jogador utiliza um arquivo `.py` separado.
9. **Execução protegida:** cada agente roda em um processo próprio e possui timeout por decisão.
10. **Torneio automatizado:** confrontos de ida e volta, ranking e exportação CSV.
11. **Log auditável:** movimentos, bombas, explosões, itens, maldição e eliminações são preservados.
12. **Spritesheets:** quatro personagens, bomba e explosões segmentadas são animados por frames.

## Estrutura do projeto

```text
bomberman_ai_project_v3_3/
├── main.py
├── tournament.py
├── requirements.txt
├── players/
│   ├── player_1.py
│   ├── player_2.py
│   ├── player_3.py
│   ├── player_4.py
│   ├── ai_utils.py
│   ├── agent_config.py
│   └── player_template.py
├── agents/
│   ├── base_agent.py
│   ├── random_agent.py
│   └── student_agent.py
├── bomberman/
│   ├── agent_runtime.py
│   ├── arena.py
│   ├── config.py
│   ├── engine.py
│   ├── enums.py
│   ├── renderer.py
│   ├── render_state.py
│   └── state.py
├── assets/
│   ├── sprites/
│   ├── sheets/
│   │   ├── player_1.png
│   │   ├── player_2.png
│   │   ├── player_3.png
│   │   ├── player_4.png
│   │   ├── bomb.png
│   │   └── flames.png
│   ├── sprite_sheets_preview.png
│   └── v3_game_preview.png
├── tools/
│   ├── generate_sprites.py
│   ├── build_sprite_sheets.py
│   └── generate_game_preview.py
├── tests/
│   ├── test_engine.py
│   ├── test_render_state.py
│   ├── test_four_default_players.py
│   ├── test_ai_players.py
│   └── test_variability.py
└── outputs/
    ├── fixed_seed_result.json
    ├── fixed_seed_events.json
    ├── automatic_seed_result.json
    ├── automatic_seed_events.json
    ├── leaderboard.csv
    └── variability_validation.json
```

## Instalação

Recomenda-se Python 3.11 ou superior.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Linux ou macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Executar uma partida

Quatro agentes, com interface gráfica:

```bash
python main.py
```

Por padrão, a arena sempre abre com P1, P2, P3 e P4. Para uma atividade com menos competidores, informe manualmente apenas 2 ou 3 módulos em `--agents`.

O comando padrão agora inicia **quatro jogadores** e equivale a:

```bash
python main.py --agents \
  players.player_1:Agent \
  players.player_2:Agent \
  players.player_3:Agent \
  players.player_4:Agent
```


No Windows, o mesmo comando pode ser escrito em uma única linha.

Modo sem interface gráfica, com uma seed nova a cada execução:

```bash
python main.py --headless
```

Para repetir exatamente a mesma arena e as mesmas decisões aleatórias, informe uma seed:

```bash
python main.py --headless --seed 42
```

A seed efetivamente utilizada é mostrada no terminal e também salva no resultado JSON.

Salvar resultado e log completo:

```bash
python main.py --headless --seed 42 \
  --json-output outputs/result.json \
  --event-log outputs/match_events.json
```

### Taxa lógica e taxa visual

```bash
python main.py --tick-rate 8 --render-fps 60
```

- `--tick-rate`: frequência do motor e das decisões dos agentes;
- `--render-fps`: frequência da animação;
- alterar `--render-fps` não altera colisões, explosões ou resultados.

O argumento legado `--fps` continua aceito como alias de `--tick-rate`.

## Arquivo individual do aluno

Cada aluno deve copiar `players/player_template.py` para um arquivo próprio, por exemplo:

```text
turma/agente_ana.py
turma/agente_bruno.py
```

Interface mínima:

```python
class Agent:
    def __init__(self, player_id: int = 0, seed: int = 0) -> None:
        self.player_id = player_id
        self.seed = seed

    def decide(self, observation: dict) -> str:
        # Executar o modelo de IA e retornar uma ação.
        return "WAIT"
```

Ações válidas:

```text
WAIT, UP, DOWN, LEFT, RIGHT, BOMB
```

Exemplo de confronto:

```bash
python main.py --agents turma.agente_ana:Agent turma.agente_bruno:Agent
```

## Quatro modelos de IA fornecidos como exemplo

Os quatro jogadores padrão são implementados em arquivos separados e usam
famílias de modelos diferentes. Nenhum deles depende de NumPy, scikit-learn ou
arquivos externos de pesos.

| Jogador | Arquivo | Modelo | Comportamento básico |
|---|---|---|---|
| P1 | `players/player_1.py` | Perceptron linear | **Defensivo:** maximiza segurança e mobilidade; exploração de 5%. |
| P2 | `players/player_2.py` | Árvore de decisão | **Agressivo:** persegue oponentes e coloca mais bombas; exploração de 14%. |
| P3 | `players/player_3.py` | k-NN, `k=5` | **Coletor:** prioriza itens e destruição de caixas; exploração de 10%. |
| P4 | `players/player_4.py` | Rede neural MLP `12-6-1` | **Territorial:** favorece o centro e o controle de corredores; exploração de 8%. |

Cada arquivo contém sua própria classe `Agent` e seu próprio método
`decide(observation)`. O módulo `players/ai_utils.py` apenas extrai atributos,
calcula perigo e procura rotas de fuga; ele não escolhe a ação de nenhum player.

Todos os modelos possuem uma rotina emergencial de busca em largura, mas cada
perfil pontua as rotas seguras de forma diferente: P1 busca maior distância do
perigo, P2 tenta permanecer próximo do adversário, P3 favorece itens e P4 favorece
o centro. Vizinhos e empates equivalentes são embaralhados pelo gerador próprio
do agente. Com seed fixa, a escolha continua reproduzível.

Cada modelo também utiliza exploração controlada e desempate aleatório. A
exploração considera apenas ações válidas: não entra deliberadamente em chamas e
só considera `BOMB` quando existe uma rota de fuga. Os parâmetros ficam em
`players/agent_config.py`.

### Exemplo do perceptron linear

```text
score(ação) = Σ peso_i × atributo_i
```

### Exemplo da rede neural

```text
12 atributos → 6 neurônios ReLU → 1 escore por ação
```

Os atributos incluem perigo imediato e futuro, mobilidade, aproximação de itens
e adversários, aproximação do centro, utilidade de colocar uma bomba e existência
de rota de fuga.

Os pesos e protótipos estão definidos diretamente nos arquivos para que o jogo
funcione imediatamente. Em uma atividade mais avançada, os alunos podem treinar
esses parâmetros com dados de partidas, algoritmos genéticos ou aprendizagem por
reforço.

## Observação recebida pelo agente

O método `decide` recebe uma cópia serializável e independente do estado. O agente não recebe referências mutáveis do motor.

Campos principais:

- `board`: `.` piso, `#` parede, `+` caixa e `X` fechamento;
- `self`: estado do próprio jogador;
- `players`: estado dos concorrentes;
- `bombs`: posição, proprietário, alcance e temporizador;
- `flames`: células em chamas;
- `items`: itens visíveis;
- `shrink`: margem e tempo para o próximo fechamento;
- `events`: eventos do último tick;
- `available_actions`: comandos aceitos.

## Spritesheets

A convenção dos personagens é compatível com a referência analisada:

```text
Frames 0–2: cima
Frames 3–5: direita
Frames 6–8: baixo
Frames 9–11: esquerda
```

As explosões possuem frames separados para:

- centro;
- segmento horizontal;
- segmento vertical;
- ponta superior;
- ponta direita;
- ponta inferior;
- ponta esquerda.

Recriar os spritesheets:

```bash
python tools/build_sprite_sheets.py
```

Os sprites distribuídos neste projeto são originais, inspirados na estética de jogos do gênero. Os arquivos proprietários do projeto de referência não foram redistribuídos.

## Torneio

```bash
python tournament.py \
  players.player_1:Agent \
  players.player_2:Agent \
  players.player_3:Agent \
  players.player_4:Agent \
  --rounds 5 \
  --output leaderboard.csv
```

Pontuação padrão:

- vitória: 3 pontos;
- empate: 1 ponto;
- derrota: 0 ponto.

Cada duelo possui ida e volta para reduzir o viés da posição inicial. O CSV contém ranking, partidas, vitórias, empates, derrotas, pontuação, eliminações, itens e falhas do agente.

## Testes

```bash
python -m unittest discover -s tests -v
```

A suíte verifica, entre outros pontos:

- rotas iniciais de fuga;
- bloqueio de bombas;
- maldição e transmissão;
- itens obrigatórios;
- fechamento da arena;
- alcance da explosão;
- bloqueio de entrada em chama persistente;
- causa e posição de uma eliminação;
- separação entre coordenada visual e coordenada lógica;
- chegada visual à célula de dano antes da eliminação;
- integridade dos spritesheets;
- persistência do log de eventos.

## Segurança para uso com uma turma

Processos separados e timeout evitam que um loop infinito congele a partida, mas não constituem sandbox completo. Execute códigos não confiáveis em contêiner ou máquina virtual sem credenciais, com limites de CPU, memória, disco, tempo e acesso à rede.

## Alterações da versão 3.3

Consulte `CHANGELOG_V3_3.md` para a lista objetiva das mudanças de variabilidade, perfis e testes.
