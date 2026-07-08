# 00. 共通仕様(認可・レイアウト・サイドバー)

## 概要

全画面に共通する認可制御、ナビゲーション、サイドバー(統計・更新情報)の仕様。
各機能仕様の前提条件は本書の認可マトリクスを参照する。

## 用語

| 用語 | 意味 |
|---|---|
| ログインユーザー | 署名Cookie `uid` + `auto_login_token` が users テーブルと一致する利用者 |
| 管理者 | `users.is_admin = true` のログインユーザー |
| BANユーザー | `users.is_ban = true` のユーザー |
| 履歴(histories) | Credit/Author/Wanted の保存時に追加される操作フィード |

## 認可マトリクス

| コントローラ | 匿名 | ログイン | 管理者 | 備考 |
|---|---|---|---|---|
| home | ○ | ○ | ○ | |
| sessions | ○ | ○ | ○ | 認証コールバック/ログアウト |
| infos(index/show/**destroy**) | ○ | ○ | ○ | destroyが匿名可なのは認可漏れの疑い(下記S-05) |
| infos(new/create/edit/update) | × | × | ○ | `check_admin` |
| videos / emms / wanteds / credits / authors / ranks | × | ○ | ○ | `login_required` |
| users(全action) | × | × | ○ | `check_admin` |

- 認可判定は `ApplicationController#auth` によるコントローラ名比較
  (除外: home / sessions / infos)。詳細は [ADR 0008](../adr/0008-コントローラ名ベースの認可制御.md)。

## 前提条件

- サイドバーは全ページで `ApplicationController#get_side_info` により描画される
  (認可より前でなく `before_action :auth, :get_side_info` の宣言順で両方実行)。

## 振る舞い仕様

### S-01: 未ログインで要ログインページへアクセス

- Given: ログインしていない(署名Cookieなし)
- When: `GET /videos` にアクセスする
- Then: root(`/`)へリダイレクトされ、notice「ログインしてください。」が表示される

### S-02: BANユーザーのアクセス拒否

- Given: `users` に `is_ban=true` のユーザーが存在し、そのユーザーの有効な署名Cookieを持つ
- When: `GET /videos` にアクセスする
- Then: `/logout` へリダイレクトされ、alert「お使いのアカウントはブロックされています。」が表示される。
  ログアウト処理によりCookieが削除され、以後未ログイン状態になる

### S-03: 非管理者の管理ページアクセス拒否

- Given: `is_admin=false` のログインユーザー
- When: `GET /users` にアクセスする
- Then: root へリダイレクトされる(メッセージなし)

### S-04: サイドバー統計の表示

- Given: credit未紐付けのwantedが2件(うち1件は当日作成)、creditが5件、authorが3件存在する
- When: 任意のページ(例 `/`)を表示する
- Then: サイドバー「統計」に Wantend「2件」+当日分「+1」、クレジット情報「5件」、
  作者情報「3件」が表示される(当日増分は0の場合バッジ非表示)

### S-05: サイドバー更新情報の表示

- Given: histories に31件のレコードが存在する
- When: 任意のページを表示する
- Then: 「更新情報」に新しい順で30件表示される。各行は 日時(`%Y/%m/%d %H:%M:%S`)+
  種別(Wanted/クレジット/作者)+「登録/更新」+ 名称(20文字でtruncate)。
  ログイン時のみ名称が編集ページへのリンクになる(未ログイン時はテキスト)

### S-06: ナビゲーションの出し分け

- Given: (a)未ログイン (b)一般ユーザー (c)管理者 の3状態
- When: 任意のページを表示する
- Then: (a)メニューなし (b)動画情報/Wanted/クレジット情報/作者情報/ランキング
  (c)(b)+Info+ユーザー が表示される

## 検証上の注意

- 「当日増分」は `created_at` が当日(`0.day.ago.all_day`)のレコード数。テストデータの
  created_at をタイムゾーン(JST想定、`config/application.rb` 要確認)込みで制御すること。
- S-02 のBAN判定はリダイレクトが2段(要ログインページ→/logout→root)になる。
  E2Eでは最終到達URLとフラッシュの両方を検証する。

## 実装参照

- `app/controllers/application_controller.rb#auth,login_required,check_admin,get_side_info`
- `app/views/sides/_sidemenu.html.slim`
- `app/views/layouts/application.html.slim`

## 未確認事項

- `infos#destroy` が匿名実行可能(auth除外+check_admin対象外)。仕様ではなくバグの可能性が高い。
- `session[:user_id]` はログイン時に設定されるが参照箇所がなく、実質未使用。
