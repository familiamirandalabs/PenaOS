# Changelog — PenaOS

Todas as mudancas relevantes do PenaOS. Formato baseado em "Keep a Changelog".
O PenaOS e um sistema operacional levinho, sem telemetria, da familia Miranda.

## [0.1.1] — 2026-06-07

### Corrigido
- **Resolucao da tela**: a janela ficava minuscula presa no canto superior
  esquerdo. Agora a sessao usa a maior resolucao disponivel (`xrandr --auto`)
  e o painel/janelas se ajustam direito a tela inteira.
- **Desligamento "do nada"**: o `.bash_profile` so desliga a VM se existir o
  arquivo-sentinela `/tmp/penaos-shutdown`. Se a sessao grafica quebrar, agora
  cai num shell de diagnostico mostrando os logs — em vez de apagar silencioso.
- **Menu Iniciar sumia** ao clicar nos itens (oscilacao de foco sem WM).
- **Caminho do config**: na ISO o `default.json` nao carregava por causa de um
  caminho errado (`/opt/config` em vez de `/opt/penaos/config`). Agora ha busca
  em varios candidatos.

### Adicionado
- **Navegador nativo do PenaOS** (`pena_browser.py`): mini-navegador proprio em
  Python + WebKitGTK (mesmo motor do Safari, sem o peso de um navegador
  inteiro). Barra de endereco, voltar/avancar, busca no DuckDuckGo Lite (aceita
  `!bangs`) e **redirect automatico YouTube -> Invidious** (inv.nadeko.net) pra
  assistir video leve e sem rastreamento.
- **Gerenciador de janelas Openbox** + painel proprio (barra de 36px embaixo
  com logo/menu/relogio/atalhos). Alt-Tab estilo Mac, mover/redimensionar reais.
- **Terminal** (xterm tematizado) acessivel pelo painel e pelo menu.
- **Otimizacao pra pouca RAM (POTATO)**: `zram-generator` (swap comprimido em
  RAM com zstd) + ajustes de `sysctl` (swappiness, page-cluster) — segura o
  navegador vivo em maquinas de ~500MB.
- **Renderizacao por software estavel** (WebKit) — fim das telas "Oops!".
- **Esqueleto multi-arquitetura**: build parametrizado por `PENA_ARCH`
  (x86_64 funcional; i686/aarch64 com pacotes e mirrors prontos).

### Mudado
- **Central de Programas** agora instala **de verdade** (modo simulado removido):
  abre um terminal mostrando o `pacman` baixando o pacote.

## [0.1.0] — historico
- Shell dual-mode (GUI Tkinter / TUI curses), base archiso enxuta, autologin,
  branding Claude starburst `-(*)-`, sem telemetria.
