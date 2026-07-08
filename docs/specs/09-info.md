# 09. お知らせ(Info)

## 概要

運営からのお知らせの掲載。閲覧は匿名可、作成・編集は管理者のみ。
トップページに最新5件が表示され、RSS/Atomフィードを配信する。

## 前提条件

- 閲覧: 認可不要(認可マトリクスの例外コントローラ)。
- new/create/edit/update: 管理者のみ(`check_admin`)。

## 振る舞い仕様

### S-01: 匿名閲覧

- Given: infos に2件(date/title/note入り)存在する
- When: 未ログインで `GET /infos` および `GET /infos/:id` を表示する
- Then: 一覧(id降順)と詳細が表示される

### S-02: 管理者による作成

- Given: 管理者でログイン済み
- When: `GET /infos/new` から date='2026-07-04', title='メンテのお知らせ', note='本文' でPOSTする
- Then: 登録され詳細へリダイレクト+notice「お知らせ情報を登録しました。」

### S-03: 非管理者の作成拒否

- Given: 一般ユーザーでログイン済み
- When: `GET /infos/new` にアクセスする
- Then: root へリダイレクトされる

### S-04: 更新・削除

- Given: 既存 info
- When: 管理者が編集しPATCH / DELETEする
- Then: それぞれ notice「お知らせ情報を更新しました。」「お知らせ情報を削除しました。」

### S-05: トップページ表示とフィード

- Given: infos に6件存在する
- When: `GET /` `GET /home/index.rss` `GET /home/index.atom` を表示する
- Then: トップには最新5件のみ。RSS/Atomはそれぞれのフォーマットで返る

## 検証上の注意

- title は NOT NULL(DB制約)だがモデル検証がないため、空titleの登録は
  500(`ActiveRecord::NotNullViolation`)になる。バリデーションエラー表示ではない。

## 実装参照

- `app/controllers/infos_controller.rb`, `app/controllers/home_controller.rb`
- `app/views/home/index.rss.builder`, `index.atom.builder`

## 未確認事項

- **`DELETE /infos/:id` は匿名で実行できる**(check_admin の only に destroy が含まれない)。
  [00-common.md](00-common.md) 未確認事項および [ADR 0008](../adr/0008-コントローラ名ベースの認可制御.md) 参照。
  修正推奨(認可漏れ)。
