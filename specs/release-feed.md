# リリースフィード仕様書（release feed / 更新通知）

## 1. 概要

Hapbeat のツール・SDK は PyPI / npm / UPM Git URL / PlatformIO / Web と**配布チャネルがばらばら**で、
「新しい版が出た」ことをユーザーが知る手段がチャネルごとに異なる（あるいは存在しない）。

本仕様は、全プロダクトの「いま取得できる最新版」を **1 つの静的 JSON（release feed）** に集約する形式と、
それを読むクライアント（Studio / helper / 各 SDK）が守るべき**更新通知の作法**を定義する（DEC-053）。

対象外:

- **デバイスファームウェア** — 既に [firmware-distribution.md](./firmware-distribution.md) の統合 manifest が
  「最新 + アーカイブ」を配信しており、Studio はそれをローカルに持っている。二重管理を避けるため
  release feed には載せず、更新通知は firmware manifest との比較で行う。
- **プロトコル互換性** — 「この版未満だと動かない」という要求関係はペア固有（例: Studio → helper）なので、
  要求する側のビルド定数が source of truth（[versioning.md](./versioning.md)）。feed は互換性を宣言しない。

## 2. 配信

| 項目 | 値 |
|---|---|
| URL | `https://devtools.hapbeat.com/releases.json` |
| 生成 | `hapbeat-devtools-site` の CI（deploy 時 + 各 repo の release 通知時） |
| Content-Type | `application/json` |
| CORS | `Access-Control-Allow-Origin: *`（ブラウザから読む Studio のため必須） |
| Cache-Control | `max-age=1800`（再生成は deploy 単位。30 分の陳腐化は許容） |

feed の各エントリは、**GitHub のタグではなく実際の配布チャネル**（PyPI / npm / PlatformIO registry）を
情報源とする。「タグは打ったが publish に失敗している」版を通知して `pipx upgrade` しても上がらない、
という事故を防ぐため。配布チャネルが git そのものであるもの（UPM Git URL）だけ GitHub Releases を見る。

## 3. スキーマ

