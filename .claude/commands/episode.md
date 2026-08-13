---
description: brief.yaml から台本・TTS稿・note記事・検査レポートまでを一気に作る
argument-hint: <episode_id>
---

# エピソード制作：$1

`episodes/$1/brief.yaml` と `episodes/$1/sources/` を入力に、以下を順に実行する。

## ゲート0（開始前）
- `sources/` が空 → **生成せずに停止**
- `anchor.published` が制作日から31日超 → **停止**して、より新しいトリガを探すか `trigger_wait` に回すか人間に確認

## 実行順

1. **extract-facts** → `facts.yaml`（★以降、原文は一切渡さない）
2. **write-outline** → `outline.md`
3. **write-script** → `script_draft.md`
   - 書く前に `personas/{host}.md` と `episodes/` の直近2〜3本を必ず読む
4. **review-episode** → `python3 scripts/check.py episodes/$1` を実行 → `review.md`
   - FAIL → 3へ差し戻し（最大2周、それで通らなければ人間へ）
5. **tts-format** → `script_tts.txt`
6. **write-article** → `article.md` ＋ `shownotes.md` → 再度 review
   - 書く前に `episodes/` の直近3本の**タイトルの語尾**を見る（同じ型を3本続けない）
7. **write-infographic** → `infographic.html`（**省略不可**）
   - 書かないとサイトが `facts.yaml` からの簡易ビューに落ちる
   - 数値は事実カードにあるものだけ。図の種類は内容で選ぶ
8. **write-figures** → `figures.html`（**省略不可**）
   - note に貼る図版3枚（`cover` / `combo` / `number`）
   - これが無いと、note へ持っていく画像が1枚も無い状態になる
9. **サイト再生成** → `python3 scripts/build_site.py`
   - 出力の `[インフォグラフィック: 手作り]` を確認する。`自動` なら7が漏れている
10. **画像の書き出し** → `python3 scripts/export_figures.py $1`
   - `docs/$1/images/` に PNG が出る。見出し画像は 1280×670
   - 書き出したら **もう一度 `build_site.py`** を実行する（ダウンロード欄が出る）

## 完了後の報告
- 検算結果のサマリ（PASSした項目数・要判断の判断根拠）
- **人間がやること**：単独出典の裏取り／TTS通し聴取／制作日依存の表現の確認
- `ledger/episodes_log.csv` に1行追記する
  - **`created_on` は制作した日（today）を書く。**アーカイブの時系列はこの列で並ぶ
  - `air_date` は公開予定日の目安。**実際に出すかどうかは人間が決める**ので、ここが埋まっていても公開済みを意味しない
- 巡回で選ばれなかった候補を `ledger/backlog.yaml` に書き戻す（`/patrol` の手順4）
