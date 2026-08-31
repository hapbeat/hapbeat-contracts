# SDK multi-stream session model

## 1. Scope

本仕様は、Hapbeat SDK が WifiUdp の `STREAM_BEGIN / STREAM_DATA / STREAM_END` を用いて、1 アプリから複数の論理 source を複数の target へ同時送信するための共通契約を定める。wire format は `message-format.md` から変更しない。

EspNowStreamSource / EspNowStreamReceiver / EspNowStreamRepeater は会場向け連続音声 transport であり、本仕様の SDK sender session には含めない。Python SDK を利用する TouchDesigner / VRChat integration は Python SDK の実装を共有し、独自の mixer や wire session を複製しない。

## 2. Terms

| 用語 | 定義 |
|---|---|
| logical source | clip、PCM buffer、live push、generator など、アプリが独立に開始・停止・調整する音声 source |
| Playback | 1 logical source の生存期間を表す handle。source ID、状態、gain、pan、loop、stop を所有する |
| device endpoint | PONG で確認した `(IPv4, UDP port, device address)` の組 |
| endpoint session | 1 device endpoint へ送る 1 本の wire stream。対応する全 logical source を混合した PCM を運ぶ |
| StreamHub | source、endpoint 解決、endpoint session、mixing、packet pacing を隠蔽する SDK 内の深い module |

## 3. Public capability

各言語の命名規則には従ってよいが、SDK は概念上、次の capability を 1 つの StreamHub から提供する。

```text
playStream(source, options) -> Playback

Playback:
  id
  status = Deferred | Active | Stopped
  deferredReason = NoResolvedEndpoint | None
  gain
  pan
  loop
  stop()  // idempotent
```

既存の `playClip`、`streamPcm`、`openStream`、generator helper 等の利便 API は残してよい。ただし、それぞれが独自の単一 session を管理してはならず、同じ StreamHub に source を登録する薄い入口にする。

## 4. Endpoint resolution

1. target 文字列は `device-addressing.md` の規則で、PONG が報告した完全な device address に照合する。
2. target に一致した各 device endpoint に 1 endpoint session を割り当てる。`STREAM_BEGIN.target` には PONG が報告した完全な device address を入れる。
3. `STREAM_DATA` と `STREAM_END` は target を持たないため、同じ endpoint session の全 packet を対応 endpoint の exact unicast へ送る。
4. target に一致する既知 endpoint が 0 台なら Playback を `Deferred(NoResolvedEndpoint)` とする。stream packet を broadcast してはならない。
5. 新しい PONG または endpoint expiry の後、StreamHub は source と endpoint の対応を再評価する。Deferred source が初めて解決した場合、有限 source は先頭から開始する。
6. device address または宛先 route の変更だけで STREAM_END / STREAM_BEGIN を交差経路へ送ってはならない。`message-format.md` の順序制約に従う。

### 4.1 Address Override の即時反映

Playback の Address Override（target）を変更した場合、StreamHub は次の tick を待たずに
新しい effective target で active source を再解決し、endpoint session の所属を Reconcile
しなければならない。再生を stop / play し直すことは要求しない。

1. 旧 effective target にだけ一致していた endpoint から source を直ちに除外し、最後の
   source ならその endpoint へ exact unicast の END を送って以後の STREAM_DATA を停止する。
2. 新 effective target に一致する既知 endpoint には直ちに source を追加し、必要ならその
   endpoint だけへ BEGIN を送って送信を開始する。
3. 新 effective target に一致する既知 endpoint が 0 台なら、source は
   `Deferred(NoResolvedEndpoint)` となり、SDK は直ちに discovery PING を送る。STREAM packet
   を broadcast してはならない。対応する PONG を受信したら、その endpoint を自動参加させる。
4. override による endpoint membership の変更は route-only update ではない。旧 endpoint の
   END と新 endpoint の BEGIN が必要になる場合でも、それぞれの endpoint への exact unicast
   に限定する。この別 endpoint session の終了・開始は、同一 endpoint session の packet を
   宛先集合をまたいで送る禁止事項には該当しない。Playback を replay してはならない。

## 5. Mixing and wire profile

1. 同じ device endpoint に一致する logical source は、送信側で 1 endpoint session に混合する。異なる endpoint の source は別 session に分離する。
2. 標準出力は **16,000 Hz / stereo / PCM16 little-endian** とする。入力 source は StreamHub 内でこの形式へ正規化する。
3. source ごとに gain と linear-balance pan を適用してから加算し、全 source の和を最後に 1 回だけ PCM16 範囲へ飽和させる。
4. pan は `-1.0` で left のみ、`0.0` で中央、`+1.0` で right のみとし、係数は次を用いる。

```text
leftGain  = gain * (pan <= 0 ? 1 : 1 - pan)
rightGain = gain * (pan >= 0 ? 1 : 1 + pan)
```

5. endpoint session の `STREAM_BEGIN` は `sample_rate=16000`、`channels=2`、`format=PCM16`、`total_samples=0`、`gain=1.0` とする。source gain / pan は PCM に適用済みとする。
6. 1 logical source が複数 endpoint に一致する場合、各 endpoint session がその source の独立 cursor を持つ。endpoint 間の packet 到達同期は保証しない。

## 6. Lifecycle

1. endpoint session は最初の source が active になった時に BEGIN を 1 回送る。
2. source の追加・削除・gain / pan 変更だけでは BEGIN / END を送らない。
3. endpoint session の最後の source が停止または完了した時に END を 1 回送る。
4. 1 source の stop は同じ endpoint session の sibling source を停止してはならない。
5. Playback の stop は複数回呼んでも結果が変わらない。
6. live push source が Deferred の間、SDK は入力を無制限に保持してはならない。SDK は未解決中の write を drop するか、bounded buffer / backpressure を提供し、その方針を API 文書へ明記する。

## 7. Conformance cases

各 SDK の memory / fake transport test は最低限、次を確認する。

1. 異なる 2 endpoint の source が別 endpoint session へ送られ、全 STREAM packet が exact unicast である。
2. 同じ endpoint の 2 source が 1 session で混合され、BEGIN は 1 回だけである。
3. source ごとの gain / pan / stop が sibling source に影響しない。
4. endpoint 未解決時は packet を送らず Deferred となり、PONG 後に source 先頭から Active になる。
5. 最後の source 停止時だけ END が 1 回送られる。
6. broadcast の STREAM packet と、経路をまたぐ短間隔 END -> BEGIN が存在しない。
7. Active source の Address Override は即時に endpoint membership を Reconcile し、旧 endpoint
   への送信を停止する。既知の新 endpoint は即参加し、未知の新 target は即時 PING と PONG 後の
   自動参加になる。

共通 fixture は `../fixtures/sdk-multi-stream-routing.json` を用いる。

## 8. SDK applicability

| SDK / integration | 適用方法 |
|---|---|
| Unity | StreamHub 相当の endpoint mixer と Playback handle を SDK 内に持つ |
| Unreal | subsystem / runner から endpoint session map を所有する StreamHub 相当へ委譲する |
| Python | 共通 StreamHub を実装し、clip / live / integration から共有する |
| JavaScript | 共通 StreamHub を実装し、Node / React Native / Browser transport で同じ endpoint semantics を使う |
| Arduino | 固定容量 source / endpoint pool と cooperative tick で同じ状態遷移を実装する |
| Godot | engine node に StreamHub 相当を持ち、Playback object を返す |
| TouchDesigner / VRChat | Python SDK の StreamHub と Playback を利用する。独自実装は持たない |
| EspNowStream receiver library | 対象外。EspNowStream transport 契約に従う |
