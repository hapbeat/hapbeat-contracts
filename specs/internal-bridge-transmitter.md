# [INTERNAL] Bridge-Transmitter 間内部インターフェース仕様書

> **[INTERNAL] この文書は Bridge と Transmitter Firmware 間の内部インターフェースを定義する。SDK からは直接参照されない。**

## 1. 概要

本文書は、Bridge と送信機ファームウェア間の通信仕様を定義する。このプロトコルは SDK には公開されない内部仕様であり、Bridge が SDK から受信したコマンドを送信機に中継する際に使用される。

## 2. 物理層

| 項目 | 値 |
|---|---|
| インターフェース | USB シリアル（初期実装） |
| ボーレート | 921600 bps |
| データビット | 8 |
| パリティ | なし |
| ストップビット | 1 |

将来的には SPI / I2C による接続も検討可能とする。

## 3. フレーム構造

USB シリアル上の各フレームは以下の構造を持つ。

| オフセット | フィールド | 型 | サイズ | 説明 |
|---|---|---|---|---|
| 0 | start_marker | uint8 | 1 byte | 固定値 `0xAA`（フレーム開始マーカー） |
| 1 | frame_length | uint16 | 2 bytes | payload のバイト長 |
| 3 | command_type | uint8 | 1 byte | コマンド種別 |
| 4 | seq | uint16 | 2 bytes | シーケンス番号 |
| 6 | payload | variable | frame_length bytes | コマンド固有のデータ |
| 6 + frame_length | checksum | uint8 | 1 byte | XOR チェックサム（command_type から payload 末尾までの全バイトの XOR） |
| 7 + frame_length | end_marker | uint8 | 1 byte | 固定値 `0x55`（フレーム終了マーカー） |

チェックサムの計算範囲は `command_type`、`seq`、`payload` の全バイトである。

## 4. コマンド定義（Bridge → Transmitter）

### 0x01 DISPATCH_PLAY

触覚イベントの再生を送信機に指示する。

| フィールド | 型 | 説明 |
|---|---|---|
| event_id | null-terminated string | イベント識別子 |
| target_time | int64 | 再生開始時刻（マイクロ秒） |
| target_group | uint8 | 対象グループ ID |
| gain | float32 | 再生ゲイン（0.0 〜 1.0） |

### 0x02 DISPATCH_STOP

指定イベントの停止を送信機に指示する。

| フィールド | 型 | 説明 |
|---|---|---|
| event_id | null-terminated string | イベント識別子 |
| target_group | uint8 | 対象グループ ID |

### 0x03 DISPATCH_STOP_ALL

指定グループの全イベント停止を送信機に指示する。

| フィールド | 型 | 説明 |
|---|---|---|
| target_group | uint8 | 対象グループ ID |

### 0x20 TIME_SYNC

送信機の時刻を Bridge の時刻に同期するためのコマンド。

| フィールド | 型 | 説明 |
|---|---|---|
| bridge_time | int64 | Bridge の現在時刻（マイクロ秒） |

送信機はこの値を用いて内部時刻を補正する。

### 0x30 QUERY_STATUS

送信機の状態を問い合わせる。payload は空である。

### 0x31 DEVICE_SCAN

ESP-NOW デバイスのスキャンを送信機に指示する。payload は空である。送信機はスキャン完了後に DEVICE_INFO レスポンスを返す。

## 5. レスポンス（Transmitter → Bridge）

### 0x80 ACK

コマンドに対する確認応答。

| フィールド | 型 | 説明 |
|---|---|---|
| seq | uint16 | 対応するコマンドのシーケンス番号 |
| status | uint8 | 結果コード。`0` = 正常、`1` = エラー |

### 0x81 DEVICE_INFO

接続中のデバイス情報を返す。DEVICE_SCAN の結果または定期レポートとして送信される。

| フィールド | 型 | 説明 |
|---|---|---|
| device_count | uint8 | 検出されたデバイス数 |
| devices[] | 以下の繰り返し | device_count 回繰り返し |

devices[] の各要素:

| フィールド | 型 | 説明 |
|---|---|---|
| device_id | 6 bytes | デバイスの MAC アドレス |
| group | uint8 | デバイスが属するグループ ID |
| rssi | int8 | 受信信号強度（dBm） |
| battery | uint8 | バッテリー残量（パーセント、0 〜 100） |

### 0x82 TX_STATUS

送信機の内部状態を返す。QUERY_STATUS に対する応答として送信される。

| フィールド | 型 | 説明 |
|---|---|---|
| tx_queue_depth | uint8 | 送信キューに滞留中のコマンド数 |
| last_tx_result | uint8 | 直前の ESP-NOW 送信結果（0 = 成功、その他 = エラーコード） |
| uptime_sec | uint32 | 送信機の起動からの経過時間（秒） |

## 6. フロー制御

- ACK ベースのフロー制御を採用する
- Bridge はコマンドを送信した後、送信機からの ACK を待ってから次のコマンドを送信する
- ACK タイムアウト: **100ms**
- タイムアウト発生時は最大 **3 回** リトライする
- 3 回リトライしても ACK が得られない場合、Bridge はエラーとして処理し、SDK にエラーレスポンス（0xFF）を返す

## 7. ESP-NOW パケット（Transmitter → Device）概要

本文書では ESP-NOW パケットの構造概要のみを記載する。詳細は device-firmware 側の仕様書で定義される。

| フィールド | 型 | サイズ | 説明 |
|---|---|---|---|
| command | uint8 | 1 byte | コマンド種別。`0x01` = play、`0x02` = stop、`0x03` = stop_all |
| event_id_hash | uint32 | 4 bytes | Event ID の CRC32 ハッシュ値 |
| target_time | uint32 | 4 bytes | 再生開始時刻（ミリ秒単位。ESP-NOW 側では精度を落とす） |
| group | uint8 | 1 byte | 対象グループ ID |
| gain | uint8 | 1 byte | ゲイン値。0 〜 255 にマッピング（0 = 0.0、255 = 1.0） |

ESP-NOW のパケットサイズ制限（250 bytes）のため、Event ID 文字列をそのまま送信することはできない。代わりに CRC32 ハッシュを使用する。

## 8. Event ID ハッシュ

- ESP-NOW パケットサイズ（250 bytes 制限）の制約により、Event ID 文字列をデバイス側にそのまま送信しない
- 代わりに、Event ID 文字列の **CRC32 ハッシュ** を使用する
- デバイスは Kit インストール時に Event ID → ハッシュの対応テーブルを構築する
- 送信機はコマンド中継時に Event ID 文字列を CRC32 ハッシュに変換してから ESP-NOW パケットに格納する

## 9. 注意事項

- **本仕様は内部仕様であり、SDK 開発者には公開しない**
- 本仕様の変更時は、Bridge と Transmitter Firmware の双方を同時に更新する必要がある
- 片方のみを更新した場合、プロトコルの不整合により通信障害が発生する可能性がある
- バージョン管理: Bridge と Transmitter Firmware は同一リリースサイクルで管理すること
