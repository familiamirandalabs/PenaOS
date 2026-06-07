#!/usr/bin/env python3
# ============================================================================
#  pena_browser.py  —  o mini-navegador do PenaOS (leve, com privacidade)
# ----------------------------------------------------------------------------
#  Feito com Python + WebKitGTK (mesmo motor do Safari/GNOME Web, mas SEM o
#  peso de um navegador inteiro). Uma aba, barra de endereco, voltar/avancar.
#
#  TRUQUE DE PRIVACIDADE/LEVEZA:
#    Todo acesso ao YouTube (digitado, clicado num link, colado, ou ate um
#    redirect feito por JavaScript) e automaticamente trocado por uma
#    instancia do Invidious (inv.nadeko.net). O Invidious mostra o video
#    SEM o YouTube pesado da Google: sem rastreamento, sem JS gigante, roda
#    numa POTATO. O redirect e feito em DOIS lugares pra nao escapar nada:
#      1) na hora de decidir a navegacao (decide-policy) -> pega quase tudo
#      2) um userscript no inicio da pagina -> pega redirects via JS
#
#  BANGS NATIVOS (novo):
#    A gente NAO depende mais do DuckDuckGo pros !bangs — eles sao tratados
#    aqui dentro. Digite "!yt gato" e aperte espaco: a barra vira uma PILL
#    verde "YouTube │ gato" e a busca vai direto pro site certo. Backspace no
#    comeco apaga a pill. Lista de bangs la embaixo em BANGS.
#
#  Busca normal (sem bang): vai pro DuckDuckGo Lite (HTML puro, levissimo).
# ============================================================================
import sys
import urllib.parse

import gi
# o pacote da ISO e o webkit2gtk-4.1; tentamos 4.1 e caimos pra 4.0 se preciso
try:
    gi.require_version("WebKit2", "4.1")
except ValueError:
    gi.require_version("WebKit2", "4.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, WebKit2, GLib  # noqa: E402

# ---- configuracao -----------------------------------------------------------
INVIDIOUS = "inv.nadeko.net"
HOMEPAGE = "https://lite.duckduckgo.com/lite/"
SEARCH = "https://lite.duckduckgo.com/lite/?q=%s"   # busca normal (sem bang)

# ---- BANGS NATIVOS ----------------------------------------------------------
#  chave -> (Nome bonito que aparece na pill, URL com %s no lugar do termo)
#  O termo vai sempre urlencoded. YouTube cai no Invidious (privacidade+leveza).
BANGS = {
    "yt":   ("YouTube",    "https://" + INVIDIOUS + "/search?q=%s"),
    "v":    ("YouTube",    "https://" + INVIDIOUS + "/search?q=%s"),
    "w":    ("Wikipedia",  "https://pt.wikipedia.org/w/index.php?search=%s"),
    "g":    ("Google",     "https://www.google.com/search?q=%s"),
    "ddg":  ("DuckDuckGo", "https://lite.duckduckgo.com/lite/?q=%s"),
    "gh":   ("GitHub",     "https://github.com/search?q=%s&type=repositories"),
    "img":  ("Imagens",    "https://duckduckgo.com/?ia=images&iax=images&q=%s"),
    "mapa": ("Mapas",      "https://www.openstreetmap.org/search?query=%s"),
    "ml":   ("Mercado Livre",
             "https://lista.mercadolivre.com.br/%s"),
}

# dominios do YouTube que a gente intercepta
YT_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}

# cores PenaOS (casa com o resto do sistema)
CSS = b"""
.penatop { background:#090f1e; }
.addrbar entry { background:#0d1929; color:#FAF6EE; border-radius:6px;
        padding:4px 8px; caret-color:#3DDC97; }
/* a pill verde do bang (ex: "YouTube") */
.bangpill { background:#3DDC97; color:#090f1e; border-radius:6px;
        padding:2px 9px; margin:0 2px 0 4px; font-weight:bold; }
button { background:#0d1929; color:#3DDC97; border:0; padding:4px 8px;
         margin:0 1px; }
button:hover { background:#16213C; }
"""


