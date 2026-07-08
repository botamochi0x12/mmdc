# 01. 認証(Twitterログイン・自動ログイン)

## 概要

認証はTwitter OmniAuthのみ。ログイン状態は署名Cookie(uid + auto_login_token、14日)で維持する。
背景は [ADR 0001](../adr/0001-twitter-omniauth認証と署名cookie自動ログイン.md)。

## 用語

| 用語 | 意味 |
|---|---|
| auto_login_token | `users.auto_login_token`。`SecureRandom.hex` で保存の度に再生成 |
| rehash | 最新トークンを署名Cookieへ書き直す処理(`rehash_token`) |

## 前提条件

- `config/secrets.yml` に Twitter の consumer_key / consumer_secret が設定されている。

## 振る舞い仕様

### S-01: 初回ログイン(ユーザー作成)

- Given: `users` に provider='twitter', uid='12345' のレコードが存在しない
- When: Twitter認証を完了し `GET /auth/twitter/callback` に到達する
  (auth hash: uid='12345', info.nickname='taro', info.name='太郎')
- Then: `users` に provider='twitter', uid='12345', screen_name='taro', name='太郎',
  is_admin=false, is_ban=false の行が作成され、root へリダイレクト。
  署名Cookie `uid` と `auto_login_token`(期限14日)が設定される

### S-02: 再ログイン(プロフィール同期)

- Given: provider='twitter', uid='12345', screen_name='old_name' のユーザーが存在する
- When: 同uidで再ログインする(info.nickname='new_name')
- Then: 新規行は作成されず、既存行の screen_name が 'new_name' に更新される

### S-03: Cookieによる自動ログイン

- Given: 有効な署名Cookie `uid` / `auto_login_token` を持つ(セッションは空)
- When: `GET /videos` にアクセスする
- Then: ログイン状態として扱われ、動画一覧が表示される

### S-04: ログアウト

- Given: ログイン状態
- When: `GET /logout` にアクセスする
- Then: root へリダイレクトし、`auto_login_token` / `uid` Cookieが削除される。
  以後、要ログインページにアクセスするとS-01(00-common)の通り弾かれる

### S-05: トークン再生成による旧Cookie無効化

- Given: 端末Aと端末Bが同一ユーザーの有効なCookieを持つ
- When: 端末Aで再ログインする(User保存 → auto_login_token再生成)
- Then: 端末Bの旧Cookieは `find_by_uid_and_auto_login_token` に一致せず、
  次回アクセスで「ログインしてください。」となる

### S-06: 改ざんCookieの拒否

- Given: `auto_login_token` Cookieを署名なしの生値に改ざんした状態
- When: `GET /videos` にアクセスする
- Then: `cookies.signed` の復号に失敗して未ログイン扱いになり、root へリダイレクトされる

## 検証上の注意

- Twitter外部依存は **OmniAuth test mode** で排除できる:
  `OmniAuth.config.test_mode = true` +
  `OmniAuth.config.mock_auth[:twitter] = OmniAuth::AuthHash.new(provider:'twitter', uid:'12345', info:{nickname:'taro', name:'太郎'})`。
  この状態で `/auth/twitter/callback` に直接GETすればコールバックが再現できる。
- 署名Cookieをテストから直接作る場合は `secret_key_base` を用いた署名が必要。
  ブラウザE2Eでは「ログイン→Cookie保存→セッションCookieのみ削除」の手順が現実的。
- Cookie期限(14日)の検証はブラウザのCookie属性(expires)を読む。

## 実装参照

- `app/controllers/sessions_controller.rb#callback,destroy`
- `app/controllers/application_controller.rb#login_required,rehash_token,current_user`
- `app/models/user.rb`(before_save, `create_with_omniauth`)
- `config/initializers/omniauth.rb`

## 未確認事項

- 認証失敗時(ユーザーがTwitter側で拒否した場合)のfailureルートのハンドリングは未定義
  (OmniAuthデフォルトの `/auth/failure` に対応するルート・画面がない)。
