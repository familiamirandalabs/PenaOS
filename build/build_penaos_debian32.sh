#!/usr/bin/env bash
# ============================================================================
#  build_penaos_debian32.sh  —  atalho: monta a ISO do PenaOS em 32-bit (i386)
# ----------------------------------------------------------------------------
#  Mesma coisa do build_penaos_debian.sh, mas ja com PENA_ARCH=i386 — pro
#  "moco com computador travado 32-bit". Roda o build 64-bit com:
#       sudo ./build_penaos_debian.sh
#  e o 32-bit com este aqui:
#       sudo ./build_penaos_debian32.sh
#
#  As duas ISOs ficam LADO A LADO (nomes diferentes, nao se sobrescrevem):
#       build/debian/work/penaos-debian-amd64.iso   <- 64-bit
#       build/debian/work/penaos-debian-i386.iso    <- 32-bit  (esta)
#
#  No VirtualBox, crie DUAS VMs: na de 32-bit escolha a ISO i386. Detalhe: a
#  VM 32-bit funciona ate numa maquina host 64-bit — bom pra testar antes de
#  gravar o pendrive pro PC antigo de verdade.
#
#  O kernel troca sozinho pro 'linux-image-686-pae' (otimizado p/ PC antigo).
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "  -(*)-  PenaOS: montando a ISO de 32-bit (i386)..."
echo "         (saida final: build/debian/work/penaos-debian-i386.iso)"
echo

# repassa TODOS os argumentos e variaveis, so forcando a arquitetura i386.
PENA_ARCH=i386 exec "$SCRIPT_DIR/build_penaos_debian.sh" "$@"
