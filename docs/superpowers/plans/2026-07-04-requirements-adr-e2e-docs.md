# 要件ドキュメント整備(ADR + E2E仕様) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MMDクレジット(Rails 5.1)の現行仕様を、ADR 8本 + E2Eテスト可能なGWT仕様書11本として `docs/` に文書化する。

**Architecture:** コード変更は一切行わない。各タスクは「対象コードの精読 → ドキュメント執筆 → 受入基準セルフチェック」のサイクルで1ファイル(または関連ADR群)を完成させる。仕様の根拠は必ず実コードに求め、推測は「未確認事項」に隔離する。

**Tech Stack:** Markdown のみ。対象コードは Ruby 2.5 / Rails 5.1 / MySQL 5.5。

## Global Constraints

- **コミットしない**: ユーザー指示により、このセッションでは git commit を行わない(ユーザーが最後にまとめて行う)。タスク末尾のコミットステップは全て省略する。
- 言語: 全ドキュメント日本語。コード識別子・ファイル名は原文のまま。
- 仕様書テンプレート(設計書 `docs/superpowers/specs/2026-07-04-requirements-adr-e2e-docs-design.md` 記載): `概要 / 用語 / 前提条件 / 振る舞い仕様(GWT) / 検証上の注意 / 実装参照 / 未確認事項`
- ADRテンプレート: `Status(Accepted・現状追認) / Context / Decision / Consequences`。経緯不明な点は「経緯不明」と明記し推測と区別する。
- **E2E受入基準**(全GWTシナリオに適用):
  1. Then が外部から観測可能(画面表示・リダイレクト先・DB状態・生成ファイル)
  2. Given が投入可能なテストデータとして具体的(カラム値レベル)
- 実装参照は `ファイルパス#メソッド名` 形式(行番号は変動しやすいため使わない)。
- シナリオIDは `S-01` 形式でファイル内連番。

## 前提知識(全タスク共通・コードから確認済みの事実)

- 認証: Twitter OmniAuthのみ(`config/initializers/omniauth.rb`)。ログイン後 `session[:user_id]` + 署名Cookie `uid` / `auto_login_token`(14日)を設定(`app/controllers/sessions_controller.rb`, `app/controllers/application_controller.rb#rehash_token`)。
- 認可: `ApplicationController#auth` が `home` / `sessions` / `infos` 以外の全コントローラでログイン必須。`check_admin` は `infos`(edit/update/new/create) と `users`(全action)。
- `User` は `before_save` で毎回 `auto_login_token` を `SecureRandom.hex` で再生成。
- `is_ban=true` のユーザーは `login_required` でログアウトへリダイレクト。
- 動画削除は論理削除(`is_show=false`)。`users#destroy` は物理削除でなく `is_ban=true`。
- ファイル振り分け(`app/services/upfile_manage_service.rb`): 拡張子 `.xml`→`XmlRegistService`、`.mpj`→`MpjRegistService`(先頭36byteスキップ後zlib展開)、その他→`EmmRegistService`(iniパース、`Object`/`Effect`セクション)。
- emmコピー時にWindows-31J→UTF-8変換、`\`→`/`、`#`→`＃`(iniコメント記号回避)。値が空/`none`/`true`/`false` の行はスキップ。
- **wanted昇格条件**: 同一 `file_name`+`folder_name` を**3人以上の異なるユーザー**が使用した時のみ `wanteds` へ登録(`EmmRegistService#is_wanted`)。`wanteds` は (file_name, folder_name, extension) でユニーク。
- クレジット照合: `mmd_objects` と `wanteds` を file_name+folder_name+extension の完全一致でJOIN、`credits.wanted_id` はユニーク(wanted 1件にcredit 1件)。
- `Credit` 保存時: 作者名から `Author` を検索、なければ自動作成。変更があれば `credit_logs` と `histories` に記録。`distribution` は `(sm|nm|im|td)+数字` 形式でニコニコURLへ変換。
- zip DL: `credit.csv`(Windows-31J、ヘッダ `名前,作者,配布先,拡張子,ステータス`) + `tree.txt`(配布先ID 10個ごと空白区切り) を zip 化(`app/models/video.rb#create_dl_zip`)。`musts` テーブルの定番データ(カテゴリ all/mmd/mmm)を先頭に含める。
- ランキング: `credit_logs` の user_id 別件数で降順、同ポイント同ランク(`app/services/ranking_service.rb`)。
- サイドバー(`ApplicationController#get_side_info`): 履歴30件、wanted残数/credit数/author数と各当日増分。
- 既知の疑義: `emms_controller#create` が存在しない `EmmRegistService.save` を呼んでいる(実在するのは `save_emm`)。壊れている可能性が高い。

