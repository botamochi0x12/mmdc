# 08. 貢献度ランキング

## 概要

クレジット情報の登録・更新回数(credit_logs 件数)によるユーザーランキング。
背景は [ADR 0006](../adr/0006-credit_logとhistoriesによる変更監査.md)。

## 用語

| 用語 | 意味 |
|---|---|
| ポイント | そのユーザーの credit_logs 行数(クレジットの作成+実変更を伴う更新の回数) |

## 前提条件

- `/ranks` はログイン必須。トップページのランキング表示は匿名でも見える。

## 振る舞い仕様

### S-01: ランキング表示

- Given: credit_logs がユーザーA=5件、B=3件、C=1件
- When: `GET /ranks` を表示する
- Then: A(1位・5pt)、B(2位・3pt)、C(3位・1pt)の順に最大50位まで表示される

### S-02: 同ポイント同ランク

- Given: credit_logs がA=5件、B=3件、C=3件、D=1件
- When: ランキングを表示する
- Then: A=1位、B=2位、C=2位、D=4位(3位は欠番)

### S-03: トップページのランキング

- Given: S-01と同じデータ
- When: 匿名で `GET /` を表示する
- Then: 上位3名が表示される

## 検証上の注意

- ポイントは credits の現在値ではなく **credit_logs の行数**。テストデータは
  credit_logs を直接投入するか、クレジット操作([05-credit.md](05-credit.md) S-01/S-05)で積む。
- `limit(50)` は `group` の前に適用されるため、厳密には「先頭50行を集計」でなく
  MySQLの実行計画依存の挙動になり得る(未確認事項参照)。

## 実装参照

- `app/services/ranking_service.rb#getRanks`
- `app/controllers/ranks_controller.rb`, `app/controllers/home_controller.rb`

## 未確認事項

- `CreditLog.limit(50).group('user_id')...count` の limit は集計後の件数制限として
  効いているか要実機確認(Rails 5.1 + MySQLでの動作依存)。
- BANユーザー・退会相当ユーザーもランキングに表示され続ける。
