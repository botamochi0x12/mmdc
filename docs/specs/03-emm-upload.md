# 03. emmアップロード・解析

## 概要

動画登録時に添付された emm / xml / mpj ファイルを解析し、使用オブジェクトを
`mmd_objects` に登録する。条件を満たしたオブジェクトは `wanteds` へ昇格する。
方式の背景は [ADR 0002](../adr/0002-emm解析のサービス層同期実行.md)、
昇格条件は [ADR 0003](../adr/0003-ファイル名完全一致照合と3ユーザー閾値wanted昇格.md)。

## 用語

| 用語 | 意味 |
|---|---|
| emm | MikuMikuEffectが保存するINI形式のプロジェクトファイル(Windows-31J) |
| mpj | MikuMikuMovingのプロジェクト(36byteヘッダ+zlib圧縮XML) |
| mmd_object | 解析で得た使用ファイル1件(full_path/file_name/folder_name/extension) |
| wanted昇格 | mmd_object と同名ファイルの使用者が3人以上になった時に wanteds へ登録すること |

## 前提条件

- `config/secrets.yml` の `save_dir_path` が書き込み可能なディレクトリを指している。
- 解析は動画登録(`POST /videos`)の中で同期実行される。

## 振る舞い仕様

### S-01: emm(INI)の解析

- Given: 以下の内容のemmファイル(Windows-31J):
  ```ini
  [Info]
  Version = 3
  [Object]
  Pmd1 = C:\mmd\models\Tda式ミク\Tda式初音ミク.pmx
  Acs1 = C:\mmd\accessory\stage01\stage.x
  [Effect]
  Default = none
  Obj1 = C:\mmd\effects\ray\ray.x
  ```
- When: このファイルを添付して動画を登録する
- Then: `mmd_objects` に3件登録される。例1件目:
  full_path='C:/mmd/models/Tda式ミク/Tda式初音ミク.pmx', file_name='Tda式初音ミク.pmx',
  folder_name='Tda式ミク', extension='pmx'。`Default = none` は登録されない

### S-02: スキップ値

- Given: `[Object]` セクションの値が空 / `none` / `true` / `false` の行を含むemm
- When: 動画を登録する
- Then: それらの行は mmd_objects に登録されない

### S-03: xml(MikuMikuMoving)の解析

- Given: `MMProject/Models` 配下に `Model`/`Accessory`/`Effect` 要素を持ち、
  各要素の `File` にフルパスが入ったxmlファイル
- When: `.xml` 拡張子で添付して動画を登録する
- Then: 各 File 値が mmd_objects 化される(`\` は `/` に置換)

### S-04: mpjの解析

- Given: 先頭36バイトのヘッダに続き S-03 相当のXMLを zlib 圧縮した `.mpj` ファイル
- When: 添付して動画を登録する
- Then: 展開後のXMLがS-03と同様に解析される

### S-05: 同一emm内の重複排除

- Given: 同じ folder_name + file_name を2行含むemm
- When: 動画を登録する
- Then: mmd_objects には1件だけ登録される

### S-06: wanted昇格(3ユーザー閾値)

- Given: ユーザーA・Bがそれぞれ folder_name='Tda式ミク', file_name='Tda式初音ミク.pmx' を含む
  動画を登録済みで、wanteds に該当行がない
- When: ユーザーCが同じファイルを含む動画を登録する
- Then: wanteds に file_name='Tda式初音ミク.pmx', folder_name='Tda式ミク', extension='pmx' が
  1件作成され、histories に item='Wanted' の行が追加される。
  (ユーザーBの登録時点=2人では作成されない)

### S-07: 解析失敗行のスキップ

- Given: 拡張子のないパス(例 `C:\mmd\models\readme`)を含むemm
- When: 動画を登録する
- Then: その行は登録されず、`log/` に警告「emm解析失敗 ...」が出力される。
  他の行の登録は継続される

### S-08: 原本保存

- Given: S-01のemmを添付する(ログインユーザー id=5)
- When: 動画を登録する
- Then: `save_dir_path` に `5_{YYYYMMDDhhmmss}_0.emm` が保存され、内容はUTF-8変換済み・
  `\`→`/`・`#`→`＃` 置換済み。emms.original_name に元ファイル名、save_file_name に保存名が入る

## 検証上の注意

- emmフィクスチャは**必ずWindows-31Jで**作成する(UTF-8だと `copy_file` の変換が壊れる)。
  作成例: `File.write(path, content.encode('Windows-31J'))`。
- mpjフィクスチャ生成例: `36.times.map{0}.pack('C*') + Zlib::Deflate.deflate(xml_string)`
  (実ファイルのヘッダ構造は解析側が無視するため36バイトはダミーで可)。
- S-06 は「3人の**動画所有者**」が条件(同一ユーザーの複数動画ではカウント1)。
- wanted昇格判定は is_show を見ないため、論理削除済み動画も母数に入る(ADR 0005)。

## 実装参照

- `app/services/upfile_manage_service.rb`(拡張子振り分け)
- `app/services/emm_regist_service.rb#save_emm,analyze_emm,createMmdObject,createWanted,is_wanted,copy_file`
- `app/services/xml_regist_service.rb` / `app/services/mpj_regist_service.rb`
- 既存テスト: `spec/models/emm_spec.rb`

## 未確認事項

- `EmmsController#create` は `EmmRegistService.save`(未定義メソッド)を呼んでおり、
  `/emms/new` からの単独アップロードは **NoMethodError で常に失敗する**と推定される。
  実運用経路は動画登録(`UpfileManageService.save`)のみ。修正または画面撤去の判断が必要。
- 拡張子判定は小文字前提(`.EMM` 等大文字拡張子は EmmRegistService に流れるため動くが、
  `.XML` はINIとして解析されて空振りする)。
