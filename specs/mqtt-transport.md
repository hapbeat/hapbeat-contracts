# MQTT transport 仕様書

## 1. 概要

`mqtt` transport は、**センサ起点の遠隔通知**ユースケース（例: 施設内のセンサ値をトリガに、離れた場所の装着者へ振動通知）のための通信モード。

```
[sensor node] --publish--> [broker node (組み込み MQTT)] --deliver--> [receiver node(s)]
   role=sensor                 role=broker                              role=receiver, transport=mqtt
```

- **broker は Hapbeat の組み込みノード**（M5 AtomS3 等、`role=broker`）で動作する。PC は不要（無人常設可。DEC-034）。
- 施設の既存 Wi-Fi（LAN）上で完結する。Studio / Helper は **セットアップ・管理専任**で、稼働中のデータ経路には介在しない。
- payload は既存 UDP `PLAY`（`message-format.md` 0x01）と意味的に等価。**触覚資産（Kit/event）は transport 非依存**で共通。

## 2. ブローカー

| 項目 | 値 |
|---|---|
| 実体 | Hapbeat broker ノード（`role=broker`）上の組み込み MQTT broker |
| ポート | 1883（既定。`set_broker_config.port` で変更可、plaintext、LAN 内前提） |
| mDNS | サービス `_mqtt._tcp`（ポートを advertise）、ホスト名はデバイス名（既定 `<board>-<MAC4>`） |
| 認証 | LAN 内前提のため必須としない（将来 username/role 分類は任意拡張） |
| QoS | **1（at-least-once）+ アプリ層の定期再送**（§2.1） |

> plaintext/no-auth は「施設の隔離 LAN 内」を前提とする割り切り。インターネット越え/TLS が要るユースケースは本仕様の対象外（別途検討）。

### 2.1 配信信頼性モデル（MQTT は「確実に届く」ことが重要）

MQTT transport の主用途は **UDP とは異なる**。UDP は「ライブ会場の同期触覚」で momentary・遅延より欠落が正だが、
**MQTT は「施設アラートの遠隔通知」（例: ナースコール色灯 → 離れた装着者へ振動）で、数秒の遅延は許容する代わりに
"アラートが起きたことが確実に伝わる" ことが最重要**。このため **QoS 1（at-least-once）** を使う。

**実装（2026-06-13 に PubSubClient → 256dpi/MQTT へ移行）**:

- クライアント（sensor publisher / receiver subscriber）は **256dpi/MQTT（arduino-mqtt, lwmqtt）** を使い、
  `publish(..., qos=1)` / `subscribe(..., qos=1)`。`publish` は PUBACK を同期待機する（at-least-once）。
- 組み込み broker（sMQTTBroker v0.1.8）は **publisher の QoS 1 PUBLISH に PUBACK を返し、subscriber へ
  QoS 1 ヘッダを保持して relay する**。これは参照実装（HospitalColorSensor）と同一の実績ある構成。
- **publisher→broker は真の at-least-once**（lwmqtt が PUBACK まで再送）。broker→subscriber は QoS 1 ラベル
  での単発配信（subscriber は PUBACK を返すが、broker 側の再送キューは持たない＝確立済み TCP 上では実質確実、
  接続断時のみ取りこぼし得る）。
- それを補完するため、**アプリ層の定期再送も併用する**: sensor はアラート条件（一致 `key`）が継続している間、
  `debounce_ms` 間隔で同じ `<root>/play` を再送し続ける（§5、既定 4000ms）。瞬間的なアラートには
  `debounce_ms` を短く設定する。

> 配信保証の階層: ① QoS 1（publisher→broker の at-least-once）+ ② TCP の信頼性（broker→subscriber）+
> ③ アプリ層の定期再送（接続断・取りこぼしのバックストップ）。`debounce_ms` がユーザー可変な再送ノブ。
> 真の end-to-end QoS 1（broker→subscriber の再送キュー）が要るユースケースが立ち上がったら、broker の
> PUBACK 追跡 + 再送実装を別途検討する（現状の sMQTTBroker は subscriber PUBACK を無視）。

## 3. ブローカー発見（zero-config）

receiver / sensor は broker を以下の優先順で解決する。

