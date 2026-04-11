# Instructions: Streaming Command Definitions

**対象リポジトリ**: hapbeat-contracts
**作成日**: 2026-04-09
**作成元**: hapbeat-studio セッション
**適用済み**: 2026-04-10（message-format.md に反映、コマンドコードを 0x30 系に修正）

## 概要

`specs/message-format.md` に UDP ストリーミングコマンドの定義を追加する。

## 追加するコマンド

### Layer 1 Command Types（既存テーブルに追加）

| Code | Name | Direction | Description |
|------|------|-----------|-------------|
| 0x30 | STREAM_BEGIN | SDK/Manager → Device | ストリーミング開始（デコーダーリセット + バッファクリア） |
| 0x31 | STREAM_DATA | SDK/Manager → Device | オーディオデータチャンク |
| 0x32 | STREAM_END | SDK/Manager → Device | ストリーミング終了ヒント（ACK なし） |

**注**: 当初 0x20-0x22 で定義されていたが、0x20 は CONNECT_STATUS で使用済みのため 0x30 系に変更。

### STREAM_BEGIN (0x30) Payload

```
Offset  Size    Field          Description
0       2       sample_rate    uint16 LE (Hz, e.g. 8000, 16000, 44100)
2       1       channels       uint8 (1=mono, 2=stereo)
3       1       format         uint8 (0=PCM16, 1=IMA_ADPCM)
4       4       total_samples  uint32 LE (0=unknown, optional)
```

### STREAM_DATA (0x31) Payload

```
Offset  Size    Field    Description
0       4       offset   uint32 LE (byte offset, informational)
4       N       data     Audio data (PCM16 or ADPCM bytes)
```

- PCM16: raw interleaved 16-bit LE samples
- ADPCM mono: 2 samples per byte (low nibble first)
- ADPCM stereo: 1 frame per byte (L nibble low, R nibble high)

### STREAM_END (0x32) Payload

空。リングバッファは自然にドレインされる。ACK は返さない。

### 設計方針

- ストリーミングは voice ミキサーと**並行動作**（排他モードではない）
- STREAM_BEGIN はローカルクリップの再生を停止しない
- リングバッファが空なら何も起きない（ゼロオーバーヘッド）
- ACK/モード切替なし。fire-and-forget 方式

## IMA ADPCM 仕様

参考実装: `hapbeat-wireless-firmware/lib/ima_adpcm/ima_adpcm.h`

- 標準 IMA ADPCM（stepTable[89], indexTable[16]）
- 圧縮比: 4:1（PCM16 → 4-bit nibble）
- ステレオ: 1 byte = L nibble (bits 0-3) | R nibble (bits 4-7)
- モノ: 1 byte = sample[n] (bits 0-3) | sample[n+1] (bits 4-7)

## ファイル変更

| ファイル | 変更内容 |
|---------|---------|
| `specs/message-format.md` | CONNECT_STATUS (0x20) + STREAM 系 (0x30-0x32) 追加、パケットサイズ制限更新 |