---

### Task 1: ADR 0001 + 0008(認証・認可)

**Files:**
- Read: `app/controllers/sessions_controller.rb`, `app/controllers/application_controller.rb`, `config/initializers/omniauth.rb`, `app/models/user.rb`
- Create: `docs/adr/0001-twitter-omniauth認証と署名cookie自動ログイン.md`
- Create: `docs/adr/0008-コントローラ名ベースの認可制御.md`

**Interfaces:**
- Produces: ADRテンプレート構成(後続仕様書の 01-auth.md / 00-common.md が参照するADR番号)

- [ ] **Step 1: 対象コードを精読し、以下の決定事項を確認する**
  - 0001: Twitter単一プロバイダ / session + 署名Cookie二重管理 / トークン14日 / 保存毎トークン再生成 / logoutでCookie削除
  - 0008: `auth` の除外リストがコントローラ名文字列比較 / `check_admin` の適用範囲 / `is_ban` チェックが `login_required` 内
- [ ] **Step 2: 各ADRを執筆する(Context=当時の課題の推定は「推定」と明記 / Decision=コードが体現する決定 / Consequences=帰結。例: トークン再生成により複数端末同時ログイン不可)**
- [ ] **Step 3: セルフチェック** — テンプレート4セクション充足 / 推測と事実の区別 / 「現状追認」明記

### Task 2: ADR 0002 + 0003 + 0004(emm解析・照合・生SQL)

**Files:**
- Read: `app/services/upfile_manage_service.rb`, `app/services/emm_regist_service.rb`, `app/services/xml_regist_service.rb`, `app/services/mpj_regist_service.rb`, `app/models/video.rb`, `app/models/emm.rb`
- Create: `docs/adr/0002-emm解析のサービス層同期実行.md`
- Create: `docs/adr/0003-ファイル名完全一致照合と3ユーザー閾値wanted昇格.md`
- Create: `docs/adr/0004-集計照合クエリの生SQL実装.md`

- [ ] **Step 1: 精読** — 継承階層(EmmRegistService←XmlRegistService←MpjRegistService)、リクエスト同期処理(ジョブキューなし)、文字コード/エスケープ変換、is_wanted の3ユーザー閾値、生SQL(select_all/select_one + sanitize_sql_array)
- [ ] **Step 2: 執筆** — 0003 には「なぜ3人か」は経緯不明と明記。0004 の Consequences に「ActiveRecordの関連と乖離しテスト困難」「emm_id条件の文字列埋め込みはプレースホルダ非経由(ただし nil 判定のみで値は埋め込まれない)」を記載
- [ ] **Step 3: セルフチェック**(Task 1 と同基準)

### Task 3: ADR 0005 + 0006(論理削除・監査)

**Files:**
- Read: `app/controllers/videos_controller.rb#destroy,destroy_all`, `app/controllers/users_controller.rb#destroy`, `app/models/credit.rb#save_credit_log,add_history`, `app/models/author.rb#add_history`, `app/models/wanted.rb#add_history`, `app/models/history.rb`, `app/models/credit_log.rb`
- Create: `docs/adr/0005-動画とユーザーの論理無効化.md`
- Create: `docs/adr/0006-credit_logとhistoriesによる変更監査.md`

- [ ] **Step 1: 精読** — is_show / is_ban による論理無効化、全集計SQLの `is_show = true` フィルタ、credit_log(構造化ログ・貢献度算出の基盤) と histories(サイドバー表示用) の役割分担
- [ ] **Step 2: 執筆** — 0006 の Consequences に「ランキングは credit_logs 依存 → クレジット編集がポイントになる」を含める
- [ ] **Step 3: セルフチェック**

