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
7. **write-infographic** → `infographic.html`（**省略不可**）
   - 書かないとサイトが `facts.yaml` からの簡易ビューに落ちる
   - 数値は事実カードにあるものだけ。図の種類は内容で選ぶ
8. **サイト再生成** → `python3 scripts/build_site.py`
   - 出力の `[インフォグラフィック: 手作り]` を確認する。`自動` なら7が漏れている

## 完了後の報告
- 検算結果のサマリ（PASSした項目数・要判断の判断根拠）
- **人間がやること**：単独出典の裏取り／TTS通し聴取／制作日依存の表現の確認
- `ledger/episodes_log.csv` に1行追記する
- 巡回で選ばれなかった候補を `ledger/backlog.yaml` に書き戻す（`/patrol` の手順4）
