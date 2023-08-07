FROM python:3.8-slim

ENV WORKDIR /home/app
WORKDIR $WORKDIR

RUN apt-get update \
 && apt-get install --no-install-recommends --no-install-suggests -y apt-utils \
 && apt-get install --no-install-recommends --no-install-suggests -y gcc bzip2 git curl nginx libpq-dev gettext \
    libgdal-dev python3-cffi python3-gdal vim build-essential

RUN pip install -U pip==22.3.1
RUN pip install poetry==1.2.2
RUN apt-get install -y libjpeg-dev libgpgme-dev linux-libc-dev musl-dev libffi-dev libssl-dev
ENV LIBRARY_PATH=/lib:/usr/lib

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi

COPY . .

RUN chmod +x ./entrypoint.sh
ENTRYPOINT [ "./entrypoint.sh" ]
