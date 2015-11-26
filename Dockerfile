FROM gliderlabs/alpine:3.2
MAINTAINER Chris Roemmich <croemmich@myriadmobile.com>

RUN apk-install \
  build-base \
  file \
  gcc \
  git \
  libffi-dev \
  libxml2-dev \
  libxslt-dev \
  openssl-dev \
  python3 \
  python3-dev \
  py-pip && \
  pip install --upgrade pip && \
  pip install virtualenv && \
  virtualenv -p python3 /env

COPY app /app
WORKDIR /app

RUN /env/bin/pip install -r /app/requirements.txt

RUN apk del --purge \
      build-base \
      gcc \
      python3-dev && \
    rm -rf /root/.cache \
      /usr/share/doc \
      /tmp/* \
      /var/cache/apk/*

ENTRYPOINT ["/env/bin/python", "./main.py"]