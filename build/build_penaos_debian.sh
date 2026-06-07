#!/usr/bin/env bash
# ============================================================================
#  build_penaos_debian.sh  —  monta a ISO live do PenaOS sobre DEBIAN
# ----------------------------------------------------------------------------
#  ESCRITO DO ZERO, espelhando o build_penaos_iso.sh do Arch: uma sequencia
#  direta, UMA opcao de boot, e checagens que FAZEM o build PARAR com erro
#  claro em vez de cuspir uma ISO que da kernel panic ou cai sem area grafica.
#
#  POR QUE NA MAO: no Arch o mkarchiso faz tudo sozinho. No Debian a ferramenta
#  equivalente (live-build / 'lb') nao existe no Arch nem no AUR. Entao montamos
#  a ISO com o que o Arch TEM, em 4 ferramentas:
#     debootstrap   -> baixa um Debian minimo  (o "rootfs")
#     chroot + apt  -> instala os pacotes DENTRO desse rootfs
#     mksquashfs    -> comprime o rootfs num arquivo (filesystem.squashfs)
#     grub-mkrescue -> gera a ISO bootavel hibrida (BIOS+UEFI, serve em pendrive)
#  O 'apt' SO roda dentro do chroot Debian — nunca toca no Arch do host.
#
#  COMO USAR (rodando num Arch):
#    sudo pacman -S debootstrap debian-archive-keyring squashfs-tools \
#                   libisoburn grub mtools
#    sudo ~/Documents/penaos/build/build_penaos_debian.sh        # 64-bit
#    sudo ~/Documents/penaos/build/build_penaos_debian32.sh      # 32-bit
#    # a ISO sai em:  build/debian/work/penaos-debian-<arch>.iso
# ============================================================================
set -euo pipefail

# ---- caminhos (funciona mesmo rodando com sudo) -----------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_DIR="$(dirname "$SCRIPT_DIR")"
SHARED_OVERLAY="$SCRIPT_DIR/overlay/airootfs"   # area de trabalho (compart. c/ Arch)
DEB_DIR="$SCRIPT_DIR/debian"
PKG_LIST="$DEB_DIR/packages.list.chroot"
SHELL_SRC="$PROJ_DIR/shell/pena_shell.py"
BROWSER_SRC="$PROJ_DIR/shell/pena_browser.py"
RUNEXE_SRC="$PROJ_DIR/shell/pena_run_exe.py"

# ---- alvo (sobrescrevivel por variavel de ambiente) -------------------------
DIST="${PENA_DIST:-bookworm}"
ARCH="${PENA_ARCH:-amd64}"
MIRROR="${PENA_MIRROR:-http://deb.debian.org/debian/}"

WORK="$DEB_DIR/work"
ROOTFS="$WORK/rootfs"
ISODIR="$WORK/iso"
OUT="$WORK/penaos-debian-$ARCH.iso"

# cache que SOBREVIVE entre builds (nao e apagado com o $WORK): evita rebaixar
# o kernel/webkit toda vez. debs-* = .debs do debootstrap; apt-* = do apt.
DEB_CACHE="$DEB_DIR/cache"
BOOT_CACHE="$DEB_CACHE/debs-$DIST-$ARCH"
APT_CACHE="$DEB_CACHE/apt-$DIST-$ARCH"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
err() { printf '\n\033[1;31mERRO: %s\033[0m\n' "$*" >&2; exit 1; }

# ---- checagens de pre-requisito ---------------------------------------------
[[ $EUID -eq 0 ]] || err "rode como root:  sudo $0"
need() { command -v "$1" >/dev/null 2>&1 || err "falta '$1'. Instale no Arch:
  sudo pacman -S debootstrap debian-archive-keyring squashfs-tools libisoburn grub mtools"; }
need debootstrap; need mksquashfs; need xorriso; need grub-mkrescue

KEYRING="/usr/share/keyrings/debian-archive-keyring.gpg"
[[ -f "$KEYRING" ]]        || err "falta a chave do Debian: $KEYRING
  Arch:  sudo pacman -S debian-archive-keyring"
[[ -f "$PKG_LIST" ]]       || err "lista de pacotes nao encontrada: $PKG_LIST"
[[ -f "$SHELL_SRC" ]]      || err "nao achei o painel: $SHELL_SRC"
[[ -d "$SHARED_OVERLAY" ]] || err "overlay compartilhado ausente: $SHARED_OVERLAY"

case "$ARCH" in
  amd64) KPKG="linux-image-amd64";   say "Arquitetura: amd64 (ISO BIOS+UEFI)";;
  i386)  KPKG="linux-image-686-pae"; say "Arquitetura: i386 (PC antigo 32-bit)";;
  *) err "arquitetura '$ARCH' nao gera ISO x86 aqui (use amd64 ou i386)";;
