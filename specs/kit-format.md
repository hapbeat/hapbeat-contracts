# Kit フォーマット仕様

## 用語注記

- 本文書で定義する触覚コンテンツの配布単位を **Kit** と呼称する
- 旧称 "Pack" は 2026-04-25 に **Kit** へ統一された。新規ドキュメント・実装は Kit のみ使用する（履歴は git log を参照）

## 1. 概要

Kit は Hapbeat デバイス向け触覚コンテンツの配布単位である。wav クリップファイル、manifest（メタデータおよび Event ID とクリップの対応表）、UI アセット等をひとつのディレクトリにまとめたローカル資産パッケージとして構成される。

Kit を差し替えるだけでデバイスの触覚体験を変更でき、ファームウェアの更新は不要である。

## 2. 設計原則

| 原則 | 説明 |
|------|------|
| ファームウェア更新不要 | コンテンツ変更は Kit の差し替えのみで完結する。ファームウェアの再ビルド・再書き込みは必要ない。 |
| オフライン動作 | Kit はすべてローカルに保持される。ネットワーク接続なしで動作する。 |
| プラットフォーム中立 | Kit のディレクトリ構造・manifest 形式は OS やツールチェーンに依存しない。 |
| バージョン管理可能 | Kit には semver バージョンが付与され、変更履歴を追跡できる。 |
| 顧客に開発環境を要求しない | VSCode や PlatformIO 等の開発環境を顧客がインストールする必要はない。 |

## 3. Kit ディレクトリ構造

```
<kit-id>/
  manifest.json       — Kit のメタデータと Event ID → clip 対応表
  install-clips/      — デバイスに焼き込む command-mode wav (必須)
    *.wav
  stream-clips/       — SDK がホストから UDP ストリーミングする wav (任意)
    *.wav
  assets/             — UI アセット等（オプション）
  README.md           — Kit の説明（オプション）
```

### 各要素の説明

