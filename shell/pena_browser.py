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
#  Busca: se o que voce digitar nao for um endereco, mandamos pro DuckDuckGo
#  Lite (HTML puro, levissimo) que ainda aceita !bangs (ex: "!w arduino").
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
from gi.repository import Gtk, WebKit2, GLib  # noqa: E402

# ---- configuracao -----------------------------------------------------------
INVIDIOUS = "inv.nadeko.net"
HOMEPAGE = "https://lite.duckduckgo.com/lite/"
SEARCH = "https://lite.duckduckgo.com/lite/?q=%s"   # %s = termo (aceita !bangs)

# dominios do YouTube que a gente intercepta
YT_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}

# cores PenaOS (casa com o resto do sistema)
CSS = b"""
.penatop { background:#090f1e; }
entry { background:#0d1929; color:#FAF6EE; border-radius:6px; padding:4px 8px;
        caret-color:#3DDC97; }
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

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Digite um site ou uma busca (aceita !bangs)")
        self.entry.connect("activate", self.on_enter)
        bar.pack_start(self.entry, True, True, 4)

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

        # economia de RAM: sem cache em disco (live nao tem disco) + leve
        try:
            s = self.web.get_settings()
            s.set_enable_developer_extras(False)
            s.set_enable_page_cache(False)
            s.set_enable_offline_web_application_cache(False)
            s.set_enable_html5_database(False)
            s.set_enable_smooth_scrolling(False)
        except Exception:
            pass

        self.web.connect("decide-policy", self.on_decide)
        self.web.connect("load-changed", self.on_load_changed)
        box.pack_start(self.web, True, True, 0)

        self.connect("destroy", Gtk.main_quit)

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
            uri = web.get_uri() or ""
            self.entry.set_text(uri)

    def on_enter(self, entry):
        text = entry.get_text().strip()
        if looks_like_url(text):
            if not text.startswith(("http://", "https://", "about:", "file://")):
                text = "https://" + text
            self.load(text)
        else:
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