### Task 4: ADR 0007(zip成果物)

**Files:**
- Read: `app/models/video.rb#create_dl_zip,create_csv,create_tree_txt,get_dl_video_info,get_three_info,csv_column_names`, `app/models/must.rb`
- Create: `docs/adr/0007-zip成果物-windows31j-csvとコンテンツツリーtxt.md`

- [ ] **Step 1: 精読** — Windows-31J選択(Excel想定と推定)、tmp/への一時ファイル生成と削除、musts(定番モデル)のカテゴリ分岐(mmd/mmm)、tree.txt の10件区切り(ニコニコのコンテンツツリー登録UI都合と推定)
- [ ] **Step 2: 執筆**(推定箇所は明記)
- [ ] **Step 3: セルフチェック**

### Task 5: specs/00-common.md(共通仕様)

**Files:**
- Read: `app/controllers/application_controller.rb`, `app/views/layouts/`, `app/views/sides/`
- Create: `docs/specs/00-common.md`

**Interfaces:**
- Produces: 認可マトリクス(コントローラ×要ログイン×要admin)。後続仕様書は前提条件からこの表を参照する。

- [ ] **Step 1: ビュー含め精読**(サイドバーの実表示項目を `app/views/sides/` で確認)
- [ ] **Step 2: 執筆** — 以下を必須収載:
  - 認可マトリクス: 全11コントローラについて 匿名可(home/sessions/infos閲覧) / 要ログイン / 要admin(infos編集系・users) を表化
  - S-01: 未ログインで要ログインURL(例 `/videos`)へアクセス → rootへリダイレクト+「ログインしてください。」
  - S-02: BANユーザー(`users.is_ban=true`)でアクセス → logoutへリダイレクト+「お使いのアカウントはブロックされています。」
  - S-03: 非adminで `/users` へアクセス → rootへリダイレクト
  - S-04: サイドバー統計(履歴最新30件 / wanted残数=credit未紐付けwanted数 / 当日増分)の表示仕様
- [ ] **Step 3: 受入基準チェック** — 全シナリオの Given がカラム値レベルか、Then が観測可能か

### Task 6: specs/01-auth.md(認証)

**Files:**
- Read: `app/controllers/sessions_controller.rb`, `app/controllers/application_controller.rb#login_required,rehash_token,current_user`, `app/models/user.rb`
- Create: `docs/specs/01-auth.md`

- [ ] **Step 1: 執筆** — 必須シナリオ:
  - S-01: 初回Twitterログイン → users レコード作成(provider/uid/screen_name/name)、rootへ
  - S-02: 再ログイン → 既存ユーザーの screen_name/name 更新
  - S-03: 自動ログイン(署名Cookie uid+auto_login_token 有効) → セッションなしでもログイン状態
  - S-04: ログアウト → session/Cookie削除、rootへ
  - S-05: トークン再生成 — ユーザー保存の度に auto_login_token が変わる(旧Cookieは無効化)
  - 検証上の注意: OmniAuth test mode(`OmniAuth.config.test_mode = true` + mock_auth)でTwitter外部依存を排除できること、署名Cookieの検証には secret_key_base が必要なことを記載
- [ ] **Step 2: 受入基準チェック**

### Task 7: specs/02-video.md(動画管理)

**Files:**
- Read: `app/controllers/videos_controller.rb`, `app/models/video.rb#set_total,delete_by_ids`, `spec/controllers/videos_controller_spec.rb`, `spec/models/video_spec.rb`
- Create: `docs/specs/02-video.md`

- [ ] **Step 1: 既存specと突き合わせて執筆** — 必須シナリオ:
  - S-01: 一覧 — 自分の is_show=true の動画のみ、id降順、10件ページネーション、集計4指標(total/yets/wants/resolveds)表示
  - S-02: 登録 — name必須(最大100文字)+ファイル必須。ファイルなしはエラー「は最低1つアップしてください。」
  - S-03: 更新(name変更)
  - S-04: 削除 — DB上 is_show=false になり一覧から消える(レコードは残る)
  - S-05: 一括削除(destroy_all, ids配列)
  - S-06: 他ユーザーの動画は set_video(user_id条件)で見えない
  - 集計4指標の定義(total=重複除去オブジェクト数 / yets=wanted未登録 / wants=wanted有りcredit無し / resolveds=credit有り)を用語セクションで定義
