#!/usr/bin/env bash
# ============================================================================
#  build_penaos_debian.sh  —  monta a ISO live do PenaOS sobre DEBIAN
# ----------------------------------------------------------------------------
#  POR QUE DEBIAN: super suportado, estavel, e multi-arquitetura OFICIAL
#  (amd64/i386/armhf/arm64) num ecossistema so — sem precisar de archlinux32
#  nem Arch Linux ARM (projetos terceiros). Perfeito pro objetivo do PenaOS.
#
#  FERRAMENTA: live-build (a oficial do Debian pra ISO live). Ela cuida de
#  debootstrap + squashfs + initramfs (live-boot) + bootloader sozinha.
#
#  REAPROVEITA TUDO: o mesmo overlay do desktop (Openbox, .xinitrc, painel
#  pena_shell.py, navegador pena_browser.py, zram, sysctl) — eles sao Python
#  e arquivos de config, nao dependem da base. So a "como montar a imagem"
#  muda de archiso pra live-build.
#
#  COMO USAR:
#    # 1) instalar a ferramenta (uma vez):
#    sudo apt install live-build        # (ou: sudo pacman -S debian-live-build no Arch)
#    # 2) rodar como root:
#    sudo ~/Documents/penaos/build/build_penaos_debian.sh
#    # multi-arch:  PENA_ARCH=i386 sudo ./build_penaos_debian.sh
#    # 3) a ISO sai em:  build/debian/live-image-*.hybrid.iso
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_DIR="$(dirname "$SCRIPT_DIR")"
SHARED_OVERLAY="$SCRIPT_DIR/overlay/airootfs"     # desktop compartilhado c/ Arch
DEB_DIR="$SCRIPT_DIR/debian"                       # config especifica Debian
PKG_LIST="$DEB_DIR/packages.list.chroot"
SHELL_SRC="$PROJ_DIR/shell/pena_shell.py"
BROWSER_SRC="$PROJ_DIR/shell/pena_browser.py"
RUNEXE_SRC="$PROJ_DIR/shell/pena_run_exe.py"
LB="$DEB_DIR/lb"                                    # diretorio de trabalho do live-build

# distribuicao Debian estavel atual
DIST="${PENA_DIST:-bookworm}"
ARCH="${PENA_ARCH:-amd64}"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
err() { printf '\n\033[1;31mERRO: %s\033[0m\n' "$*" >&2; exit 1; }

# ---- checagens --------------------------------------------------------------
[[ $EUID -eq 0 ]] || err "rode como root:  sudo $0"
command -v lb >/dev/null 2>&1 || err "falta o live-build (comando 'lb').
  Debian/Ubuntu:  sudo apt install live-build
  Arch:           sudo pacman -S debian-live-build  (ou via AUR: live-build)"
[[ -f "$PKG_LIST" ]]    || err "lista de pacotes nao encontrada: $PKG_LIST"
[[ -f "$SHELL_SRC" ]]   || err "nao achei o shell: $SHELL_SRC"
[[ -d "$SHARED_OVERLAY" ]] || err "overlay compartilhado ausente: $SHARED_OVERLAY"

# ---- arquitetura: amd64/i386 = ISO BIOS; ARM = imagem diferente -------------
BINARY_IMAGES="iso-hybrid"
case "$ARCH" in
  amd64)
    say "Arquitetura: amd64 (Debian) — ISO live BIOS, caminho suportado"
    ;;
  i386)
    say "Arquitetura: i386 (Debian 32-bit OFICIAL) — ISO live BIOS"
    ;;
  armhf|arm64)
    err "ARM ($ARCH) nao gera ISO BIOS. live-build pode montar uma imagem de
  disco (--binary-images hdd) com U-Boot/UEFI especifico da placa, mas isso
  e um fluxo separado (a fazer). amd64/i386 funcionam por aqui."
    ;;
  *)
    err "arquitetura desconhecida: '$ARCH' (use amd64, i386, armhf, arm64)"
    ;;
