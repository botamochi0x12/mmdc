# 02. 動画管理

## 概要

ログインユーザーが自分の動画を登録し、emm等のプロジェクトファイルを添付する。
動画一覧ではクレジット解決状況の集計4指標を表示する。削除は論理削除
([ADR 0005](../adr/0005-動画とユーザーの論理無効化.md))。

## 用語(集計4指標)

1動画内の使用オブジェクト(file_name+folder_name+extension で重複除去)について:

| 指標 | 定義 |
|---|---|
| total | 重複除去後の全オブジェクト数 |
| yets | wanted 未登録のオブジェクト数(3ユーザー閾値未達) |
| wants | wanted 登録済みだが credit 未登録のオブジェクト数 |
| resolveds | credit 登録済みのオブジェクト数 |

(total = yets + wants + resolveds)

## 前提条件

- ログイン必須(00-common 認可マトリクス)。
- ファイル解析の仕様は [03-emm-upload.md](03-emm-upload.md)。

## 振る舞い仕様

### S-01: 一覧表示

- Given: 自分の動画3件(is_show=true 2件・is_show=false 1件)と他ユーザーの動画1件が存在する
- When: `GET /videos` を表示する
- Then: 自分の is_show=true の2件のみが id 降順で表示され、各行に集計4指標が表示される

### S-02: ページネーション

- Given: 自分の is_show=true の動画が11件存在する
- When: `GET /videos` を表示する
- Then: 10件表示され、2ページ目に残り1件が表示される(kaminari, `paginates_per 10`)

### S-03: 動画登録(正常系)

- Given: ログイン済み
- When: `GET /videos/new` から name='テスト動画'、ファイルにemmを1つ以上添付してPOSTする
- Then: `videos` に user_id=自分, is_show=true の行が作成され、添付ファイルが解析される
  (03-emm-upload参照)。`/videos` へリダイレクトし notice「動画情報を登録しました。」

### S-04: 動画登録(ファイルなし)

- Given: ログイン済み
- When: name のみ入力しファイル無しでPOSTする
- Then: 登録されず new が再表示され、file に「は最低1つアップしてください。」のエラー

### S-05: 動画登録(name不正)

- Given: ログイン済み
- When: name が空、または101文字でPOSTする
- Then: バリデーションエラーで new が再表示される(presence / maximum:100)

### S-06: 動画名の更新

- Given: 自分の動画 name='旧名' が存在する
- When: `GET /videos/:id/edit` で name='新名' に変更しPATCHする
- Then: nameが更新され、動画詳細へリダイレクト

### S-07: 論理削除

- Given: 自分の動画(is_show=true)が存在する
- When: 一覧から削除を実行する(`DELETE /videos/:id`)
- Then: DBの該当行は残り is_show=false になる。一覧から消え、
  notice「動画情報を削除しました」が表示される

### S-08: 一括削除

- Given: 自分の動画が3件存在する
- When: ids=[id1, id2] を指定して `DELETE /videos/destroy_all` を実行する
- Then: 指定2件の is_show が false になり、`/videos` へリダイレクト

### S-09: 他ユーザーの動画へのアクセス

- Given: 他ユーザーの動画IDを知っている
- When: `GET /videos/:id`(show/edit/zip等)にアクセスする
- Then: `set_video` が user_id 条件で検索するため見つからず、エラーになる
  (`find_by` が nil を返し NoMethodError → 500。404ではない点に注意)

## 検証上の注意

- 集計4指標の検証は 03-emm-upload の3ユーザー閾値と組み合わせたデータ設計が必要。
  最小構成: ユーザーA/B/Cが同一オブジェクトを含む動画を持つ(→wanted化)+Aのみのオブジェクト(→yet)。
- S-09 の「500になる」挙動は現状仕様として記録する(E2Eでは 200 でないことを確認する程度に留める)。

## 実装参照

- `app/controllers/videos_controller.rb`
- `app/models/video.rb#set_total,delete_by_ids`
- 既存テスト: `spec/controllers/videos_controller_spec.rb`, `spec/models/video_spec.rb`

## 未確認事項

- `destroy_all` は ids が nil の場合 `where(id: nil)` となり何も起きない(エラーにもならない)。
- 一括削除は所有者チェックがなく、**他人の動画IDを ids に含めれば論理削除できる**
  (`Video.delete_by_ids` は user_id を見ない)。脆弱性の疑い。
