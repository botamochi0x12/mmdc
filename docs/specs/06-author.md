# 06. 作者情報管理

## 概要

モデル・アクセの製作者情報(名前・表記名・各種SNS/配布サイト)を管理する。
クレジット登録時の自動作成([05-credit.md](05-credit.md) S-02)と、この画面からの手動管理の両方がある。

## 用語

| 用語 | 意味 |
|---|---|
| name | 作者の一意な識別名(ユニーク制約) |
| disp_name | クレジットcsv等に出力される表記名。未入力なら name が複写される |

## 前提条件

- ログイン必須。

## 振る舞い仕様

### S-01: 一覧と検索

- Given: authors が複数存在する
- When: `GET /authors` を表示する
- Then: name昇順で一覧表示(ページネーションあり)。ransack検索対象は name / disp_name

### S-02: 登録(正常系)

- Given: ログイン済み
- When: name='Tda', twitter='tda_pmx', nico='12345', url='https://example.com' でPOSTする
- Then: authors に updated_by=操作者 の行が作成され、`/authors` へリダイレクト+
  notice「作者情報を登録しました。」。histories に item='作者' の行が追加される

### S-03: バリデーション

- When: 次の不正値でPOSTする
- Then: 登録されずフォーム再表示:
  | 項目 | ルール |
  |---|---|
  | name | 必須・最大100・ユニーク |
  | disp_name | 最大200 |
  | nico / pixiv | 正の整数のみ・最大20桁(空可) |
  | url | http(s)形式・最大250(空可) |
  | twitter | 最大30 |
  | email | メール形式・最大250(空可) |

### S-04: disp_name の自動補完

- Given: disp_name を空にして name='Tda' で登録する
- When: 保存する
- Then: disp_name='Tda' が保存される

### S-05: 使用中の作者は削除不可

- Given: credits に紐付いている author が存在する
- When: `DELETE /authors/:id` を実行する
- Then: 削除されず `/authors` へリダイレクト+
  alert「既に使用されている作者情報の為、削除できません。」

### S-06: 未使用の作者は削除可

- Given: credits に紐付いていない author が存在する
- When: `DELETE /authors/:id` を実行する
- Then: 物理削除され notice「作者情報を削除しました。」

## 検証上の注意

- S-06 は `delete`(コールバックなし)なので histories に削除の記録は残らない。
- name のユニーク制約はモデル検証のみでなくDB側にもユニークインデックスがある。

## 実装参照

- `app/controllers/authors_controller.rb`
- `app/models/author.rb#set_disp_name,add_history`
- 既存テスト: `spec/controllers/authours_controller_spec.rb`, `spec/models/author_spec.rb`

## 未確認事項

- ルートは `except: [:show]` だが `before_action :set_author` に `:show` が含まれる(不整合、実害なし)。
- credit_logs と authors の多対多(habtm)があり、削除可否判定は credits のみを見ている。
  過去ログにだけ登場する作者は削除でき、credit_logs 側の関連が浮く。
