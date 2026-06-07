#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
#  PenaOS  —  pena_shell.py
# ----------------------------------------------------------------------------
#  Modo GUI   : Tkinter fullscreen (se DISPLAY disponivel — Estagio 3)
#  Modo TUI   : curses (fallback em terminal puro — Estagio 1)
#
#  Como rodar:
#    GUI  → python3 pena_shell.py   (dentro de uma sessao X11)
#    TUI  → python3 pena_shell.py   (em tty sem DISPLAY)
#
#  Atalhos comuns (GUI e TUI):
#    F2 / clicar no logo  ..... abre o Menu Iniciar
#    Tab / Alt+Tab  ........... alternador de janelas (estilo Mac)
#    Esc  ..................... fecha janela / cancela
# ============================================================================

import os
import json
import time
import subprocess
from pathlib import Path

# ---- Identidade do sistema --------------------------------------------------
OS_NAME    = "PenaOS"
OS_VERSION = "0.1.1 (Estagio 3 - GUI)"

CLAUDE_LOGO = "-(*)-"
CLAUDE_BIG  = [
    r"  \ | /  ",
    r" --(*)-- ",
    r"  / | \  ",
]

# ---- Caminhos de configuracao -----------------------------------------------
SCRIPT_DIR      = Path(__file__).resolve().parent
USER_CONFIG_DIR = Path.home() / ".config" / "penaos"
USER_CONFIG     = USER_CONFIG_DIR / "config.json"

# O default.json pode estar em lugares diferentes dependendo de ONDE rodamos:
#   - dev (arvore do projeto): .../penaos/config/default.json   (../config)
#   - ISO live: o shell vive em /opt/penaos/ e o config em ./config/
# Procuramos em todos os candidatos e usamos o 1o que existir. Sem isso, na
# ISO o config padrao nao carregava (o shell achava /opt/config por engano).
DEFAULT_CONFIG_CANDIDATES = [
    SCRIPT_DIR / "config" / "default.json",          # ao lado do script (ISO)
    SCRIPT_DIR.parent / "config" / "default.json",   # arvore do projeto (dev)
    Path("/opt/penaos/config/default.json"),         # caminho fixo da ISO
]


def _find_default_config():
    for p in DEFAULT_CONFIG_CANDIDATES:
        if p.is_file():
            return p
    return DEFAULT_CONFIG_CANDIDATES[0]


DEFAULT_CONFIG = _find_default_config()


