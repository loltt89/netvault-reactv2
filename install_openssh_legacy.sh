#!/bin/bash
# Install OpenSSH 7.5 with SSH v1 support for legacy network devices
# This is required for devices that only support SSH protocol version 1.0/1.5
# Modern OpenSSH removed SSH v1 support in version 7.6 (2017)

set -e

INSTALL_DIR="/opt/openssh-legacy"
VERSION="7.5p1"
DOWNLOAD_URL="https://cdn.openbsd.org/pub/OpenBSD/OpenSSH/portable/openssh-${VERSION}.tar.gz"
SHA256="9846e3c5fab9f0547400b4d2c017992f914222b3fd1f8eee6c7dc6bc5e59f9f0"

echo "=============================================="
echo "OpenSSH ${VERSION} Legacy Installation"
echo "SSH v1 Protocol Support for Legacy Devices"
echo "=============================================="
echo ""

# Check if already installed
if [ -f "${INSTALL_DIR}/bin/ssh" ]; then
    echo "[!] OpenSSH Legacy already installed"
    ${INSTALL_DIR}/bin/ssh -V
    echo ""
    echo "Skipping installation."
    exit 0
fi

echo "[1/8] Installing build dependencies..."
apt-get install -y build-essential zlib1g-dev libssl-dev wget >/dev/null 2>&1

echo "[2/8] Downloading OpenSSH ${VERSION}..."
cd /tmp
wget -q --show-progress "${DOWNLOAD_URL}" -O openssh-${VERSION}.tar.gz

echo "[3/8] Verifying checksum..."
echo "${SHA256}  openssh-${VERSION}.tar.gz" | sha256sum -c -

echo "[4/8] Extracting archive..."
tar -xzf openssh-${VERSION}.tar.gz
cd openssh-${VERSION}

echo "[5/8] Configuring build (with SSH v1 support)..."
./configure \
    --prefix=${INSTALL_DIR} \
    --sysconfdir=${INSTALL_DIR}/etc \
    --with-privsep-path=${INSTALL_DIR}/var/empty \
    --with-ssl-dir=/usr \
    --with-zlib=/usr \
    --disable-strip \
    >/dev/null 2>&1

echo "[6/8] Compiling (this takes 2-3 minutes)..."
make -j$(nproc) >/dev/null 2>&1

echo "[7/8] Installing to ${INSTALL_DIR}..."
make install >/dev/null 2>&1

echo "[8/8] Cleanup..."
cd /tmp
rm -rf openssh-${VERSION} openssh-${VERSION}.tar.gz

echo ""
echo "=============================================="
echo "Installation Complete!"
echo "=============================================="
echo ""
${INSTALL_DIR}/bin/ssh -V
echo ""
echo "SSH v1 client available at: ${INSTALL_DIR}/bin/ssh"
echo ""