esac

# ---- trap: desmonta o chroot ACONTECA O QUE ACONTECER -----------------------
cleanup() {
    set +e
    for m in var/cache/apt/archives dev/pts dev proc sys run; do
        mountpoint -q "$ROOTFS/$m" && umount -lf "$ROOTFS/$m" 2>/dev/null
    done
}
trap cleanup EXIT

say "Limpando trabalho anterior"
cleanup
rm -rf "$WORK"
mkdir -p "$ROOTFS" "$ISODIR/live" "$ISODIR/boot/grub"

# ============================================================================
#  1) debootstrap: baixa um Debian minimo (UMA extracao limpa, com cache)
# ============================================================================
mkdir -p "$BOOT_CACHE"
say "debootstrap: Debian $DIST/$ARCH (reaproveita .debs do cache se houver)"
debootstrap --arch="$ARCH" --variant=minbase --keyring="$KEYRING" \
    --cache-dir="$BOOT_CACHE" "$DIST" "$ROOTFS" "$MIRROR"

# ============================================================================
#  2) prepara o chroot (apt sources, montagens, trava de daemons, initramfs)
# ============================================================================
say "Preparando o chroot (apt sources, montagens)"
cat > "$ROOTFS/etc/apt/sources.list" <<EOF
deb $MIRROR $DIST main contrib non-free-firmware
deb $MIRROR $DIST-updates main contrib non-free-firmware
deb http://security.debian.org/debian-security $DIST-security main contrib non-free-firmware
EOF
cp /etc/resolv.conf "$ROOTFS/etc/resolv.conf"
echo "penaos" > "$ROOTFS/etc/hostname"

mount -t proc  proc     "$ROOTFS/proc"
mount -t sysfs sys      "$ROOTFS/sys"
mount --bind   /dev     "$ROOTFS/dev"
mount --bind   /dev/pts "$ROOTFS/dev/pts"

# cache do apt por bind-mount: kernel/webkit ficam guardados entre builds.
# Desmontado antes do squashfs -> NAO entra na ISO.
mkdir -p "$APT_CACHE/partial"
mount --bind "$APT_CACHE" "$ROOTFS/var/cache/apt/archives"

# durante a instalacao, nenhum daemon pode subir dentro do chroot.
printf '#!/bin/sh\nexit 101\n' > "$ROOTFS/usr/sbin/policy-rc.d"
chmod +x "$ROOTFS/usr/sbin/policy-rc.d"

# o initramfs PRECISA conter os modulos da raiz live. Sem overlay/squashfs a
# raiz subiria SO-LEITURA e o systemd (PID 1) morreria -> kernel panic.
mkdir -p "$ROOTFS/etc/initramfs-tools"
{ echo overlay; echo squashfs; echo loop; echo isofs; } \
    >> "$ROOTFS/etc/initramfs-tools/modules"

# locale + teclado padrao (sem depender do live-config, que brigava c/ autologin)
echo 'LANG=pt_BR.UTF-8' > "$ROOTFS/etc/default/locale"
cat > "$ROOTFS/etc/default/keyboard" <<'EOF'
XKBMODEL="pc105"
XKBLAYOUT="br"
XKBVARIANT=""
XKBOPTIONS=""
EOF

# ============================================================================
#  3) instala os pacotes DENTRO do chroot
# ----------------------------------------------------------------------------
#  LICAO QUE CUSTOU CARO: NAO alimentar o chroot via 'bash <<HEREDOC' pela
#  STDIN. Postinsts (keyboard-configuration, console-setup) LEEM a stdin e
#  ENGOLEM o resto do heredoc -> o 'apt-get install $PKGS' (X, openbox...) nao
#  roda, a ISO sai SEM area grafica e da 'startx: command not found'. Por isso
#  escrevemos o script num ARQUIVO e rodamos com '</dev/null' (stdin fechado).
# ============================================================================
PKGS="$(grep -vE '^\s*#|^\s*$' "$PKG_LIST" | tr '\n' ' ')"
say "Instalando pacotes no chroot (kernel + live-boot + $(echo "$PKGS" | wc -w) da lista)"

cat > "$ROOTFS/root/penaos-install.sh" <<CHROOT
#!/bin/bash
set -e
apt-get update

