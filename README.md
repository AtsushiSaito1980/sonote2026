# その手があったか

平日毎日、5分の音声番組と独立した note 記事を作るリポジトリ。

## はじめての方

**→ `START-HERE.md` を読んでください。** GitHubとスマホだけで運用する手順を、専門用語なしで書いています。

## ファイルの役割

| ファイル | 中身 |
|---|---|
| `START-HERE.md` | 初めての人向けの手順書（まずこれ） |
| `SETUP.md` | 技術寄りの移植手順・つまずき対応 |
| `CLAUDE.md` | Claude が毎回読む制作ルール |
| `docs/plan.md` | 全仕様（企画書 v3.5） |
| `personas/` | ホスト2人と放送作家の設定 |
| `library/` | 手14・動機7・風5・型8・読み辞書 |
| `episodes/ep001〜006` | 完成済みの見本6本（文体はここで決まる） |
| `ledger/episodes_log.csv` | 放送済み台帳（同じネタの重複を防ぐ） |
| `scripts/check.py` | 台本の自動検算 |
| `inbox/ネタ集めの手引き.md` | **スマホに保存してチャットに添付するファイル。**巡回の外で拾ったネタを聞き出してもらう |
| `scripts/build_site.py` | 制作アーカイブサイト（docs/）の生成 |
| `docs/` | 全仕様 plan.md ＋ 生成済みの閲覧サイト |

## 毎日の流れ（スマホ）

claude.ai/code で `sonote` を開き、

```
/patrol            → 今日の候補を出す
3番でいこう          → 1本選ぶ（ここだけが人間の仕事）
/episode ep007     → 台本・TTS原稿・note記事を作る
PRを作って           → 提案書が立つ。読んで Merge
```

そのあと `script_tts.txt` を ElevenLabs に貼り、**必ず一度通して聴いてから**公開する。

## 巡回の外でネタを拾ったとき

`/patrol` が回るのは決まった6つの棚だけ。移動中や店先で見つけたものは、そこに載らない。

1. スマホの Claude（`claude.ai/code` ではなく普通のチャット）に `inbox/ネタ集めの手引き.md` を添付する
2. 聞かれるまま話して、「書き出して」と言う → `.md` が出てくる
3. それを `inbox/` に置いて、`/intake` → `python3 scripts/build_site.py`

サイトの「ネタ帳」に全文が出て、次の `/patrol` が未採点の新規候補として読む。
くわしくは `inbox/README.md`。

## 制作アーカイブサイト（docs/）

台本・note記事・インフォグラフィック・制作データを、日付とタイトルごとにブラウザで見られる静的サイト。

- **見る**：`docs/index.html` をブラウザで開くだけで動く（サーバ不要）
- **Web で見る**：<https://atsushisaito1980.github.io/sonote2026/>
  - main に push するたび `.github/workflows/pages.yml` がサイトを作り直して自動公開する
  - すぐ反映したいときは Actions タブ →「Deploy archive site to GitHub Pages」→ Run workflow
  - Pages の設定（Settings → Pages → Source =「GitHub Actions」）は設定済み。作り直すときはこの設定が要る（ワークフローからは自動化できない）
  - **サイトは URL を知っていれば誰でも読める**（閲覧制限つき Pages は Enterprise 限定）。未放送の台本を出したくない期間は Settings → Pages で公開を止める
- **各回のページ**：インフォグラフィック（図解）／note記事（Markdownコピー付き）／台本（**ワンボタンで ElevenLabs 用にコピー**・概要欄コピー付き）／**読み上げ**（下記）／制作ファイル（brief・事実カード・検査レポート・ドラフト）
- **読み上げページ**（`read.html`）：**タグも注釈も無い、台本の本文だけ。**ブラウザの音声読み上げで聴くためのページで、**間を置くところが、そのまま改行になっている**（読み上げ機能は段落の切れ目で息を入れるため）。ページ内の「読み上げる」を押すとブラウザ内蔵の音声で再生し、そのときだけ短い間と長い間が区別される。元は `script_tts.txt` なので**読み辞書の読みが当たった状態**で読まれる（目で追うと仮名が多いのはそのため）
- **再生成**：`python3 scripts/build_site.py`（episodes/ と ledger/ から docs/ を作り直す。plan.md には触れない）
- **インフォグラフィックの原稿**は `episodes/epNNN/infographic.html`（本文フラグメント）。無い回は facts.yaml から簡易版が自動生成される
- 新しいエピソードを作ったら、再生成して docs/ もコミットする