`schemas/release-feed.schema.json` を正とする。

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-02T00:00:00Z",
  "products": {
    "helper": {
      "name": "hapbeat-helper",
      "channel": "pypi",
      "latest": "0.3.1",
      "published_at": "2026-07-28T00:00:00Z",
      "severity": "info",
      "upgrade": "pipx upgrade hapbeat-helper",
      "notes": "https://devtools.hapbeat.com/docs/tools/helper/changelog/"
    },
    "unity-sdk": {
      "name": "Hapbeat Unity SDK",
      "channel": "upm-git",
      "latest": "0.3.0",
      "published_at": "2026-07-26T00:00:00Z",
      "severity": "info",
      "upgrade": "https://github.com/Hapbeat/hapbeat-unity-sdk.git#v0.3.0",
      "notes": "https://devtools.hapbeat.com/docs/sdk-integration/unity-sdk/changelog/"
    }
  }
}
```

### 3.1 トップレベル

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `schema_version` | integer | ✓ | 現在 `1`。破壊的変更で増やす |
| `generated_at` | string (ISO 8601 UTC) | ✓ | 生成時刻 |
| `products` | object | ✓ | プロダクト ID → エントリ |

### 3.2 products エントリ

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `name` | string | ✓ | 表示名（配布チャネル上の名前） |
| `channel` | enum | ✓ | `pypi` / `npm` / `upm-git` / `platformio` / `web` |
| `latest` | string | ✓ | semver。**先頭 `v` を含まない正準形** |
| `published_at` | string (ISO 8601) | | リリース日時。取得できない場合は省略 |
| `severity` | enum | ✓ | `info`（通常）/ `recommended`（重要な修正を含む） |
| `upgrade` | string | | 更新コマンド、または更新先 URL |
| `notes` | string (URL) | | 変更履歴ページ |

プロダクト ID は repo 名から `hapbeat-` を除いたもの（`helper` / `studio` / `unity-sdk` /
`python-sdk` / `js-sdk` / `arduino`）。

### 3.3 欠落の扱い

生成時に配布チャネルへの問い合わせが失敗したプロダクトは、**エントリごと省略する**（古い値や
プレースホルダを載せない）。クライアントは欠落を「不明」として扱い、**何も表示しない**。
「最新版が取得できませんでした」という通知自体がノイズになるため、失敗は常に静かに握る。

## 4. 版の比較

- semver の数値セグメント比較。`0.3.10` > `0.3.9`。
- 開発ビルドの接尾辞（helper の `0.3.1d4` 等）は**除去してから**比較する。`0.3.1d4` は `0.3.1` と同値。
  → 開発ビルドを使っている人に「同じ版へ更新しろ」と促さない。
- 先頭の `v` は比較前に除去する（feed 側は正準形で持つが、クライアントの手持ち値には付き得る）。
- 解釈できない文字列は「比較不能」とし、**通知しない**方に倒す。

## 5. 更新通知ポリシー（全クライアント共通）

「気付いてほしい」と「邪魔をしない」を両立させるため、以下を全クライアントの必須要件とする。

### 5.1 繰り返してよい頻度は「閉じる操作の有無」で決まる

**閉じる操作を要求する表示**（バナー / チップ / バッジ）と、**視界の端を流れるだけの表示**
（Console や起動ログの 1 行）では、繰り返してよい頻度が違う。前者は繰り返すと「作業を止めて
消す」コストが毎回かかるが、後者にそのコストは無く、むしろ一度見逃したら二度と出ない方が害が大きい。

#### A. 閉じる操作があるもの（バナー / チップ / バッジ）— 1 版につき 1 回

- ユーザーが閉じたら、**その版に対しては二度と表示しない**。
- より新しい版が出たら、また 1 回だけ表示してよい。
- 実装: 閉じた時点の `latest` を永続化し、`compare(latest, dismissed) <= 0` の間は抑制する。
  永続化先はクライアント依存（localStorage / EditorPrefs / 状態ファイル）。
- **セッション単位の抑制にしてはならない**。起動のたびに閉じさせるのは「毎回手動で消させる」ことであり、
  意図的に版を固定している開発者にとって純粋なノイズになる。

#### B. 閉じる操作が無いもの（Console / 起動ログの 1 行）— 実行単位で 1 回

- 版ごとの永続抑制は**しない**。閉じる操作が無い＝コストが無いので、見逃しの方が損失。
- ただし**同じ実行の中で繰り返さない**こと。目安:

| 実行形態 | 頻度 |
|---|---|
| エディタ拡張（Unity Editor 等） | プロセス（セッション）ごとに 1 回。**domain reload で重複させない** |
| 常駐デーモンの起動ログ | 起動ごとに 1 回（起動自体が稀なので抑制不要） |
| 短命 CLI（連続実行され得るもの） | 24 時間ごとに 1 回。ただし版が変わったら即出す |

### 5.2 通知は受動的な場所に置く

| 置いてよい | 置いてはいけない |
|---|---|
| dismissible なバナー / バッジ / 1 行ログ | モーダルダイアログ |
| 「見に行く場所」（設定画面・管理モーダル・メニュー）での常時表示 | 起動をブロックする確認 |
| 既存 UI の余白（レイアウトを動かさない位置） | 既存要素を押し下げる差し込み |

- 「見に行く場所」に出す常時表示は 5.1 の対象外（ユーザーが能動的に開いた画面なので邪魔にならない）。
- バナー等を出す場合、既存要素を押し下げてレイアウトを動かさないこと（workspace UI ルール）。

### 5.3 severity と出し方

| severity | 出し方 |
|---|---|
| `info` | バッジ / 1 行ログ程度。バナーを出さない |
| `recommended` | dismissible バナー可。§5.1 A の 1 版 1 回は同じく必須 |

「動かなくなる」レベルの互換要求（`MIN_HELPER_VERSION` 等）は feed の対象外で、
要求側が自前で警告する。こちらは §5.1 A の対象だが、**ステータス表示（接続 pill の色など）は
dismiss 後も維持**してよい（通知ではなく状態の表示のため）。

同じ用件を「目立つ UI」と「テキスト 1 行」の両方で同時に出さないこと。どちらも読まれなくなる。

### 5.4 取得の作法

| 要件 | 値 |
|---|---|
| タイムアウト | 3 秒以内 |
| 失敗時 | 完全にサイレント（ログにも警告を出さない） |
| キャッシュ | 24 時間以上（Studio のような常駐 Web UI は 6 時間以上） |
| 実行タイミング | 起動時・非同期。処理をブロックしない |
| opt-out | 環境変数またはフラグで無効化できること |

**ライブラリの import / require ではネットワークアクセスをしてはならない。** チェックしてよいのは
CLI 実行時・デーモン起動時・エディタ拡張の初期化時のみ。CI やオフライン環境で
`import hapbeat` が外部通信するのは副作用として不適切。

## 6. 生成側の責務

`hapbeat-devtools-site` が唯一の生成者。

1. 各配布チャネルへ問い合わせ、`latest` / `published_at` を得る。
2. `severity` は既定 `info`。重要な修正を含む版だけ、生成側の設定で `recommended` に上書きする。
3. 失敗したプロダクトは省略（§3.3）。ビルドは失敗させない。
4. 再生成のトリガ:
   - devtools-site の `master` push / deploy
   - 各 repo の release workflow からの `repository_dispatch`（`release-published`）

## 7. 変更履歴

### 2026-08-02 — 新規制定（DEC-053）

- release feed の配信・スキーマ・更新通知ポリシーを規定。
- firmware は既存の統合 manifest に委ね、feed の対象外とした。
