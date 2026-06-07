#!/bin/bash
# ============================================================================
#  .xinitrc  —  inicializa a sessao X11 do PenaOS (Openbox + painel)
# ============================================================================

# Numa VM nao faz sentido a tela apagar: desliga screensaver e power management
xset s off      2>/dev/null || true
xset -dpms      2>/dev/null || true
xset s noblank  2>/dev/null || true

# ---- Renderizacao por software estavel (sem GPU no VESA/VM) -----------------
# Sem isto o WebKit (GNOME Web) tenta acelerar por GPU que nao existe e o
# processo morre -> tela "Oops!". Forcamos software puro: mais lento, mas NAO
# trava, e ainda economiza RAM desligando o compositor/sandbox extra.
export LIBGL_ALWAYS_SOFTWARE=1
export WEBKIT_DISABLE_COMPOSITING_MODE=1
export WEBKIT_DISABLE_DMABUF_RENDERER=1
export GDK_BACKEND=x11
export MOZ_ACCELERATED=0

# Usa a MAIOR resolucao disponivel na saida conectada (corrige tela pequena)
OUT=$(xrandr 2>/dev/null | awk '/ connected/{print $1; exit}')
[ -z "$OUT" ] && OUT=$(xrandr 2>/dev/null | awk 'NR==2{print $1}')
[ -n "$OUT" ] && xrandr --output "$OUT" --auto 2>/dev/null || true

# Inicia o Openbox como gerenciador de janelas.
# O painel do PenaOS (pena_shell.py) e o fundo sobem pelo autostart do Openbox
# (~/.config/openbox/autostart). Quando o Openbox sai (menu "Desligar" chama
# 'openbox --exit'), o xinitrc termina e o controle volta pro .bash_profile.
exec openbox-session
