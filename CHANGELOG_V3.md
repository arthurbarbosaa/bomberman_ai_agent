# Alterações da versão 3

- Adotados spritesheets de 12 frames para cada jogador, seguindo a organização direcional do projeto de referência.
- Criados spritesheets de bomba e explosão segmentada.
- Adicionada `bomberman/render_state.py`, que mantém snapshots gráficos independentes do motor.
- A animação passou a usar dois estados: antes e depois de cada tick.
- Movimentos são mostrados antes de explosões e eliminações do mesmo tick.
- A posição interpolada nunca é consultada pelo motor.
- Eventos de eliminação agora podem registrar `bomb_id`, `bomb_position` e `flame_created_tick`.
- Adicionado histórico persistente de eventos com `event_id` e `tick`.
- Adicionados `--tick-rate`, `--render-fps` e `--event-log`.
- Incluído `players/player_template.py` para entregas individuais.
- Adicionados testes da camada de animação e da integridade dos spritesheets.