# ============================================================================
#  Config  (compartilhada entre GUI e TUI)
# ============================================================================
def load_config():
    cfg = {}
    try:
        with open(DEFAULT_CONFIG, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {"os_name": OS_NAME, "version": OS_VERSION}
    try:
        with open(USER_CONFIG, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(USER_CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


# ---- Sentinela de desligamento ----------------------------------------------
#  O .bash_profile so desliga a VM se este arquivo existir. Assim, se o shell
#  quebrar sozinho, a VM NAO apaga do nada — cai num shell mostrando o erro.
SHUTDOWN_SENTINEL = Path("/tmp/penaos-shutdown")

def request_shutdown():
    try:
        SHUTDOWN_SENTINEL.write_text("desligar")
    except Exception:
        pass


# ============================================================================
#  ██████╗ ██╗   ██╗██╗
#  ██╔════╝ ██║   ██║██║
#  ██║  ███╗██║   ██║██║
#  ██║   ██║██║   ██║██║
#  ╚██████╔╝╚██████╔╝██║
#   ╚═════╝  ╚═════╝ ╚═╝
#  Interface grafica (Tkinter)
# ============================================================================
def run_gui():
    import shutil
    import tkinter as tk
    from tkinter import messagebox

    # ---- Paleta de cores ---------------------------------------------------
    BG          = "#16213C"   # fundo do desktop
    BG2         = "#1e2a45"   # fundo das janelas
    PANEL       = "#090f1e"   # painel (barra de tarefas)
    TITLE_BG    = "#0d1929"   # cabecalhos internos
    ACCENT      = "#3DDC97"   # verde PenaOS
    TEXT        = "#FAF6EE"   # texto principal (creme)
    TEXT_DIM    = "#5a7299"   # texto secundario
    RED         = "#E85D3C"   # fechar / alertas
    YELLOW      = "#F5C518"   # avisos

    FONT        = ("Monospace", 10)
    FONT_B      = ("Monospace", 10, "bold")
    FONT_SM     = ("Monospace", 9)
    FONT_LG     = ("Monospace", 14, "bold")

    PANEL_H     = 36          # altura do painel (casa com a margem do rc.xml)

    cfg = load_config()

    # ========================================================================
    #  Janelas de app: Toplevel REAIS, decorados/gerenciados pelo Openbox.
    #  (mover, redimensionar, alt-tab = tudo por conta do WM)
    # ========================================================================
    open_windows = {}   # nome -> Toplevel (1 instancia de cada)

    def app_window(name, title, w, h):
        """Cria (ou foca, se ja existe) um Toplevel tematizado."""
        ex = open_windows.get(name)
        if ex is not None and ex.winfo_exists():
            ex.deiconify(); ex.lift(); ex.focus_force()
            return None
        win = tk.Toplevel()
        win.title(title)
        win.configure(bg=BG2)
        win.geometry("%dx%d" % (w, h))
        open_windows[name] = win
        def _close():
            win.destroy()
            open_windows.pop(name, None)
        win.protocol("WM_DELETE_WINDOW", _close)
        body = tk.Frame(win, bg=BG2, padx=16, pady=12)
        body.pack(fill="both", expand=True)
        return body

    # ---- Bem-vindo ----------------------------------------------------------
    def open_welcome():
        body = app_window("welcome", "Bem-vindo ao " + OS_NAME, 480, 360)
        if body is None:
            return
        for line in CLAUDE_BIG:
            tk.Label(body, text=line, bg=BG2, fg=ACCENT, font=FONT_LG).pack()
        tk.Label(body, text="", bg=BG2).pack()
        tk.Label(body, text=f"{OS_NAME}  {OS_VERSION}",
                 bg=BG2, fg=TEXT, font=FONT_B).pack()
        tk.Label(body, text="Sistema levinho, sem telemetria,",
                 bg=BG2, fg=TEXT_DIM, font=FONT_SM).pack()
        tk.Label(body, text="feito com carinho pela familia Miranda.",
                 bg=BG2, fg=TEXT_DIM, font=FONT_SM).pack()
        tk.Label(body, text="─────────────────────────────────",
                 bg=BG2, fg=TEXT_DIM).pack(pady=6)
        for d in ["Clique no logo -(*)-  ...  Menu Iniciar",
                  "Alt+Tab  ............... Alternar janelas",
                  "Super+Enter  ........... Abrir terminal",
                  "Arraste a barra de titulo pra mover a janela"]:
            tk.Label(body, text=d, bg=BG2, fg=TEXT, font=FONT_SM,
                     anchor="w").pack(fill="x")

    # ---- Configuracoes ------------------------------------------------------
    def open_settings():
        body = app_window("settings", "Central de Configuracoes", 480, 360)
        if body is None:
            return
        items = [
            ("theme",               "Tema",              ["escuro", "claro"]),
            ("accent",              "Cor de destaque",   ["verde", "ciano", "amarelo", "vermelho"]),
            ("clock_24h",           "Relogio 24h",       [True, False]),
            ("show_clock",          "Mostrar relogio",   [True, False]),
            ("power_profile",       "Energia",           ["economia", "equilibrado", "desempenho"]),
        ]
        tk.Label(body, text="Clique em < ou > para mudar o valor.",
                 bg=BG2, fg=TEXT_DIM, font=FONT_SM).pack(anchor="w")
        tk.Label(body, text="As mudancas salvam automaticamente.",
                 bg=BG2, fg=TEXT_DIM, font=FONT_SM).pack(anchor="w", pady=(0, 8))

        def fmt(v):
            return "sim" if v is True else ("nao" if v is False else str(v))

        for key, label, opts in items:
            row = tk.Frame(body, bg=BG2); row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=BG2, fg=TEXT, font=FONT,
                     width=20, anchor="w").pack(side="left")
            var = tk.StringVar(value=fmt(cfg.get(key, opts[0])))
            def cycle(k=key, o=opts, v=var, d=0):
                cur = cfg.get(k, o[0])
                try:    idx = o.index(cur)
                except ValueError: idx = 0
                cfg[k] = o[(idx + d) % len(o)]
                v.set(fmt(cfg[k])); save_config(cfg)
            tk.Button(row, text="<", bg=TITLE_BG, fg=ACCENT, bd=0, font=FONT_B,
                      cursor="hand2", command=lambda k=key,o=opts,v=var: cycle(k,o,v,-1)
                      ).pack(side="left", padx=4)
            tk.Label(row, textvariable=var, bg=BG2, fg=YELLOW, font=FONT_B,
                     width=13, anchor="center").pack(side="left")
            tk.Button(row, text=">", bg=TITLE_BG, fg=ACCENT, bd=0, font=FONT_B,
                      cursor="hand2", command=lambda k=key,o=opts,v=var: cycle(k,o,v,+1)
                      ).pack(side="left", padx=4)
        tk.Label(body, text=f"Config: {USER_CONFIG}", bg=BG2, fg=TEXT_DIM,
                 font=("Monospace", 8)).pack(anchor="w", pady=(10, 0))

    # ---- Central de Programas ----------------------------------------------
    def open_software():
        body = app_window("software", "Central de Programas", 500, 400)
        if body is None:
            return
        catalog = [
            ("Firefox",     "Outro navegador (pesado)", "firefox"),
            ("Falkon",      "Navegador leve (Qt)",      "falkon"),
            ("NetSurf",     "Navegador minusculo",      "netsurf"),
            ("Gedit",       "Editor de texto",          "gedit"),
            ("LibreOffice", "Documentos e planilhas",   "libreoffice-fresh"),
            ("GIMP",        "Editar imagens",           "gimp"),
            ("VLC",         "Videos e musicas",         "vlc"),
            ("Wine",        "Programas do Windows",     "wine"),
            ("Winetricks",  "Ajustes pro Wine",         "winetricks"),
            ("Arduino IDE", "Programar o robozinho",    "arduino-ide"),
        ]
        tk.Label(body, text="Clique duas vezes para instalar de verdade.",
                 bg=BG2, fg=ACCENT, font=FONT_B).pack(anchor="w")
        tk.Label(body, text="(abre um terminal mostrando o download)",
                 bg=BG2, fg=TEXT_DIM, font=FONT_SM).pack(anchor="w", pady=(0, 6))

        lbf = tk.Frame(body, bg=BG2); lbf.pack(fill="both", expand=True)
        sb = tk.Scrollbar(lbf); sb.pack(side="right", fill="y")
        lb = tk.Listbox(lbf, bg=TITLE_BG, fg=TEXT, font=FONT,
                        selectbackground=ACCENT, selectforeground=BG,
                        bd=0, highlightthickness=0, yscrollcommand=sb.set)
        lb.pack(fill="both", expand=True); sb.config(command=lb.yview)
        for name, desc, _ in catalog:
            lb.insert("end", f"  {name:<14}  {desc}")
        status = tk.StringVar()
        tk.Label(body, textvariable=status, bg=BG2, fg=TEXT_DIM, font=FONT_SM,
                 wraplength=460, anchor="w").pack(fill="x", pady=(4, 0))

        def install(_=None):
            sel = lb.curselection()
            if not sel:
                return
            name, _, pkg = catalog[sel[0]]
            if not messagebox.askyesno(
                    "Instalar " + name,
                    f"Instalar '{name}' agora?\n\npacote: {pkg}\n\n"
                    "Vai baixar da internet (precisa estar conectado)."):
                return
            status.set(f"Instalando {name}... (veja o terminal que abriu)")
            # roda pacman num xterm pra criança ver o progresso; pausa no fim.
            cmd = ("pacman -Sy --needed --noconfirm %s; "
                   "echo; echo '--- terminou. ENTER pra fechar ---'; read _" % pkg)
            if shutil.which("xterm"):
                subprocess.Popen([
                    "xterm", "-title", "Instalando " + name,
                    "-bg", "#0d1929", "-fg", "#FAF6EE", "-fa", "Monospace", "-fs", "11",
                    "-e", "bash", "-lc", cmd])
            else:
                subprocess.Popen(["bash", "-lc", cmd])
        lb.bind("<Double-Button-1>", install)

    # ---- Sobre --------------------------------------------------------------
    def open_about():
        body = app_window("about", "Sobre o " + OS_NAME, 470, 340)
        if body is None:
            return
        infos = [
            (f"{OS_NAME}  {OS_VERSION}", TEXT, FONT_B),
            ("", BG2, FONT),
            ("Base ........... Linux (kernel Arch), enxuto", TEXT, FONT),
            ("Janelas ........ Openbox + painel proprio",    TEXT, FONT),
            ("Compatibilidade  Wine + Winetricks (a fazer)", TEXT, FONT),
            ("Telemetria ..... NENHUMA. (nem da pra ter, ne)", TEXT, FONT),
            ("", BG2, FONT),
            ("Estagios do projeto:", ACCENT, FONT_B),
            ("  0) Shell TUI                    [FEITO]",  ACCENT, FONT),
            ("  1) ISO que boota na VM          [FEITO]",  ACCENT, FONT),
            ("  2) Wine + instalador proprio    [a fazer]", TEXT_DIM, FONT),
            ("  3) GUI levinha (Openbox+painel) [FEITO]",  ACCENT, FONT),
            ("  4) Multi-arquitetura (32/64,arm)[a fazer]", TEXT_DIM, FONT),
            ("", BG2, FONT),
            ("Feito pela familia Miranda + Claude.", TEXT_DIM, FONT_SM),
        ]
        for text, color, font in infos:
            tk.Label(body, text=text, bg=BG2, fg=color, font=font,
                     anchor="w").pack(fill="x")

    # ---- Acoes do sistema ---------------------------------------------------
    def open_terminal():
        for term, args in [("xterm", ["-bg", BG, "-fg", TEXT, "-fa", "Monospace",
                                       "-fs", "11", "-title", "Terminal - PenaOS"])]:
            if shutil.which(term):
                subprocess.Popen([term] + args)
                return
        messagebox.showinfo("Terminal", "xterm nao encontrado na ISO.")

    # busca padrao: DuckDuckGo Lite (HTML puro, leve, e aceita !bangs)
    HOMEPAGE = "https://lite.duckduckgo.com/lite/"

    PENA_BROWSER = "/opt/penaos/pena_browser.py"

    def open_browser():
        # navegador proprio do PenaOS (redirect YouTube->Invidious embutido)
        if os.path.exists(PENA_BROWSER):
            subprocess.Popen(["python3", PENA_BROWSER, HOMEPAGE])
            return
        # fallback: se por acaso o nosso nao estiver presente
        for b in ("epiphany", "firefox", "falkon", "netsurf", "chromium"):
            if shutil.which(b):
                subprocess.Popen([b, HOMEPAGE])
                return
        messagebox.showinfo(
            "Navegador",
            "O navegador do PenaOS nao foi encontrado.\n\n"
            "Era esperado em: " + PENA_BROWSER)

    def do_shutdown():
        request_shutdown()                       # libera o poweroff no .bash_profile
        try:
            subprocess.Popen(["openbox", "--exit"])   # encerra a sessao X limpa
        except Exception:
            pass

    # ========================================================================
    #  Painel (barra na base) — roda por cima do Openbox
    # ========================================================================
    class Panel:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("PenaOS-Panel")
            self.root.configure(bg=PANEL)
            self.root.overrideredirect(True)     # sem moldura; Openbox ignora
            self.root.update_idletasks()
            self.sw = self.root.winfo_screenwidth()
            self.sh = self.root.winfo_screenheight()
            self.root.geometry("%dx%d+0+%d" % (self.sw, PANEL_H, self.sh - PANEL_H))
            try:    self.root.attributes("-topmost", True)
            except Exception: pass

            # logo / botao iniciar
            self.btn_logo = tk.Button(
                self.root, text=f" {CLAUDE_LOGO} ", bg=PANEL, fg=ACCENT,
                activebackground=TITLE_BG, activeforeground=ACCENT,
                bd=0, font=FONT_B, cursor="hand2", command=self.toggle_menu)
            self.btn_logo.pack(side="left", padx=6)
            tk.Frame(self.root, bg=TEXT_DIM, width=1).pack(side="left", fill="y", pady=6)

            # atalhos rapidos no painel
            for txt, cmd in [(" Terminal ", open_terminal),
                             (" Navegador ", open_browser)]:
                tk.Button(self.root, text=txt, bg=PANEL, fg=TEXT,
                          activebackground=ACCENT, activeforeground=BG,
                          bd=0, font=FONT_SM, cursor="hand2",
                          command=cmd).pack(side="left", padx=2)

            # relogio
            self.clock = tk.Label(self.root, text="", bg=PANEL, fg=TEXT, font=FONT_B)
            self.clock.pack(side="right", padx=10)

            self.root.bind("<F2>", lambda e: self.toggle_menu())
            self._menu = None
            self._tick()
            open_welcome()

        def _tick(self):
            if cfg.get("show_clock", True):
                fmt = "%H:%M:%S" if cfg.get("clock_24h", True) else "%I:%M %p"
                self.clock.config(text=time.strftime(fmt))
            else:
                self.clock.config(text="")
            self.root.after(1000, self._tick)

        # ---- menu iniciar ---------------------------------------------------
        def close_menu(self):
            if self._menu is not None and self._menu.winfo_exists():
                self._menu.destroy()
            self._menu = None

        def toggle_menu(self):
            if self._menu is not None and self._menu.winfo_exists():
                self.close_menu()
                return
            self._menu = tk.Toplevel(self.root)
            self._menu.overrideredirect(True)
            try:    self._menu.attributes("-topmost", True)
            except Exception: pass
            self._menu.configure(bg=TITLE_BG)

            items = [
                ("  [*]  Bem-vindo",            open_welcome),
                ("  [=]  Configuracoes",        open_settings),
                ("  [v]  Central de Programas", open_software),
                ("  [@]  Navegador",            open_browser),
                ("  [>]  Terminal",             open_terminal),
                ("  [i]  Sobre o " + OS_NAME,   open_about),
                ("  [x]  Desligar",             do_shutdown),
            ]
            mw, mh = 250, len(items) * 36 + 46
            bx = self.btn_logo.winfo_rootx()
            self._menu.geometry("%dx%d+%d+%d" % (mw, mh, bx, self.sh - PANEL_H - mh))

            hdr = tk.Frame(self._menu, bg=BG, height=38); hdr.pack(fill="x")
            hdr.pack_propagate(False)
            tk.Label(hdr, text=f"  {CLAUDE_LOGO}  {OS_NAME}", bg=BG, fg=ACCENT,
                     font=FONT_B).pack(side="left", padx=8, pady=6)
            tk.Frame(self._menu, bg=ACCENT, height=1).pack(fill="x")

            for label, cmd in items:
                def run(c=cmd):
                    self.close_menu()
                    c()
                tk.Button(self._menu, text=label, bg=TITLE_BG, fg=TEXT,
                          activebackground=ACCENT, activeforeground=BG,
                          bd=0, font=FONT, anchor="w", cursor="hand2",
                          command=run).pack(fill="x", padx=2, pady=1, ipady=6)

            # Esc fecha; clicar fora tambem (quando o foco volta pro painel)
            self._menu.bind("<Escape>", lambda e: self.close_menu())
            self._menu.focus_set()

        def run(self):
            self.root.mainloop()

    Panel().run()


# ============================================================================
#  ████████╗██╗   ██╗██╗
#  ╚══██╔══╝██║   ██║██║
#     ██║   ██║   ██║██║
#     ██║   ██║   ██║██║
#     ██║   ╚██████╔╝██║
#     ╚═╝    ╚═════╝ ╚═╝
#  Interface texto (curses) — fallback sem DISPLAY
# ============================================================================
def run_tui():
    import curses

    def safe_addstr(win, y, x, text, attr=0):
        h, w = win.getmaxyx()
        if y < 0 or y >= h or x < 0 or x >= w:
            return
        text = text[: max(0, w - x - 1)]
        try:
            win.addstr(y, x, text, attr)
        except curses.error:
            pass

    class App:
        def __init__(self, title, icon="[ ]"):
            self.title  = title
            self.icon   = icon
            self.cursor = 0
            self.scroll = 0
        def draw(self, win, y0, x0, h, w, cfg): pass
        def handle_key(self, key, cfg): return None

    class WelcomeApp(App):
        def __init__(self):
            super().__init__("Bem-vindo", "[*]")
        def draw(self, win, y0, x0, h, w, cfg):
            lines = []
            for l in CLAUDE_BIG:
                lines.append(l.center(w - 2))
            lines += ["", (OS_NAME + "  " + OS_VERSION).center(w - 2), "",
                      "Um sistema operacional levinho, sem telemetria,".center(w - 2),
                      "feito com carinho pela familia Miranda.".center(w - 2),
                      "", "- - - - - - - - - - - - - - - - -".center(w - 2), "",
                      "F2 ......... Menu Iniciar",
                      "Tab ........ Alternar janelas (estilo Mac)",
                      "Esc ........ Fecha esta janela"]
            for i, ln in enumerate(lines):
                if y0 + i >= y0 + h: break
                safe_addstr(win, y0 + i, x0 + 1, ln[: w - 2])

    class SettingsApp(App):
        def __init__(self):
            super().__init__("Central de Configuracoes", "[=]")
            self.items = [
                ("theme",             "Tema",               ["escuro", "claro"]),
                ("accent",            "Cor de destaque",    ["verde", "ciano", "amarelo"]),
                ("wallpaper_pattern", "Papel de parede",    ["pontos", "linhas", "liso"]),
                ("taskbar_position",  "Barra de tarefas",   ["embaixo", "em cima"]),
                ("clock_24h",         "Relogio 24h",        [True, False]),
                ("show_clock",        "Mostrar relogio",    [True, False]),
                ("power_profile",     "Energia",            ["economia", "equilibrado", "desempenho"]),
            ]
        def draw(self, win, y0, x0, h, w, cfg):
            safe_addstr(win, y0, x0+1, "Use ^ v pra escolher, < > pra mudar o valor."[:w-2])
            safe_addstr(win, y0+1, x0+1, "As mudancas salvam sozinhas."[:w-2])
            for i, (key, label, opts) in enumerate(self.items):
                val = cfg.get(key, opts[0])
                shown = "sim" if val is True else ("nao" if val is False else str(val))
                marker = ">" if i == self.cursor else " "
                line = " %s %-26s [ %s ]" % (marker, label, shown)
                attr = curses.A_REVERSE if i == self.cursor else curses.A_NORMAL
                safe_addstr(win, y0+3+i, x0+1, line[:w-2], attr)
            safe_addstr(win, y0+h-1, x0+1, ("Config: %s" % USER_CONFIG)[:w-2], curses.A_DIM)
        def _cycle(self, cfg, direction):
            key, label, opts = self.items[self.cursor]
            cur = cfg.get(key, opts[0])
            try:   idx = opts.index(cur)
            except ValueError: idx = 0
            cfg[key] = opts[(idx + direction) % len(opts)]
            save_config(cfg)
        def handle_key(self, key, cfg):
            if key in (curses.KEY_UP, ord("k")):   self.cursor = (self.cursor-1)%len(self.items)
            elif key in (curses.KEY_DOWN, ord("j")):self.cursor = (self.cursor+1)%len(self.items)
            elif key in (curses.KEY_LEFT, ord("h")): self._cycle(cfg, -1)
            elif key in (curses.KEY_RIGHT, ord("l"), ord("\n"), curses.KEY_ENTER): self._cycle(cfg, +1)
            elif key == 27: return "close"
            return None

    class SoftwareApp(App):
        def __init__(self):
            super().__init__("Central de Programas", "[v]")
            self.catalog = [
                ("Firefox",     "Outro navegador (pesado)", "firefox"),
                ("Gedit",       "Editor de texto", "gedit"),
                ("LibreOffice", "Docs e planilhas", "libreoffice-fresh"),
                ("GIMP",        "Editar imagens", "gimp"),
                ("VLC",         "Videos e musicas", "vlc"),
                ("Wine",        "Programas Windows", "wine"),
                ("Winetricks",  "Ajustes pro Wine", "winetricks"),
                ("Arduino IDE", "Programar robo", "arduino-ide"),
            ]
            self.message = ""
        def draw(self, win, y0, x0, h, w, cfg):
            safe_addstr(win, y0, x0+1, "Central de Programas (instala de verdade)"[:w-2], curses.A_BOLD)
            safe_addstr(win, y0+1, x0+1, "Enter=instalar  ^v=navegar  Esc=fechar"[:w-2])
            list_h = h - 5
            if self.cursor < self.scroll: self.scroll = self.cursor
            elif self.cursor >= self.scroll + list_h: self.scroll = self.cursor - list_h + 1
            for vis in range(list_h):
                i = self.scroll + vis
                if i >= len(self.catalog): break
                name, desc, _ = self.catalog[i]
                marker = ">" if i == self.cursor else " "
                attr = curses.A_REVERSE if i == self.cursor else curses.A_NORMAL
                safe_addstr(win, y0+3+vis, x0+1, (" %s %-18s %s"%(marker,name,desc))[:w-2], attr)
            if self.message:
                safe_addstr(win, y0+h-1, x0+1, self.message[:w-2], curses.A_DIM)
        def handle_key(self, key, cfg):
            if key in (curses.KEY_UP, ord("k")):   self.cursor = (self.cursor-1)%len(self.catalog)
            elif key in (curses.KEY_DOWN, ord("j")):self.cursor = (self.cursor+1)%len(self.catalog)
            elif key in (ord("\n"), curses.KEY_ENTER): self._install(cfg)
            elif key == 27: return "close"
            return None
        def _install(self, cfg):
            name, _, pkg = self.catalog[self.cursor]
            # sai do curses, roda o pacman vendo o progresso, e volta
            curses.def_prog_mode(); curses.endwin()
            os.system("clear; pacman -Sy --needed --noconfirm %s; "
                      "echo; read -p '--- ENTER pra voltar ---' _" % pkg)
            curses.reset_prog_mode(); curses.curs_set(0)
            self.message = "Tentou instalar '%s' (pacote: %s)." % (name, pkg)

    class AboutApp(App):
        def __init__(self):
            super().__init__("Sobre o " + OS_NAME, "[i]")
        def draw(self, win, y0, x0, h, w, cfg):
            info = [
                OS_NAME + " " + OS_VERSION, "",
                "Base ............ Linux (kernel), archiso",
                "Telemetria ...... NENHUMA.",
                "Privacidade ..... nem sabe seu nome.", "",
                "Estagios:",
                "  0) Shell TUI            [FEITO]",
                "  1) ISO que boota na VM  [FEITO]",
                "  2) Wine + instalador    [a fazer]",
                "  3) GUI levinha          [FEITO]",
                "  4) Multi-arch           [a fazer]", "",
                "Feito pela familia Miranda + Claude.",
            ]
            for i, ln in enumerate(info):
                if i >= h: break
                safe_addstr(win, y0+i, x0+1, ln[:w-2])

    class TerminalLauncher:
        title = "Terminal"
        @staticmethod
        def run(stdscr):
            curses.endwin()
            shell = os.environ.get("SHELL", "/bin/bash")
            print("\n[%s] Terminal — digite 'exit' pra voltar ao desktop.\n" % OS_NAME)
            try:    subprocess.call([shell])
            except Exception as e:
                print("Erro ao abrir terminal: %s" % e)
                time.sleep(1.5)
            stdscr.clear()
            curses.doupdate()

    class TUIDesktop:
        def __init__(self, stdscr, cfg):
            self.stdscr          = stdscr
            self.cfg             = cfg
            self.windows         = []
            self.active          = 0
            self.start_menu_open = False
            self.start_cursor    = 0
            self.switcher_open   = False
            self.switcher_idx    = 0
            self.running         = True
            self.menu_items = [
                ("Central de Configuracoes", lambda: SettingsApp()),
                ("Central de Programas",     lambda: SoftwareApp()),
                ("Bem-vindo",                lambda: WelcomeApp()),
                ("Sobre o " + OS_NAME,       lambda: AboutApp()),
                ("Terminal", "terminal"),
                ("Desligar", "shutdown"),
            ]
            self.open_app(WelcomeApp())

        def open_app(self, app):
            self.windows.append(app)
            self.active = len(self.windows) - 1

        def close_active(self):
            if self.windows:
                del self.windows[self.active]
                if self.active >= len(self.windows):
                    self.active = len(self.windows) - 1

        def focus(self, idx):
            if 0 <= idx < len(self.windows):
                self.active = idx

        def draw(self):
            scr = self.stdscr
            scr.erase()
            h, w = scr.getmaxyx()
            bar_top = self.cfg.get("taskbar_position", "embaixo") == "em cima"
            desk_y0 = 1 if bar_top else 0
            desk_h  = h - 1
            # wallpaper
            pat = self.cfg.get("wallpaper_pattern", "pontos")
            for y in range(desk_y0, desk_y0+desk_h):
                if pat == "pontos" and (y-desk_y0)%2==0:
                    safe_addstr(scr, y, 0, "".join("." if x%4==0 else " " for x in range(w)), curses.A_DIM)
            # janela ativa
            if self.windows:
                self._draw_window(self.windows[self.active], desk_y0, desk_h, w)
            else:
                msg = "Area de trabalho vazia. F2 = Menu Iniciar."
                safe_addstr(scr, desk_y0+desk_h//2, max(0,(w-len(msg))//2), msg, curses.A_DIM)
            # taskbar
            self._draw_taskbar(0 if bar_top else h-1, w)
            if self.start_menu_open:  self._draw_start_menu(h, w, bar_top)
            if self.switcher_open:    self._draw_switcher(h, w)
            scr.noutrefresh()
            curses.doupdate()

        def _draw_window(self, app, y0, h, w):
            mx = max(2, w//12); my = 1
            wx0,wy0,ww,wh = mx,y0+my,w-2*mx,h-2*my
            if ww<20 or wh<6: wx0,wy0,ww,wh = 0,y0,w,h
            safe_addstr(self.stdscr, wy0, wx0, "+"+"-"*(ww-2)+"+")
            for i in range(1, wh-1):
                safe_addstr(self.stdscr, wy0+i, wx0, "|")
                safe_addstr(self.stdscr, wy0+i, wx0+ww-1, "|")
            safe_addstr(self.stdscr, wy0+wh-1, wx0, "+"+"-"*(ww-2)+"+")
            title = " %s %s " % (app.icon, app.title)
            safe_addstr(self.stdscr, wy0, wx0+2, title, curses.A_BOLD|curses.A_REVERSE)
            safe_addstr(self.stdscr, wy0, wx0+ww-22, " Esc:fechar Tab:trocar ", curses.A_DIM)
            app.draw(self.stdscr, wy0+2, wx0+1, wh-3, ww-2, self.cfg)

        def _draw_taskbar(self, y, w):
            scr = self.stdscr
            safe_addstr(scr, y, 0, " "*w, curses.A_REVERSE)
            logo = " %s " % CLAUDE_LOGO
            safe_addstr(scr, y, 0, logo, curses.A_REVERSE|curses.A_BOLD)
            self._logo_x1 = len(logo)
            sx = self._logo_x1 + 1
            safe_addstr(scr, y, sx, " Iniciar ", curses.A_REVERSE|curses.A_BOLD)
            self._start_x0, self._start_x1 = sx, sx+9
            tx = sx + 11; self._tabs = []
            for i, app in enumerate(self.windows):
                label = " %s " % app.title
                attr = curses.A_BOLD if i==self.active else curses.A_REVERSE
                safe_addstr(scr, y, tx, label, attr)
                self._tabs.append((tx, tx+len(label), i))
                tx += len(label)+1
                if tx > w-12: break
            if self.cfg.get("show_clock", True):
                fmt = "%H:%M" if self.cfg.get("clock_24h", True) else "%I:%M %p"
                clock = time.strftime(fmt)
                safe_addstr(scr, y, w-len(clock)-1, clock, curses.A_REVERSE|curses.A_BOLD)

        def _draw_start_menu(self, h, w, bar_top):
            items = self.menu_items
            mh,mw = len(items)+4, 34
            my = 1 if bar_top else h-1-mh
            safe_addstr(self.stdscr, my, 0, "+"+"-"*(mw-2)+"+")
            for i in range(1, mh-1):
                safe_addstr(self.stdscr, my+i, 0, "|")
                safe_addstr(self.stdscr, my+i, mw-1, "|")
            safe_addstr(self.stdscr, my+mh-1, 0, "+"+"-"*(mw-2)+"+")
            safe_addstr(self.stdscr, my, 2, " Menu Iniciar ", curses.A_BOLD|curses.A_REVERSE)
            safe_addstr(self.stdscr, my+1, 2, "%s  %s" % (CLAUDE_LOGO, OS_NAME), curses.A_BOLD)
            for i, (label, _) in enumerate(items):
                marker = ">" if i==self.start_cursor else " "
                attr = curses.A_REVERSE if i==self.start_cursor else curses.A_NORMAL
                safe_addstr(self.stdscr, my+3+i, 2, (" %s %s"%(marker,label)).ljust(mw-4), attr)

        def _draw_switcher(self, h, w):
            if not self.windows: return
            bw = max(30, min(w-4, max(len(a.title) for a in self.windows)+14))
            bh = len(self.windows)+4
            by,bx = (h-bh)//2, (w-bw)//2
            for i in range(bh):
                safe_addstr(self.stdscr, by+i, bx, " "*bw, curses.A_REVERSE)
            safe_addstr(self.stdscr, by, bx, "+"+"-"*(bw-2)+"+")
            for i in range(1, bh-1):
                safe_addstr(self.stdscr, by+i, bx, "|"); safe_addstr(self.stdscr, by+i, bx+bw-1, "|")
            safe_addstr(self.stdscr, by+bh-1, bx, "+"+"-"*(bw-2)+"+")
            safe_addstr(self.stdscr, by, bx+2, " Alternar janela (Tab/setas, Enter) ", curses.A_BOLD|curses.A_REVERSE)
            for i, app in enumerate(self.windows):
                marker = "=>" if i==self.switcher_idx else "  "
                line = " %s %s %s" % (marker, app.icon, app.title)
                attr = curses.A_BOLD|curses.A_REVERSE if i==self.switcher_idx else curses.A_REVERSE
                safe_addstr(self.stdscr, by+2+i, bx+2, line.ljust(bw-4), attr)

        def handle(self, key):
            if self.switcher_open:   self._switcher_key(key); return
            if self.start_menu_open: self._start_menu_key(key); return
            if key == curses.KEY_MOUSE: self._mouse(); return
            if key in (ord("\t"), 9): self._open_switcher(); return
            if key == curses.KEY_F2:
                self.start_menu_open = True; self.start_cursor = 0; return
            if key in (ord("q"), ord("Q")) and not self.windows:
                request_shutdown(); self.running = False; return
            if self.windows:
                res = self.windows[self.active].handle_key(key, self.cfg)
                if res == "close": self.close_active()

        def _open_switcher(self):
            if not self.windows: return
            self.switcher_open = True
            self.switcher_idx = (self.active+1) % len(self.windows)

        def _switcher_key(self, key):
            n = len(self.windows)
            if n == 0: self.switcher_open = False; return
            if key in (curses.KEY_DOWN, curses.KEY_RIGHT, ord("\t"), 9):
                self.switcher_idx = (self.switcher_idx+1)%n
            elif key in (curses.KEY_UP, curses.KEY_LEFT, curses.KEY_BTAB):
                self.switcher_idx = (self.switcher_idx-1)%n
            elif key in (ord("\n"), curses.KEY_ENTER):
                self.focus(self.switcher_idx); self.switcher_open = False
            elif key == 27: self.switcher_open = False

        def _start_menu_key(self, key):
            n = len(self.menu_items)
            if key in (curses.KEY_UP, ord("k")):    self.start_cursor = (self.start_cursor-1)%n
            elif key in (curses.KEY_DOWN, ord("j")): self.start_cursor = (self.start_cursor+1)%n
            elif key in (ord("\n"), curses.KEY_ENTER): self._activate_menu(self.start_cursor)
            elif key in (27, curses.KEY_F2): self.start_menu_open = False
            elif key == curses.KEY_MOUSE: self._mouse()

        def _activate_menu(self, idx):
            label, action = self.menu_items[idx]
            self.start_menu_open = False
            if action == "shutdown":   request_shutdown(); self.running = False
            elif action == "terminal": TerminalLauncher.run(self.stdscr)
            elif callable(action):
                new = action()
                for i, a in enumerate(self.windows):
                    if a.title == new.title: self.active = i; return
                self.open_app(new)

        def _mouse(self):
            try: _, mx, my, _, bstate = curses.getmouse()
            except curses.error: return
            h, w = self.stdscr.getmaxyx()
            bar_top = self.cfg.get("taskbar_position","embaixo") == "em cima"
            bar_y = 0 if bar_top else h-1
            if bstate & curses.BUTTON4_PRESSED:
                if self.windows: self.active = (self.active-1)%len(self.windows)
                return
            if bstate & getattr(curses,"BUTTON5_PRESSED",0):
                if self.windows: self.active = (self.active+1)%len(self.windows)
                return
            if bstate & (curses.BUTTON1_CLICKED|curses.BUTTON1_PRESSED):
                if my == bar_y:
                    if mx < getattr(self,"_logo_x1",0):
                        self._open_switcher(); return
                    if getattr(self,"_start_x0",0) <= mx < getattr(self,"_start_x1",0):
                        self.start_menu_open = not self.start_menu_open
                        self.start_cursor = 0; return
                    for (x0,x1,i) in getattr(self,"_tabs",[]):
                        if x0 <= mx < x1: self.focus(i); return

    def _tui_main(stdscr):
        cfg = load_config()
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(500)
        try: curses.mousemask(curses.ALL_MOUSE_EVENTS|curses.REPORT_MOUSE_POSITION)
        except curses.error: pass
        desk = TUIDesktop(stdscr, cfg)
        while desk.running:
            desk.draw()
            try: key = stdscr.getch()
            except KeyboardInterrupt: break
            if key == -1: continue
            desk.handle(key)

    curses.wrapper(_tui_main)


# ============================================================================
#  Dispatcher: GUI se tiver X11, TUI se nao tiver
# ============================================================================
def run():
    if not os.isatty(0) and not os.environ.get("DISPLAY"):
        print("O %s precisa de um terminal ou sessao X11 pra rodar." % OS_NAME)
        print("Rode:  python3 %s" % __file__)
        return

    if os.environ.get("DISPLAY"):
        # Tenta GUI; se tkinter nao estiver disponivel cai pro TUI
        try:
            import tkinter  # noqa: F401
            run_gui()
            return
        except ImportError:
            print("[PenaOS] tkinter nao encontrado, iniciando modo TUI...")

    run_tui()


if __name__ == "__main__":
    run()