# nucleo do sistema live: kernel + systemd-sysv (o /sbin/init) + live-boot
# (monta a squashfs no boot) + initramfs-tools (gera o initrd).
apt-get install -y --no-install-recommends \
    $KPKG systemd-sysv live-boot initramfs-tools \
    dbus xserver-xorg-legacy \
    systemd-resolved sudo iproute2 ca-certificates \
    locales keyboard-configuration console-setup

# os pacotes do PenaOS (X, openbox, python, webkit, gstreamer, zram, fontes...)
apt-get install -y --no-install-recommends $PKGS

# locale pt_BR
sed -i 's/^# *pt_BR.UTF-8/pt_BR.UTF-8/' /etc/locale.gen || true
locale-gen || true

# root sem senha (e live; o autologin do tty1 sobe a area de trabalho)
passwd -d root || true

# REDE DE SEGURANCA: aceita login com senha VAZIA (so Enter). Se o autologin
# falhar por qualquer motivo, ninguem fica trancado pra fora. O Debian as vezes
# NAO traz 'nullok' por padrao -> sem isto, login sem senha e recusado.
if [ -f /etc/pam.d/common-auth ] && ! grep -q 'pam_unix.so.*nullok' /etc/pam.d/common-auth; then
    sed -i '/pam_unix\.so/ s/\$/ nullok/' /etc/pam.d/common-auth
fi

# ---- CHECAGENS DE SANIDADE (fazem o BUILD falhar aqui, nao no boot) ----------
# 1) /sbin/init valido -> sem isso a ISO daria "kernel panic: kill init".
dpkg-query -W -f='\${Status}' systemd-sysv 2>/dev/null | grep -q 'install ok installed' \
    || { echo "FATAL: systemd-sysv nao instalado (init faltando)"; exit 2; }
test -x "\$(readlink -f /sbin/init)" \
    || { echo "FATAL: /sbin/init nao aponta pra um binario valido"; exit 2; }
# 2) nada meio-configurado.
dpkg --audit 2>/dev/null | grep -q . \
    && { echo "FATAL: pacotes meio-configurados:"; dpkg --audit; exit 2; }
# 3) o DESKTOP existe mesmo -> e o que separa "sobe a area de trabalho" de
#    "startx: command not found". Se faltar qualquer um, build PARA.
for bin in startx Xorg openbox python3 xterm; do
    command -v "\$bin" >/dev/null 2>&1 \
        || { echo "FATAL: '\$bin' nao foi instalado (area grafica faltando)"; exit 4; }
done
echo "OK: /sbin/init valido + desktop (startx/Xorg/openbox/python3/xterm) presente."
CHROOT

chmod +x "$ROOTFS/root/penaos-install.sh"
chroot "$ROOTFS" /usr/bin/env -i \
    HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin \
    DEBIAN_FRONTEND=noninteractive LANG=C \
    bash /root/penaos-install.sh </dev/null
rm -f "$ROOTFS/root/penaos-install.sh"

# ============================================================================
#  4) aplica a area de trabalho do PenaOS (overlay + painel + navegador)
# ----------------------------------------------------------------------------
#  rsync SEM -o/-g (usamos -rlptD): copia como root:root. Com -a, os uids do
#  host (miguel/1000) vazariam pra dentro do rootfs.
# ============================================================================
say "Aplicando o desktop do PenaOS (overlay + painel + navegador + abridor .exe)"
rsync -rlptD --exclude 'etc/pacman.d' "$SHARED_OVERLAY/." "$ROOTFS/"
mkdir -p "$ROOTFS/opt/penaos"
cp "$SHELL_SRC" "$ROOTFS/opt/penaos/pena_shell.py"
[[ -f "$BROWSER_SRC" ]] && cp "$BROWSER_SRC" "$ROOTFS/opt/penaos/pena_browser.py"
[[ -f "$RUNEXE_SRC" ]]  && cp "$RUNEXE_SRC"  "$ROOTFS/opt/penaos/pena_run_exe.py"
chown -R 0:0 "$ROOTFS/opt/penaos"
# o overlay traz ID_LIKE=arch; aqui e Debian.
[[ -f "$ROOTFS/etc/os-release" ]] && \
    sed -i 's/^ID_LIKE=.*/ID_LIKE=debian/' "$ROOTFS/etc/os-release" || true