- [ ] **Step 2: 受入基準チェック**

### Task 8: specs/03-emm-upload.md(emmアップロード・解析)

**Files:**
- Read: `app/services/upfile_manage_service.rb`, `app/services/emm_regist_service.rb`, `app/services/xml_regist_service.rb`, `app/services/mpj_regist_service.rb`, `app/controllers/emms_controller.rb`, `spec/models/emm_spec.rb`, `spec/factories/`
- Create: `docs/specs/03-emm-upload.md`

- [ ] **Step 1: 執筆** — 必須シナリオ:
  - S-01: emm(ini)アップロード → Object/Effectセクションの各行が mmd_objects 化(full_path/extension/file_name/folder_name)
  - S-02: 値が空/none/true/false の行はスキップ
  - S-03: .xml → MMProject/Models 配下 Model/Accessory/Effect の File 要素を登録
  - S-04: .mpj → 36byteスキップ+zlib展開後xmlとして解析
  - S-05: 同一動画・同一emm内の重複オブジェクトは登録しない
  - S-06: wanted昇格 — 同一 file_name+folder_name を3人目の別ユーザーが登録した時点で wanteds に1件生成(2人までは生成されない)
  - S-07: 解析失敗行(拡張子等欠落)はログ警告のみでスキップ
  - 検証上の注意: フィクスチャemmの最小内容例(iniテキスト)を仕様内に添付 / 保存先 `secrets.save_dir_path` の設定が必要 / Windows-31Jで書かれたemmを用意
  - 未確認事項: `emms_controller#create` の `EmmRegistService.save` 未定義呼び出し(動画作成経由 `UpfileManageService.save` が実運用経路と推定)
- [ ] **Step 2: 受入基準チェック**

### Task 9: specs/04-wanted.md

**Files:**
- Read: `app/controllers/wanteds_controller.rb`, `app/models/wanted.rb`, `spec/controllers/wanteds_controller_spec.rb`, `app/views/wanteds/`
- Create: `docs/specs/04-wanted.md`

- [ ] **Step 1: 執筆** — S-01: 一覧はcredit未紐付けのみ・folder_name昇順 / S-02: ransack検索(file_name/folder_name/extension) / S-03: 編集・更新 / S-04: 保存時に histories へ「Wanted」レコード追加(link=/credits/new/:id)
- [ ] **Step 2: 受入基準チェック**

### Task 10: specs/05-credit.md(クレジット登録)

**Files:**
- Read: `app/controllers/credits_controller.rb`, `app/models/credit.rb`, `spec/controllers/credits_controller_spec.rb`, `spec/models/credit_spec.rb`
- Create: `docs/specs/05-credit.md`

- [ ] **Step 1: 執筆** — 必須シナリオ:
  - S-01: wanted からの新規登録(`/credits/new/:wanted_id`) → 保存後 wanteds_path へ、通知「クレジット情報を登録しました。」
  - S-02: 作者名の自動作成 — 未知の作者名なら authors に新規行、既知ならそのIDを紐付け
  - S-03: バリデーション一式(name必須/100文字、distribution `(sm|im|td|nm)数字` 形式、url http(s)形式250文字、description 255文字、作者名1個以上・重複不可・100文字以下)
  - S-04: distribution_url 変換(sm/nm→nicovideo watch、im→seiga、td→3d.nicovideo)
  - S-05: 更新時 credit_logs と histories に記録される / 実質変更なしなら updated_by 据え置き・ログなし
  - S-06: autocomplete(作者名)
  - S-07: destroy は何も起きない(空実装)— 仕様として明記
- [ ] **Step 2: 受入基準チェック**

### Task 11: specs/06-author.md

**Files:**
- Read: `app/controllers/authors_controller.rb`, `app/models/author.rb`, `spec/controllers/authours_controller_spec.rb`, `spec/models/author_spec.rb`
- Create: `docs/specs/06-author.md`

