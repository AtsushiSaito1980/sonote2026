---
description: brief.yaml から台本・TTS稿・note記事・検査レポートまでを一気に作る
argument-hint: <episode_id>
---

# エピソード制作：$1

`episodes/$1/brief.yaml` と `episodes/$1/sources/` を入力に、以下を順に実行する。

## ゲート0（開始前）
- `sources/` が空 → **生成せずに停止**
- **`duration_min` が 6 でない → 6 に直してから始める。**2026-08改の標準は6分（1,900〜2,200字）。
  拡大版（総集編・特集）を人間が明示して指定したときだけ例外
- `anchor.published` が制作日から31日超 → **停止**して、より新しいトリガを探すか `trigger_wait` に回すか人間に確認
- **`ledger/selection.yaml` にこの回の採点が無い → 停止。**`/patrol` の採点を先に記録する
- 採点の**核（Q1／Q2）が両方 ✗ → 停止して人間に確認。**儲けている主体も動機を持つ人も出てこない回は、
  番組の2つの問いに答えられない（ep011 の轍）
- `region` が `海外` → **CLAUDE.md §9 の5つの追加ルールを先に読む。**
  出所が海外になるだけで、**台本も記事も日本語**。英語一次に当たる／通貨は原通貨（記号は書かない）／
  固有名詞は初出だけカタカナ／制度は地形として扱う／**解剖の三点のうち1つは日本の業界への置き換え**。
  台帳 `episodes_log.csv` の `region` 列も忘れずに `海外` で埋める（ばらつきが別勘定になる）

## 実行順

1. **extract-facts** → `facts.yaml`（★以降、原文は一切渡さない）
2. **write-outline** → `outline.md`
3. **write-script** → `script_draft.md`
   - 書く前に `personas/{host}.md` と `episodes/` の直近2〜3本を必ず読む
   - **6分・咀嚼の3拍・平均文長18字以下・フィラー15〜20個。**字数の下限は
     事実ではなく咀嚼で埋める（`library/episode_types.md` の「語りの作り」）
4. **review-episode** → `python3 scripts/check.py episodes/$1` を実行 → `review.md`
   - FAIL → 3へ差し戻し（最大2周、それで通らなければ人間へ）
5. **tts-format** → `script_tts.txt`
   - 書いたら `python3 scripts/dictionary.py --apply $1` で辞書を当てる。
     過去の回の誤読を繰り返さないための工程で、check.py の「辞書の適用」が FAIL で止める
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
   - **書き出すのは `docs/` の側なので、figures.html を直したら先に `build_site.py`。**
     直さずに書き出すと、前の図が出てくる
   - **`⚠ 文字が重なっています` が出たら直して書き出し直す。**
     SVGのラベルは実際の描画位置で重なりを見ている。2行に分けるか viewBox を広げる
   - 書き出したら **もう一度 `build_site.py`** を実行する（ダウンロード欄が出る）

## 完了後の報告
- 検算結果のサマリ（PASSした項目数・要判断の判断根拠）
- **人間がやること**：単独出典の裏取り／TTS通し聴取／制作日依存の表現の確認
  - 聴いて誤読が出たら、読みを決めて `library/dictionary.yaml` に足す（読みは人間しか決められない）
  - そのあと `python3 scripts/dictionary.py --collect --write` で、この回で開いた語を辞書へ回収する
- `ledger/episodes_log.csv` に1行追記する
  - **`created_on` は制作した日（today）を書く。**アーカイブの時系列はこの列で並ぶ
  - `air_date` は公開予定日の目安。**実際に出すかどうかは人間が決める**ので、ここが埋まっていても公開済みを意味しない
- 巡回で選ばれなかった候補を `ledger/backlog.yaml` に書き戻す（`/patrol` の手順4）
