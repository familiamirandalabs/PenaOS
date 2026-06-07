#!/usr/bin/env python3
# ============================================================================
#  pena_run_exe.py  —  "abridor de .exe" do PenaOS  (o "fork enxuto do Wine")
# ----------------------------------------------------------------------------
#  POR QUE ISTO EXISTE:
#  O usuario pediu um Wine que, ao abrir um .exe, mostre O PROPRIO APP — nao
#  uma estrutura de pastas. Forkar o codigo do Wine seria gigante e pesado.
#  A forma ENXUTA (mesma filosofia do nosso navegador) e um lancador fino:
#  recebe o caminho do .exe, mostra uma janelinha "abrindo..." e roda o app
#  direto pelo Wine. O resultado pro usuario e identico ao pedido: clicou no
#  .exe -> o programa abre. Sem gerenciador de arquivos, sem pasta, sem ruido.
#
#  COMO O SISTEMA USA:
#  o overlay registra o MIME do .exe (application/x-ms-dos-executable) para
#  abrir com este script. Ai um duplo-clique no arquivo ja cai aqui.
#
#  USO MANUAL:
#     python3 pena_run_exe.py /caminho/programa.exe [args...]
# ============================================================================
import os
import sys
import shutil
import subprocess
import threading

APP_NAME = "PenaOS"

# ---- paleta (casa com o resto do PenaOS) -----------------------------------
BG    = "#16213C"
BG2   = "#1e2a45"
ACC   = "#3DDC97"
TEXT  = "#FAF6EE"
DIM   = "#5a7299"
RED   = "#E85D3C"


def _gui_message(title, msg, kind="info"):
    """Mostra um aviso simples; se nem Tk tiver, cai pro terminal."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        (messagebox.showerror if kind == "error" else messagebox.showinfo)(title, msg)
        root.destroy()
    except Exception:
        print(f"[{title}] {msg}", file=sys.stderr)


def _loading_window(appname):
    """Janelinha 'abrindo <app>...' enquanto o Wine sobe. Retorna (root, close)."""
    try:
        import tkinter as tk
    except Exception:
        return None, (lambda: None)
    root = tk.Tk()
    root.title(f"Abrindo {appname}")
    root.configure(bg=BG2)
    root.geometry("360x140")
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    tk.Label(root, text="-(*)-", bg=BG2, fg=ACC,
             font=("Monospace", 20, "bold")).pack(pady=(18, 4))
    tk.Label(root, text=f"Abrindo {appname}...", bg=BG2, fg=TEXT,
             font=("Monospace", 11, "bold")).pack()
    tk.Label(root, text="(a primeira vez pode demorar um pouco)",
             bg=BG2, fg=DIM, font=("Monospace", 9)).pack(pady=(2, 0))
    root.update_idletasks()
    root.update()

    def close():
        try:
            root.destroy()
        except Exception:
            pass
    return root, close


def _ensure_wine():
    """Garante que o Wine existe. Se nao, oferece instalar pela Central."""
    if shutil.which("wine"):
        return True
    msg = ("Para abrir programas do Windows (.exe), o PenaOS precisa do Wine.\n\n"
           "Abra a Central de Programas e instale 'Wine' (e 'Winetricks').\n"
           "Depois e so abrir o .exe de novo.")
    _gui_message("Falta o Wine", msg, kind="error")
    return False


def main():
    if len(sys.argv) < 2:
        _gui_message("Abrir .exe",
                     "Uso: pena_run_exe.py /caminho/programa.exe", kind="error")
        return 2

    exe = sys.argv[1]
    extra = sys.argv[2:]

    if not os.path.isfile(exe):
        _gui_message("Arquivo nao encontrado",
                     f"Nao achei o arquivo:\n{exe}", kind="error")
        return 1

    if not _ensure_wine():
        return 1

    appname = os.path.basename(exe)

    # diretorio do .exe vira o "cwd" (muitos apps esperam isso pra achar dados)
    workdir = os.path.dirname(os.path.abspath(exe)) or os.getcwd()

    # ambiente: prefixo proprio do PenaOS (isolado, em ~/.penaos-wine)
    env = dict(os.environ)
    env.setdefault("WINEPREFIX", os.path.expanduser("~/.penaos-wine"))
    env.setdefault("WINEDEBUG", "-all")      # silencioso = mais leve no log

    root, close_loading = _loading_window(appname)

    result = {"code": None, "err": None}

    def run():
        try:
            # roda o app e ESPERA: assim sabemos quando fechou (e nao deixa zumbi)
            result["code"] = subprocess.call(
                ["wine", os.path.abspath(exe)] + extra,
                cwd=workdir, env=env)
        except Exception as e:        # noqa: BLE001
            result["err"] = str(e)
        finally:
            # fecha a janelinha de carregando assim que o Wine retorna o controle
            if root is not None:
                root.after(0, close_loading)

    t = threading.Thread(target=run, daemon=True)
    t.start()

    # mantem a janelinha viva ~ enquanto o app carrega; o Wine ja desenha
    # a JANELA REAL do programa por cima — o usuario ve O APP, nao uma pasta.
    if root is not None:
        # fecha o "abrindo..." depois de alguns segundos (o app ja apareceu)
        root.after(6000, close_loading)
        try:
            root.mainloop()
        except Exception:
            pass

    t.join()  # espera o app fechar de fato

    if result["err"]:
        _gui_message("Erro ao abrir",
                     f"Nao consegui abrir {appname}:\n{result['err']}",
                     kind="error")
        return 1
    return result["code"] or 0


if __name__ == "__main__":
    sys.exit(main())
