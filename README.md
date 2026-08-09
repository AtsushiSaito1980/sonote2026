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

## 毎日の流れ（スマホ）

claude.ai/code で `sonote` を開き、

```
/patrol            → 今日の候補を出す
3番でいこう          → 1本選ぶ（ここだけが人間の仕事）
/episode ep007     → 台本・TTS原稿・note記事を作る
PRを作って           → 提案書が立つ。読んで Merge
```

そのあと `script_tts.txt` を ElevenLabs に貼り、**必ず一度通して聴いてから**公開する。
