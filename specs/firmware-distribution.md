# ファーム配布 manifest 仕様書（firmware distribution）

## 1. 概要

ESP-NOW / MQTT の追加で、Hapbeat のファームは **複数 repo × 複数 role/transport/board** に増える。
本仕様は、それらを **1 つの統合 manifest** に集約し、Studio が「このノードに正しいファーム」を提示・書込できるようにする配布形式を定義する（DEC-034）。

## 2. 課題と方針

- 従来 manifest は PlatformIO `env` 名のみを単位にしていた（`{ "envs": [{ env, fwVersion, appOta, fullSerial }] }`）。
- role/transport/board の 3 軸が増えると `env` 名だけでは Studio が分類・フィルタできない。
- **方針:** manifest を v2 に拡張し、各成果物に `repo` / `role` / `transport` / `board` / `label` を付与。複数 repo の成果物を 1 ファイルに集約する。

## 3. 集約フロー

```
[各 firmware repo CI]
  hapbeat-device-firmware   → 成果物(.bin) + manifest.fragment.json (自 repo の variants)
  hapbeat-wireless-firmware → 成果物 + fragment
  wireless-sender-firmware  → 成果物 + fragment
  （sensor/broker repo）     → 成果物 + fragment
        │
        ▼ (集約)
[配布側] 全 fragment を merge → 統合 manifest.json + 全 .bin を 1 箇所へ
        │
        ▼
[Studio] manifest.json を fetch → role/transport/board でフィルタ表示 → 書込
```

- 各 repo は **自分の fragment** だけを生成する責務を持つ（自 repo の variants のみ）。
- 集約は配布側（Studio ビルド時 or devtools-site CI）で行い、`variants` を連結する。
- 成果物ファイル名は repo を跨いで衝突しないよう **`<repo-short>_<env>_<stem>.bin`** を推奨（例: `dev_band_wl_v3_firmware_app_ota.bin`）。

## 4. manifest v2 フォーマット

```json
{
  "schema_version": 2,
  "generated_at": 1717400000000,
  "variants": [
    {
      "id": "dev/band_wl_v3",
      "repo": "hapbeat-device-firmware",
      "env": "band_wl_v3",
      "role": "receiver",
      "transport": "udp",
      "transports": ["udp", "mqtt"],
      "board": "band_wl_v3",
      "label": "Band — Wi-Fi (UDP/MQTT)",
      "description": "標準の装着デバイス。Unity 等 SDK 連携 + センサ通知。",
      "fwVersion": "v0.2.0",
      "appOta":     { "filename": "dev_band_wl_v3_firmware_app_ota.bin",     "size": 1234567, "mtime": 1717400000000 },
      "fullSerial": { "filename": "dev_band_wl_v3_firmware_full_serial.bin", "size": 1556789, "mtime": 1717400000000 }
    },
    {
      "id": "wl/duo_wl_v3_stream",
      "repo": "hapbeat-wireless-firmware",
      "env": "DuoWL_V3_STREAM_ESPNOW",
      "role": "receiver",
      "transport": "espnow_stream",
      "board": "duo_wl_v3",
      "label": "Necklace — ESP-NOW Live (受信)",
      "description": "会場同報のライブ音声を受信して触覚再生。",
      "fwVersion": "v0.3.0",
      "fullSerial": { "filename": "wl_duo_wl_v3_stream_firmware_full_serial.bin", "size": 1100000, "mtime": 1717400000000 }
    },
    {
      "id": "snd/atom_audio_tx",
      "repo": "wireless-sender-firmware",
      "env": "M5Stack_basic_AudioStream_ModuleAudio",
      "role": "transmitter",
      "transport": "espnow_stream",
      "board": "m5stack_core",
      "label": "ESP-NOW 送信機（PA 入力）",
      "description": "PA ライン入力を ESP-NOW で同報する送信機。",
      "fwVersion": "v0.1.0",
      "fullSerial": { "filename": "snd_atom_audio_tx_firmware_full_serial.bin", "size": 900000, "mtime": 1717400000000 }
    }
  ]
}
```

### variant フィールド

| フィールド | 必須 | 説明 |
|---|:--:|---|
| `id` | ✅ | manifest 内で一意な ID（`<repo-short>/<env>`） |
| `repo` | ✅ | 由来 repo 名 |
| `env` | ✅ | PlatformIO env 名 |
| `role` | ✅ | `receiver` / `sensor` / `broker` / `transmitter`（`node-roles.md`） |
| `transport` | ✅ | `udp` / `mqtt` / `espnow_stream` |
| `transports` | ➖ | 複数 transport 対応時のリスト |
| `board` | ➖ | 基板識別子（書込時の board mismatch 検証に使用）。v2 fragment では明示推奨。v1 からの推論で決まらない場合は省略可（mismatch 検証は board 未定なら skip） |
| `label` | ✅ | Studio 表示名（人間向け） |
| `description` | ➖ | 補足説明 |
| `fwVersion` | ✅ | ビルドに焼かれた FIRMWARE_VERSION |
| `appOta` | ➖ | Wi-Fi OTA 用 app-only イメージ（Wi-Fi ノードのみ） |
| `fullSerial` | ✅ | USB serial download 用 merged イメージ |

- `appOta` は Wi-Fi 経路を持つノード（receiver(udp/mqtt) / broker / sensor）のみ。transmitter / espnow_stream 受信機は serial のみ。
- `fullSerial` は全 variant 必須（Studio からの初回書込は USB serial が基本経路）。

## 5. 後方互換（移行）

- Hapbeat はリリース前のため後方互換レイヤは作らない。manifest は v2 に一本化する。
- ただし Studio 側 reader は、`variants` 不在で `envs` のみの旧 manifest（dev plugin 等）を受け取った場合、各 env を `role:"receiver", transport:"udp"` の variant として解釈してよい（dev 環境の暫定動作）。これは互換目的ではなく **dev plugin がまだ v1 を返すための glue**。

## 6. 関連文書

- `node-roles.md` — role/transport/board taxonomy
- `schemas/firmware-manifest.schema.json` — 本 manifest の JSON Schema
- `../docs/decision-log.md` DEC-034