esac

# ---- area de trabalho limpa -------------------------------------------------
say "Limpando configuracao live-build anterior"
rm -rf "$LB"
mkdir -p "$LB"
cd "$LB"

# ---- configura o live-build -------------------------------------------------
#  --bootappend-live: 'live-config' autoconfigura; pedimos teclado BR e
#  desligamos a criacao de usuario (nossa sessao sobe como root no tty1).
say "Configurando o live-build (Debian $DIST / $ARCH)"
lb config \
    --distribution "$DIST" \
    --architectures "$ARCH" \
    --binary-images "$BINARY_IMAGES" \
    --debian-installer none \
    --apt-indices false \
    --apt-recommends false \
    --memtest none \
    --firmware-binary false \
    --firmware-chroot false \
    --bootappend-live "boot=live components quiet splash keyboard-layouts=br locales=pt_BR.UTF-8" \
    --iso-application "PenaOS Live" \
    --iso-publisher "Familia Miranda; https://github.com/familiamirandalabs" \
    --iso-volume "PENAOS"

# ---- lista de pacotes -------------------------------------------------------
mkdir -p config/package-lists
cp "$PKG_LIST" config/package-lists/penaos.list.chroot

# ---- desktop: joga o overlay compartilhado dentro da imagem -----------------
#  includes.chroot = arquivos que vao pro / da imagem (igual airootfs do Arch).
say "Aplicando o desktop do PenaOS (overlay compartilhado + painel + navegador)"
mkdir -p config/includes.chroot
#  copia tudo do overlay MENOS o que e especifico do Arch (pacman)
rsync -a --exclude 'etc/pacman.d' "$SHARED_OVERLAY/." config/includes.chroot/
#  injeta painel e navegador
mkdir -p config/includes.chroot/opt/penaos
cp "$SHELL_SRC"   config/includes.chroot/opt/penaos/pena_shell.py
[[ -f "$BROWSER_SRC" ]] && cp "$BROWSER_SRC" config/includes.chroot/opt/penaos/pena_browser.py
[[ -f "$RUNEXE_SRC" ]]  && cp "$RUNEXE_SRC"  config/includes.chroot/opt/penaos/pena_run_exe.py

# ---- ajusta o os-release pra dizer "parecido com Debian" --------------------
OSREL="config/includes.chroot/etc/os-release"
if [[ -f "$OSREL" ]]; then
    sed -i 's/^ID_LIKE=.*/ID_LIKE=debian/' "$OSREL" || true
fi

# ---- hook: liga autologin e zram dentro do chroot ---------------------------
#  (o overlay ja traz o drop-in de autologin do getty@tty1 e o
#   zram-generator.conf; aqui so garantimos que os servicos certos rodem.)
mkdir -p config/hooks/live
cat > config/hooks/live/0100-penaos.hook.chroot <<'HOOK'
#!/bin/sh
set -e
# habilita o swap comprimido (systemd-zram-generator le /etc/systemd/zram-generator.conf)
systemctl enable systemd-zram-setup@zram0.service 2>/dev/null || true
# o autologin do root no tty1 vem do drop-in do overlay (includes.chroot).
HOOK
chmod +x config/hooks/live/0100-penaos.hook.chroot

# ---- constroi! --------------------------------------------------------------
say "Construindo a ISO Debian (baixa pacotes; demora alguns minutos)"
lb build

# ---- resultado --------------------------------------------------------------
ISO=$(ls -1 "$LB"/live-image-*.iso 2>/dev/null | head -1 || true)
[[ -n "$ISO" ]] || err "a ISO nao foi criada — veja o log do live-build acima"

# devolve o arquivo pro usuario (saiu como root)
if [[ -n "${SUDO_USER:-}" ]]; then
    chown "$SUDO_USER":"$SUDO_USER" "$ISO" || true
fi

say "PRONTO! ISO Debian do PenaOS:"
ls -lh "$ISO"
