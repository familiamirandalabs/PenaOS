# ============================================================================
#  .bash_profile  —  inicia o PenaOS no tty1
# ----------------------------------------------------------------------------
#  No tty1 (autologin), inicia a sessao grafica X11 com a area de trabalho.
#  Nos outros terminais (Ctrl+Alt+F2...F6) fica o shell normal.
#
#  IMPORTANTE: NUNCA desligamos a VM "no susto". So desligamos se o usuario
#  escolheu "Desligar" no menu (que cria o arquivo-sentinela). Se o X ou o
#  shell quebrarem, mostramos o erro e caimos num shell — assim da pra ver
#  o que aconteceu em vez de a VM apagar do nada.
# ============================================================================

if [[ "$(tty)" == "/dev/tty1" ]]; then
    rm -f /tmp/penaos-shutdown

    # pista visivel: se a tela ficar PRETA depois desta linha, o travamento e
    # no X (startx); se nunca aparecer, o autologin do root nem rodou.
    clear
    echo "  -(*)-  PenaOS: iniciando a area de trabalho..."
    echo "         (se demorar muito numa tela preta, algo no X travou —"
    echo "          aperte Ctrl+Alt+F2 pra um terminal e veja /tmp/penaos-startx.log)"

    # inicia o X11 com nosso xinitrc; loga tudo pra diagnostico
    startx /opt/penaos/.xinitrc -- :0 vt1 &> /tmp/penaos-startx.log
    code=$?

    if [[ -f /tmp/penaos-shutdown ]]; then
        # o usuario escolheu "Desligar" no menu — saida limpa
        clear
        echo "Desligando o PenaOS..."
        poweroff
    else
        # algo deu errado: NAO desliga. Mostra o erro e abre um shell.
        clear
        echo "============================================================"
        echo "  PenaOS: a area de trabalho encerrou inesperadamente."
        echo "  (codigo de saida do startx: $code)"
        echo "============================================================"
        echo
        echo "--- ultimas linhas do startx (/tmp/penaos-startx.log) ---"
        tail -n 20 /tmp/penaos-startx.log 2>/dev/null
        echo
        echo "--- saida do pena_shell (/tmp/penaos-shell.log) ---"
        tail -n 20 /tmp/penaos-shell.log 2>/dev/null || echo "(vazio)"
        echo
        echo "--- log do servidor X (/var/log/Xorg.0.log) ---"
        tail -n 20 /var/log/Xorg.0.log 2>/dev/null || echo "(sem Xorg.0.log)"
        echo
        echo "Voce esta num shell. Comandos uteis:"
        echo "  cat /tmp/penaos-startx.log           # erro completo do X"
        echo "  cat /tmp/penaos-shell.log            # erro do pena_shell"
        echo "  python3 /opt/penaos/pena_shell.py    # tenta a versao TUI"
        echo "  startx /opt/penaos/.xinitrc          # tenta a GUI de novo"
        echo "  poweroff                             # desligar a VM"
        echo
        exec bash
    fi
fi
