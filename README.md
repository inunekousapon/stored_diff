# 概要
SQLServerのストアドプロシージャを環境別に比較したものを可視化します。

# 環境

 - SQLServer 20xx
接続先が3つあること
 - Python3.x

# インストール

```sh
git clone https://github.com/inunekousapon/stored_diff.git
cd stored_diff
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

# 使い方

## サーバー起動

開発/ステージング/本番 向けのDB接続名を設定します

```
DEVELOP_DNS='DB接続名'
STAGING_DNS='DB接続名'
PRODUCTION_DNS='DB接続名' 
python manage.py runserver
```

## ストアドプロシージャ取り込み

```
http://localhost:5000/sync
```

## 表示

http://localhost:5000
