# SDK multi-stream session model

## 1. Scope

本仕様は、Hapbeat SDK が WifiUdp の `STREAM_BEGIN / STREAM_DATA / STREAM_END` を用いて、1 アプリから複数の論理 source を複数の target へ同時送信するための共通契約を定める。wire format は `message-format.md` と `stream-session-v2.md` に従う。

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

1. 旧 effective target にだけ一致していた endpoint から source を直ちに除外し、Reconcile
   完了後の STREAM_DATA を直ちに停止する。最後の source の END は §6 の endpoint lifecycle と
   実装の linger 方針に従って exact unicast で送る（Address Override 自体は即時 END を要求しない）。
2. 新 effective target に一致する既知 endpoint には直ちに source を追加し、必要ならその
   endpoint だけへ BEGIN を送って送信を開始する。新 endpoint の cursor は既存の late-join 規約に
   従い、有限 source は frame 0 から開始する。
3. 新 effective target に一致する既知 endpoint が 0 台なら、source は
   `Deferred(NoResolvedEndpoint)` となり、SDK は直ちに discovery PING を送る。STREAM packet
   を broadcast してはならない。対応する PONG を受信したら、その endpoint を自動参加させる。
4. override による endpoint membership の変更は route-only update ではない。旧 endpoint の
   END と新 endpoint の BEGIN が必要になる場合でも、それぞれの endpoint への exact unicast
   に限定する。この別 endpoint session の終了・開始は、同一 endpoint session の packet を
   宛先集合をまたいで送る禁止事項には該当しない。caller が `playStream` を再発行したり Playback
   handle を置換したりする必要はない。この禁止は新 endpoint の frame 0 late-join を妨げない。

## 5. Mixing and wire profile

1. 同じ device endpoint に一致する logical source は、送信側で 1 endpoint session に混合する。異なる endpoint の source は別 session に分離する。
2. 標準出力は **16,000 Hz / stereo / PCM16 little-endian** とする。入力 source は StreamHub 内でこの形式へ正規化する。
3. source ごとに gain と linear-balance pan を適用してから加算する。和は §5.8 の limiter を通し、最後に 1 回だけ PCM16 範囲へ飽和させる。
4. pan は `-1.0` で left のみ、`0.0` で中央、`+1.0` で right のみとし、係数は次を用いる。

```text
leftGain  = gain * (pan <= 0 ? 1 : 1 - pan)
rightGain = gain * (pan >= 0 ? 1 : 1 + pan)
```

5. endpoint session の `STREAM_BEGIN` は `sample_rate=16000`、`channels=2`、`format=PCM16`、`total_samples=0`、`gain=1.0` とする。source gain / pan は PCM に適用済みとする。
6. 1 logical source が複数 endpoint に一致する場合、各 endpoint session がその source の独立 cursor を持つ。endpoint 間の packet 到達同期は保証しない。
7. **パラメータ変更の平滑化**: Playback の gain / pan を再生中に変えた場合、mixer は各 source の
   channel gain（§5.4 の leftGain / rightGain）を、直前の mix block の値から新しい値まで、その
   block 内でサンプルごとに線形補間する。block 境界での階段状の変化（zipper）を作ってはならない。
   新しく加わった source の最初の block は補間せず、指定値から始める（onset は source の PCM が持つ）。
8. **limiter**: limiter 係数が 1.0（非作動・release 完了後）で、和の絶対値のピークが full scale
   （32767）以下の block は値を一切変えない（soft knee も掛けない。limiter を通しても bit 単位で
   同一）。ピークが full scale を超える場合は gain reduction を掛ける。release 途中（係数 < 1.0）の
   block は、ピークが full scale 以下でも残りの係数と soft knee を適用する。
   - 目標: その block のピークを `0.9 × full scale` に収める係数 `0.9 × FS / peak`。
   - attack: 係数を下げる変化は、その block 内でサンプルごとに線形に適用する。
   - release: 係数を上げる変化は 1 block あたり最大 `+0.05` とし、1.0 まで戻す。
   - soft knee: 係数を掛けた後の値が `0.95 × FS` を超える部分は
     `0.95·FS + 0.05·FS · tanh((|v| − 0.95·FS) / (0.05·FS))` で丸める。
   - 最後に §5.3 の飽和を 1 回だけ行う。hard clamp だけで過大な和を処理してはならない。
9. **入力 resample**: 16,000 Hz 以外の入力は、少なくとも線形補間で変換する（最近傍は不可）。
10. mix block の長さ（例: 10 ms / 256 frame）と send-ahead は実装依存とするが、§5.7 / §5.8 はどの block 長でも満たす。

## 6. Lifecycle

1. endpoint session は最初の source が active になった時に BEGIN を 1 回送る。
2. source の追加・削除・gain / pan 変更だけでは BEGIN / END を送らない。
3. endpoint session の最後の source が停止または完了した時に END を 1 回送る。
4. 1 source の stop は同じ endpoint session の sibling source を停止してはならない。
5. Playback の stop は複数回呼んでも結果が変わらない。
6. live push source が Deferred の間、SDK は入力を無制限に保持してはならない。SDK は未解決中の write を drop するか、bounded buffer / backpressure を提供し、その方針を API 文書へ明記する。
7. 最後の source を外した endpoint session は、実装が既に持つ linger を適用してから END を送ってよい。
   linger 中も外れた source の DATA を送ってはならない。
8. `stream-session-v2.md` のdevice-issued leaseとgenerationを全streamに付ける。END後の300 ms cooldownは持たず、次世代を即開始できる。lingerとcooldownを混同しない。
9. v2非対応（旧）ファームの機器には `stream-session-v2.md` の Legacy receiver fallback に従い、その機器だけv1 streamと300 ms END→BEGIN guardで送る。SDKだけの更新で旧ファームの機器を無音にしない。

## 7. Conformance cases

各 SDK の memory / fake transport test は最低限、次を確認する。

1. 異なる 2 endpoint の source が別 endpoint session へ送られ、全 STREAM packet が exact unicast である。
2. 同じ endpoint の 2 source が 1 session で混合され、BEGIN は 1 回だけである。
3. source ごとの gain / pan / stop が sibling source に影響しない。
4. endpoint 未解決時は packet を送らず Deferred となり、PONG 後に source 先頭から Active になる。
5. 最後の source 停止時だけ END が 1 回送られる。
6. broadcast の STREAM packet が存在しない。v2機器では、旧世代END/BEGIN/DATAを遅延・並替えしても、新世代の再生を停止・再初期化・汚染しない。終了直後の新世代に300 msの待ちが入らない。旧ファームの機器にはv1 streamで送り、300 ms guardはその機器だけに掛かる。
7. Active source の Address Override は即時に endpoint membership を Reconcile し、旧 endpoint
   への DATA を停止する。最後の source の END は linger 方針に従い、既知の新 endpoint は frame 0
   で即参加する。caller が Playback を再発行せず、未知の新 target は即時 PING と PONG 後の自動参加
   になる。

8. 再生中に gain / pan を変えても、出力 PCM の隣接サンプル間の差が、変更前後それぞれの定常出力で
   生じる最大差を大きく超えない（block 境界に段差がない）。
9. limiter 非作動中の full scale 以下の和は limiter 前後で同一（0.95·FS〜FS の和も無加工）。full gain の正弦波 source を 4 本重ねても、出力が
   attack の最初の 2 block を除き ±32767 に張り付くサンプルは生じず（soft knee により < FS）、ピークは
   0.85〜0.95·FS に収まり、block 境界に段差がない。attack 中の block は係数が 1.0 から線形に下がるため、
   block 前半で knee の上限に達してよい。

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