1. `set_broker_host` で `"auto"`（既定）の場合: **mDNS `_mqtt._tcp` browse** で `hapbeat-broker` を発見。
2. 明示ホスト/IP が設定されている場合: それを使用。
3. （任意 fallback）ゲートウェイ subnet 上の固定オクテット（broker の `set_broker_config.static_octet`）から算出。

broker は起動時に mDNS 登録 + 固定 IP（`static_octet`）を自己設定する。これにより**同一 LAN なら設定不要で繋がる**。

## 4. トピックとペイロード

トピックは平坦な CSV を避け、**役割で分けた階層 + JSON payload** を用いる（参考実装の踏襲ではなく再設計）。

**topic root**: トピックの第 1 階層（既定 `default-topic`）。sender は色ごと / カード単位に送信
root を選べ（§5 `topic`）、receiver は購読する root を複数選べる（§6 `recv_topics`）。同一 broker
上で複数システム / グループを分離したい場合に使う。以下の表は既定 root（`default-topic`）を
`hapbeat` と略記せず、説明上の例として示す。

| トピック | publisher | subscriber | retain | 用途 |
|---|---|---|---|---|
| `hapbeat/play` | sensor | receiver | false | event 再生コマンド |
| `hapbeat/stop` | sensor | receiver | false | event 停止コマンド |
| `hapbeat-sys/presence/<client_id>` | sensor / receiver | broker / 管理 | **true** | ノード自己紹介（§4.4） |

> **presence は固定 root（`hapbeat-sys`）で、ユーザーの `topic_root` から独立**（DEC-034
> follow-up, 2026-06-13）。presence はシステム内部のノード台帳であり、ユーザーが見る
> イベントチャンネル（`<topic_root>/play`）とは別系統に保つ。broker は `/presence/`
> セグメントで presence を識別する（root 非依存）ので、固定 prefix はユーザー topic と
> 衝突しなければよい。`play`/`stop` の root は §7 の `topic_root` で可変。

### 4.1 `hapbeat/play` payload（JSON）

| フィールド | 型 | 説明 |
|---|---|---|
| `event_id` | string | Kit manifest `events`（command-mode）キー。`message-format.md` PLAY と同義 |
| `target` | string | ターゲットアドレス（空 = 全台）。`device-addressing.md` 準拠 |
| `gain` | number | 0.0〜1.0 |
| `loop` | bool | optional。ループ再生（既定 false）。receiver の alert-loop 設定（§6）と OR される |
| `oled` | string | optional。受信機の OLED に表示する文言（≤32 文字、例 `"Red alert occured"`）。空/未指定 = 表示なし。色ごとに mapping で設定する（§5） |
| `key` | string | optional。検知した分類キー（色名、例 `"red"`、§5 の mapping `key`）。情報用 — Studio の通信フロー図が「どの色が発火したか」を表示する。再生判定には使わない |
| `aid` | string | optional。**alert episode id**（§6.2）。検知状態が変わるたびに sensor が発行する一意 ID（`<mac4>-<seq>`）。同じ状態が続く間は同じ `aid` で再送される。空/未指定は episode 抑制なし（毎回再生＝旧挙動 / SDK 直送） |
| `critical` | bool | optional。**重要フラグ**（§6.3）。true の色は receiver が「制限モード」でも再生する。false/未指定は通常（制限モード中は抑制）。色ごとに mapping で設定する（§5） |
| `ts` | number | optional。送信時刻（ms epoch、情報用） |

例:
```json
{"event_id": "alert-kit.urgent", "target": "player_1/chest", "gain": 1.0, "loop": false, "oled": "Red alert occured"}
```

### 4.2 `hapbeat/stop` payload（JSON）

| フィールド | 型 | 説明 |
|---|---|---|
| `event_id` | string | 停止対象（空文字 = target の全 event 停止） |
| `target` | string | ターゲットアドレス |

### 4.3 retain / late-joiner

