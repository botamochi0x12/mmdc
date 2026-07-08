# 07. クレジット一覧ダウンロード(zip)

## 概要

動画1件について、使用オブジェクトのクレジット一覧csvとコンテンツツリー登録支援txtを
zipでダウンロードする。本サービスの最終成果物。
形式の背景は [ADR 0007](../adr/0007-zip成果物-windows31j-csvとコンテンツツリーtxt.md)。

## 用語

| 用語 | 意味 |
|---|---|
| must | どの動画でも必須のクレジット項目(MMD本体等)。`musts` テーブルで管理 |
| mustカテゴリ | `all`(常時) / `mmd`(emm動画) / `mmm`(xml・mpj動画) |
| コンテンツツリー | ニコニコ動画の親子作品登録機能。作品IDで登録する |

## 前提条件

- ログイン必須。対象は自分の動画のみ(`set_video` が user_id 条件)。
- `musts` テーブルにカテゴリ別の定番データが投入されていること。

## 振る舞い仕様

### S-01: zipダウンロード

- Given: 自分の動画(name='テスト動画')にemm由来のオブジェクトが存在する
- When: `GET /videos/:id/zip` にアクセスする
- Then: `Content-Type: application/zip` で
  `{URLエンコード済み動画名}_{YYYYMMDDhhmmss}.zip` がダウンロードされ、
  展開すると `credit.csv` と `tree.txt` の2ファイルが含まれる

### S-02: credit.csv の内容

- Given: musts(category='all', name='MikuMikuDance', author_name='樋口M', video='sm1097445')1件と、
  動画に credit解決済みオブジェクト1件(credit.name='Tda式初音ミク', 作者disp_name='Tda',
  distribution='td14712', 拡張子pmx)、未解決オブジェクト1件(file_name='mystage.x')がある
- When: zipをダウンロードし credit.csv を Windows-31J で読む
- Then: 内容は次の通り:
  ```csv
  名前,作者,配布先,拡張子,ステータス
  MikuMikuDance,樋口M,sm1097445,,○
  Tda式初音ミク,Tda,td14712,pmx,○
  mystage.x,,,x,×
  ```
  (must行が先頭、以降は拡張子昇順→モデル名昇順。credit無しは file_name が名前になり×)

### S-03: 複数作者の連結

- Given: credit に作者が2人(disp_name='Tda', 'かこみき')紐付いている
- When: csvを確認する
- Then: 作者列は `Tda/かこみき`(disp_name昇順・`/`区切り)

### S-04: tree.txt の内容

- Given: musts の video='sm1097445' と、distribution が入った credit が12件ある
- When: tree.txt を確認する
- Then: 計13個の作品IDが空白区切りで並び、10個ごとに改行される(1行目10個・2行目3個)。
  distribution が空文字の credit は含まれない

### S-05: mustカテゴリの選択

- Given: musts に category='all'/'mmd'/'mmm' の行が各1件ある
- When: (a) emmのみの動画 (b) xml添付の動画 のzipをそれぞれダウンロードする
- Then: (a) には all+mmd の行、(b) には all+mmm の行が含まれる

### S-06: 論理削除済み動画の除外

- Given: is_show=false の自分の動画
- When: `GET /videos/:id/zip` にアクセスする
- Then: `set_video` は is_show を見ないためzip自体は生成されるが、
  集計SQLが is_show=true 条件を含むため **csvはmust行のみ**になる

## 検証上の注意

- csvは Windows-31J。テストでは `CSV.read(path, encoding: 'Windows-31J:UTF-8')` 等で読む。
- ファイル名のタイムスタンプは実行時刻依存。E2Eではファイル名パターン
  (`/_\d{14}\.zip$/`)で検証する。
- zip生成後の一時zipは `Rails.root/tmp` に残る。テストのteardownで掃除すること。

## 実装参照

- `app/controllers/videos_controller.rb#zip`
- `app/models/video.rb#create_dl_zip,create_csv,create_tree_txt,get_dl_video_info,get_three_info,csv_column_names`
- `app/models/must.rb#select_musts`

## 未確認事項

- S-06 の「論理削除済みでもzipは落とせる(中身は空)」は仕様か漏れか不明。
- モデル名等に Windows-31J 非対応文字が含まれる場合の挙動(例外の可能性、ADR 0007参照)。
