# hapbeat-contracts

## この repo は何か

Hapbeat SDK エコシステム全体の**中核仕様リポジトリ**です。
すべての実装 repo が参照する「信頼できる唯一の情報源 (Single Source of Truth)」として機能します。

本リポジトリで定義・管理する仕様:

- **Event ID 命名規則** -- 触覚イベントを一意に識別するための ID 体系
- **Kit 形式仕様** -- 触覚パターンをまとめた Kit ファイルのマニフェスト・ディレクトリ構造
- **UDP/TCP メッセージ仕様** -- SDK・デバイス間で流れるメッセージのフォーマット
- **デバイスアドレッシング仕様** -- グループ・ターゲット指定の方式
- **display-layout 仕様** -- OLED 表示レイアウトの JSON スキーマ
- **シリアル設定コマンド仕様** -- USB シリアル経由の設定コマンド体系
- **Bridge API 仕様** -- hapbeat-bridge が公開する API エンドポイントの定義
- **バージョニング方針** -- 仕様のバージョン管理と互換性の維持ルール

## 全体の中での位置づけ

hapbeat-contracts は**依存関係の起点**です。

```
hapbeat-contracts (ここ)
 ├── hapbeat-kit-tools
 ├── hapbeat-device-firmware
 ├── hapbeat-bridge
 ├── hapbeat-transmitter-firmware
 ├── hapbeat-unity-sdk
 ├── hapbeat-unreal-sdk
 └── hapbeat-creative-kit
```

他の全 repo はここで定義された仕様に従って実装されます。
hapbeat-contracts 自体は他のどの repo にも依存しません。

## 設計方針

**contracts 起点の開発フロー**を採用します。

1. まず hapbeat-contracts で仕様を策定・合意する
2. 合意された仕様を各実装 repo に反映する
3. 仕様変更が必要な場合は、まず hapbeat-contracts で議論・更新してから実装に着手する

これにより、複数 repo にまたがる仕様の不整合を防ぎ、各チーム・各 repo が同じ仕様に基づいて並行開発できる体制を実現します。

## 依存関係

| 方向 | 内容 |
|------|------|
| **この repo が依存するもの** | なし |
| **この repo に依存する repo** | hapbeat-kit-tools, hapbeat-device-firmware, hapbeat-bridge, hapbeat-transmitter-firmware, hapbeat-unity-sdk, hapbeat-unreal-sdk, hapbeat-creative-kit |

## 現在の状態

主要仕様は策定済みで、各実装 repo が本リポジトリの仕様に基づいて稼働中です。

### specs/（規範的な仕様文書）

| ファイル | 内容 |
|---|---|
| `kit-format.md` | Kit マニフェスト形式・ディレクトリ構造・フィールド定義 |
| `event-id.md` | Event ID 命名規則（`<kit-name>.<clip-name>` 形式） |
| `message-format.md` | UDP/TCP メッセージプロトコル（PLAY/STOP/STOP_ALL/CONNECT_STATUS 他、`udp` transport） |
| `node-roles.md` | ノード役割 / 通信モード taxonomy（receiver/sensor/broker/transmitter × udp/mqtt/espnow_stream、DEC-034） |
| `mqtt-transport.md` | MQTT transport（センサ起点の遠隔通知。topic/payload/broker 発見） |
| `espnow-stream.md` | ESP-NOW streaming transport（会場同報のライブ音声。packet 形式、DEC-033） |
| `firmware-distribution.md` | ファーム配布 manifest（複数 repo × role/transport/board の集約） |
| `device-addressing.md` | デバイスアドレッシング仕様（`group_<N>` suffix 方式） |
| `display-layout.md` | OLED display_layout.json スキーマ |
| `serial-config.md` | シリアルコマンド仕様（全ノード共通の設定プロトコル + 役割固有コマンド） |
| `kit-install-protocol.md` | Kit インストールプロトコル（TCP 経由の転送手順） |
| `bridge-api.md` | hapbeat-bridge 公開 API 仕様 |
| `internal-bridge-transmitter.md` | Bridge ↔ Transmitter 内部プロトコル（ESP-NOW 経路） |
| `versioning.md` | 仕様バージョニング方針・互換性ルール |

### schemas/

JSON Schema ファイル（manifest 検証用）。

### fixtures/

テスト・検証用サンプルデータ。
