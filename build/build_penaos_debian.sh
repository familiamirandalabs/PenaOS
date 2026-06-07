#!/usr/bin/env bash
# ============================================================================
#  build_penaos_debian.sh  —  monta a ISO live do PenaOS sobre DEBIAN
# ----------------------------------------------------------------------------
#  POR QUE DEBIAN: super suportado, estavel, e multi-arquitetura OFICIAL
#  (amd64/i386/armhf/arm64) num ecossistema so — sem precisar de archlinux32
#  nem Arch Linux ARM (projetos terceiros). Perfeito pro objetivo do PenaOS.
#
#  POR QUE *NAO* O LIVE-BUILD: o live-build (comando 'lb') e a ferramenta
#  oficial do Debian pra ISO live, MAS ele nao esta empacotado pro Arch (nem no
#  repo oficial, nem no AUR). Como a maquina de build aqui e Arch, montamos a
#  ISO "na mao" com ferramentas que o Arch TEM:
#     debootstrap   -> baixa um Debian minimo (o rootfs)
#     chroot + apt  -> instala os pacotes DENTRO desse rootfs
#     mksquashfs    -> comprime o rootfs nun unico arquivo (filesystem.squashfs)
#     grub-mkrescue -> gera a ISO bootavel (BIOS + UEFI), hibrida (pendrive tb)
#  O 'apt' so roda DENTRO do chroot Debian, nunca no host Arch.
#
#  REAPROVEITA TUDO: o mesmo overlay do desktop (Openbox, .xinitrc, painel
#  pena_shell.py, navegador pena_browser.py, zram, sysctl).
#
#  COMO USAR (no Arch):
#    # 1) ferramentas (uma vez):
#    sudo pacman -S debootstrap debian-archive-keyring squashfs-tools \
#                   libisoburn grub mtools
#    # 2) rodar como root:
#    sudo ~/Documents/penaos/build/build_penaos_debian.sh
#    # multi-arch:  PENA_ARCH=i386 sudo ./build_penaos_debian.sh
#    # 3) a ISO sai em:  build/debian/work/penaos-debian-<arch>.iso
#
#  AVISO HONESTO: montar Debian live a partir do Arch funciona, mas tem varios
#  pontos que so da pra validar rodando (debootstrap, initramfs do live-boot,
#  grub-mkrescue). Se travar, o erro aparece na tela — me manda que eu destravo.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_DIR="$(dirname "$SCRIPT_DIR")"
SHARED_OVERLAY="$SCRIPT_DIR/overlay/airootfs"      # desktop compartilhado c/ Arch
DEB_DIR="$SCRIPT_DIR/debian"                        # config especifica Debian
PKG_LIST="$DEB_DIR/packages.list.chroot"
SHELL_SRC="$PROJ_DIR/shell/pena_shell.py"
BROWSER_SRC="$PROJ_DIR/shell/pena_browser.py"
RUNEXE_SRC="$PROJ_DIR/shell/pena_run_exe.py"

# distribuicao Debian estavel atual
DIST="${PENA_DIST:-bookworm}"
ARCH="${PENA_ARCH:-amd64}"
MIRROR="${PENA_MIRROR:-http://deb.debian.org/debian/}"

WORK="$DEB_DIR/work"
ROOTFS="$WORK/rootfs"
ISODIR="$WORK/iso"
OUT="$WORK/penaos-debian-$ARCH.iso"