def youtube_to_invidious(uri):
    """Se 'uri' for do YouTube, devolve a versao Invidious. Senao, devolve None."""
    try:
        p = urllib.parse.urlsplit(uri)
    except Exception:
        return None
    host = (p.hostname or "").lower()

    # youtu.be/VIDEO_ID  ->  inv.nadeko.net/watch?v=VIDEO_ID
    if host in ("youtu.be", "www.youtu.be"):
        vid = p.path.lstrip("/")
        q = "v=" + vid
        if p.query:
            q += "&" + p.query
        return urllib.parse.urlunsplit(("https", INVIDIOUS, "/watch", q, p.fragment))

    # qualquer outro host do YouTube: troca so o dominio, mantem caminho+query
    if host in YT_HOSTS:
        return urllib.parse.urlunsplit(
            ("https", INVIDIOUS, p.path, p.query, p.fragment))

    return None


def looks_like_url(text):
    """Decide se o que a crianca digitou e um endereco ou uma busca."""
    text = text.strip()
    if not text:
        return False
    if " " in text:
        return False
    if text.startswith(("http://", "https://", "about:", "file://")):
        return True
    # tem ponto e parece dominio (ex: arduino.cc, github.com)
    if "." in text and not text.startswith("."):
        return True
    return False


class PenaBrowser(Gtk.Window):
    def __init__(self):
        super().__init__(title="Navegador do PenaOS")
        self.set_default_size(1000, 680)

        self.active_bang = None      # chave do bang atual (ex: "yt") ou None
        self._guard = False          # evita recursao no sinal 'changed'

        # tema
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), prov, Gtk.STYLE_PROVIDER_PRIORITY_USER)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(box)

        # ---- barra de cima: voltar, avancar, recarregar, endereco ----------
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        bar.get_style_context().add_class("penatop")
        bar.set_border_width(4)
        box.pack_start(bar, False, False, 0)

        def mkbtn(label, cb):
            b = Gtk.Button(label=label)
            b.connect("clicked", cb)
            bar.pack_start(b, False, False, 0)
            return b

        mkbtn("←", lambda *_: self.web.go_back())     # voltar
        mkbtn("→", lambda *_: self.web.go_forward())   # avancar
        mkbtn("↻", lambda *_: self.web.reload())       # recarregar

        # caixa de endereco = [pill do bang] + [entry], lado a lado, parecendo
        # uma barra so. A pill so aparece quando tem bang ativo.
        addr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        addr.get_style_context().add_class("addrbar")
        bar.pack_start(addr, True, True, 4)

        self.bang_label = Gtk.Label()
        self.bang_label.get_style_context().add_class("bangpill")
        self.bang_label.set_no_show_all(True)   # nao aparece no show_all()
        addr.pack_start(self.bang_label, False, False, 0)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text(
            "Site ou busca  —  dica: !yt gato, !w arduino, !g ...")
        # lupinha no comeco da barra (igual a foto)
        try:
            self.entry.set_icon_from_icon_name(
                Gtk.EntryIconPosition.PRIMARY, "system-search-symbolic")
        except Exception:
            pass
        self.entry.connect("activate", self.on_enter)
        self.entry.connect("changed", self.on_changed)
        self.entry.connect("key-press-event", self.on_key)
        addr.pack_start(self.entry, True, True, 0)

        mkbtn("⌂", lambda *_: self.load(HOMEPAGE))     # inicio

        # ---- area da pagina (WebView) --------------------------------------
        # userscript: redirect via JS no inicio da pagina (pega o que escapar)
        self.ucm = WebKit2.UserContentManager()
        js = ("(function(){var h=location.hostname.replace(/^www\\./,'');"
              "var yt=['youtube.com','m.youtube.com','music.youtube.com',"
              "'youtube-nocookie.com'];"
              "if(yt.indexOf(h)>=0){location.replace("
              "location.href.replace(/([a-z]+\\.)?youtube(-nocookie)?\\.com/,"
              "'%s'));}"
              "else if(h==='youtu.be'){location.replace('https://%s/watch?v='"
              "+location.pathname.slice(1)+location.search.replace('?','&'));}"
              "})();" % (INVIDIOUS, INVIDIOUS))
        self.ucm.add_script(WebKit2.UserScript.new(
            js,
            WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            WebKit2.UserScriptInjectionTime.START,
            None, None))

        self.web = WebKit2.WebView.new_with_user_content_manager(self.ucm)

        # economia de RAM + codecs/video ligados (sem isto o Invidious nao toca)
        try:
            s = self.web.get_settings()
            s.set_enable_developer_extras(False)
            s.set_enable_page_cache(False)
            s.set_enable_offline_web_application_cache(False)
            s.set_enable_html5_database(False)
            s.set_enable_smooth_scrolling(False)
            # --- VIDEO: o player do Invidious usa MSE (Media Source Extensions).
            #     Sem isto o player nem aparece / da "incompatible". ---
            s.set_enable_mediasource(True)
            # deixa o video tocar sozinho (crianca nao precisa "destravar")
            s.set_media_playback_requires_user_gesture(False)
            s.set_enable_webaudio(True)
        except Exception:
            pass

        self.web.connect("decide-policy", self.on_decide)
        self.web.connect("load-changed", self.on_load_changed)
        box.pack_start(self.web, True, True, 0)

        self.connect("destroy", Gtk.main_quit)

    # ---- BANGS: pill verde -------------------------------------------------
    def set_bang(self, key):
        self.active_bang = key
        self.bang_label.set_text(BANGS[key][0])
        self.bang_label.show()

    def clear_bang(self):
        if self.active_bang is not None:
            self.active_bang = None
            self.bang_label.hide()

    def on_changed(self, entry):
        """Quando digita '!yt ' (com espaco), promove pra pill verde."""
        if self._guard or self.active_bang is not None:
            return
        text = entry.get_text()
        if not text.startswith("!") or " " not in text:
            return
        token, rest = text[1:].split(" ", 1)
        token = token.lower()
        if token in BANGS:
            self._guard = True
            self.set_bang(token)
            entry.set_text(rest)          # so a busca fica no campo
            entry.set_position(-1)        # cursor no fim
            self._guard = False

    def on_key(self, entry, event):
        """Backspace no comeco da busca apaga a pill do bang."""
        if (self.active_bang is not None
                and event.keyval == Gdk.KEY_BackSpace
                and entry.get_position() == 0):
            self.clear_bang()
            return True   # nao apaga letra nenhuma desta vez
        return False

    # ---- redirect no nivel da navegacao (pega digitado/clicado/colado) -----
    def on_decide(self, web, decision, dtype):
        if dtype != WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            return False
        try:
            uri = decision.get_navigation_action().get_request().get_uri()
        except Exception:
            return False
        new = youtube_to_invidious(uri)
        if new and new != uri:
            decision.ignore()           # cancela ir pro YouTube
            GLib.idle_add(self.load, new)   # e vai pro Invidious
            return True
        return False

    def on_load_changed(self, web, event):
        # mantem a barra de endereco sincronizada com a pagina atual
        if event == WebKit2.LoadEvent.COMMITTED:
            self.clear_bang()
            uri = web.get_uri() or ""
            self._guard = True
            self.entry.set_text(uri)
            self._guard = False

    def on_enter(self, entry):
        text = entry.get_text().strip()
        # 1) bang ativo (pill verde): vai direto pro site do bang
        if self.active_bang is not None:
            url = BANGS[self.active_bang][1] % urllib.parse.quote(text)
            self.load(url)
            return
        # 2) bang digitado sem espaco ainda (ex: "!yt gato" colado de uma vez)
        if text.startswith("!") and " " in text:
            token, rest = text[1:].split(" ", 1)
            if token.lower() in BANGS:
                url = BANGS[token.lower()][1] % urllib.parse.quote(rest.strip())
                self.load(url)
                return
        # 3) endereco normal
        if looks_like_url(text):
            if not text.startswith(("http://", "https://", "about:", "file://")):
                text = "https://" + text
            self.load(text)
        else:
            # 4) busca normal
            self.load(SEARCH % urllib.parse.quote(text))

    def load(self, uri):
        # ja redireciona aqui tambem (cinto + suspensorio)
        self.web.load_uri(youtube_to_invidious(uri) or uri)
        return False


def main():
    win = PenaBrowser()
    win.show_all()
    # 1o argumento opcional = url inicial (o shell passa a HOMEPAGE)
    start = sys.argv[1] if len(sys.argv) > 1 else HOMEPAGE
    win.load(start)
    Gtk.main()


if __name__ == "__main__":
    main()
