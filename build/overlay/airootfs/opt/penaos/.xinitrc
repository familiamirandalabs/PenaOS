#!/bin/bash
# ============================================================================
#  .xinitrc  —  inicializa a sessao X11 do PenaOS (Openbox + painel)
# ----------------------------------------------------------------------------
#  NAO usamos 'openbox-session' de proposito: o wrapper dele muda de distro
#  pra distro (le autostart XDG, dbus, etc.) e foi suspeito de tela preta no
#  Debian. Aqui a gente controla tudo na mao: pinta o fundo, sobe o painel e
#  da 'exec openbox' puro. Funciona igual em Arch e Debian.
# ============================================================================

# Numa VM nao faz sentido a tela apagar: desliga screensaver e power management
xset s off      2>/dev/null || true
xset -dpms      2>/dev/null || true
xset s noblank  2>/dev/null || true

# Fundo azul-marinho do PenaOS JA AQUI. Diagnostico: se a tela ficar PRETA,
# o X nem subiu; se ficar AZUL sem painel, o X subiu e so o painel falhou.
xsetroot -solid "#16213C"        2>/dev/null || true
xsetroot -cursor_name left_ptr   2>/dev/null || true

# ---- Renderizacao por software estavel (sem GPU no VESA/VM) -----------------
# Sem isto o WebKit tenta acelerar por GPU que nao existe e o processo morre.
# Forcamos software puro: mais lento, mas NAO trava, e economiza RAM.
export LIBGL_ALWAYS_SOFTWARE=1
export WEBKIT_DISABLE_COMPOSITING_MODE=1
export WEBKIT_DISABLE_DMABUF_RENDERER=1
export GDK_BACKEND=x11
export MOZ_ACCELERATED=0

# Usa a MAIOR resolucao disponivel na saida conectada (corrige tela pequena)
OUT=$(xrandr 2>/dev/null | awk '/ connected/{print $1; exit}')
[ -z "$OUT" ] && OUT=$(xrandr 2>/dev/null | awk 'NR==2{print $1}')
[ -n "$OUT" ] && xrandr --output "$OUT" --auto 2>/dev/null || true

# Painel/launcher do PenaOS (em segundo plano; erros vao pro log de diagnostico)
python3 /opt/penaos/pena_shell.py 2>/tmp/penaos-shell.log &

# Openbox como gerenciador da sessao. Plano B: se o painel morrer, ainda da
# pra clicar com o botao direito no fundo e abrir um terminal pelo menu.
# Quando o Openbox sai (menu "Desligar" -> 'openbox --exit'), o xinitrc termina
# e o controle volta pro .bash_profile.
exec openbox
