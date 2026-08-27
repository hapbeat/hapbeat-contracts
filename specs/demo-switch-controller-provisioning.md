# Demo Switch controller USB provisioning protocol

Demo Switch controller 専用の USB provisioning 契約。既存の Hapbeat device serial-config と共有せず、Demo Switch controller の USB CDC serial endpoint だけに適用する。Demo Switch UDP control（7710）は [`demo-switch-control.md`](demo-switch-control.md)、Hapbeat UDP command（7700）は既存の command 契約を正とする。

## Transport

| 項目 | 値 |
|---|---|
| Interface | USB CDC serial |
| Baud rate | 115200 |
| Encoding | UTF-8 |
| Framing | newline-delimited JSON (NDJSON)。1 line = 1 JSON object、LF (`0x0A`) 終端。CRLF を受ける実装は LF 前の CR だけを除去してよい。 |
| Line limit | LF を含めて 1024 UTF-8 bytes。超過 line は破棄し、後続 line を正常に処理できるよう resynchronize する。 |

JSON object 以外、空 line、複数 object を 1 line に連結した入力、1024 bytes を超える入力は無効である。controller は解析できる `id` がある無効 request には `error` response を返す。`id` を取得できない JSON 構文エラーまたは長過ぎる line では、`id:null` の `error` response を返してよい。

## Frames

全 request は `version:1`、一意な ASCII `id`、および `type` を持つ。`id` は host が request ごとに生成し、再試行時は同じ値を使う。controller は直近 request result を `id` とともに永続化し、同じ `id` の再試行には設定を再適用せず同じ response を返す。異なる request 内容で既存 `id` を再利用してはならない。

request の `type` は `get_config`、`set_config`、`factory_reset`、`reboot` のいずれか。controller は各 request に必ず 1 つの `response` frame を返す。response の `response` は `config`、`status`、`error` のいずれかで、それぞれ同名 object を持つ。version 1 の未知 field と未知 command は拒否する。

### Read configuration

```json
{"version":1,"type":"get_config","id":"read-001"}
```

```json
{"version":1,"type":"response","id":"read-001","response":"config","config":{"wifi_profiles":[{"ssid":"DemoLan","open":false,"wifi_password_set":true}],"hmd_ip":"192.168.10.20","controller_id":"m5-main","target_a_demo_id":"gloveball","target_b_demo_id":"dance","target_c_demo_id":"menu","shared_secret_set":true,"allow_unsigned":false,"isolated_lan":false,"next_sequence":43}}
```

`config` response は常に全 field を返す。`wifi_profiles` は最大 5 件の順序付き配列で、index 0 が現在 active/MRU profile である。各 profile は `ssid`、`open`、`wifi_password_set` だけを返す。`wifi_password` と `shared_secret` は、値、ハッシュ、長さ、encoding を含めて **絶対に response、log、diagnostic、fixture、telemetry に出してはならない**。

### Update configuration

```json
{"version":1,"type":"set_config","id":"setup-001","config":{"wifi_profiles":[{"ssid":"DemoLan","wifi_password":"input-only"}],"hmd_ip":"192.168.10.20","controller_id":"m5-main","target_a_demo_id":"gloveball","target_b_demo_id":"dance","target_c_demo_id":"menu"}}
```

`set_config.config` の controller-global field を省略した場合、現在値を保持する。`wifi_profiles` があれば全 profile list を置換する。list の各 SSID は一意、最大 5 件である。既存と同じ SSID の secured profile は `wifi_password` を省略して credential を保持できる。新しい secured SSID は `wifi_password` が必須である。`open:true` は password を持たず、同じ SSID の既存 credential を消去する。`clear_wifi_profiles:true` は全 Wi-Fi profile を消去する。`wifi_profiles` と `clear_wifi_profiles:true` は同じ request に含めてはならない。

| 設定 field | clear flag |
|---|---|
| `wifi_profiles` | `clear_wifi_profiles` |
| `hmd_ip` | `clear_hmd_ip` |
| `controller_id` | `clear_controller_id` |
| `target_a_demo_id` | `clear_target_a_demo_id` |
| `target_b_demo_id` | `clear_target_b_demo_id` |
| `target_c_demo_id` | `clear_target_c_demo_id` |
| `shared_secret` | `clear_shared_secret` |

