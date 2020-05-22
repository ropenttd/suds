FROM python:2-alpine
MAINTAINER Dang Mai <contact@dangmai.net>

ENV LIMNORIA_VERSION master-2019-12-21

RUN apk --no-cache add git bash openssl ca-certificates vim less \
    && pip install -r https://raw.githubusercontent.com/ProgVal/Limnoria/${LIMNORIA_VERSION}/requirements.txt \
    && pip install git+https://github.com/ProgVal/Limnoria.git@${LIMNORIA_VERSION} --upgrade \
    && pip install requests netaddr \
    && pip install git+https://github.com/ropenttd/libottdadmin2.git#egg=libottdadmin2 \
    && apk del git

VOLUME ["/var/supybot/data"]
WORKDIR /var/supybot/data

COPY . /plugin

RUN chmod u+x /plugin/docker/start.sh
ENTRYPOINT ["/bin/bash", "/plugin/docker/start.sh"]