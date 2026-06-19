# ポート台帳（Port Registry）

Hapbeat エコシステム全体で使用するネットワークポートの**単一の正**。
新しいサービス／ツールを追加するときは、まずここに登録してから実装する。

> 由来: DEC-036。旧 `bridge-api.md` のポート表は **deprecated の Bridge 設計**
> （DEC-026 で廃止）に基づくため、現行アーキテクチャ（device + hapbeat-helper +
> Studio）のポートは本文書を正とする。

## 1. 一覧

| ポート | プロトコル | 待受 / 所有者 | 役割 | 種別 |
|---|---|---|---|---|
| **7700** | UDP | **デバイス**（ファーム） | コマンド面: `PLAY` / `STOP` / `STOP_ALL` / `PING` / `STREAM_*` | デバイス固定・共有 |
| **7701** | TCP | **デバイス**（ファーム） | 設定面: `get_info` / Kit 配布 / OTA / `log_stream` / Wi-Fi / display-layout | デバイス固定・共有 |
| **7702** | UDP (OSC) | ツール（例: `hapbeat osc-bridge`） | OSC 入口 `/hapbeat/*` を受け、7700 へ中継 | ツールサービス |
| **7703** | WebSocket (TCP) | **hapbeat-helper** | ブラウザ↔helper の JSON `{type,payload}` リレー（Studio / web-sdk browser transport） | ツールサービス |
| **7100** | HTTP (TCP) | **hapbeat-python-sdk** `hapbeat launchpad` | ブラウザ↔launchpad の UI/API | ツールサービス |
| **5353** | UDP (mDNS) | デバイスが `_hapbeat._udp` を advertise | ゼロコンフィグ発見（TXT: `name`/`group`/`fw`/`mac`/`role`/`transport`） | 標準 mDNS |
| **1883** | TCP (MQTT) | broker（DEC-034、M5 組み込み） | 施設アラートの MQTT transport | 別 transport（`mqtt-transport.md`） |

「デバイス固定・共有」= デバイスが待ち受ける唯一のエンドポイント。**全送信側がここへ送る**（番号をツール別に分けられない、§3 参照）。
「ツールサービス」= 各ツールが自分で立てるサーバーポート。別番号で衝突回避する。

## 2. ホスト側の受信 bind 方針（最重要）

デバイスのコマンドポート 7700 は **単一の共有エンドポイント**。これに対し
**ホスト（PC）側でローカル 7700 を bind するのは daemon（hapbeat-helper）ただ一つ**とする。

- **helper（daemon）** … ローカル UDP 7700 を専有 bind。PONG とデバイスからの
  **非同期ブロードキャスト**（volume 変化等）を受ける。
- **各 SDK / ツール（python / web(Node) / unity / launchpad）** … 送信先は
  デバイスの 7700 だが、**受信は ephemeral（OS 任せの一時）ポートに bind** する。
  自分の `PING` への `PONG` は送信元 ephemeral ポートへ返るため **discovery は成立**する。
  失うのは「非同期ブロードキャスト受信」だけで、それが要るのは daemon のみ。

これにより **SDK スクリプト（や launchpad）と Hapbeat Studio を同時稼働**できる。
複数プロセスが同一ローカルポートを取り合うと、OS（特に Windows の `SO_REUSEADDR`）の
ポート共有挙動で PONG 配送が奪われ、helper が取りこぼして Studio がデバイスを見失う。

### 実装状況（2026-06-19 時点）

| 実装 | 受信 bind | 状態 |
|---|---|---|
| hapbeat-helper | 7700 を専有 | ✅ daemon として正 |
| hapbeat-unity-sdk | `new UdpClient(0)`（ephemeral） | ✅ 準拠 |
| hapbeat-python-sdk | 既定 ephemeral（`bind_port=0`）。`bind_port=port` で 7700 受信に opt-in 可 | ✅ 準拠（DEC-036 で既定化） |
| hapbeat-web-sdk (Node) | 7700 を試行 → busy なら ephemeral fallback | ⚠️ 概ね可。既定 ephemeral へ寄せる follow-up |

## 3. なぜコマンドポートを 1 本にするのか

ツール別に**デバイスポートを分けることはしない**。理由:

- **ハード制約ではない。** ESP32-S3 / lwIP は複数 UDP/TCP ソケットを同時に持てる。
  実際デバイスは **7700(UDP) + 7701(TCP) + mDNS(5353) を同時に listen** している。
- **1 サービス = 1 既知ポート**（HTTP=80 のような）という設計上の選択。コマンドポートを
  複数に割っても、全送信側がどのポートに送るか合意が要るうえ、競合の実体は
  **ホスト側の受信 bind**（§2）なのでデバイス側を割っても解決しない。利得が無い。
- **複数台 / プレイヤー分離**は **アプリ層の target アドレス + group** で解決済み
  （`device-addressing.md`）。ポート分割は不要。

## 4. 新規ポートを足すとき

1. 本台帳に行を追加（ポート / プロトコル / 所有者 / 役割 / 種別）。
2. 既存ポートと衝突しないことを確認。OS の動的ポート域（概ね 49152–65535）と
   よく使われるアプリポートを避ける。
3. デバイス待受を増やす変更は firmware 影響が大きいので原則避け、§3 の方針に従う。