`hmd_ip` は任意の manual override である。未設定または `clear_hmd_ip:true` のとき、controller は [`demo-switch-control.md`](demo-switch-control.md) の `DISCOVER` / `HERE` で前面 Quest を自動検出する。複数の Quest が応答した場合に自動選択してはならず、固定 `hmd_ip` を設定するか LAN を分離する。

`wifi_password` と `shared_secret` は set request でのみ書込み可能で、空文字は許可しない。`controller_id` の clear は新しいランダム controller ID を生成することを意味し、`null` を保存してはならない。

controller は request 全体を検証してから、更新された全 field、controller ID、次 sequence、重複 request result を単一の永続 transaction として commit する。1 field でも無効、clear と値が競合、または永続化に失敗した場合は、**一切の設定を変更せず** `error` を返す。設定途中の Wi-Fi 接続、UDP send、reboot は開始してはならない。

### Status and errors

成功した `set_config` は `status.state:"updated"`、`factory_reset` は `"reset"`、`reboot` は `"rebooting"` を返す。reboot は response の serial transmission を flush した後に開始する。

```json
{"version":1,"type":"response","id":"setup-001","response":"status","status":{"command":"set_config","state":"updated"}}
```

```json
{"version":1,"type":"response","id":"setup-001","response":"error","error":{"code":"invalid_config","message":"hmd_ip must be a unicast IPv4 address"}}
```

`error.code` は `invalid_json`、`line_too_long`、`unsupported_version`、`unknown_command`、`invalid_request`、`invalid_config`、`conflicting_update`、`write_failed`、`busy` のいずれか。`message` は secret を含めず、256 UTF-8 bytes 以下にする。

## Validation

- `id`、`controller_id`、各 `target_*_demo_id` は ASCII `[a-z0-9][a-z0-9._-]{0,63}`。package name、Activity、executable、URI、argument を demo ID として受け入れない。
- `hmd_ip` は dotted-decimal IPv4 の unicast address。`0.0.0.0`、`255.255.255.255`、loopback、multicast、予約済みの先頭 octet 240..255 は拒否する。実装は文字列比較でなく IP parser で検証する。
- profile の `ssid` は 1..32 UTF-8 bytes。password と shared secret は 1..256 UTF-8 bytes。schema の `maxLength` は補助であり、実装は UTF-8 byte 数も検証する。
- `allow_unsigned` の既定値は `false`。`true` にする update は同じ transaction で `isolated_lan:true` を明示しなければならない。`allow_unsigned:true` の間は controller の接続先を隔離 demo LAN に限定し、設定 UI と log に警告を表示する。`shared_secret` が設定済みの場合でも unsigned command は受理しない。
- `shared_secret_set:true` のとき、Demo Switch UDP command/status は既存 [`demo-switch-control.md`](demo-switch-control.md) の HMAC-SHA256 を使用する。secret が未設定かつ `allow_unsigned:false` のとき、UDP control は無効である。

## Controller ID and sequence persistence

controller は `controller_id` と Demo Switch UDP `next_sequence` を不揮発に保存する。UDP `SWITCH` を送る前に使用する sequence を予約・永続化し、再起動や電源断後に sequence が減少しないようにする。`controller_id` が set または clear で変更された場合、`next_sequence` は `1` に reset する。controller は `Number.MAX_SAFE_INTEGER` を超える sequence を送らない。

## Factory reset

`factory_reset` は Wi-Fi profiles、HMD IP、target A/B/C demo ID、shared secret、isolated-LAN/unsigned opt-in、request-result cache を消去する。controller ID は消去後に新しいランダムな valid identifier を生成して永続化し、`next_sequence` は `1` にする。これにより reset 前の UDP replay state と新しい controller identity が衝突しない。factory reset は response を flush してから実行し、途中で失敗した場合は reset 前の設定を保持する。

JSON Schema は [`demo-switch-controller-provisioning.schema.json`](../schemas/demo-switch-controller-provisioning.schema.json)、valid/invalid fixture と検証は [`demo-switch-controller-provisioning.test.mjs`](../tests/demo-switch-controller-provisioning.test.mjs) を正とする。
