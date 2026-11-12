# [INTERNAL] Kit インストールプロトコル仕様

> **[INTERNAL] この文書は PC → デバイス間の Kit 転送プロトコルを定義する。SDK からは直接参照されない。**

## 1. 概要

本文書は、PC 上の kit-tools CLI からデバイス（ESP32-S3）へ Kit ファイルを USB シリアル経由で転送・インストールするプロトコルを定義する。Wi-Fi（TCP 7701 の JSON の `kit_install`・`file_begin`・`kit_commit`・`kit_delete`。helper が使う）の転送も、機器の上の Kit と音声領域の扱い（§9・§10）は USB と同じにする。

## 2. 物理層

| 項目 | 値 |
|---|---|
| インターフェース | USB CDC シリアル |
| ボーレート | 921600 bps（ESP32-S3 USB CDC では実効速度は USB 依存） |
| データビット | 8 |
| パリティ | なし |
| ストップビット | 1 |

## 3. フレーム構造

Kit インストール用の独立したフレーム構造を使用する。

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

コマンド種別は `0x40`–`0x4F` の範囲を使用する。

### 0x40 INSTALL_BEGIN

Kit インストールの開始を通知する。デバイスは既存の同名 Kit があれば削除し（§9）、新しい Kit ディレクトリを作成する。ほかに Kit が無ければ、応答の前に音声領域を消去する（§10。数秒かかることがある、§6「タイムアウト」）。

| フィールド | 型 | 説明 |
|---|---|---|
| kit_id | null-terminated string | Kit ID（例: `basic-impacts`） |
| file_count | uint16_le | 転送するファイル数 |
| total_size | uint32_le | 全ファイルの合計バイト数 |

### 0x41 FILE_BEGIN

1 ファイルの転送を開始する。デバイスはファイルを書き込み用に開く。

| フィールド | 型 | 説明 |
|---|---|---|
| file_path | null-terminated string | Kit ルートからの相対パス（例: `manifest.json`, `install-clips/damage.wav`） |
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

全ファイルの転送が完了し、Kit をアクティベートする。デバイスは Kit の整合性を確認し、イベントテーブルを再構築する。

payload は空である。

### 0x45 KIT_LIST

インストール済み Kit の一覧を要求する。payload は空である。

### 0x46 KIT_DELETE

指定 Kit を削除する。音声領域の扱いは §10（ほかの Kit の音声は残す。Kit が 1 つも残らなければ、応答の前に音声領域を消去する）。

| フィールド | 型 | 説明 |
|---|---|---|
| kit_id | null-terminated string | 削除する Kit ID |

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
| 0x01 | ERR_NO_SPACE | ストレージ容量不足。音声領域が満杯、または目次が上限に達した（`FILE_DATA`・`FILE_END`・`INSTALL_COMMIT` で返す、§10） |
| 0x02 | ERR_FS_ERROR | ファイルシステムエラー |
| 0x03 | ERR_CRC_MISMATCH | CRC32 不一致 |
| 0x04 | ERR_INVALID_STATE | プロトコル状態不正（例: FILE_DATA が FILE_BEGIN の前に来た） |
| 0x05 | ERR_KIT_NOT_FOUND | 指定 Kit が見つからない |
| 0x06 | ERR_INVALID_FRAME | フレーム解析エラー |
| 0x07 | ERR_FIRMWARE_TOO_OLD | Kit の `target_device.firmware_version_min` を機体が満たさない（0.x のファームが既に使っている値。1.x は major だけを比べる、`versioning.md` §11） |
| 0x08 | ERR_SCHEMA_UNSUPPORTED | **[1.x]** manifest の `schema_version` の major が機体の `caps.kit_schema` の範囲外 |
| 0x09 | ERR_STORAGE_INCOMPATIBLE | **[1.x]** 音声領域の版が合わず使えない（`get_info` の `storage_incompatible`。`reset_storage` で初期化してから入れ直す、`serial-config.md` §4.23） |

拒否した Kit は、機体に残さない（次の起動で読み込まれないようにする）。

### 0xC2 KIT_LIST_RESPONSE

インストール済み Kit 一覧の応答。

| フィールド | 型 | 説明 |
|---|---|---|
| kit_count | uint16_le | Kit 数 |
| entries | 繰り返し | 以下の構造を kit_count 回繰り返す |

各 entry の構造:

| フィールド | 型 | 説明 |
|---|---|---|
| kit_id | null-terminated string | Kit ID |
| version | null-terminated string | バージョン文字列 |
| event_count | uint16_le | イベント数 |

### 0xC3 SPACE_RESPONSE

ストレージ情報の応答。

| フィールド | 型 | 説明 |
|---|---|---|
| fs_total | uint32_le | LittleFS（manifest 等を置く）の総容量 |
| fs_used | uint32_le | LittleFS の使用量 |
| audio_total | uint32_le | 音声領域（§10）のデータ部の容量 |
| audio_used | uint32_le | 音声領域の使用量。追記だけなので、削除した Kit の分も消去まで残る（§10） |

## 6. プロトコルフロー

### Kit インストール

```
PC                              Device
│                                  │
│─── INSTALL_BEGIN ───────────────▶│  Kit ディレクトリ作成
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
│─── INSTALL_COMMIT ─────────────▶│  Kit 有効化、イベントテーブル再構築
│◀── ACK(0x44) ───────────────────│
```