- `hapbeat/play` / `hapbeat/stop` は **retain=false**。触覚イベントは momentary であり「遅れて届くより消えた方がマシ」（UDP と同じ思想）。
- 再起動した receiver は過去のイベントを取りこぼすが、通知用途では許容。retain による誤再発火を避ける。
- 継続状態（例: 持続アラート）が要るユースケースが立ち上がった時点で、別途 retained な `hapbeat/state/<target>` トピックを追加検討する（現時点では未定義）。

### 4.4 `hapbeat/presence/<client_id>` payload（JSON, retained）

クライアント（sensor / receiver）が **broker 接続直後に 1 回 publish** する自己紹介。retained なので
broker・管理ツールは接続順に依存せず全ノードの素性を把握できる。broker はこれを LCD 表示
（クライアント名一覧）と `get_info.mqtt_clients`（§8）に使う。

| フィールド | 型 | 説明 |
|---|---|---|
| `name` | string | デバイス名（NVS `dev_name`、未設定時は `<board>-<MAC4>` 既定名） |
| `role` | string | `sensor` / `receiver`（node-roles.md taxonomy） |
| `mac` | string | MAC アドレス |
| `fw` | string | ファームウェアバージョン |

`<client_id>` は MQTT clientId（`hapbeat-sensor-<MAC>` / `hapbeat-<mac>`）。トピックは
固定 root `hapbeat-sys/presence/<client_id>`（§4 表の注記）。
旧ファームは presence を送らない — broker は clientId プレフィックスからの推定に degrade する。

## 5. センサ → event マッピング（sensor ノード）

sensor は「センサ読み取り値の分類」→「発火する `hapbeat/play` payload」の対応表を持つ。
表は Studio の mapping editor が編集し、`serial-config.md` の `set_sensor_mapping` でノードに書き込む。

mapping エントリ:

| フィールド | 型 | 説明 |
|---|---|---|
| `key` | string | 分類ラベル（例: 色名 `red`/`blue`） |
| `match` | object | センサ種別依存の一致条件（色センサ: RGB 閾値ボックス `r_min`/`r_max`/`g_min`/`g_max`/`b_min`/`b_max`） |
| `event_id` | string | 一致時に publish する event |
| `target` | string | ターゲットアドレス |
| `gain` | number | 0.0〜1.0 |
| `debounce_ms` | number | optional。同一 key 連続発火の最小間隔（既定はノード実装値） |
| `oled` | string | optional。一致時に publish する `play` payload の `oled` 文言（≤32 文字、§4.1）。受信機の OLED に表示する。空/未指定 = 表示なし |
| `critical` | bool | optional。true なら payload に `critical:true` を載せる（§6.3）。受信機が「制限モード」でも再生される重要色（例: 赤）。false/未指定は通常色（制限モード中は抑制される） |
| `topic` | string | optional。この key の publish 先 topic **root**（スラッシュ無し、≤32 文字）。指定時は `<root>/play` ではなく `<topic>/play` へ publish する。空/未指定はセンサ既定 root（§7 `topic_root`）。色やセンサ単位で受信機グループを分けたい場合に使う（receiver は §7 の自 root を subscribe するので、`topic` と受信機 root を合わせると一致グループのみ届く） |
| `topics` | string[] | optional。**複数の送り先 root**。指定時（要素 ≥ 1）はこの key を各 `<root>/play` に publish する（1 色を複数の受信機グループへ同報）。`topic`（単一）より優先。同一 payload・同一 `aid` を各 topic へ送るので、複数 topic を購読する受信機でも `aid` 抑制で 1 回のみ作用する。空/未指定は `topic` → センサ既定 root にフォールバック |

- sensor は周期的にセンサを読み、`match` に最初に一致した `key` の payload を `<topic or topic_root>/play` に publish する。
- 色センサの分類は chromaticity（clear 正規化 RGB）で行うことを推奨（明るさ変動に頑健）。実装詳細はファーム側。
- **既定はトピック単一・payload ルーティング**（全色が `topic_root/play` へ。`target` で受信機を選別）。`topic` はそれをトピック分割したい場合の任意機能で、Studio 側で「送り先」を登録 → mapping で選択する UI を提供する。

## 6. receiver 側の扱い

