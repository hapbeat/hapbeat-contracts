# Pack フォーマット仕様

## 1. 概要

Pack は Hapbeat デバイス向け触覚コンテンツの配布単位である。wav クリップファイル、manifest（メタデータおよび Event ID とクリップの対応表）、UI アセット等をひとつのディレクトリにまとめたローカル資産パッケージとして構成される。

Pack を差し替えるだけでデバイスの触覚体験を変更でき、ファームウェアの更新は不要である。

## 2. 設計原則

| 原則 | 説明 |
|------|------|
| ファームウェア更新不要 | コンテンツ変更は Pack の差し替えのみで完結する。ファームウェアの再ビルド・再書き込みは必要ない。 |
| オフライン動作 | Pack はすべてローカルに保持される。ネットワーク接続なしで動作する。 |
| プラットフォーム中立 | Pack のディレクトリ構造・manifest 形式は OS やツールチェーンに依存しない。 |
| バージョン管理可能 | Pack には semver バージョンが付与され、変更履歴を追跡できる。 |
| 顧客に開発環境を要求しない | VSCode や PlatformIO 等の開発環境を顧客がインストールする必要はない。 |

## 3. Pack ディレクトリ構造

```
<pack-id>/
  manifest.json       — Pack のメタデータと Event ID → clip 対応表
  clips/              — wav ファイル格納ディレクトリ
    *.wav
  assets/             — UI アセット等（オプション）
  README.md           — Pack の説明（オプション）
```

### 各要素の説明

