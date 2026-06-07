#!/usr/bin/env bash
# ============================================================================
#  build_penaos_iso.sh  —  monta a ISO inicializavel do PenaOS (Estagio 1)
# ----------------------------------------------------------------------------
#  O QUE FAZ (em portugues simples):
#    1. Pega a ISO "baseline" do Arch (a mais enxuta que existe).
#    2. Adiciona o Python (so isso! pra ficar levinho de batata).
#    3. Coloca a nossa area de trabalho (pena_shell.py) dentro dela.
#    4. Configura pra ligar e ja cair DIRETO no PenaOS, sem digitar nada.
#    5. Gera o arquivo .iso que voce arrasta pro VirtualBox.
#
#  COMO USAR:
#    # 1) instale a ferramenta (uma vez so):
#    sudo pacman -S archiso
#    # 2) rode este script COMO ROOT:
#    sudo ~/Documents/penaos/build/build_penaos_iso.sh
#    # 3) a ISO sai em:  ~/Documents/penaos/build/out/penaos-*.iso
#
#  Precisa de root porque o mkarchiso monta sistemas de arquivos.
#  Nao mexe em NADA do seu Arch de verdade — so cria um arquivo .iso.
# ============================================================================
set -euo pipefail

# ---- descobre os caminhos (mesmo rodando com sudo) --------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_DIR="$(dirname "$SCRIPT_DIR")"
OVERLAY="$SCRIPT_DIR/overlay"
SHELL_SRC="$PROJ_DIR/shell/pena_shell.py"
CONFIG_SRC="$PROJ_DIR/config/default.json"
BASELINE="/usr/share/archiso/configs/baseline"
WORK="$SCRIPT_DIR/work"
PROFILE="$WORK/profile"
OUT="$SCRIPT_DIR/out"

# ---- arquitetura alvo -------------------------------------------------------
#  x86_64 (padrao) = Arch mainline, ISO live BIOS -> 100% funcional aqui.
#  i686            = Arch Linux 32 (precisa repos+keyring archlinux32).
#  aarch64         = Arch Linux ARM (modelo rootfs, NAO ISO; pipeline a parte).
#  Use:  PENA_ARCH=i686 sudo ./build_penaos_iso.sh
ARCH="${PENA_ARCH:-x86_64}"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
err() { printf '\n\033[1;31mERRO: %s\033[0m\n' "$*" >&2; exit 1; }

# ---- checagens --------------------------------------------------------------
[[ $EUID -eq 0 ]] || err "rode como root:  sudo $0"
command -v mkarchiso >/dev/null 2>&1 || err "falta o archiso. Rode antes:  sudo pacman -S archiso"
[[ -d "$BASELINE" ]] || err "perfil baseline nao encontrado em $BASELINE (reinstale archiso)"
[[ -f "$SHELL_SRC" ]] || err "nao achei o shell: $SHELL_SRC"

# ---- arquitetura: x86_64 funciona; i686/aarch64 exigem outros toolchains ----
case "$ARCH" in
  x86_64)
    say "Arquitetura alvo: x86_64 (Arch mainline) — caminho 100% suportado"
    ;;
  i686)
    say "Arquitetura alvo: i686 (Arch Linux 32) — EXPERIMENTAL"
    cat >&2 <<'AVISO'
  Pra construir 32-bit voce precisa, ALEM do archiso:
    - rodar num ambiente Arch Linux 32 (ou com pacman apontando pro
      archlinux32 + binfmt/qemu pra rodar binarios i686 num host x86_64);
    - ter o pacote 'archlinux32-keyring' e confiar nas chaves;
    - conferir que os pacotes de packages.i686 existem no archlinux32.
  O script segue, mas o mkarchiso vai falhar se o pacman do host nao
  estiver configurado pro archlinux32.
AVISO
    ;;
  aarch64)
    err "aarch64 (ARM) NAO usa o modelo de ISO live / BIOS deste script.
  A Arch Linux ARM monta um ROOTFS que voce grava no cartao SD, com boot
  por U-Boot/UEFI especifico da placa. Isso e um pipeline separado
  (pacstrap do tarball ALARM + boot da placa), nao o mkarchiso BIOS.
  Os arquivos packages.aarch64 e mirrorlist.aarch64 ja estao prontos como
  base, mas a montagem do rootfs ARM sera um script proprio (a fazer)."
    ;;
  *)
    err "arquitetura desconhecida: '$ARCH' (use x86_64, i686 ou aarch64)"
    ;;