- `transport=mqtt` の receiver は broker に接続し、**購読 topic root のリスト `recv_topics`**
  （`serial-config.md` §4.16 `set_recv_topics`、NVS `hapbeat/recv_topics`）の各 root について
  `<root>/play` / `<root>/stop` を subscribe する。`recv_topics` が空なら既定チャンネル
  `default-topic` のみ購読する。sender 側で設定した送信 topic と一致させたものだけが届く。
- 受信 payload の `target` を自アドレスと照合（`device-addressing.md`）し、一致時のみ `event_id` を再生。
- payload に `oled` があれば再生と同時に OLED へ表示する（§4.1, item 9）。ループ中は acknowledge
  まで継続表示（§6.1）。
- 複数 root を購読しても、play/stop の判定は topic の末尾（`/play` / `/stop`）で行う
  （自分が購読した topic のみ届くため）。
- 再生経路・Kit・event table は `udp` と完全共通（transport だけが差し替わる）。

### 6.1 alert-loop モード（受信機設定）

施設アラート用途では「気づいて止めるまで鳴り続ける」挙動が要る（参照: 病院アラート）。
receiver は **alert-loop モード**（NVS `hapbeat/alert_loop`, 既定 ON）を持つ。

- **ON（既定）**: 受信した `play` を **本体ボタンで確認（acknowledge）されるまでループ再生**する。
- **OFF**: 1 回だけ再生（単発）。
- payload の `loop`（§4.1）とは OR される（どちらかが真ならループ）。
- 設定は `serial-config.md` §4.x `set_alert_mode` で書き込み、`get_info.alert_loop`（bool）で読む。
  ファームは NVS を都度読むため、変更は**次の受信アラートから即時反映**（再起動不要）。

#### OLED 表示の継続

`oled`（§4.1）付きのアラートをループ再生中は、その文言を **acknowledge されるまで OLED に出し続ける**
（sticky）。停止（ack / STOP）で消去する。単発（loop=false）の場合は短時間（~2.5s）だけ表示。

#### ボタンによる acknowledge（誤操作・スタック対策）

アラートループ中、本体ボタンは **ack 専用**（割り当てられた通常動作＝音量等は発火しない）。停止には
**意図的な長押し**を要求する:

1. アラート開始後に一度ボタンが**離された**こと（= 通知到来時に既に押し込まれていた／スタックした
   ボタンでは停止できない。armed 条件）、かつ
2. その後 **約 1 秒の連続長押し**。

これを満たすと当該 receiver でアラートを停止する。瞬間的なタップや押しっぱなしでは止まらない
（病院アラート用途で「人が意図して気づいて止めた」ことを担保するため）。

### 6.2 alert episode と受信側ローカル抑制（確実な通知 + 二度鳴り防止）

「危険状態に確実に気づかせるが、気づいて止めたら鳴り続けない」を、**状態変化をトリガとした
episode id（`aid`）** と **受信側ローカル抑制**で実現する。

- **sensor**: 検知 `key` が変化するたびに新しい `aid`（`<mac4>-<seq>`、seq は boot 時にランダム seed）
  を発行する。同じ `key` が続く間は **同じ `aid`** を `debounce_ms` 間隔で再送し続ける
  （取りこぼしのバックストップ）。`key` が変われば（例: 赤→別色→赤、赤→無→赤）新しい `aid`。
- **receiver（個体ごとに独立判定）**: ある `aid` に対して **一度だけ反応**する。
  - 新しい `aid` の `play` → 再生（loop / 単発）。
  - 同じ `aid` の再送 → **無視**（ループ中なら再スタートしない、単発なら二度鳴りしない、
    ack 済みなら鳴らない）。
  - ボタン ack → 当該 receiver で停止 + OLED 消去。`aid` は抑制されたままなので、**状態が変わって
    新しい `aid` が来るまで再び鳴らない**。
- **stop は sender に送らない**。各 receiver が自分の判断で当該 `aid` を抑制する。これにより
  **複数 receiver** が 1 broker にぶら下がる将来構成でも、receiver A で止めても B は鳴り続け、
  各々が自分のタイミングで ack できる（A の ack は B に影響しない）。sender は状態を反映して
  送り続けるだけ（安価）。`aid` が空の場合は抑制せず毎回再生（旧挙動 / SDK 直送）。