# ============================================================================
#  5) habilita servicos e REGENERA o initramfs ja com o live-boot
# ============================================================================
say "Habilitando autologin, zram e rede; regenerando o initramfs LIVE"
cat > "$ROOTFS/root/penaos-services.sh" <<'CHROOT'
#!/bin/bash
set -e
systemctl set-default multi-user.target 2>/dev/null || true
systemctl enable systemd-zram-setup@zram0.service 2>/dev/null || true
systemctl enable systemd-networkd.service 2>/dev/null || true
systemctl enable systemd-resolved.service 2>/dev/null || true
systemctl mask systemd-networkd-wait-online.service 2>/dev/null || true

# regenera o initramfs JA com os ganchos do live-boot. SEM '|| true': se falhar,
# o build para (em vez de gerar ISO que da panic).
update-initramfs -u

# CONFERE que o initrd ficou "live" (tem os scripts do live-boot). E o que
# separa uma ISO que BOOTA de uma que da kernel panic em "boot=live".
INITRD_FILE="$(ls -1 /boot/initrd.img-* | sort -V | tail -1)"
lsinitramfs "$INITRD_FILE" 2>/dev/null | grep -q 'scripts/live' \
    || { echo "FATAL: initramfs sem live-boot ($INITRD_FILE); boot=live seria ignorado"; exit 3; }
echo "OK: initramfs e LIVE -> $INITRD_FILE"
CHROOT

chmod +x "$ROOTFS/root/penaos-services.sh"
chroot "$ROOTFS" /usr/bin/env -i \
    HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin LANG=C \
    bash /root/penaos-services.sh </dev/null
rm -f "$ROOTFS/root/penaos-services.sh"

# ============================================================================
#  6) limpa e desmonta o chroot
# ============================================================================
rm -f "$ROOTFS/usr/sbin/policy-rc.d"
rm -f "$ROOTFS/etc/resolv.conf"
ln -sf /run/systemd/resolve/stub-resolv.conf "$ROOTFS/etc/resolv.conf"
cleanup

# ============================================================================
#  7) copia kernel + initrd pro lado da ISO
# ============================================================================
say "Copiando kernel e initrd pra arvore da ISO"
VMLINUZ="$(ls -1 "$ROOTFS"/boot/vmlinuz-*   2>/dev/null | sort -V | tail -1 || true)"
INITRD="$(ls -1 "$ROOTFS"/boot/initrd.img-* 2>/dev/null | sort -V | tail -1 || true)"
[[ -n "$VMLINUZ" && -n "$INITRD" ]] || err "kernel/initrd nao encontrados em $ROOTFS/boot"
cp "$VMLINUZ" "$ISODIR/live/vmlinuz"
cp "$INITRD"  "$ISODIR/live/initrd"

# ============================================================================
#  8) comprime o rootfs (sem o /boot, que ja foi pra ISO)
# ============================================================================
say "Comprimindo o rootfs (mksquashfs — demora e usa CPU)"
mksquashfs "$ROOTFS" "$ISODIR/live/filesystem.squashfs" \
    -comp zstd -Xcompression-level 19 -noappend \
    -e boot -wildcards -e 'proc/*' -e 'sys/*' -e 'dev/pts/*'

# ============================================================================
#  9) configuracao do GRUB — UMA opcao so (igual ao Arch)
# ============================================================================
say "Escrevendo o grub.cfg (uma unica entrada de boot)"
BOOTAPP="boot=live"
cat > "$ISODIR/boot/grub/grub.cfg" <<EOF
set default=0
set timeout=3

menuentry "PenaOS Live ($ARCH)" {
    linux  /live/vmlinuz $BOOTAPP
    initrd /live/initrd
}
EOF

# ============================================================================
#  10) gera a ISO hibrida (BIOS+UEFI, bootavel tambem em pendrive)
# ============================================================================
say "Gerando a ISO com grub-mkrescue"
grub-mkrescue --volid PENAOS -o "$OUT" "$ISODIR"

# devolve o dono do arquivo pro usuario (saiu como root)
if [[ -n "${SUDO_USER:-}" ]]; then
    chown "$SUDO_USER":"$SUDO_USER" "$OUT" 2>/dev/null || true
fi

say "PRONTO! ISO gerada em:"
ls -lh "$OUT"

cat <<FIM

  Proximo passo: testar no VirtualBox
  -----------------------------------
  1. VirtualBox -> Novo. Tipo: Linux | Versao: Debian (${ARCH/amd64/64-bit})
  2. Memoria: 1024 MB sobra (e leve). Sem disco rigido (roda da ISO, "live").
  3. Em Armazenamento, no drive optico, escolha:
       $OUT
  4. Ligar. Ele boota direto na area de trabalho do PenaOS (sem login).
FIM