- **manifest.json**（必須）: Kit の識別情報、バージョン、Event ID からクリップファイルへのマッピング等を記述する JSON ファイル。
- **install-clips/**（command-mode event がある場合は必須）: デバイスに **焼き込む** wav の格納先。Kit インストール時にデバイス側ストレージに転送され、command 再生時にデバイスがオンボードでデコード・再生する。サブディレクトリ配下に置くことも許容する。
- **stream-clips/**（stream_clip / stream_source event がある場合は必須）: SDK 側 (Unity 等) が **ホストから UDP でストリーム送信** する wav の格納先。デバイス側には焼き込まれない。
- **assets/**（オプション）: アイコン画像やプレビュー用サムネイル等の UI アセットを格納するディレクトリ。
- **README.md**（オプション）: Kit の概要・使用方法・ライセンス情報等を記述するドキュメント。

> **過去の名称**: `install-clips/` は `clips/` という名前だった。「デバイスに保存する」という意図が伝わりにくかったため 2026-04-26 に rename した（DEC-027）。`stream-clips/` と動詞対比 (install / stream) で揃えている。

### 3.1 運用上の推奨

各 SDK は Kit を ホストプロジェクトの asset 配下 に配置することを推奨する。例:

- Unity: `Assets/HapbeatKits/<kit-id>/`
- Unreal: `Content/HapbeatKits/<kit-id>/`

これにより Studio の working directory と SDK の asset 読み込みパスが一致し、二重管理が発生しない。詳細は decision-log DEC-024 参照。

## 4. Kit name (= Kit ID)

Kit の `name` は Kit を一意に識別する文字列であり、以下すべてに **同じ値** が用いられる:

- on-disk のディレクトリ名（OS Explorer で見える）
- `manifest.json` の `name` フィールド
- wire-protocol（kit-install-protocol、bridge-api 等）の `kit_id` payload field

旧仕様では `manifest.kit_id` と `manifest.name` の 2 フィールドに分かれていたが、両者が常に同じ値を持っており冗長だったため `name` 1 つに統合した（2026-04-28）。kit_id は wire-protocol の field 名としては引き続き使用される — manifest 内に重複して書かないだけ。

### 命名規則

- 使用可能文字: 英小文字（a-z）、数字（0-9）、ハイフン（-）
- 先頭文字: 英小文字のみ
- 正規表現: `^[a-z][a-z0-9-]*$`

### 例

- `basic-impacts`
- `vr-environment-v2`
- `sports-feedback`
- `music-haptics`

## 5. manifest.json の構造

manifest.json は Kit のメタデータと Event ID からクリップファイルへの対応表を定義する JSON ファイルである。

### フィールド定義

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `schema_version` | string | はい | manifest スキーマのバージョン（例: `"1.0.0"`） |
| `version` | string | はい | Kit 自体のバージョン（semver 形式、例: `"1.2.0"`） |
| `name` | string | はい | Kit name (= ID = ディレクトリ名)。`^[a-z][a-z0-9-]*$` |
| `description` | string | いいえ | Kit の説明文 |
| `author` | string | いいえ | Kit の作者名 |
| `created_at` | string | いいえ | Kit の作成日時（ISO 8601 形式、例: `"2025-01-15T10:30:00Z"`） |
| `target_device` | object | いいえ | 対象デバイス情報 |
| `events` | object | はい | Event ID → clip 定義の辞書 |
| `install_clips` | object | いいえ | install-clips/ 配下の WAV メタデータ辞書 (command mode の参照ファイル) |

### target_device オブジェクト

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `firmware_version_min` | string | はい | 対応する最小ファームウェアバージョン |
| `firmware_version_max` | string | いいえ | 対応する最大ファームウェアバージョン（省略時は上限なし） |
| `board` | string | いいえ | 想定基板識別子（例: `duo_wl_v3`、`neck_wl_v2`）。Kit 作者が「この基板で調整した」というコンテキストを保存するためのもの。ファームウェア側のメタ情報と一致しない場合の警告判定に利用してよい |
| `volume_level` | integer | いいえ | Kit 作者がチューニング時に使ったデバイス音量レベル（例: 0–N）。再現性のためのコンテキスト情報 |
| `volume_wiper` | integer | いいえ | デバイスの MCP4018 wiper 値（0–127）。`volume_level` より低レベルの値で、wiper 直接指定が必要な再現に使う |
| `volume_steps` | integer | いいえ | デバイスがレポートする音量ステップ数。Kit 作者環境を記録するためのコンテキスト |

### events オブジェクト

`events` は Event ID 文字列をキー、clip 定義オブジェクトを値とする辞書である。

**キー**: Event ID 文字列（Event ID 仕様に準拠）

Event ID の形式:
- 基本形式: `<category>.<name>`（例: `impact.hit`）
- 拡張形式: `<category>.<subcategory>.<name>`
- 名前空間付き: `<namespace>/<category>.<name>`
- 使用可能文字: 英小文字 a-z、数字 0-9、ハイフン、アンダースコア
- 区切り文字: カテゴリ内はドット、名前空間の区切りはスラッシュ

**値（clip 定義オブジェクト）**:

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `mode` | string | いいえ | 再生モード (`"command"` / `"stream_clip"` / `"stream_source"`)。既定 `"command"` |
| `clip` | string | 条件付き | mode=command では必須で `install-clips/` 配下の相対ファイル名を指す（例: `"hit_medium.wav"`、サブディレクトリ可）。stream_* では optional でキットルートからの相対パス（例: `"stream-clips/rain.wav"`） |
| `description` | string | いいえ | このイベントの説明 |
| `tags` | string[] | いいえ | 分類用タグの配列 |
| `parameters` | object | いいえ | 再生パラメータ |

### mode (string, optional, default: "command")

event の再生モード。SDK が Kit を読み込む際、どのような方法で触覚再生を行うかを決定する。

- `"command"` (default): device 側に焼き込んだ clip を eventId で再生する従来モード。`clip` フィールド必須。kit-tools が device binary を生成する際はこの mode の event のみ含める。
- `"stream_clip"`: SDK (Unity 等) が AudioClip を PCM データとして UDP STREAM_BEGIN/DATA/END で送信するモード。`clip` フィールドは optional（Kit に音源を同梱して SDK が Asset として import する場合に指定）。device 側には焼き込まれない。
- `"stream_source"`: SDK が live AudioSource をキャプチャして UDP ストリーミングするモード。`clip` フィールドは不要。device 側には何も焼き込まれない。

device firmware は mode != "command" の event を load 時にスキップする (後方互換のため、mode が無い既存 manifest は command として扱う)。

**parameters オブジェクト**:

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `intensity` | number | いいえ | 制作者が意図した基準強度。0.0〜1.0（デフォルト: 1.0） |
| `device_wiper` | integer | いいえ | イベント調整時の MCP4018 ワイパー値（0–127）。再現性のための参照情報 |
| `loop` | boolean | いいえ | ループ再生の有無。デフォルトは `false` |

### intensity (number, 0.0–1.0, default: 1.0)

制作者が意図した基準強度。WAV のフル振幅に対する倍率。

- `1.0`: WAV をそのまま再生（デフォルト）
- `0.7`: WAV の 70% の強さ（制作者が「これが中」と判断した値）
- SDK の gain パラメータは intensity に対する追加倍率として適用される
- 最終出力 = WAV振幅 × intensity × SDK_gain × デバイス音量

**SDK_gain の範囲**: 1.0 を基準として 0.0 ～ 約 2.0。1.0 で intensity そのままの強さ、2.0 で intensity の倍（ただし最終値は SDK 側で clip される）。

**stream_clip / stream_source mode での intensity**: `device 側で stored clip の振幅に乗算される` のではなく、`SDK 側が STREAM_BEGIN.gain または PLAY.gain の float32 値に intensity を乗算して送信する`。

**デバイス音量**: SDK は感知しない。Studio で kit authoring 時点のデバイス wiper 値を `parameters.device_wiper` に記録しており、再現するユーザーは当該 wiper 値にデバイスを合わせることで制作者の意図した強度を得られる。

### device_wiper (integer, 0–127, optional)

イベント調整時の Hapbeat デバイスの MCP4018 ワイパー値。
再現性のための参照情報。デバイスが異なるモデルの場合は無視される。

### install_clips オブジェクト（オプション）

`install_clips` は **install-clips/ 配下の WAV ファイル** のメタデータ辞書。キーは `events.<id>.clip` と同じ表記（bare filename、サブディレクトリを含む場合はそのまま）。値はメタデータオブジェクト。command mode の参照ファイルが対象。stream-clips/ 配下のファイルはここには含めない。バリデーションや表示用途に使用する。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `duration_ms` | number | いいえ | クリップの再生時間（ミリ秒） |
| `sample_rate` | number | いいえ | サンプルレート（Hz） |
| `channels` | number | いいえ | チャンネル数 |
| `format` | string | いいえ | フォーマット識別子（例: `"pcm_s16le"`） |

### manifest.json の例

```json
{
  "schema_version": "1.0.0",
  "version": "1.0.0",
  "name": "basic-impacts",
  "description": "衝撃・打撃系の基本的な触覚フィードバック",
  "author": "Hapbeat",
  "created_at": "2025-01-15T10:30:00Z",
  "target_device": {
    "firmware_version_min": "0.1.0"
  },
  "events": {
    "impact.hit": {
      "clip": "hit_medium.wav",
      "description": "中程度の打撃",
      "tags": ["impact", "basic"],
      "parameters": {
        "intensity": 0.8,
        "device_wiper": 64,
        "loop": false
      }
    },
    "impact.hit-soft": {
      "clip": "hit_soft.wav",
      "description": "軽い打撃"
    },
    "impact.hit-hard": {
      "clip": "hit_hard.wav",
      "description": "強い打撃",
      "parameters": {
        "intensity": 1.0,
        "device_wiper": 64
      }
    },
    "environment.rain": {
      "mode": "stream_clip",
      "clip": "stream-clips/rain_loop.wav",
      "description": "雨の環境音触覚 (host streaming)",
      "parameters": {
        "intensity": 0.3,
        "loop": true
      }
    }
  },
  "install_clips": {
    "hit_medium.wav": {
      "duration_ms": 150,
      "sample_rate": 44100,
      "channels": 1,
      "format": "pcm_s16le"
    },
    "hit_soft.wav": {
      "duration_ms": 100,
      "sample_rate": 44100,
      "channels": 1,
      "format": "pcm_s16le"
    },
    "hit_hard.wav": {
      "duration_ms": 200,
      "sample_rate": 44100,
      "channels": 1,
      "format": "pcm_s16le"
    }
  }
}
```

## 6. wav ファイル要件

### フォーマット

| 項目 | 推奨値 | 許容範囲 |
|------|--------|----------|
| フォーマット | PCM WAV（リニア PCM） | PCM WAV のみ（圧縮フォーマットは不可） |
| サンプルレート | 16000 / 24000 / 44100 Hz | 8000 Hz 〜 48000 Hz |
| ビット深度 | 16bit | 8bit または 16bit |
| チャンネル | モノラル（1ch） | モノラル推奨（デバイスがモノラル出力のため。ステレオファイルは左チャンネルのみ使用される可能性がある） |
| ファイルサイズ | — | 1 ファイルあたり最大 1MB を推奨 |

### 注意事項

- 圧縮形式（MP3、AAC、OGG 等）は対応しない。必ず PCM WAV を使用すること。
- デバイスはモノラル出力のため、ステレオファイルを使用してもステレオ効果は得られない。ファイルサイズ削減のためモノラルを推奨する。
- ESP32-S3 のメモリ制約上、極端に長い wav ファイルはストリーミング再生が必要になる場合がある。短いクリップ（数百ミリ秒〜数秒）を推奨する。

## 7. Kit のライフサイクル

Kit は以下のライフサイクルで管理される。

```
build → validate → install → activate → 差し替え / 削除
```

### 各フェーズの説明

1. **build（ビルド）**: wav ファイルと manifest.json を作成し、Kit ディレクトリを構成する。SDK ツールにより自動生成することもできる。
2. **validate（検証）**: manifest.json のスキーマ検証、Event ID 形式の検証、参照される wav ファイルの存在確認、wav フォーマットの検証を行う。
3. **install（インストール）**: Kit ディレクトリをデバイスのファイルシステムに転送する。
4. **activate（有効化）**: デバイスが Kit を読み込み、Event ID とクリップの対応表をメモリに展開する。デバイスは起動時にインストール済み Kit を自動的に有効化する。
5. **差し替え / 削除**: 既存の Kit を新しいバージョンに差し替える、または不要になった Kit を削除する。

## 8. インストール方式

### 初期（v1）

- **USB / シリアル経由**: 開発用 PC からシリアル接続経由で Kit ディレクトリをデバイスに転送する。
- **ファイルシステム**: デバイスの SPIFFS または LittleFS 上に Kit ディレクトリを配置する。
- **ツール**: SDK 提供の CLI ツールまたはスクリプトによりインストールを自動化する。

### 将来の拡張

- **Wi-Fi 経由**: デバイスが Wi-Fi に接続された状態で、Web UI またはアプリケーションから Kit をアップロードする。
- **BLE 経由**: Bluetooth Low Energy を利用した Kit 転送（ファイルサイズの制約あり）。
- **SD カード**: SD カードに Kit を配置し、デバイスに挿入することでインストールする。

### デバイス上のディレクトリ配置

```
/kits/
  <kit-id>/
    manifest.json
    install-clips/      ← デバイスにインストールされる command-mode wav
      *.wav
    assets/
```

デバイスは `/kits/` ディレクトリ配下の各サブディレクトリを Kit として認識する。`stream-clips/` 配下のファイルは SDK 専用なのでデバイスには転送されない。

## 9. バージョニング

### Kit バージョン

- Kit のバージョンは [Semantic Versioning（semver）](https://semver.org/) に準拠する。
- 形式: `MAJOR.MINOR.PATCH`（例: `1.2.0`）
- バージョン変更の指針:
  - **MAJOR**: 後方互換性のない変更（Event ID の削除・名前変更等）
  - **MINOR**: 後方互換性のある機能追加（新規 Event ID の追加等）
  - **PATCH**: バグ修正・微調整（wav ファイルの音質改善等）

### スキーマバージョン（schema_version）

- manifest.json 自体のスキーマバージョンを示す。
- スキーマに互換性のない変更が加えられた場合、メジャーバージョンが上がる。
- デバイスファームウェアは対応する schema_version の範囲を持ち、非対応バージョンの Kit はロードを拒否する。

## 10. 制約事項

### Kit 全体サイズ

- デバイスのフラッシュ容量に依存する。初期は **4MB** を想定する。
- デバイスに焼き込まれるのは `install-clips/` 配下と manifest.json のみ。`stream-clips/` 配下と assets/ は転送対象外。
- Kit 全体（manifest.json + install-clips/）のサイズが、この容量の範囲内に収まる必要がある。
- 複数の Kit を同時にインストールする場合は、合計サイズが容量を超えないよう管理する。

### Event ID の重複禁止

- 1つの Kit 内で同一の Event ID を複数回定義することはできない（JSON オブジェクトのキーとして自然に一意となる）。
- 複数の Kit がデバイスにインストールされている場合、Event ID が重複した場合の動作は未定義とする（将来の仕様で優先順位ルールを定める可能性がある）。

### clip ファイルの配置

- command mode の WAV は `install-clips/` 配下、stream mode の WAV は `stream-clips/` 配下に配置しなければならない。
- これら 2 つのディレクトリの外部にあるファイルを `clip` フィールドで参照することはできない。
- 相対パスで `../` を使用してディレクトリ外を参照することは禁止する。

### ファイル名の制約

- ファイル名には英小文字、数字、ハイフン、アンダースコア、ドット（拡張子用）のみを使用することを推奨する。
- スペースや日本語文字をファイル名に含めることは非推奨とする（ファイルシステムの互換性のため）。

### その他

- manifest.json のエンコーディングは UTF-8 とする。
- wav ファイルの拡張子は `.wav` でなければならない（大文字小文字は区別しない）。
