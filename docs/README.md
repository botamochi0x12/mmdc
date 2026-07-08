# MMDクレジット ドキュメント索引

現行コードベース(Rails 5.1 / Ruby 2.5 / MySQL 5.5)から逆起こしした要件ドキュメント。
2026-07-04 時点のコードを正とする。

## ADR(アーキテクチャ決定記録)

現状追認のADR。各決定の「なぜ」と帰結を記録する。

| ADR | 内容 |
|---|---|
| [0001](adr/0001-twitter-omniauth認証と署名cookie自動ログイン.md) | Twitter OmniAuth単独認証と署名Cookie(14日)による自動ログイン |
| [0002](adr/0002-emm解析のサービス層同期実行.md) | emm/xml/mpj 3形式の解析を継承ベースのサービス層で同期実行 |
| [0003](adr/0003-ファイル名完全一致照合と3ユーザー閾値wanted昇格.md) | file_name+folder_name+extension 完全一致照合と3ユーザー閾値のwanted昇格 |
| [0004](adr/0004-集計照合クエリの生SQL実装.md) | 多段JOIN集計を生SQL(MySQL方言)で実装 |
| [0005](adr/0005-動画とユーザーの論理無効化.md) | 動画は is_show、ユーザーは is_ban による論理無効化 |
| [0006](adr/0006-credit_logとhistoriesによる変更監査.md) | credit_logs(構造化監査)と histories(操作フィード)の2系統履歴 |
| [0007](adr/0007-zip成果物-windows31j-csvとコンテンツツリーtxt.md) | DL成果物は Windows-31J csv + コンテンツツリーtxt の zip |
| [0008](adr/0008-コントローラ名ベースの認可制御.md) | コントローラ名ベースの認可と is_admin/is_ban フラグ |

## 機能仕様(E2Eテスト可能なGWT形式)

全シナリオは「Given=投入可能なデータ状態 / When=画面操作 / Then=観測可能な結果」で記述。
テスト基盤は中立(Capybara/Playwright いずれでも実装可)で、各書に検証上の注意を付記。

| 仕様 | 内容 |
|---|---|
| [00-common](specs/00-common.md) | 認可マトリクス・サイドバー統計・更新情報・ナビゲーション |
| [01-auth](specs/01-auth.md) | Twitterログイン・自動ログイン・ログアウト・BAN拒否 |
| [02-video](specs/02-video.md) | 動画CRUD・論理削除・一括削除・集計4指標(total/yets/wants/resolveds) |
| [03-emm-upload](specs/03-emm-upload.md) | emm/xml/mpj解析・mmd_objects登録・wanted自動昇格 |
| [04-wanted](specs/04-wanted.md) | クレジット募集一覧・検索・修正 |
| [05-credit](specs/05-credit.md) | クレジット登録/更新・作者自動作成・バリデーション・監査ログ |
| [06-author](specs/06-author.md) | 作者CRUD・disp_name補完・使用中削除ガード |
| [07-credit-download](specs/07-credit-download.md) | zipダウンロード(credit.csv / tree.txt) |
| [08-rank](specs/08-rank.md) | 貢献度ランキング(credit_logs件数・同点同順位) |
| [09-info](specs/09-info.md) | お知らせ(匿名閲覧・管理者編集・RSS/Atom) |
| [10-user-admin](specs/10-user-admin.md) | ユーザー管理・BAN |

## 文書化で見つかった要修正候補

各仕様の「未確認事項」から、バグ・脆弱性の疑いが強いものを抜粋:

1. **`DELETE /infos/:id` が匿名実行可能**(認可漏れ) — [09-info](specs/09-info.md), [ADR 0008](adr/0008-コントローラ名ベースの認可制御.md)
2. **`DELETE /videos/destroy_all` に所有者チェックがない**(他人の動画を論理削除可能) — [02-video](specs/02-video.md)
3. **`EmmsController#create` が未定義メソッド `EmmRegistService.save` を呼ぶ**(単独アップロード画面は常に失敗と推定) — [03-emm-upload](specs/03-emm-upload.md)

## 関連

- 設計書: [superpowers/specs/2026-07-04-requirements-adr-e2e-docs-design.md](superpowers/specs/2026-07-04-requirements-adr-e2e-docs-design.md)
- 実装計画: [superpowers/plans/2026-07-04-requirements-adr-e2e-docs.md](superpowers/plans/2026-07-04-requirements-adr-e2e-docs.md)