- [ ] **Step 1: 執筆** — S-01: 一覧(name昇順・ransack検索 name/disp_name) / S-02: 登録(name一意・各SNS項目バリデーション、nico/pixivは正整数) / S-03: disp_name 空なら name を複写 / S-04: credits で使用中の作者は削除不可(alert文言) / S-05: 未使用作者は削除可 / S-06: 保存時 histories 追加
- [ ] **Step 2: 受入基準チェック**

### Task 12: specs/07-credit-download.md(zip DL)

**Files:**
- Read: `app/models/video.rb#zip関連5メソッド`, `app/models/must.rb`, `app/controllers/videos_controller.rb#zip`
- Create: `docs/specs/07-credit-download.md`

- [ ] **Step 1: 執筆** — 必須シナリオ:
  - S-01: `/videos/:id/zip` → `動画名(URLエンコード)_タイムスタンプ.zip` がDLされ、credit.csv と tree.txt を含む
  - S-02: csv内容 — 1行目ヘッダ(名前,作者,配布先,拡張子,ステータス)、musts行が先頭(ステータス○)、以降は拡張子昇順・モデル名昇順、credit有り=○/無し=×、credit無しは file_name がモデル名になる
  - S-03: 複数作者は disp_name を `/` 連結
  - S-04: tree.txt — musts の video + credits の distribution(空以外)を10個ごと空白区切り改行
  - S-05: musts カテゴリ選択 — emm拡張子が .xml/.mpj を含む動画は mmm、それ以外は mmd(all は常に含む)
  - 検証上の注意: csvは Windows-31J なのでテストでは encoding 指定して読むこと / zip解凍検証手順
- [ ] **Step 2: 受入基準チェック**

### Task 13: specs/08-rank.md + specs/09-info.md

**Files:**
- Read: `app/services/ranking_service.rb`, `app/controllers/ranks_controller.rb`, `app/controllers/home_controller.rb`, `app/controllers/infos_controller.rb`
- Create: `docs/specs/08-rank.md`, `docs/specs/09-info.md`

- [ ] **Step 1: 08-rank 執筆** — S-01: credit_logs のユーザー別件数降順・上位50 / S-02: 同ポイント同ランク(次順位は飛ぶ) / S-03: home には top3 表示
- [ ] **Step 2: 09-info 執筆** — S-01: 一覧・詳細は匿名閲覧可 / S-02: 作成・編集は admin のみ(非adminはrootへ) / S-03: CRUD一式(date/title/note、title必須はDB制約) / S-04: home に最新5件、atom/rss フィード対応
- [ ] **Step 3: 受入基準チェック**

### Task 14: specs/10-user-admin.md

**Files:**
- Read: `app/controllers/users_controller.rb`, `spec/models/user_spec.rb`
- Create: `docs/specs/10-user-admin.md`

- [ ] **Step 1: 執筆** — S-01: 全action admin限定 / S-02: 一覧(id昇順・ransack・ページネーション) / S-03: 編集(is_ban/is_admin含む) / S-04: destroy=BAN(is_ban=true、レコード残存、通知「ユーザーをバンしました。」) / S-05: BANされたユーザーの次回アクセス挙動(00-common S-02 への相互参照)
- [ ] **Step 2: 受入基準チェック**

### Task 15: 全体セルフレビューと索引作成

**Files:**
- Read: 作成した全19ファイル
- Create: `docs/README.md`(ADR・仕様の索引)
- Modify: 必要に応じて各ファイル

- [ ] **Step 1: 設計書の受入基準で全仕様書を横断チェック**(Then観測可能性 / Given具体性 / プレースホルダ禁止 / ADR番号相互参照の整合)
- [ ] **Step 2: 用語の一貫性チェック**(wanted/credit/mmd_object/must/history の定義が全ファイルで同一か)
- [ ] **Step 3: `docs/README.md` に索引(各ファイル1行の要約付き)を作成**
- [ ] **Step 4: 完了報告**(ユーザーがコミットできるよう変更ファイル一覧を提示)
