#!/bin/bash
if [ -z "${1}" ]; then
    echo "set a device name as \$1, exiting."
    exit
fi

set -euo pipefail

DEVICE_NAME="${1}"

if [ ! -d "/repo/work/templ_out/${DEVICE_NAME}" ]; then
    echo "run template.py outside of the docker container first."
    exit
fi

export MAKEFLAGS="-j`nproc` V=s"
export FORCE_UNSAFE_CONFIGURE=1

cd work/

git clone \
    --depth=1 \
    --recursive \
    --shallow-submodules \
    git://git.openwrt.org/openwrt/openwrt.git \
    -b openwrt-23.05

cd openwrt/

./scripts/feeds update -a

if [ "$(find /repo/files/patches/base -name \*.patch | wc -l)" -gt 0 ]; then
    for patch in /repo/files/patches/base/*.patch; do
        patch -p1 < "${patch}"
    done
fi

if [ -d "/repo/files/patches/${DEVICE_NAME}" ]; then
    if [ "$(find /repo/files/patches/${DEVICE_NAME} -name \*.patch | wc -l)" -gt 0 ]; then
        for patch in /repo/files/patches/base/*.patch; do
            patch -p1 < "${patch}"
        done
    fi
fi

./scripts/feeds install -a

cp -rfv /repo/files/Kconfig/${DEVICE_NAME} ./.config

mkdir -pv files/

cp -rfv /repo/work/templ_out/${DEVICE_NAME}/etc/ files/

time make defconfig download clean world

mkdir -pv /repo/out
mv -v \
    bin/targets/ramips/mt7621/*squashfs*.bin \
    bin/targets/ramips/mt7621/*toolchain*gcc*.tar.xz \
    /repo/out

cd /repo
rm -rf work/