esac

# ---- prepara area de trabalho limpa -----------------------------------------
say "Limpando area de trabalho anterior"
rm -rf "$WORK"
mkdir -p "$PROFILE" "$OUT"

say "Copiando a ISO baseline do Arch (base enxuta)"
cp -r "$BASELINE/." "$PROFILE/"

# ---- SUBSTITUI a lista de pacotes pela nossa (minima) -----------------------
# A baseline vem com cloud-init, hyperv, open-vm-tools, qemu-guest-agent,
# openssh, pv... nada disso serve pra VirtualBox + TUI. Trocamos pela nossa
# lista enxuta (so o que da boot + python). Isso corta ~100-150 MB.
PKG_SRC="$OVERLAY/packages.$ARCH"
[[ -f "$PKG_SRC" ]] || err "nao achei a lista de pacotes: $PKG_SRC"
say "Usando a lista MINIMA de pacotes ($ARCH) do PenaOS"
# o archiso espera o arquivo chamado packages.<arch_do_profile>. Como o
# profile e x86_64 por padrao, geramos packages.x86_64; pra i686 o archiso
# usa o mesmo nome de arquivo do profiledef (ajustado mais abaixo).
ARCHISO_PKG_NAME="packages.x86_64"
[[ "$ARCH" == "i686" ]] && ARCHISO_PKG_NAME="packages.i686"
rm -f "$PROFILE"/packages.x86_64 "$PROFILE"/packages.i686
grep -vE '^[[:space:]]*(#|$)' "$PKG_SRC" \
    | sed 's/[[:space:]]*#.*//' | sed 's/[[:space:]]*$//' \
    | grep -vE '^[[:space:]]*$' \
    > "$PROFILE/$ARCHISO_PKG_NAME"

# ---- pacman.conf: nao extrair docs/man/locales (ISO menor) ------------------
# Numa area de trabalho em texto, manual, traducoes e documentacao so ocupam
# espaco. Mandamos o pacman PULAR esses arquivos na hora de montar a ISO.
say "Cortando docs, manuais e traducoes (deixa a ISO bem menor)"
PCONF="$PROFILE/pacman.conf"
if [[ -f "$PCONF" ]] && ! grep -q 'PenaOS-slim' "$PCONF"; then
    cat >> "$PCONF" <<'SLIM'

# --- PenaOS-slim: nao extrair gordura ---
NoExtract = usr/share/man/* usr/share/doc/*
NoExtract = usr/share/info/* usr/share/help/*
NoExtract = usr/share/locale/* !usr/share/locale/locale.alias
NoExtract = usr/share/i18n/charmaps/*
NoExtract = usr/lib/firmware/*
SLIM
fi

# ---- sobrepoe nossos arquivos (autologin, motd, os-release, etc) ------------
say "Aplicando a cara do PenaOS (autologin, branding, area de trabalho)"
cp -r "$OVERLAY/airootfs/." "$PROFILE/airootfs/"

# mirrorlist certo pra arquitetura (sobrepoe o que veio do airootfs)
MIRROR_SRC="$OVERLAY/mirrorlist.$ARCH"
if [[ -f "$MIRROR_SRC" ]]; then
    say "Aplicando mirrors do pacman para $ARCH"
    mkdir -p "$PROFILE/airootfs/etc/pacman.d"
    cp "$MIRROR_SRC" "$PROFILE/airootfs/etc/pacman.d/mirrorlist"
fi

# ---- injeta a area de trabalho dentro da ISO --------------------------------
mkdir -p "$PROFILE/airootfs/opt/penaos"
cp "$SHELL_SRC" "$PROFILE/airootfs/opt/penaos/pena_shell.py"
# nosso mini-navegador (Python + WebKitGTK, redirect YouTube->Invidious)
BROWSER_SRC="$PROJ_DIR/shell/pena_browser.py"
[[ -f "$BROWSER_SRC" ]] && cp "$BROWSER_SRC" "$PROFILE/airootfs/opt/penaos/pena_browser.py"
# lancador enxuto de .exe (abre o app pelo Wine, sem mostrar pasta)
RUNEXE_SRC="$PROJ_DIR/shell/pena_run_exe.py"
[[ -f "$RUNEXE_SRC" ]] && cp "$RUNEXE_SRC" "$PROFILE/airootfs/opt/penaos/pena_run_exe.py"
[[ -f "$CONFIG_SRC" ]] && \
    mkdir -p "$PROFILE/airootfs/opt/penaos/config" && \
    cp "$CONFIG_SRC" "$PROFILE/airootfs/opt/penaos/config/default.json"

# copia o .xinitrc (inicializador da sessao X11)
XINITRC_SRC="$OVERLAY/airootfs/opt/penaos/.xinitrc"
if [[ -f "$XINITRC_SRC" ]]; then
    cp "$XINITRC_SRC" "$PROFILE/airootfs/opt/penaos/.xinitrc"
fi

# ---- renomeia o produto pra PenaOS ------------------------------------------
say "Renomeando a ISO pra PenaOS"
PDEF="$PROFILE/profiledef.sh"
sed -i \
    -e 's/^iso_name=.*/iso_name="penaos"/' \
    -e 's/^iso_label=.*/iso_label="PENAOS_$(date +%Y%m)"/' \
    -e 's#^iso_publisher=.*#iso_publisher="Familia Miranda <github.com/familiamirandalabs>"#' \
    -e 's/^iso_application=.*/iso_application="PenaOS Live"/' \
    "$PDEF"

