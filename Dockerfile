# syntax = docker/dockerfile:1

ARG PYTHON_VERSION="3.8"
ARG POETRY_VERSION="1.2.2"

ARG BUILD_DEPS="\
  python3-dev \
  python3-cffi \
  python3-gdal \
  build-essential \
  gettext \
  libpq-dev \
  libgdal-dev \
  libjpeg-dev \
  libgpgme-dev \
  linux-libc-dev \
  libffi-dev \
  libssl-dev \
  musl-dev \
  cmake \
  pkg-config \
  autoconf \
  libtool \
  automake"

ARG RUNTIME_DEPS="\
  apt-utils \
  gcc \
  bzip2 \
  git \
  curl \
  nginx \
  vim \
  gosu \
  gettext \
  postgresql-client"

FROM python:${PYTHON_VERSION}-slim as base

ARG POETRY_VERSION

ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  DEBIAN_FRONTEND=noninteractive \
  PROJECT=Weni-engine \
  PROJECT_PATH=/home/app \
  PROJECT_USER=app_user \
  PROJECT_GROUP=app_group \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PATH="/install/bin:${PATH}" \
  APP_PORT=${APP_PORT} \
  APPLICATION_NAME="Weni-engine" \
  RUNTIME_DEPS=${RUNTIME_DEPS} \
  BUILD_DEPS=${BUILD_DEPS} \
  PYTHONIOENCODING=UTF-8 \
  LIBRARY_PATH=/lib:/usr/lib

ARG COMPRESS_ENABLED
ARG BRANDING_ENABLED

RUN addgroup --gid 1999 "${PROJECT_GROUP}" \
  && useradd --system -m -d "${PROJECT_PATH}" -u 1999 -g 1999 "${PROJECT_USER}"

WORKDIR "${PROJECT_PATH}"

RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache

FROM base as build-poetry

ARG POETRY_VERSION

COPY pyproject.toml poetry.lock ./

RUN --mount=type=cache,mode=0755,target=/pip_cache,id=pip pip install --cache-dir /pip_cache -U poetry=="${POETRY_VERSION}" \
  && poetry cache clear -n --all pypi \
  && poetry export --without-hashes --output requirements.txt
#  && poetry add -n --lock $(cat pip-requires.txt) \

FROM base as build

ARG BUILD_DEPS

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  apt-get update \
  && apt-get install --no-install-recommends --no-install-suggests -y ${BUILD_DEPS}
 
COPY --from=build-poetry "${PROJECT_PATH}/requirements.txt" /tmp/dep/
RUN --mount=type=cache,mode=0755,target=/pip_cache,id=pip pip install --cache-dir /pip_cache --prefix=/install -r /tmp/dep/requirements.txt

FROM base

ARG BUILD_DEPS
ARG RUNTIME_DEPS

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  apt-get update \
  && SUDO_FORCE_REMOVE=yes apt-get remove --purge -y ${BUILD_DEPS} \
  && apt-get autoremove -y \
  && apt-get install -y --no-install-recommends ${RUNTIME_DEPS} \
  && rm -rf /usr/share/man /usr/share/doc

COPY --from=build /install /usr/local
COPY --chown=${PROJECT_USER}:${PROJECT_GROUP} . ${PROJECT_PATH}

USER "${PROJECT_USER}:${PROJECT_USER}"
EXPOSE 8000
ENTRYPOINT ["bash", "./entrypoint.sh"]
CMD ["start"]

