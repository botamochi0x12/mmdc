# ADR 0006: credit_logとhistoriesによる変更監査

- Status: Accepted(現状追認 — 2026-07-04 にコードから逆起こし)
- 関連: [ADR 0005](0005-動画とユーザーの論理無効化.md), [specs/05-credit.md](../specs/05-credit.md), [specs/08-rank.md](../specs/08-rank.md)

## Context

クレジット情報は不特定のログインユーザーが誰でも編集できる(Wiki的な共同編集モデル)。
荒らしや誤編集に備えて「誰がいつ何をどう変えたか」を追える必要がある。
また、貢献してくれたユーザーを可視化(ランキング)するための集計基盤も欲しい。

## Decision

用途の異なる2つの履歴テーブルを持つ:

1. **`credit_logs` — クレジットの構造化変更履歴**
   - `Credit` の `after_save` で、作成時および実変更があった更新時に
     スナップショット(name/distribution/url/作者関連/user_id)を1行追加する
     (`app/models/credit.rb#save_credit_log`)。
   - 実変更の判定: 作成時以外は `lock_version_changed?` で判断。
     name/distribution/url/description のいずれも変わらない保存では `updated_by` も
     元の値に戻し(`#check_changed`)、ログを追加しない。
   - 貢献度ランキング(`RankingService`)はこのテーブルの user_id 別件数を集計する。
2. **`histories` — サイドバー表示用の操作フィード**
   - Credit / Author / Wanted の保存時に「何が作成/更新されたか」+遷移リンクを1行追加する
     (各モデルの `add_history`)。
   - `ApplicationController#get_side_info` が最新30件を全ページのサイドバーに表示する。
   - 外部キーを持たない非正規化テーブル(リンクはパス文字列)。

## Consequences

- 荒らし編集の事後追跡と、貢献の可視化が同じ仕組みで実現できる。
- **ランキングが credit_logs 件数ベースのため、クレジットを編集するほどポイントが増える**。
  微修正の繰り返しでポイントを稼げる余地がある(実変更チェックである程度抑制)。
- histories は参照整合性がなく、元レコードが消えるとリンク切れになる
  (credits は削除導線がないため実害は限定的)。
- ロールバック機能はない。credit_logs は「見る」ためのもので、復元はDB直接操作が必要。
