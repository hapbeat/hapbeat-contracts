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

## 4. manifest v3 フォーマット

> **schema v3（DEC-035）**: 各 env が独立 semver を持つ前提に拡張。artifact に `contentHash`（バイト同一性・advisory）と `path`（private repo の same-origin proxy URL）、version/variant に `buildSha`（監査）を追加。reader は **v2/v3 両対応**。

```json
{
  "schema_version": 3,
  "generated_at": 1717400000000,
  "variants": [
    {
      "id": "dev/band_v3",
      "repo": "hapbeat-device-firmware",
      "env": "band_v3",
      "role": "receiver",
      "transport": "udp",
      "transports": ["udp", "mqtt"],
      "board": "band_wl_v3",
      "hapbeat": true,
      "label": "Band — Wi-Fi (UDP/MQTT)",
      "description": "標準の装着デバイス。Unity 等 SDK 連携 + センサ通知。",
      "fwVersion": "0.1.4",
      "appOta":     { "filename": "dev_band_v3_0.1.4_firmware_app_ota.bin",     "size": 1234567, "mtime": 1717400000000, "contentHash": "sha256:1111111111111111111111111111111111111111111111111111111111111111", "path": "/firmware/hapbeat-device-firmware/dev_band_v3_0.1.4_firmware_app_ota.bin" },
      "fullSerial": { "filename": "dev_band_v3_0.1.4_firmware_full_serial.bin", "size": 1556789, "mtime": 1717400000000 },
      "buildSha": "9f3d058",
      "versions": [
        {
          "fwVersion": "0.1.4",
          "tag": "dev/band_v3/v0.1.4",
          "publishedAt": 1718600000000,
          "buildSha": "9f3d058",
          "appOta":     { "filename": "dev_band_v3_0.1.4_firmware_app_ota.bin",     "size": 1234567, "contentHash": "sha256:1111111111111111111111111111111111111111111111111111111111111111" },
          "fullSerial": { "filename": "dev_band_v3_0.1.4_firmware_full_serial.bin", "size": 1556789 }
        },
        {
          "fwVersion": "0.1.3",
          "tag": "dev/band_v3/v0.1.3",
          "publishedAt": 1716000000000,
          "appOta":     { "filename": "dev_band_v3_0.1.3_firmware_app_ota.bin",     "size": 1233000 },
          "fullSerial": { "filename": "dev_band_v3_0.1.3_firmware_full_serial.bin", "size": 1555000 }
        }
      ]
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
      "fwVersion": "0.3.0",
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
      "fwVersion": "0.1.0",
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
| `hapbeat` | ➖ | `true` = 装着型 Hapbeat 本体（`duo_wl_*` / `band_wl_*`）、`false` = エコシステム周辺機器（broker / sensor / transmitter）。Studio はファームライブラリ/オンボーディングを**この値**でグループ分けする（`role` ではない: サードパーティ製ノードも `role=receiver` になり得るため、role は「Hapbeat か否か」の信頼できる判定にならない）。省略時は board 接頭辞（`duo_wl`/`band_wl`）から推論 |
| `label` | ✅ | Studio 表示名（人間向け） |
| `description` | ➖ | 補足説明 |
| `fwVersion` | ✅ | **最新版**の FIRMWARE_VERSION（`versions[0]` のコピー）。**先頭 `v` を含まない正準形**（例 `0.2.0`）。表示側が `v` を付与するため、集約時に旧ファームが焼き込んだ `v` 付き値（例 `v0.1.0`）は剥がす |
| `appOta` | ➖ | **最新版**の Wi-Fi OTA 用 app-only イメージ（Wi-Fi ノードのみ） |
| `fullSerial` | ✅ | **最新版**の USB serial download 用 merged イメージ |
| `buildSha` | ➖ | 最新版のビルド元 commit sha（監査用）。`versions[0].buildSha` のミラー |
| `versions` | ➖ | **アーカイブを含む全バージョン**（新しい順）。各要素は `{fwVersion, tag?, publishedAt?, buildSha?, appOta?, fullSerial?}`。省略時は最新のみ（dev 環境等） |

#### `versions[]` 要素フィールド

| フィールド | 必須 | 説明 |
|---|:--:|---|
| `fwVersion` | ✅ | その版の FIRMWARE_VERSION（正準形・先頭 `v` なし。dev build は `dN` 接尾辞） |
| `tag` | ➖ | 由来 GitHub Release タグ。**env 別 namespaced** = `<repoShort>/<env>/vX.Y.Z`（例 `dev/necklace_v3/v0.1.4`） |
| `publishedAt` | ➖ | **リリースタグの公開日時（epoch ms）**。artifact の `mtime`（CI が `.bin` を取得した時刻 ≒ デプロイ時刻）とは別物で、Studio は版の「リリース日」表示にこちらを使う。GitHub Release を経由しない dev/手書き manifest では省略 |
| `buildSha` | ➖ | ビルド元 commit sha（監査用） |
| `appOta` | ➖ | その版の Wi-Fi OTA 用 app-only イメージ |
| `fullSerial` | ➖ | その版の USB serial download 用 merged イメージ |

#### artifact フィールド（`appOta` / `fullSerial`）

| フィールド | 必須 | 説明 |
|---|:--:|---|
| `filename` | ✅ | 成果物ファイル名 |
| `size` | ✅ | バイト数 |
| `mtime` | ➖ | ファイル更新時刻（epoch ms・CI 取得時刻）。リリース日は `version.publishedAt` を使う |
| `contentHash` | ➖ | **公開バイトの sha256**（`sha256:<64hex>`。appOta は app-only / serial 専用 env は full）。**advisory** — 「バイトは変わったのに版据え置き」を検出する識別子であって **OTA gate ではない**（デバイスは自イメージの hash を報告できない） |
| `path` | ➖ | 成果物の**絶対 URL**（same-origin proxy or CDN）。存在時は consumer が `<BASE>/<filename>` を組み立てず**この URL をそのまま fetch**。private repo 配布で必須（filename だけでは到達不可） |

- `appOta` は Wi-Fi 経路を持つノード（receiver(udp/mqtt) / broker / sensor）のみ。transmitter / espnow_stream 受信機は serial のみ。
- `fullSerial` は全 variant 必須（Studio からの初回書込は USB serial が基本経路）。

### アーカイブ（過去バージョンへのロールバック）

GitHub Releases は過去リリースを保持し続ける（新リリースで旧版は消えない）。配布側の集約は **直近 N リリース**（既定 6）を全て取り込み、variant ごとに `versions[]` へ新しい順で格納する。これにより Studio はユーザーがいつでも過去バージョンへ書き戻せる（例: v0.1.4 で問題が出たら v0.1.3 を選んで再書込）。

- 成果物ファイル名はバージョンを含めて衝突回避する: **`<repo-short>_<env>_<fwVersion>_<stem>.bin`**
- variant のトップレベル `fwVersion`/`appOta`/`fullSerial` は常に `versions[0]`（最新）のコピー（versions 非対応の reader 互換）。

## 5. 後方互換（移行）

- Hapbeat はリリース前のため後方互換レイヤは作らない。manifest は v2 に一本化する。
- ただし Studio 側 reader は、`variants` 不在で `envs` のみの旧 manifest（dev plugin 等）を受け取った場合、各 env を `role:"receiver", transport:"udp"` の variant として解釈してよい（dev 環境の暫定動作）。これは互換目的ではなく **dev plugin がまだ v1 を返すための glue**。

## 6. 関連文書

- `node-roles.md` — role/transport/board taxonomy
- `schemas/firmware-manifest.schema.json` — 統合 manifest の JSON Schema（v3）
- `schemas/firmware-manifest-fragment.schema.json` — per-release fragment の JSON Schema
- `../docs/decision-log.md` DEC-034 / DEC-035

## 7. Per-variant independent versioning（DEC-035）

各 PlatformIO env は **独立した semver** を持つ。1 env のリリースが他 env の version を動かさない。

- **真実ソース**: 各 firmware repo ルートの `firmware-versions.json`（`{ "_repoShort": "...", "envs": { "<env>": "X.Y.Z", ... } }`）。タグはここから導出し、食い違ったらファイルが正。
- **タグ**: env 別 namespaced = `<repoShort>/<env>/vX.Y.Z`（例 `dev/necklace_v3/v0.1.4`、`tx/m5stack_audio_tx/v0.1.0`）。CI の release trigger は `*/v*`、release job は **その 1 env のみ**ビルド/添付する（matrix 全 env を添付すると他 env が tag 由来の誤 `fwVersion` を継ぐ）。
- **デバイス報告 `FIRMWARE_VERSION`** は素の semver（dev build は `<base>dN`、`dN` は **env 単位**で進む）。`build_version.py` は `git describe --match "<repoShort>/<env>/v*"` で env 独立に解決する。`$PIOENV` 不明時は旧グローバル挙動に fallback。
- **content-hash（advisory）**: ビルドは `appOtaHash`（app-only sha256）を `variant.json`→fragment→manifest に伝播。「バイトは変わったが版据え置き」/「版上げたがバイト同一」を **警告**するための識別子で、自動 bump も OTA gate もしない（デバイスが自イメージ hash を報告できないため）。版をどの firmware で動かすかは人間が決める。
- `firmware-versions.json` に無く `platformio.ini` にある env は、グローバル fallback 共有による `fwVersion` 衝突を避けるため **警告/fail** とする。

## 8. Dynamic server-side aggregation（DEC-035）

統合 manifest を **実行時集約**（Cloudflare Pages Function）に移行する。リリースが Studio 再デプロイなしで TTL 内に反映される。

- Function（route = Studio の `${BASE_URL}firmware/manifest.json`）が各 firmware repo の `GET /releases?per_page=N` を読み、release body の fenced JSON か `manifest.fragment.json` asset から variant メタを取得 → variant id で group 化 → `versions[]` を semver 降順に。
- **firmware repo は private** のため、artifact `path` は **same-origin の asset proxy ルート**を指す（`browser_download_url` の匿名 cross-origin fetch は 401/404、署名付き URL も短命で不適）。proxy は server-side token で stream し、`repo`/`asset` を allowlist 検証（オープンプロキシ化防止）。
- **部分失敗の扱い**: 1 repo でも取得失敗したら、成功分 + committed fallback をマージして返す（部分 manifest を `200 + cache` で固定しない）。`Cache-Control: public, max-age=300` + ETag。全失敗時は committed fallback を `X-Manifest-Source: fallback` 付きで返す。
- fallback（`functions` 同梱の committed manifest）は低頻度 CI cron で live を叩いて更新（最新リリースに最大その間隔ぶん遅延しうる）。
- ビルド時集約（`aggregate-firmware-manifest.mjs`）は fallback 生成用に残す。動的 Function が production 稼働を確認してから、配布側の集約 download/aggregate ステップと `repository_dispatch` を撤去する（**唯一の不可逆ステップ・最後**）。