### タイムアウト

| 項目 | 値 |
|---|---|
| ACK 待ちタイムアウト | 3000 ms |
| ACK 待ちタイムアウト（`INSTALL_BEGIN`・`KIT_DELETE`） | 30000 ms |
| リトライ回数 | 3 回 |
| リトライ間隔 | 500 ms |

ACK が得られない場合、PC 側は同一フレームを再送する。3 回リトライしても応答がなければインストールを中断する。PC 側は応答の `seq` を照合し、前のフレームへの遅れた応答を読み飛ばす。

`INSTALL_BEGIN` と `KIT_DELETE` は、音声領域を消去してから応答することがある（§10）。消去は書き込んだ量 1 MB あたり約 2 秒かかる（Duo WL v3 で計測。4 MB の領域が満杯で約 9 秒、7.4 MB の領域なら約 16 秒）。Wi-Fi の `kit_install`・`kit_delete` も同じで、helper は 10 秒待つ（7.4 MB の領域の大半を使った機体では、消去がこれを超えることがある）。

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

- `IDLE` 状態では `INSTALL_BEGIN`、`KIT_LIST`、`KIT_DELETE`、`SPACE_QUERY` を受け付ける
- `RECEIVING` 状態では `FILE_BEGIN` のみ受け付ける
- `FILE_TRANSFER` 状態では `FILE_DATA`、`FILE_END` のみ受け付ける
- 状態不正のコマンドを受信した場合は `NAK(ERR_INVALID_STATE)` を返す

## 8. CRC32 仕様

Event ID ハッシュと同一の CRC32 アルゴリズムを使用する（多項式: `0xEDB88320`、reflected）。

## 9. デバイス上のディレクトリ操作

### インストール時

1. `/kits/<kit_id>/` ディレクトリを作成
2. 必要なサブディレクトリ（`install-clips/` 等）を作成
3. 各ファイルを書き込み
4. INSTALL_COMMIT 時に Kit をロードしイベントを登録

### 既存 Kit の上書き

1. INSTALL_BEGIN で既存の `/kits/<kit_id>/` を削除する（退避しない）
2. 新しい Kit をインストールする
3. 失敗・拒否したときは、新しい Kit も残さない。前の版にも戻らないので、Kit を入れ直す

### 削除時

1. `/kits/<kit_id>/` 内の全ファイルを削除
2. ディレクトリを削除
3. 音声領域を §10 のとおり片付ける
4. イベントテーブルを再構築（全 Kit を再スキャン）

## 10. 音声領域

機器は Kit の WAV を LittleFS に置かず、flash の音声領域（`audio` 区画）へ、16 bit の WAV は IMA ADPCM に、8 bit の WAV はそのまま書く。音声領域は、先頭の目次（TOC。1 項目がイベント 1 つ、上限 256 項目）と、後ろのデータ部からなる。USB と Wi-Fi のどちらで入れても、次のとおりにする。

- **追記だけ**: データ部は前から順に書き足す。Kit を消しても、そのバイトは音声領域を消去するまで使用中のまま（SPACE_RESPONSE の `audio_used`）。
- **1 イベント 1 項目、新しいインストールが勝つ**: INSTALL_COMMIT（`kit_commit`）で、このインストールで書いたクリップを manifest の各イベントに結び付け、同じイベントの古い項目を目次から除く。どの Kit の manifest にも無いイベントの項目も除く。
- **削除**（`KIT_DELETE`・`kit_delete`）: 消した Kit のイベントの項目を目次から除き、ほかの Kit の音声は残す。Kit が 1 つも残らなければ、音声領域を消去する（`audio_used` が 0 に戻る）。
- **入れ直し**（`INSTALL_BEGIN`・`kit_install`）: 置き換える Kit のイベントの項目を、書く前に目次から除く。ほかに Kit が無ければ、書く前に音声領域を消去する。Kit が 1 つの機体では、入れ直しを何度くり返しても満杯にならない。
- **満杯**: データ部に書けない、または目次が上限を超えるときは、`NAK(ERR_NO_SPACE)`（Wi-Fi は `"audio storage full"` のエラー）を返し、その Kit を残さない。ほかの Kit の音声は残す。Wi-Fi では、そのファイルの残りのバイトを読み捨ててからエラーを返す。片付け（Kit が残らないときの消去）は応答の後に行う。Kit が 2 つ以上ある機体は、入れ直すたびに追記されるので、いずれ満杯になる。そのときは全 Kit を削除して入れ直す。
- **消去の範囲**: 書いた部分（使用量と、途中で止まったインストールが書いた部分）だけを消す。
- **途中で止まったインストール**: 送り手が消えた、電源が切れた、などで終わらなかったインストールが書いたバイトの上には書かず、その後ろから書く（flash は 1→0 にしか書けない）。そのバイトは消去まで使用中になる。
- **同じ event_id**: 異なる Kit が同じ event_id を持つと、後に入れた Kit の音声が鳴る。その Kit を消しても、残る Kit のそのイベントは消した Kit の音声を指したままになる（event_id の衝突は `event-id.md` の名前空間で避ける）。
- **起動時**: 目次に同じイベントの項目が複数あれば、最後の項目を使う。1.0.0 までのファームは、Kit を入れ直すたびに同じイベントの古い項目を前に残し、古い音声を鳴らしていた。ファームを更新すれば、入れ直さなくても新しい音声が鳴る。
