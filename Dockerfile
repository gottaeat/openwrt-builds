FROM debian:latest as openwrt-build

RUN \
    apt update && \
    apt install -y \
        bison \
        build-essential \
        clang \
        file \
        flex \
        g++ \
        g++-multilib \
        gawk \
        gcc-multilib \
        gettext \
        git \
        libncurses-dev \
        libssl-dev \
        python3-distutils \
        rsync \
        unzip \
        wget \
        zlib1g-dev

WORKDIR /repo