# cache (sobrevive entre builds; NAO e apagado com o $WORK) — evita rebaixar
# 1 GB toda vez. debs-* = .debs do debootstrap; apt-* = .debs do apt no chroot.
DEB_CACHE="$DEB_DIR/cache"
BOOT_CACHE="$DEB_CACHE/debs-$DIST-$ARCH"
APT_CACHE="$DEB_CACHE/apt-$DIST-$ARCH"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
err()  { printf '\n\033[1;31mERRO: %s\033[0m\n' "$*" >&2; exit 1; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*" >&2; }

# ---- checagens --------------------------------------------------------------
[[ $EUID -eq 0 ]] || err "rode como root:  sudo $0"

need() { command -v "$1" >/dev/null 2>&1 || err "falta '$1'. Instale no Arch:
  sudo pacman -S debootstrap debian-archive-keyring squashfs-tools libisoburn grub mtools"; }
need debootstrap
need mksquashfs
need xorriso
need grub-mkrescue

# keyring do Debian (senao o debootstrap recusa as assinaturas)
KEYRING="/usr/share/keyrings/debian-archive-keyring.gpg"
[[ -f "$KEYRING" ]] || err "falta a chave do Debian: $KEYRING
  Arch:  sudo pacman -S debian-archive-keyring"

[[ -f "$PKG_LIST" ]]    || err "lista de pacotes nao encontrada: $PKG_LIST"
[[ -f "$SHELL_SRC" ]]   || err "nao achei o shell: $SHELL_SRC"
[[ -d "$SHARED_OVERLAY" ]] || err "overlay compartilhado ausente: $SHARED_OVERLAY"

# ---- arquitetura: kernel certo por arch -------------------------------------
case "$ARCH" in
  amd64) KPKG="linux-image-amd64";    say "Arquitetura: amd64 (ISO BIOS+UEFI)";;
  i386)  KPKG="linux-image-686-pae";  say "Arquitetura: i386 (Debian 32-bit oficial)";;
  armhf|arm64)
    err "ARM ($ARCH) nao gera ISO BIOS/UEFI x86. Precisa de imagem de disco com
  U-Boot/UEFI da placa — fluxo separado (a fazer). amd64/i386 funcionam aqui.";;
  *) err "arquitetura desconhecida: '$ARCH' (use amd64, i386)";;
esac

# ---- limpeza + trap pra desmontar sempre ------------------------------------
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

# ---- 1) debootstrap: baixa um Debian minimo (com cache) ---------------------
#  IMPORTANTE: uma extracao SO, limpa, no $ROOTFS (que acabou de ser apagado).
#  Usamos --cache-dir pra GUARDAR os .debs baixados e nao rebaixar na proxima.
#  (NAO usar make-tarball+unpack-tarball na mesma pasta: aquilo extrai DUAS vezes
#   por cima, deixa o dpkg/systemd meio-configurado e o init morre no boot —
#   foi o que causou o 'kernel panic: Attempted to kill init'.)
mkdir -p "$BOOT_CACHE"
say "debootstrap: montando Debian $DIST/$ARCH (.debs vem do cache se ja baixados)"
debootstrap --arch="$ARCH" --variant=minbase --keyring="$KEYRING" \
    --cache-dir="$BOOT_CACHE" \
    "$DIST" "$ROOTFS" "$MIRROR"

# ---- 2) prepara o chroot ----------------------------------------------------
say "Preparando o chroot (apt sources, montagens, rede)"
cat > "$ROOTFS/etc/apt/sources.list" <<EOF
deb $MIRROR $DIST main contrib non-free-firmware
deb $MIRROR $DIST-updates main contrib non-free-firmware
deb http://security.debian.org/debian-security $DIST-security main contrib non-free-firmware
EOF
cp /etc/resolv.conf "$ROOTFS/etc/resolv.conf"
echo "penaos" > "$ROOTFS/etc/hostname"

mount -t proc  proc   "$ROOTFS/proc"
mount -t sysfs sys    "$ROOTFS/sys"
mount --bind   /dev   "$ROOTFS/dev"
mount --bind   /dev/pts "$ROOTFS/dev/pts"

# cache do apt: bind-mount de um diretorio persistente -> os .debs baixados
# (kernel, webkit, etc.) ficam guardados e nao baixam de novo no proximo build.
# Como desmontamos antes do squashfs, esses .debs NAO entram na ISO.
mkdir -p "$APT_CACHE/partial"
mount --bind "$APT_CACHE" "$ROOTFS/var/cache/apt/archives"

# nao deixa daemons subirem durante a instalacao no chroot
cat > "$ROOTFS/usr/sbin/policy-rc.d" <<'EOF'
#!/bin/sh
exit 101
EOF
chmod +x "$ROOTFS/usr/sbin/policy-rc.d"

# ---- 3) instala pacotes DENTRO do chroot (via apt) --------------------------
#  le a lista (tira comentarios e linhas vazias) e junta numa linha so.
PKGS="$(grep -vE '^\s*#|^\s*$' "$PKG_LIST" | tr '\n' ' ')"
say "Instalando pacotes no chroot (kernel + $(echo "$PKGS" | wc -w) da lista)"
chroot "$ROOTFS" /usr/bin/env -i \
    HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin \
    DEBIAN_FRONTEND=noninteractive LANG=C \
    bash -e <<CHROOT
