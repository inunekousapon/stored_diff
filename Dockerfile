# syntax=docker/dockerfile:experimental
FROM python:3.7.4-slim-buster as base

ENV LANG ja_JP.UTF-8
ENV LC_CTYPE ja_JP.UTF-8
ENV APP_ROOT /app

WORKDIR $APP_ROOT

USER root

# gitの導入でLOCALEを聞かれるので、それを回避する
ENV DEBIAN_FRONTEND=noninteractive

# aptの先を日本にする
RUN sed -i.bak -e "s%http://archive.ubuntu.com/ubuntu/%http://ftp.iij.ad.jp/pub/linux/ubuntu/archive/%g" /etc/apt/sources.list

# セットアップのための標準ライブラリを導入
RUN set -x \
    && apt-get -qq -y update \
    && apt-get -qq -y upgrade \
    && apt-get install -y --no-install-recommends curl ca-certificates apt-transport-https gnupg ssh g++ git \
    && curl -O -fsSL https://packages.microsoft.com/keys/microsoft.asc \ 
    && apt-key add microsoft.asc \
    && curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && apt-get install -y --no-install-recommends unixodbc-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY ./ $APP_ROOT

RUN pip install -r requirements.txt

RUN chmod +x $APP_ROOT/start.sh

EXPOSE 8000