# 移植手順（技術寄り）

> **初めての方・スマホ運用が目的の方は `START-HERE.md` を先に読んでください。**
> 本書はターミナルを使う場合の手順と、つまずき対応をまとめたものです。


## Step 0. ファイルをMacに持ってくる

チャット内の各ファイルカードからダウンロードする（Macのブラウザで claude.ai を開き、同じ会話を表示するのが早い）。必要なもの：

- 企画書 v3.5 → `docs/plan.md` にリネーム
- ep001〜ep006 の各ファイル（brief / facts / script_draft / script_tts / article / shownotes / review）
- `ledger/episodes_log.csv`
- 本雛形（sonote/ 一式）

## Step 1. リポジトリ化

```bash
cd ~/dev/sonote
git init && git add -A && git commit -m "init: 企画書v3.5 + パイロット6本"
gh repo create sonote --private --source=. --push   # 任意
```

## Step 1b. ブラウザの Claude Code で使う場合

クラウドセッションは**GitHub からクローンして始まる**ため、初回コミットだけは
ターミナルか GitHub の画面アップロードで済ませておく必要がある（VM はローカルマシンからは取得しない）。

1. claude.ai/code → GitHub を接続 → `sonote` を選択
2. 動作確認を3つ：`CLAUDE.md の禁止事項を教えて` / `python3 scripts/check.py episodes/ep003` / `/patrol`
3. 以後の作業はブランチ＋PR として提案される。**マージ＝公開キュー**として運用する
4. セッションはブラウザを閉じても継続し、Claude モバイルアプリから監視・操作できる
5. Mac に引き取りたいときは `claude --teleport`

### クラウド特有の確認点

- **ネットワーク**：Anthropic ホスト環境では既定でアクセスが制限される。`/patrol` が巡回先に届かない場合、cloud environment の許可ドメインを広げる
- **Python**：`scripts/check.py` が動くかを最初のタスクで確認する
- **TTS と通し聴取だけはクラウドの外**：`script_tts.txt` を GitHub 上で開いてコピーする

## Step 2. Claude Code の設定

```bash
cd ~/dev/sonote
claude
```

- **WebSearch / WebFetch を許可**（トリガ巡回に必須）
- `/patrol` `/episode` がコマンドとして出るか確認
- 初回は `/patrol` だけ回して、候補の質を見る

## Step 3. 検算スクリプトの動作確認

```bash
python3 scripts/check.py episodes/ep003    # PASS が出れば正常
python3 scripts/check.py episodes/ep006
```

既存6本で PASS しなければ、スクリプト側のパターンを直す（台本ではなく）。

## Step 4. 1本を手動で通す

`/episode ep007` を実行し、brief 記入 → 生成 → check → TTS まで人手で確認する。
**ここで文体が崩れたら、原因はほぼ「過去回を読ませていない」**。write-script が `episodes/` の直近2〜3本を読んでいるか確認する。

## Step 5. 日課にする（Step 4 が安定してから）

- 朝：`/patrol` → 候補から1本選び brief 記入（5分）
- 生成：`/episode` を回す（自動）
- 昼：TTS 生成 → 通し聴取 → 誤読を dictionary に追記 → 公開（10分）

## Step 6. 自動化（急がない）

安定してから、以下のどれかを足す。最初から作らない。

- **GitHub をキューにする**：巡回結果を Issue 化 → ラベルで選択、原稿を PR → **マージが公開トリガー**。監査証跡が自動で残る（著作権面でも有効）
- **定時実行**：朝の `/patrol` をスケジュール実行し、候補だけ用意させる
- 承認UIの自作は不要。GitHub で足りる

## つまずきやすい点

| 症状 | 原因 |
|---|---|
| 文体が説明調・キメ台詞が出る | 過去回を読ませていない／CLAUDE.md 禁止事項9が効いていない |
| 文字数が毎回下限割れ | facts が薄い。sources を増やすか density を balanced に固定 |
| 数字が多すぎる | 「系統」で数えていない。review.md に数え方の規約を書かせる |
| TTS が英字を読み違える | tts-format がカタカナ展開していない。dictionary.yaml に追記 |
| 同じ手ばかり出る | /patrol が ledger を読んでいない。6棚を全部舐めさせる |
