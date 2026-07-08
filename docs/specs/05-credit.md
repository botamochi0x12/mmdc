# 05. クレジット登録・編集

## 概要

wanted に対して名前・作者・配布先を登録する、本サービスの中核機能。
誰でも編集できる共同編集モデルで、変更は監査ログに残る
([ADR 0006](../adr/0006-credit_logとhistoriesによる変更監査.md))。

## 用語

| 用語 | 意味 |
|---|---|
| credit | wanted 1件に対する正式なクレジット情報(名前・作者・配布先)。wanted と 1:1 |
| distribution | ニコニコの作品ID(sm/nm=動画, im=静画, td=立体)。コンテンツツリー登録に使う |
| 作者(author) | クレジットに紐付く製作者。credit とは多対多 |

## 前提条件

- ログイン必須。
- 登録対象の wanted が存在すること(新規登録は wanted 起点のみ)。

## 振る舞い仕様

### S-01: 新規登録(正常系)

- Given: credit未登録の wanted(id=10)が存在する
- When: `GET /credits/new/10` で name='Tda式初音ミク', author_names=['Tda'],
  distribution='td14712', url='https://example.com/dist' を入力しPOSTする
- Then: credits に wanted_id=10, updated_by=ログインユーザーid の行が作成され、
  `/wanteds` へリダイレクト+notice「クレジット情報を登録しました。」。
  同時に credit_logs 1行と histories(item='クレジット', is_create=true)1行が追加される

### S-02: 作者の自動作成と再利用

- Given: authors に name='Tda' が存在しない
- When: author_names=['Tda', '既存作者'] でクレジットを登録する
- Then: 'Tda' が authors に自動作成され(updated_by=操作者)、既存作者は既存行が紐付く。
  authors_credits に2行できる

### S-03: バリデーション

- Given: wanted 起点の新規登録フォーム
- When: 次の不正値でPOSTする
- Then: いずれも登録されずフォーム再表示:
  | 項目 | 不正値の例 | ルール |
  |---|---|---|
  | name | 空 / 101文字 | 必須・最大100 |
  | distribution | `abc123` / `sm` | `(sm|nm|im|td)+数字` のみ(空は可) |
  | url | `ftp://x` / 251文字 | http(s)形式・最大250(空は可) |
  | description | 256文字 | 最大255 |
  | author_names | [] / ['a','a'] / [101文字] | 1個以上・重複不可・各最大100 |

### S-04: distribution_url 変換

- Given: distribution がそれぞれ 'sm9', 'nm123', 'im456', 'td789' の credit
- When: クレジット表示・一覧を表示する
- Then: リンク先はそれぞれ `http://www.nicovideo.jp/watch/sm9`(nmも同様)、
  `https://seiga.nicovideo.jp/seiga/im456`、`https://3d.nicovideo.jp/works/td789`。
  形式外は リンクなし(nil)

### S-05: 更新と監査ログ

- Given: 既存 credit(name='旧名', updated_by=ユーザーA)がある
- When: ユーザーBが `GET /credits/:id/edit` で name='新名' に変更しPATCHする
- Then: credit の updated_by がBになり、credit_logs に新しいスナップショット行が追加される。
  `/credits` へリダイレクト+notice「クレジット情報を更新しました。」

### S-06: 実質無変更の保存

- Given: 既存 credit(updated_by=ユーザーA)
- When: ユーザーBが値を一切変えずPATCHする
- Then: updated_by はAのまま維持され、credit_logs は増えない

### S-07: 一覧と検索

- Given: credits が複数存在する
- When: `GET /credits` を表示する
- Then: name昇順で一覧表示(ページネーションあり)。ransack検索は
  wanted_file_name / wanted_folder_name / author_name / name

### S-08: 作者名オートコンプリート

- Given: authors に name='Tda' が存在する
- When: `GET /credits/autocomplete_author_name?term=Td` を呼ぶ
- Then: 'Tda' を含むJSON配列が返る(部分一致 `:full => true`)

### S-09: 削除は無効

- Given: 既存 credit
- When: `DELETE /credits/:id` を送る
- Then: 何も起きない(destroy は空実装。credit は削除できないのが仕様)

## 検証上の注意

- S-05/S-06 の監査検証は credit_logs の件数比較で行う(画面には出ない)。
- 楽観ロック(lock_version)があるため、E2Eで同一レコードを並行編集すると
  `ActiveRecord::StaleObjectError` になる。競合シナリオを書く場合は500になる点に注意
  (レスキュー処理なし)。
- author_names はフォーム上、複数入力欄(配列 `params['author_names']`)で送られる。
  permit外のトップレベルパラメータである点に注意(credit_params とは別に代入される)。

## 実装参照

- `app/controllers/credits_controller.rb`
- `app/models/credit.rb#set_author_id,check_changed,save_credit_log,validate_author_names,distribution_url`
- 既存テスト: `spec/controllers/credits_controller_spec.rb`, `spec/models/credit_spec.rb`

## 未確認事項

- ルートに `except: [:delete]` とあるが正しくは `:destroy`(タイポ)。そのため
  DELETE ルート自体は生きており、空実装の destroy が呼ばれる。
- 編集時のフォーム再表示(バリデーションエラー時)で author_names の入力値が
  復元されるかは画面確認が必要。