# ---- arquitetura do profile (x86_64 padrao; i686 muda arch e pacman) --------
if [[ "$ARCH" == "i686" ]]; then
    say "Ajustando profiledef e pacman.conf para i686 (Arch Linux 32)"
    sed -i 's/^arch=.*/arch="i686"/' "$PDEF" || true
    # pacman.conf do profile precisa saber que a arquitetura e i686
    if [[ -f "$PCONF" ]]; then
        sed -i 's/^Architecture *=.*/Architecture = i686/' "$PCONF" || \
            printf '\nArchitecture = i686\n' >> "$PCONF"
    fi
fi

# ---- boot so em modo BIOS (que e o do VirtualBox) ---------------------------
# A baseline traz tambem boot UEFI (uefi.grub), que adiciona uma particao FAT
# e modulos do grub = mais MB. Como o VirtualBox usa BIOS, tiramos o UEFI.
say "Deixando so o boot BIOS (VirtualBox) — tira peso do UEFI/grub"
sed -i "/^bootmodes=(/,/)/c\\bootmodes=('bios.syslinux')" "$PDEF"

# ---- garante que /root/.bash_profile tem permissao certa ---------------------
# (o profiledef usa um array file_permissions; adicionamos os nossos)
if ! grep -q '/root/.bash_profile' "$PDEF"; then
    sed -i "/^file_permissions=(/a\  [\"/root/.bash_profile\"]=\"0:0:644\"" "$PDEF" || true
fi
# xinitrc precisa ser executavel
if ! grep -q 'penaos/.xinitrc' "$PDEF"; then
    sed -i "/^file_permissions=(/a\  [\"/opt/penaos/.xinitrc\"]=\"0:0:755\"" "$PDEF" || true
fi

# ---- constroi! --------------------------------------------------------------
say "Construindo a ISO (isso demora alguns minutos e baixa pacotes)"
mkarchiso -v -w "$WORK/tmp" -o "$OUT" "$PROFILE"

# ---- ajeita o dono do arquivo (saiu como root, devolve pro usuario) ---------
if [[ -n "${SUDO_USER:-}" ]]; then
    chown -R "$SUDO_USER":"$SUDO_USER" "$OUT" || true
fi

say "PRONTO! ISO gerada em:"
ls -lh "$OUT"/*.iso 2>/dev/null || err "a ISO nao foi criada — veja o log acima"

cat <<'FIM'

  Proximo passo: criar a VM no VirtualBox
  ---------------------------------------
  1. Abra o VirtualBox -> Novo
  2. Tipo: Linux | Versao: Arch Linux (64-bit)
  3. Memoria: 1024 MB ja sobra (e leve!). Pode por ate 512 MB.
  4. Nao precisa de disco rigido (e "live", roda da ISO).
  5. Em Armazenamento, no drive optico, escolha a penaos-*.iso
  6. Ligar. Ele boota sozinho na area de trabalho do PenaOS.

  Dica: no console da VM o teclado funciona 100% (Tab, setas, F2).
  O mouse no console de texto precisa do 'gpm' (adicionamos depois).
FIM