apt-get update
# kernel + base do live (live-boot monta a squashfs; initramfs-tools faz o initrd)
#  IMPORTANTE: instalamos so o 'live-boot' (que monta a squashfs no boot).
#  NAO instalamos 'live-config': no Debian-live ele cria um usuario 'user' e
#  configura um autologin proprio que BRIGA com o nosso autologin de root no
#  tty1 — resultado era tela preta (ninguem logava como root pra subir o X).
#  Aqui o autologin vem do nosso drop-in do overlay e o desktop sobe pelo
#  .bash_profile do root. Mais simples e previsivel.
apt-get install -y --no-install-recommends \
    $KPKG live-boot initramfs-tools \
    dbus xserver-xorg-legacy \
    systemd-resolved sudo iproute2 ca-certificates \
    locales keyboard-configuration console-setup
# os pacotes do PenaOS (X, openbox, python, webkit, gstreamer, zram, fontes...)
apt-get install -y --no-install-recommends $PKGS
# locale pt_BR
sed -i 's/^# *pt_BR.UTF-8/pt_BR.UTF-8/' /etc/locale.gen || true
locale-gen || true
# root sem senha (live; o autologin do tty1 sobe a area de trabalho)
passwd -d root || true
# NAO roda 'apt-get clean' aqui: queremos manter os .debs no cache (bind-mount).

# SANIDADE: se o systemd/init ficou meio-configurado, a ISO daria 'kernel panic:
# Attempted to kill init'. Melhor o BUILD falhar aqui (com erro claro) do que
# gerar uma ISO quebrada. /sbin/init TEM que existir e o dpkg NAO pode ter
# pacotes pela metade.
if ! dpkg-query -W -f='\${Status}' systemd-sysv 2>/dev/null | grep -q 'install ok installed'; then
    echo "FATAL: systemd-sysv nao ficou instalado direito (init faltando)"; exit 2
fi
test -e /sbin/init || { echo "FATAL: /sbin/init nao existe"; exit 2; }
if dpkg --audit 2>/dev/null | grep -q .; then
    echo "FATAL: ha pacotes meio-configurados (dpkg --audit):"; dpkg --audit; exit 2
fi
echo "OK: systemd-sysv instalado, /sbin/init presente, dpkg integro."
CHROOT

# ---- 4) overlay do desktop dentro do rootfs ---------------------------------
say "Aplicando o desktop do PenaOS (overlay + painel + navegador + abridor .exe)"
rsync -a --exclude 'etc/pacman.d' "$SHARED_OVERLAY/." "$ROOTFS/"
mkdir -p "$ROOTFS/opt/penaos"
cp "$SHELL_SRC"   "$ROOTFS/opt/penaos/pena_shell.py"
[[ -f "$BROWSER_SRC" ]] && cp "$BROWSER_SRC" "$ROOTFS/opt/penaos/pena_browser.py"
[[ -f "$RUNEXE_SRC" ]]  && cp "$RUNEXE_SRC"  "$ROOTFS/opt/penaos/pena_run_exe.py"

# os-release: marca como "parecido com Debian"
[[ -f "$ROOTFS/etc/os-release" ]] && \
    sed -i 's/^ID_LIKE=.*/ID_LIKE=debian/' "$ROOTFS/etc/os-release" || true

# ---- 5) habilita servicos do PenaOS (zram + autologin) ----------------------
say "Habilitando autologin do tty1 e o swap comprimido (zram)"
chroot "$ROOTFS" /usr/bin/env -i \
    HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin LANG=C bash -e <<'CHROOT'
# o drop-in de autologin do getty@tty1 ja veio do overlay (includes do desktop)
systemctl enable systemd-zram-setup@zram0.service 2>/dev/null || true
systemctl set-default multi-user.target 2>/dev/null || true
# REDE (substitui o que o live-config fazia): networkd pede IP por DHCP e
# resolved cuida do DNS. Sem isto o sistema sobe sem internet.
systemctl enable systemd-networkd.service 2>/dev/null || true
systemctl enable systemd-resolved.service 2>/dev/null || true
# nao trava o boot esperando a rede ficar pronta
systemctl mask systemd-networkd-wait-online.service 2>/dev/null || true

# regenera o initramfs JA com os ganchos do live-boot. SEM '|| true': se isto
# falhar, o initrd nao vira "live", o boot=live e ignorado, NENHUMA raiz e
# montada e o init morre no boot ('kernel panic: Attempted to kill init').
# Melhor falhar AQUI, com erro claro, do que gerar uma ISO que da panic.
update-initramfs -u

