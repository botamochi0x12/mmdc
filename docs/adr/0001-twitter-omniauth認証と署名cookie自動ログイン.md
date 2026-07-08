# ADR 0001: Twitter OmniAuth認証と署名Cookieによる自動ログイン

- Status: Accepted(現状追認 — 2026-07-04 にコードから逆起こし)
- 関連: [ADR 0008](0008-コントローラ名ベースの認可制御.md), [specs/01-auth.md](../specs/01-auth.md)

## Context

MMDクレジットは、ニコニコ動画等へ動画を投稿するMMDユーザーが利用するサービスであり、
利用者は既にTwitterアカウントを持っていることがほぼ前提にできる。
独自のID/パスワード管理を持つとパスワードリセットや漏洩対策などの運用負担が発生する。

## Decision

1. **認証はTwitter OmniAuthのみ**とする。独自のパスワード認証は持たない
   (`config/initializers/omniauth.rb`, `app/controllers/sessions_controller.rb#callback`)。
2. ログイン状態は **`session[:user_id]` と署名Cookie(`uid` + `auto_login_token`)の二重管理**とし、
   Cookieの有効期限は **14日** とする(`app/controllers/application_controller.rb#rehash_token`)。
   実際のログイン判定はCookie側(`login_required` / `current_user`)で行う。
3. `auto_login_token` は **`User` の保存のたびに `SecureRandom.hex` で再生成**する
   (`app/models/user.rb` の `before_save`)。ログイン成功時・情報更新時にCookieへ再設定(rehash)する。
4. ユーザーは `(provider, uid)` の組で一意に識別する(DBユニークインデックス)。
   再ログイン時は `screen_name` / `name` をTwitterの最新値で上書きする。
5. ログアウトは `session[:user_id]` の破棄と `auto_login_token` / `uid` Cookieの削除で行う
   (`app/controllers/sessions_controller.rb#destroy`)。

## Consequences

- パスワード管理が不要になり、実装・運用が単純になる。
- Twitter APIの仕様変更・キー失効がそのままログイン障害になる(単一障害点)。
- トークンが保存毎に再生成されるため、**あるユーザーがどこかでログインし直す(またはユーザーレコードが
  保存される)と、他端末の自動ログインCookieは無効になる**。複数端末の同時自動ログインは維持できない。
- ログイン判定がCookie依存のため、`session[:user_id]` は実質的に使われておらず、
  セッションとCookieの状態が食い違う余地がある(経緯不明。コード上は `current_user` がCookieのみ参照)。
- 署名CookieはRailsの `secret_key_base` に依存するため、鍵のローテーションで全ユーザーがログアウトされる。
