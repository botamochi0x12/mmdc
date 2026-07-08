# 10. ユーザー管理(管理者)

## 概要

管理者によるユーザーの閲覧・編集・BAN。物理削除はなく、「削除」操作はBAN
([ADR 0005](../adr/0005-動画とユーザーの論理無効化.md))。

## 前提条件

- 全action管理者のみ(`check_admin`)。

## 振る舞い仕様

### S-01: 一覧と検索

- Given: users に複数ユーザーが存在する
- When: 管理者が `GET /users` を表示する
- Then: id昇順で一覧表示(ransack検索・ページネーションあり)

### S-02: ユーザー編集

- Given: 一般ユーザー(is_admin=false, is_ban=false)が存在する
- When: 管理者が `GET /users/:id/edit` で is_admin=true に変更しPATCHする
- Then: 更新され `/users` へリダイレクト+notice「ユーザー情報を更新しました。」

### S-03: BAN(destroy)

- Given: is_ban=false のユーザーが存在する
- When: 管理者が `DELETE /users/:id` を実行する
- Then: レコードは残り is_ban=true になる。notice「ユーザーをバンしました。」。
  当該ユーザーの次回アクセスは [00-common.md](00-common.md) S-02 の通り拒否される

### S-04: 非管理者のアクセス拒否

- Given: 一般ユーザーでログイン済み
- When: `GET /users` にアクセスする
- Then: root へリダイレクトされる

## 検証上の注意

- BAN解除は S-02 の編集画面(is_ban チェックボックス)で行う。
- ユーザー編集で uid を書き換えるとそのユーザーの自動ログインCookieが無効になる
  (uid照合のため)。テストで uid を変えた場合は再ログインが必要。

## 実装参照

- `app/controllers/users_controller.rb`
- 既存テスト: `spec/models/user_spec.rb`

## 未確認事項

- 管理者が自分自身をBAN/一般化することも可能(ガードなし)。最後の管理者を失うと
  管理画面に入れなくなる(DB直接操作でのみ復旧可能)。
