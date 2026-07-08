# 04. Wanted(クレジット募集一覧)

## 概要

クレジット未登録のオブジェクト(wanted)を一覧し、クレジット登録への入口を提供する。
wanted の生成は自動([03-emm-upload.md](03-emm-upload.md) S-06)で、この画面からの新規作成はない。

## 用語

| 用語 | 意味 |
|---|---|
| wanted | 3ユーザー閾値を超えて使用が確認された、クレジット募集中のファイル |

## 前提条件

- ログイン必須。

## 振る舞い仕様

### S-01: 一覧はcredit未登録のみ

- Given: wanteds が3件あり、うち1件には credits が紐付いている
- When: `GET /wanteds` を表示する
- Then: credit未紐付けの2件のみが folder_name 昇順で表示される

### S-02: 検索

- Given: file_name='Tda式初音ミク.pmx' の wanted が存在する
- When: 検索フォームで file_name に「ミク」を含む条件で検索する(ransack)
- Then: 該当行のみ表示される。検索可能カラムは file_name / folder_name / extension のみ

### S-03: wanted の修正

- Given: folder_name にタイプミスを含む wanted が存在する
- When: `GET /wanteds/:id/edit` で folder_name を修正しPATCHする
- Then: 更新され、histories に item='Wanted', is_create=true の行が追加される
  (更新でも is_create=true になる — Wanted#add_history が固定値のため)

### S-04: クレジット登録への導線

- Given: credit未登録の wanted が一覧に表示されている
- When: 行のリンクをクリックする
- Then: `/credits/new/:wanted_id` に遷移する([05-credit.md](05-credit.md) S-01)

## 検証上の注意

- 一覧の絞り込みは `includes(:credit).where(credits: {id: nil})`。テストデータは
  「credit有り」「credit無し」両方の wanted を用意して差分を検証する。
- ページネーションあり(kaminari のデフォルト25件)。

## 実装参照

- `app/controllers/wanteds_controller.rb`
- `app/models/wanted.rb`
- 既存テスト: `spec/controllers/wanteds_controller_spec.rb`, `spec/models/wanted_spec.rb`

## 未確認事項

- ルートは `:show` を除外しているが `wanteds/show.html.slim` が残存している(デッドコード)。
- wanted の削除導線はない(誤生成された wanted はDB操作でしか消せない)。
