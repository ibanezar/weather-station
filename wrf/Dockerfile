# WRF 4.6.1 + WPS 4.6.0 (Ubuntu 20.04, gfortran 9, MPI dmpar, JasPer iz izvirne kode) za lastni napovedni model doline (glej docs/wrf-model.md).
#
# Gradnja traja ~30–60 min (WRF se prevaja iz izvirne kode); slika se zato gradi samo ob spremembi te datoteke
# (.github/workflows/wrf-image.yml → ghcr.io) in se potem le vleče na strežnik. Lokalno:
#   docker build -t meteorec-wrf -f wrf/Dockerfile wrf/
# Za okolje z lovilnim posrednikom (CA) glej opombo na koncu docs/wrf-model.md (--build-context ca=…).
#
# Slika vsebuje samo model in orodja WPS; podatki (geografski podatki, robni pogoji) in naši skripti pridejo z -v.
ARG BASE_IMAGE=ubuntu:20.04
FROM ${BASE_IMAGE} AS base
ARG DEBIAN_FRONTEND=noninteractive
ARG WRF_VERSION=4.6.1
ARG WPS_VERSION=4.6.0
ARG JASPER_VERSION=2.0.33

# Neobvezno: mapa s CA potrdilom (posredniki, ki prestrežejo TLS) in že prenesena koda WPS (npr. v peskovniku brez
# dostopa do github.com/…/archive). V Actions sta praznih; takrat se WPS prenese z `git clone`.
FROM scratch AS ca
FROM scratch AS wpssrc

FROM base AS build
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
      build-essential gfortran m4 csh tcsh perl file curl ca-certificates cmake git \
      mpich libmpich-dev libnetcdf-dev libnetcdff-dev libpng-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# WRF/WPS pričakujeta $NETCDF z include/ in lib/ (C + Fortran skupaj); Ubuntu ju razdeli, zato povezave.
RUN mkdir -p /opt/netcdf && ln -sfn /usr/include /opt/netcdf/include && ln -sfn /usr/lib/x86_64-linux-gnu /opt/netcdf/lib
ENV NETCDF=/opt/netcdf WRF_EM_CORE=1 WRF_NMM_CORE=0 JASPERLIB=/opt/jasper/lib JASPERINC=/opt/jasper/include

# JasPer (ungrib za GRIB2 / JPEG2000); Ubuntu ga od 20.04 naprej nima v repozitoriju, zato iz izvirne kode (GitHub)
RUN --mount=type=bind,from=ca,target=/ccr \
    [ -f /ccr/ca-bundle.crt ] && export SSL_CERT_FILE=/ccr/ca-bundle.crt CURL_CA_BUNDLE=/ccr/ca-bundle.crt; \
    cd /tmp && curl -fsSL -o jasper.tar.gz https://github.com/jasper-software/jasper/releases/download/version-${JASPER_VERSION}/jasper-${JASPER_VERSION}.tar.gz \
    && tar xzf jasper.tar.gz && cd jasper-${JASPER_VERSION} \
    && cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/jasper -DJAS_ENABLE_DOC=false -DJAS_ENABLE_PROGRAMS=false \
       -DJAS_ENABLE_SHARED=true -DCMAKE_INSTALL_LIBDIR=lib -DALLOW_IN_SOURCE_BUILD=true >/dev/null \
    && cmake --build build -j"$(nproc)" >/dev/null && cmake --install build >/dev/null && rm -rf /tmp/jasper*

# WRF: izberi GNU gfortran dmpar z osnovnim gnezdenjem (številka možnosti se med verzijami spreminja, zato se išče po besedilu)
RUN --mount=type=bind,from=ca,target=/ccr \
    [ -f /ccr/ca-bundle.crt ] && export SSL_CERT_FILE=/ccr/ca-bundle.crt CURL_CA_BUNDLE=/ccr/ca-bundle.crt; \
    mkdir -p /opt && cd /opt && curl -fsSL -o wrf.tar.gz https://github.com/wrf-model/WRF/releases/download/v${WRF_VERSION}/v${WRF_VERSION}.tar.gz \
    && D=$(tar tzf wrf.tar.gz | head -1 | cut -d/ -f1) && tar xzf wrf.tar.gz && mv "$D" WRF && rm wrf.tar.gz && cd WRF \
    && N=$(echo 0 | ./configure 2>&1 | grep -E 'GNU \(gfortran/gcc\)' | grep -E '\(dmpar\)' | head -1 | sed -E 's/.*[[:space:]]([0-9]+)\.[[:space:]]+\(dmpar\).*/\1/') \
    && echo "WRF configure option: $N" && [ -n "$N" ] \
    && printf '%s\n1\n' "$N" | ./configure >/dev/null 2>&1 \
    && ./compile -j "$(nproc)" em_real > /tmp/wrf-compile.log 2>&1; \
    tail -25 /tmp/wrf-compile.log; ls -la /opt/WRF/main/*.exe

RUN --mount=type=bind,from=ca,target=/ccr --mount=type=bind,from=wpssrc,target=/wpssrc \
    [ -f /ccr/ca-bundle.crt ] && export SSL_CERT_FILE=/ccr/ca-bundle.crt GIT_SSL_CAINFO=/ccr/ca-bundle.crt; \
    if [ -f /wpssrc/configure ]; then cp -r /wpssrc /opt/WPS; else git clone -q --depth 1 --branch v${WPS_VERSION} https://github.com/wrf-model/WPS.git /opt/WPS; fi \
    && cd /opt/WPS \
    && N=$(echo 0 | ./configure 2>&1 | grep -E 'gfortran' | grep -E '\(serial\)' | grep -v -i 'NO_GRIB2' | head -1 | sed -E 's/^[[:space:]]*([0-9]+)\..*/\1/') \
    && echo "WPS configure option: $N" && [ -n "$N" ] \
    && printf '%s\n' "$N" | ./configure >/dev/null 2>&1 \
    && ./compile > /tmp/wps-compile.log 2>&1; \
    tail -15 /tmp/wps-compile.log; ls -la /opt/WPS/*.exe

# Končna slika: brez prevajalnika in virov
FROM base AS runtime
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
      mpich libgfortran5 libnetcdf15 libnetcdff7 libpng16-16 libjpeg-turbo8 zlib1g csh perl curl ca-certificates \
      python3 python3-numpy python3-netcdf4 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /opt/WRF /opt/WRF
COPY --from=build /opt/WPS /opt/WPS
COPY --from=build /opt/jasper /opt/jasper
ENV LD_LIBRARY_PATH=/opt/jasper/lib PATH=/opt/WRF/main:/opt/WPS:$PATH
WORKDIR /work
