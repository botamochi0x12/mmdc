# MMDクレジット  
MikuMikuDanceで利用したモデルやアクセサリ情報をまとめるサービスです。  
<http://mmdc.tiger-star.net/>にて運用中。

## 環境
* Ruby 2.5
* Ruby on Rails 5.1
* MySQL 5.5

## 機能
* MikuMikuEffectが保存したemmファイルからモデル、アクセ情報を取り出してDBへ保存する
* モデル、アクセの作者、配布先情報をユーザーが登録する
* 解る範囲で作者、配布先情報を埋めた使用モデル一覧表をダウンロードできるようにする

## 除外ファイル
* 下記設定ファイルはコミットされていません。各々でご用意ください。
    * config/database.yml
    * config/secrets.yml

## 本番データのスナップショット

本番 (<https://mmdc.tiger-star.net/>) のデータを低負荷で写し取り、SQLite に入れる道具が
`tools/snapshot/mmdc_snapshot.py` にあります。Python 3 の標準ライブラリだけで動き、
Rails / MySQL を立てる必要はありません。

```sh
# 公開データ (お知らせ・更新情報・貢献度ランキング・統計) を取って DB を作る。合計 3 リクエスト
python3 tools/snapshot/mmdc_snapshot.py all

# ログイン必須データ (Wanted / 作者 / クレジット) も取る。自分の X アカウントでブラウザから
# ログインし、DevTools の Cookie から uid と auto_login_token を写して渡す
MMDC_COOKIE='uid=...; auto_login_token=...' python3 tools/snapshot/mmdc_snapshot.py all --gated

# 一覧で切り詰められた名前を編集画面から補完する (切り詰められた行だけ 1 件 1 リクエスト。中断しても続きから)
MMDC_COOKIE=... python3 tools/snapshot/mmdc_snapshot.py all --gated --detail

# ネットワークを使わず JSONL から SQLite を作り直す
python3 tools/snapshot/mmdc_snapshot.py load

# テスト (ネットワーク不要)
python3 -m unittest tools/snapshot/test_mmdc_snapshot.py
```

* `db/snapshot/<table>.jsonl` が正。1 行 1 レコード、キーはソート済みで、`git diff` が本番側の変化を表す
* `db/snapshot/mmdc.sqlite3` は JSONL から組み立てる派生物で、git には入れない
* `db/snapshot/meta.json` に取得日時と統計 (Wanted / クレジット / 作者の件数) を残す
* 負荷低減: 接続 1 本・リクエスト間隔 3 秒 (`--delay`、1 秒未満は拒否)・429/5xx は Retry-After を尊重して
  指数バックオフ・gzip・一覧 JSON が使える表は HTML を描画させない・編集画面は `--detail` のときに
  切り詰められた行だけ・取得済みは飛ばす
* ログイン必須ページは Wayback Machine に 1 度も保存されていないため、本番から取るしかありません。
  Cookie は本人のものを使い、本番運営者 (Tiger Star) の迷惑にならない頻度で実行してください