# CONFERE de verdade que o initrd ficou "live" (tem os scripts do live-boot).
# Esta e a checagem que faltava: e o que separa uma ISO que BOOTA de uma que
# da kernel panic. Se nao tiver, paramos o build na hora.
INITRD_FILE="$(ls -1 /boot/initrd.img-* | sort -V | tail -1)"
if ! lsinitramfs "$INITRD_FILE" 2>/dev/null | grep -q 'scripts/live'; then
    echo "FATAL: o initramfs NAO tem os scripts do live-boot."
    echo "       Arquivo: $INITRD_FILE"
    echo "       Sem isso o 'boot=live' e ignorado e o init morre no boot."
    echo "       (live-boot instalado? hooks em /usr/share/initramfs-tools/scripts/live?)"
    exit 3
fi
echo "OK: initramfs e LIVE (tem scripts/live) -> $INITRD_FILE"
CHROOT

# ---- 6) limpa e desmonta o chroot -------------------------------------------
rm -f "$ROOTFS/usr/sbin/policy-rc.d"
# o resolv.conf que copiamos pro apt sai; no lugar, aponta pro systemd-resolved
# (que vai preencher o DNS em runtime via DHCP).
rm -f "$ROOTFS/etc/resolv.conf"
ln -sf /run/systemd/resolve/stub-resolv.conf "$ROOTFS/etc/resolv.conf"
cleanup

# ---- 7) kernel + initrd pro lado da ISO -------------------------------------
say "Copiando kernel e initrd pra arvore da ISO"
VMLINUZ="$(ls -1 "$ROOTFS"/boot/vmlinuz-* 2>/dev/null | sort -V | tail -1 || true)"
INITRD="$(ls -1 "$ROOTFS"/boot/initrd.img-* 2>/dev/null | sort -V | tail -1 || true)"
[[ -n "$VMLINUZ" && -n "$INITRD" ]] || err "kernel/initrd nao encontrados em $ROOTFS/boot"
cp "$VMLINUZ" "$ISODIR/live/vmlinuz"
cp "$INITRD"  "$ISODIR/live/initrd"

# ---- 8) squashfs do rootfs (sem o /boot, que ja foi pra ISO) ----------------
say "Comprimindo o rootfs (mksquashfs — demora e usa CPU)"
mksquashfs "$ROOTFS" "$ISODIR/live/filesystem.squashfs" \
    -comp zstd -Xcompression-level 19 -noappend \
    -e boot -wildcards -e 'proc/*' -e 'sys/*' -e 'dev/pts/*'

# ---- 9) configura o GRUB da ISO ---------------------------------------------
say "Escrevendo o menu do GRUB"
# sem 'quiet splash' de proposito: mostra as mensagens do boot (ajuda a achar
# onde travou). Da pra por de volta depois que estiver redondo.
BOOTAPP="boot=live components locales=pt_BR.UTF-8 keyboard-layouts=br"
cat > "$ISODIR/boot/grub/grub.cfg" <<EOF
set default=0
set timeout=5
menuentry "PenaOS Live ($ARCH)" {
    linux  /live/vmlinuz $BOOTAPP
    initrd /live/initrd
}
menuentry "PenaOS Live (modo seguro: sem aceleracao)" {
    linux  /live/vmlinuz $BOOTAPP nomodeset
    initrd /live/initrd
}
menuentry "PenaOS (depuracao: cai num shell, sem systemd)" {
    # init=/bin/sh: o live-boot ainda monta a squashfs, mas em vez do systemd
    # roda um shell direto. Se ESTA opcao abrir um '#' e a normal der panic,
    # entao o live-boot esta OK e o problema e no systemd. Se ATE esta der
    # panic, o problema e antes (initrd nao achou/montou a squashfs).
    linux  /live/vmlinuz $BOOTAPP init=/bin/sh
    initrd /live/initrd
}
EOF

# ---- 10) monta a ISO hibrida (BIOS + UEFI) ----------------------------------
say "Gerando a ISO com grub-mkrescue"
grub-mkrescue \
    --volid PENAOS \
    -o "$OUT" "$ISODIR" \
    -- -volid PENAOS 2>/dev/null \
  || grub-mkrescue --volid PENAOS -o "$OUT" "$ISODIR"

[[ -f "$OUT" ]] || err "a ISO nao foi criada — veja o log acima"

# devolve o arquivo pro usuario (saiu como root)
if [[ -n "${SUDO_USER:-}" ]]; then
    chown "$SUDO_USER":"$SUDO_USER" "$OUT" 2>/dev/null || true
fi

say "PRONTO! ISO Debian do PenaOS:"
ls -lh "$OUT"
echo
echo "  Testar:  qemu-system-x86_64 -m 768 -cdrom \"$OUT\""
echo "  (ou crie uma VM no VirtualBox apontando pra essa ISO)"