- **manifest.json**（必須）: Pack の識別情報、バージョン、Event ID からクリップファイルへのマッピング等を記述する JSON ファイル。
- **clips/**（必須）: 触覚出力に使用する wav ファイルを格納するディレクトリ。すべてのクリップファイルはこのディレクトリ配下に配置する。サブディレクトリによる分類も許容する。
- **assets/**（オプション）: アイコン画像やプレビュー用サムネイル等の UI アセットを格納するディレクトリ。
- **README.md**（オプション）: Pack の概要・使用方法・ライセンス情報等を記述するドキュメント。

## 4. Pack ID

Pack ID は Pack を一意に識別する文字列であり、ディレクトリ名としても使用される。

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

manifest.json は Pack のメタデータと Event ID からクリップファイルへの対応表を定義する JSON ファイルである。

### フィールド定義

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `schema_version` | string | はい | manifest スキーマのバージョン（例: `"1.0.0"`） |
| `pack_id` | string | はい | Pack の一意識別子。Pack ID の命名規則に従う |
| `version` | string | はい | Pack 自体のバージョン（semver 形式、例: `"1.2.0"`） |
| `name` | string | はい | Pack の表示名 |
| `description` | string | いいえ | Pack の説明文 |
| `author` | string | いいえ | Pack の作者名 |
| `created_at` | string | いいえ | Pack の作成日時（ISO 8601 形式、例: `"2025-01-15T10:30:00Z"`） |
| `target_device` | object | いいえ | 対象デバイス情報 |
| `events` | object | はい | Event ID → clip 定義の辞書 |
| `clips` | object | いいえ | clip メタデータの辞書 |

### target_device オブジェクト

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `firmware_version_min` | string | はい | 対応する最小ファームウェアバージョン |
| `firmware_version_max` | string | いいえ | 対応する最大ファームウェアバージョン（省略時は上限なし） |

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
| `clip` | string | はい | clips/ ディレクトリからの相対パス（例: `"hit_soft.wav"`） |
| `description` | string | いいえ | このイベントの説明 |
| `tags` | string[] | いいえ | 分類用タグの配列 |
| `parameters` | object | いいえ | 再生パラメータ |

**parameters オブジェクト**:

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `gain` | number | いいえ | 再生ゲイン。0.0（無音）〜 1.0（最大）の範囲 |
| `loop` | boolean | いいえ | ループ再生の有無。デフォルトは `false` |

### clips オブジェクト（オプション）

`clips` はクリップファイルパスをキー、メタデータオブジェクトを値とする辞書である。バリデーションや表示用途に使用する。

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
  "pack_id": "basic-impacts",
  "version": "1.0.0",
  "name": "基本インパクトパック",
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
        "gain": 0.8,
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
        "gain": 1.0
      }
    },
    "environment.rain": {
      "clip": "ambient/rain_loop.wav",
      "description": "雨の環境音触覚",
      "parameters": {
        "gain": 0.3,
        "loop": true
      }
    }
  },
  "clips": {
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
    },
    "ambient/rain_loop.wav": {
      "duration_ms": 5000,
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

## 7. Pack のライフサイクル

Pack は以下のライフサイクルで管理される。

```
build → validate → install → activate → 差し替え / 削除
```

### 各フェーズの説明

1. **build（ビルド）**: wav ファイルと manifest.json を作成し、Pack ディレクトリを構成する。SDK ツールにより自動生成することもできる。
2. **validate（検証）**: manifest.json のスキーマ検証、Event ID 形式の検証、参照される wav ファイルの存在確認、wav フォーマットの検証を行う。
3. **install（インストール）**: Pack ディレクトリをデバイスのファイルシステムに転送する。
4. **activate（有効化）**: デバイスが Pack を読み込み、Event ID とクリップの対応表をメモリに展開する。デバイスは起動時にインストール済み Pack を自動的に有効化する。
5. **差し替え / 削除**: 既存の Pack を新しいバージョンに差し替える、または不要になった Pack を削除する。

## 8. インストール方式

### 初期（v1）

- **USB / シリアル経由**: 開発用 PC からシリアル接続経由で Pack ディレクトリをデバイスに転送する。
- **ファイルシステム**: デバイスの SPIFFS または LittleFS 上に Pack ディレクトリを配置する。
- **ツール**: SDK 提供の CLI ツールまたはスクリプトによりインストールを自動化する。

### 将来の拡張

- **Wi-Fi 経由**: デバイスが Wi-Fi に接続された状態で、Web UI またはアプリケーションから Pack をアップロードする。
- **BLE 経由**: Bluetooth Low Energy を利用した Pack 転送（ファイルサイズの制約あり）。
- **SD カード**: SD カードに Pack を配置し、デバイスに挿入することでインストールする。

### デバイス上のディレクトリ配置

```
/packs/
  <pack-id>/
    manifest.json
    clips/
      *.wav
    assets/
```

デバイスは `/packs/` ディレクトリ配下の各サブディレクトリを Pack として認識する。

## 9. バージョニング

### Pack バージョン

- Pack のバージョンは [Semantic Versioning（semver）](https://semver.org/) に準拠する。
- 形式: `MAJOR.MINOR.PATCH`（例: `1.2.0`）
- バージョン変更の指針:
  - **MAJOR**: 後方互換性のない変更（Event ID の削除・名前変更等）
  - **MINOR**: 後方互換性のある機能追加（新規 Event ID の追加等）
  - **PATCH**: バグ修正・微調整（wav ファイルの音質改善等）

### スキーマバージョン（schema_version）

- manifest.json 自体のスキーマバージョンを示す。
- スキーマに互換性のない変更が加えられた場合、メジャーバージョンが上がる。
- デバイスファームウェアは対応する schema_version の範囲を持ち、非対応バージョンの Pack はロードを拒否する。

## 10. 制約事項

### Pack 全体サイズ

- デバイスのフラッシュ容量に依存する。初期は **4MB** を想定する。
- Pack 全体（manifest.json + clips/ + assets/）のサイズは、この容量の範囲内に収める必要がある。
- 複数の Pack を同時にインストールする場合は、合計サイズが容量を超えないよう管理する。

### Event ID の重複禁止

- 1つの Pack 内で同一の Event ID を複数回定義することはできない（JSON オブジェクトのキーとして自然に一意となる）。
- 複数の Pack がデバイスにインストールされている場合、Event ID が重複した場合の動作は未定義とする（将来の仕様で優先順位ルールを定める可能性がある）。

### clip ファイルの配置

- すべてのクリップファイルは Pack ディレクトリ内の `clips/` ディレクトリ配下に配置しなければならない。
- `clips/` の外部にあるファイルを `clip` フィールドで参照することはできない。
- 相対パスで `../` を使用して clips/ ディレクトリ外を参照することは禁止する。

### ファイル名の制約

- ファイル名には英小文字、数字、ハイフン、アンダースコア、ドット（拡張子用）のみを使用することを推奨する。
- スペースや日本語文字をファイル名に含めることは非推奨とする（ファイルシステムの互換性のため）。

### その他

- manifest.json のエンコーディングは UTF-8 とする。
- wav ファイルの拡張子は `.wav` でなければならない（大文字小文字は区別しない）。