### 6.3 制限モード（receiver の重要色フィルタ）

施設アラート用途では「いつもは全色を通知、忙しい時は重要色（赤など）だけ通知」を receiver 側で
切り替えたい。これを **`critical` フラグ（payload）+ 制限モード（receiver 設定）** で実現する。

- **sender**: 重要色の mapping に `critical:true` を設定すると（§5）、その color の `play` payload に
  `critical:true` が載る。それ以外の色は `critical` なし。
- **receiver の制限モード**（NVS `hapbeat/alert_limit`, bool, **既定 OFF**）:
  - **OFF（既定 = 全て再生）**: `critical` の有無に関わらず全ての `play` を再生する。
  - **ON（制限モード）**: `critical:true` の payload **のみ** 再生し、それ以外は無視する。
- 判定は `aid` の episode 抑制（§6.2）**より前**に行う。制限モードで弾かれた payload は episode を
  消費しない（= モードを OFF に戻せば、次の同一 `aid` 再送で再び鳴れる）。
- 切り替えは **本体ボタンの `limit_toggle` アクション**（`serial-config.md` §4.17）で行う（シリアル
  set コマンドは持たない）。トグルのたびに OLED に現在モード（`制限モード` / `全て再生`）を短時間
  表示する。現在値は `get_info.alert_limit`（bool）で読む。RAM キャッシュを都度参照するため**次の
  受信から即時反映**（再起動不要）。
- payload に `critical` を持たない sender（SDK 直送等）は、receiver が制限モード ON のとき全て抑制される
  点に注意（重要色だけ通したいなら sender 側で `critical` を付ける）。

## 7. クライアント側 MQTT 設定（sensor / receiver(mqtt) 共通）

`serial-config.md` §4.8 `set_broker_host` で書き込む。設定面は以下の 3 項目に正規化する
設定面は以下に正規化する。

| 項目 | NVS キー | 既定 | 意味 |
|---|---|---|---|
| `host` | `hapbeat/broker_host` | `"auto"` | broker の解決方法（auto = mDNS browse / 明示 IP・ホスト名） |
| `port` | `hapbeat/broker_port` (u16) | 1883 | 明示 host 時の接続ポート。`auto` 時は mDNS が advertise したポートが優先 |
| `topic_root` | `hapbeat/mq_root` | `"default-topic"` | §4 topic root（sender の既定送信 root）。receiver の購読 root は §6 `recv_topics` |
| `qos` | `hapbeat/mq_qos` (u8) | 1 | publish/subscribe の QoS（0 or 1）。既定は §2.1 の信頼性のため 1。低遅延優先時のみ 0 |

`get_info` は同名フィールド（`broker_host` / `broker_port` / `topic_root` / `mqtt_qos`）＋
`mqtt_connected`（bool, broker への接続状態）を返す。

## 8. broker の get_info 拡張フィールド

管理ツール（Studio の MQTT タブ / 通信フロー図）向けに、broker は `get_info` で以下を返す
（`node-roles.md` の get_info 拡張）。

| フィールド | 型 | 説明 |
|---|---|---|
| `mqtt_running` | bool | broker 稼働中か（既存） |
| `mqtt_port` | number | listen ポート（既存） |
| `static_octet` | number | 固定ホストオクテット（既存） |
| `mqtt_clients` | array | 接続中クライアント: `{id, name, role}`（presence 由来。presence 未受信時 name は省略） |
| `mqtt_pub_count` | number | 起動後の play/stop publish 総数（presence は数えない） |
| `mqtt_last_topic` | string | 最後の publish のトピック |
| `mqtt_last_payload` | string | 最後の publish の payload（128 byte で切詰め） |
| `mqtt_last_from` | string | 最後に publish したクライアントの name（presence 由来、無ければ sid）。Studio フロー図の「送信元」表示用 |

## 9. 関連文書

- `node-roles.md` — role/transport taxonomy と get_info 必須フィールド
- `serial-config.md` — `set_broker_host` / `set_broker_config` / `set_sensor_mapping`
- `message-format.md` — UDP PLAY（payload の意味的等価元）
- `device-addressing.md` — target 照合
- `../docs/decision-log.md` DEC-034
