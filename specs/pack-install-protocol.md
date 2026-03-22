# [INTERNAL] Pack インストールプロトコル仕様

> **[INTERNAL] この文書は PC → デバイス間の Pack 転送プロトコルを定義する。SDK からは直接参照されない。**

## 1. 概要

本文書は、PC 上の pack-tools CLI からデバイス（ESP32-S3）へ Pack ファイルを USB シリアル経由で転送・インストールするプロトコルを定義する。

## 2. 物理層

| 項目 | 値 |
|---|---|
| インターフェース | USB CDC シリアル |
| ボーレート | 921600 bps（ESP32-S3 USB CDC では実効速度は USB 依存） |
| データビット | 8 |
| パリティ | なし |
| ストップビット | 1 |

## 3. フレーム構造

Bridge-Transmitter 間プロトコルと同一のフレーム構造を使用する。

| オフセット | フィールド | 型 | サイズ | 説明 |
|---|---|---|---|---|
| 0 | start_marker | uint8 | 1 byte | 固定値 `0xAA` |
| 1 | frame_length | uint16_le | 2 bytes | payload のバイト長（little-endian） |
| 3 | command_type | uint8 | 1 byte | コマンド種別 |
| 4 | seq | uint16_le | 2 bytes | シーケンス番号 |
| 6 | payload | variable | frame_length bytes | コマンド固有のデータ |
| 6 + frame_length | checksum | uint8 | 1 byte | XOR チェックサム |
| 7 + frame_length | end_marker | uint8 | 1 byte | 固定値 `0x55` |

チェックサムの計算範囲は `command_type`、`seq`、`payload` の全バイトである。

**最大フレームサイズ**: payload は最大 1024 bytes。フレーム全体の最大サイズは 1032 bytes。

## 4. コマンド定義（PC → デバイス）

コマンド種別は `0x40`–`0x4F` の範囲を使用する（Bridge-Transmitter コマンドと衝突しない）。

### 0x40 INSTALL_BEGIN

Pack インストールの開始を通知する。デバイスは既存の同名 Pack があれば一時退避し、新しい Pack ディレクトリを作成する。

| フィールド | 型 | 説明 |
|---|---|---|
| pack_id | null-terminated string | Pack ID（例: `basic-impacts`） |
| file_count | uint16_le | 転送するファイル数 |
| total_size | uint32_le | 全ファイルの合計バイト数 |

### 0x41 FILE_BEGIN

1 ファイルの転送を開始する。デバイスはファイルを書き込み用に開く。

| フィールド | 型 | 説明 |
|---|---|---|
| file_path | null-terminated string | Pack ルートからの相対パス（例: `manifest.json`, `clips/damage.wav`） |
| file_size | uint32_le | ファイルサイズ（バイト） |

### 0x42 FILE_DATA

ファイルデータのチャンク。デバイスは受信データをファイルに追記する。

| フィールド | 型 | 説明 |
|---|---|---|
| offset | uint32_le | ファイル先頭からのオフセット |
| data | bytes | チャンクデータ（最大 512 bytes） |

### 0x43 FILE_END

1 ファイルの転送完了を通知する。デバイスはファイルを閉じ、CRC32 を検証する。

| フィールド | 型 | 説明 |
|---|---|---|
| crc32 | uint32_le | ファイル全体の CRC32 チェックサム |

### 0x44 INSTALL_COMMIT

全ファイルの転送が完了し、Pack をアクティベートする。デバイスは Pack の整合性を確認し、イベントテーブルを再構築する。

payload は空である。

### 0x45 PACK_LIST

インストール済み Pack の一覧を要求する。payload は空である。

### 0x46 PACK_DELETE

指定 Pack を削除する。

| フィールド | 型 | 説明 |
|---|---|---|
| pack_id | null-terminated string | 削除する Pack ID |

### 0x47 SPACE_QUERY

デバイスのストレージ空き容量を問い合わせる。payload は空である。

## 5. レスポンス定義（デバイス → PC）

### 0xC0 ACK

コマンドの正常処理を応答する。

| フィールド | 型 | 説明 |
|---|---|---|
| ack_command | uint8 | 応答対象のコマンド種別 |
| status | uint8 | 0x00 = 成功 |

### 0xC1 NAK

コマンドのエラーを応答する。

| フィールド | 型 | 説明 |
|---|---|---|
| nak_command | uint8 | 応答対象のコマンド種別 |
| error_code | uint8 | エラーコード（下表参照） |
| message | null-terminated string | エラーメッセージ（人間可読、最大 128 bytes） |

**エラーコード一覧**:

| コード | 名前 | 説明 |
|---|---|---|
| 0x01 | ERR_NO_SPACE | ストレージ容量不足 |
| 0x02 | ERR_FS_ERROR | ファイルシステムエラー |
| 0x03 | ERR_CRC_MISMATCH | CRC32 不一致 |
| 0x04 | ERR_INVALID_STATE | プロトコル状態不正（例: FILE_DATA が FILE_BEGIN の前に来た） |
| 0x05 | ERR_PACK_NOT_FOUND | 指定 Pack が見つからない |
| 0x06 | ERR_INVALID_FRAME | フレーム解析エラー |

### 0xC2 PACK_LIST_RESPONSE

インストール済み Pack 一覧の応答。

| フィールド | 型 | 説明 |
|---|---|---|
| pack_count | uint8 | Pack 数 |
| entries | 繰り返し | 以下の構造を pack_count 回繰り返す |

各 entry の構造:

| フィールド | 型 | 説明 |
|---|---|---|
| pack_id | null-terminated string | Pack ID |
| version | null-terminated string | バージョン文字列 |
| event_count | uint16_le | イベント数 |
| total_size | uint32_le | Pack の合計サイズ（バイト） |

### 0xC3 SPACE_RESPONSE

ストレージ情報の応答。

| フィールド | 型 | 説明 |
|---|---|---|
| total_bytes | uint32_le | 総容量 |
| used_bytes | uint32_le | 使用済み容量 |
| free_bytes | uint32_le | 空き容量 |

## 6. プロトコルフロー

### Pack インストール

```
PC                              Device
│                                  │
│─── INSTALL_BEGIN ───────────────▶│  Pack ディレクトリ作成
│◀── ACK(0x40) ───────────────────│
│                                  │
│  ┌─── ファイルごとに繰り返し ──────┐
│  │                                │
│  │─── FILE_BEGIN ──────────────▶│  ファイル作成
│  │◀── ACK(0x41) ───────────────│
│  │                                │
│  │  ┌── チャンクごとに繰り返し ──┐ │
│  │  │                            │ │
│  │  │── FILE_DATA ────────────▶│  追記
│  │  │◀─ ACK(0x42) ────────────│
│  │  │                            │ │
│  │  └────────────────────────┘ │
│  │                                │
│  │─── FILE_END ────────────────▶│  CRC32 検証、ファイル閉じ
│  │◀── ACK(0x43) ───────────────│
│  │                                │
│  └────────────────────────────┘
│                                  │
│─── INSTALL_COMMIT ─────────────▶│  Pack 有効化、イベントテーブル再構築
│◀── ACK(0x44) ───────────────────│
```

### タイムアウト

| 項目 | 値 |
|---|---|
| ACK 待ちタイムアウト | 3000 ms |
| リトライ回数 | 3 回 |
| リトライ間隔 | 500 ms |

ACK が得られない場合、PC 側は同一フレームを再送する。3 回リトライしても応答がなければインストールを中断する。

## 7. 状態遷移（デバイス側）

```
IDLE ──INSTALL_BEGIN──▶ RECEIVING
  ▲                        │
  │                    FILE_BEGIN──▶ FILE_TRANSFER
  │                        ▲            │
  │                        │       FILE_DATA (繰り返し)
  │                        │            │
  │                    FILE_END◀────────┘
  │                        │
  │                   INSTALL_COMMIT
  │                        │
  └────── IDLE ◀───────────┘
```

- `IDLE` 状態では `INSTALL_BEGIN`、`PACK_LIST`、`PACK_DELETE`、`SPACE_QUERY` を受け付ける
- `RECEIVING` 状態では `FILE_BEGIN` のみ受け付ける
- `FILE_TRANSFER` 状態では `FILE_DATA`、`FILE_END` のみ受け付ける
- 状態不正のコマンドを受信した場合は `NAK(ERR_INVALID_STATE)` を返す

## 8. CRC32 仕様

Event ID ハッシュと同一の CRC32 アルゴリズムを使用する（多項式: `0xEDB88320`、reflected）。

## 9. デバイス上のディレクトリ操作

### インストール時

1. `/packs/<pack_id>/` ディレクトリを作成
2. 必要なサブディレクトリ（`clips/` 等）を作成
3. 各ファイルを書き込み
4. INSTALL_COMMIT 時に Pack をロードしイベントを登録

### 既存 Pack の上書き

1. 既存の `/packs/<pack_id>/` を `/packs/<pack_id>.bak/` にリネーム
2. 新しい Pack をインストール
3. INSTALL_COMMIT 成功後、`.bak` を削除
4. INSTALL_COMMIT 失敗時、`.bak` を元に戻す

### 削除時

1. `/packs/<pack_id>/` 内の全ファイルを削除
2. ディレクトリを削除
3. イベントテーブルを再構築（全 Pack を再スキャン）
