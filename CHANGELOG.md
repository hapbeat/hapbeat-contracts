# Changelog

本 repo の版は [specs/versioning.md](specs/versioning.md) §3.7 に従う。major は全製品の major、minor は追加だけの仕様変更、patch は文言の修正である。1.0.0 までは tag を打たず、変更を「Unreleased」に積む。各項目には `versioning.md` §6 の分類（追加・破壊・修正）を付ける。

## Unreleased

### 追加

- `kit-install-protocol.md` §10 音声領域: 追記だけで 1 イベント 1 項目、新しいインストールが勝つ。削除は USB（`KIT_DELETE`）と Wi-Fi（`kit_delete`）で同じにし、ほかの Kit の音声は残し、Kit が 1 つも残らなければ音声領域を消去する。入れ直しは置き換える Kit の項目を書く前に除き、ほかに Kit が無ければ書く前に消去する。満杯は `ERR_NO_SPACE`（Wi-Fi は `"audio storage full"`）で断り、その Kit を残さない。起動時は同じイベントの最後の項目を使う。途中で止まったインストールが書いたバイトの上には書かない。

### 修正

- `kit-install-protocol.md`: `INSTALL_BEGIN`・`KIT_DELETE` の ACK を 30 秒待ち、応答の `seq` を照合する（音声領域の消去は書いた量 1 MB あたり約 2 秒）。`KIT_LIST_RESPONSE`（kit_count は uint16、total_size は無い）と `SPACE_RESPONSE`（`fs_total`・`fs_used`・`audio_total`・`audio_used`）をファームの実装に合わせた。§9 の上書きは退避しない（`.bak` は実装されていない）。

## 1.0.0 — 2026-11-06

### 追加

- `versioning.md` を全面改訂（DEC-096）: 全製品の major を揃える規則、「SDK・helper の major ≥ ファームの major なら動く」、同じ major の中は追加だけ、製品単独で major を上げない、方式の世代（Stream Gen 1 / Gen 2）の呼び方、変更の分類表、無視する規則と拒否する規則、凍結している形式、永続データの版、0.x → 1.x の移行表、1.0 の条件。
- `message-format.md`: §4.0 拡張の規則と command_type の割当、0x12 CAPS_REQ / 0x13 CAPS（能力申告）、0xFF ERROR のコード表と返す規則、`protocol_version` の意味、STOP_ALL が stream session を終えること、PING・PONG の凍結。
- `serial-config.md`: `get_info` の `caps`・`stream_protocol`・`storage_incompatible`、§4.23 `reset_storage`。
- `stream-session.md`: 1.x の要件（拡張 PING は unicast で TTL/3 以下、lease slot は 32 以上、再発行の規則と tail の flag bit 2 `lease_reissued`、stream を受けないノードの tail、受信側の判定順と ERROR、送信側の要件、診断の項目）と、1.x の SDK の PONG の分類規則（32 byte 以上の tail を読み、予約と未知の flag を無視する）。superseded の保留を解くのは `lease_reissued` の応答だけ。
- `sdk-multi-stream.md`: `deferredReason` の値の追加、BEGIN の再送、live source の無入力時の無音、STOP_ALL で止まった endpoint の扱い（§6.13）。
- `helper-streaming.md`: 既存の `stream_ack`・`stream_displaced` の定義、`stream_lost` と `stream_begin.takeover`（1.x）。
- `helper-ws.md`（新規）: `helper_hello` の `generation`・`types`・`features` と、Studio・ブラウザの client が能力で機能を判定する規則。
- `sdk-multi-stream.md` §6.14 差し替え（re-splice、Unity SDK の実装を契約にした）と §6.15 モーター 1 個の endpoint では pan を適用しない混合。`message-format.md`: モーター 1 個の受信機は stereo の stream を (L+R)/2 で鳴らす、`haptic_channels` はモーターの数、BEGIN の flush の閾値 32 ms を契約として扱う。
- `kit-format.md`: `caps.kit_schema` と `caps.kit_clip_formats` による照合。
- fixture `stream-session-cases.json`（PONG の分類と受信側の判定）、`wire-extension-cases.json`（CAPS・ERROR・PLAY の末尾・PING の長さ）と、その参照テスト `tests/test_wire_compat.py`。
- `display-layout.md`「UI 設定のボタンと画面の向き」（DEC-098）: UI 設定（ui-config）の `display.orientation` と `display.button_actions`。ボタンの ID は画面の文字が読める向きで見た位置（Band は左・中央・右、Duo は 3 個の列の上・中・下と 2 個の列の上・下）で、機器が向きに応じて物理スイッチへ割り当てる。Wi-Fi 選択画面の操作も位置で固定する。
- `scene-recording.md` §2 の `takes`、§5 記録のログ（JSON Lines の `start` / `take` / `take_end` / `cue` / `level` / `fail` / `end`、印 `HAPBEAT_SCENE `）、§6 プロジェクトの設定 `hapbeat-scene.json`、§7 記録と cue 表の突き合わせ。`cue-table.md` §10 イベントの一覧（`inventory.json`）と Event Map から cue 表の初版を作る規則（DEC-101）。schema `scene-log-record`・`scene-project`・`cue-inventory` と `scene-session` の `takes`、fixture `sample-scene-log.jsonl`・`sample-scene-project.json`・`sample-cue-inventory.json`。
- `scene-recording.md`: 動画のプロジェクト（ゲームの記録を使わず、映像に触覚を付ける。`viewer-data.json` が原本）、§3.2.1 `viewer-data.json` の任意の `chapters`（映像の区切り。選んで再生・範囲で繰り返す目印）、§3.3 映像の音声トラックは任意で、動画のプロジェクトでは再生する側が番組の音として流してよい。schema `scene-viewer-data` の `chapters`。
- `demo-session.md`「デモごとの設定」と descriptor の option の `scope`（`session` / `device`）、`demo-switch-control.md`「Demo settings」の `DEMO_SETTINGS_GET` / `DEMO_SETTINGS` / `DEMO_SETTINGS_SET`（DEC-099）。`DEMO_SETTINGS` の `hub_id`。schema と fixture（`descriptor_boxing`、`unsigned_demo_settings_*`）。
- `display-layout.md`「装着位置の切り替え」（DEC-100）: UI 設定の `ui.position_cycle`（装着位置の並び）とボタンの動作 `position_cycle`（押すたびに並びの次の位置へ）。`device-addressing.md` §7 の存在しない `position_inc/dec` を `position_cycle` に改めた。
- `pwm-experiment.md`: 対象のファームに `band_v3_pwm`（BandWL v3 で band_v4_pwm と同じ MCU-PWM の改造をした基板）を加えた。board は `band_wl_v3` のまま、`get_info` の `haptic_pwm` で見分ける。

### 破壊

- 強さの名前を付け直す（DEC-103）: Kit の manifest の `parameters.intensity` → `parameters.clip_gain`、cue 表の `clips.<clip>.intensity`・`sounds.<Sound>.intensity` → `clip_gain`（cue 表でもこの欄だけ snake_case）、イベントの一覧の `events[].intensity` → `clip_gain`、`SDK_gain` → `app_gain`。式の正本は `kit-format.md`「強さの式（正本）」: `output = clip × app_gain × device_volume`、`clip = WAV × clip_gain`、送る値は `clamp(clip_gain × app_gain, 0, 1)`。API の `gain` 引数・Event Map の項目・route・variant・距離・Scene の発生の `gain` は名前を変えず `app_gain` の部品とする。STREAM_BEGIN の `gain` は 1.0 を送り、強さは source の PCM に掛ける（`message-format.md` と `sdk-multi-stream.md` §5.5 の食い違いを解消）。`cue-table.md` §9.1 素材の強さの元（Kit を持つプロジェクトは Kit の manifest、cue 表は写し。Kit の無いプロジェクトは cue 表）。古い名前は読まない（Kit の manifest・cue 表の clips と sounds・イベントの一覧の schema も、古い名前を拒否する）。`helper-streaming.md` に「Stream gain」を足す: `stream_begin` の `gain` は省くか 1.0 を送り、強さは PCM に掛ける。Helper は 0〜1 の外の `gain` を `stream_ack` の `error` で拒む。
- なし。0.x のうち Stream Gen 2 に対応した SDK（`versioning.md` §9）は、1.x のファームとつながる（PING・PONG と Stream Gen 2 のパケットの形は変えていない）。0.x の SDK は、1.x のファームが送る ERROR を無視するかログに出すだけで、`lease_reissued` の付いた応答は不正な tail として無視する（0.5.0 と同じく保留のまま）。実機で確認する。
- Kit の `firmware_version_min` は major だけを比べ、`firmware_version_max` は照合しない（`versioning.md` §11）。0.x のファームは semver 全体で比べるため、1.x の書き手が `1.0.0` と書いた Kit を 0.x の機体は拒否する（意図どおり）。
- UI 設定のボタンの ID の意味（DEC-098）: これまで機器は ID を回転させない向きの物理位置として割り当てていた。`orientation: "flipped"` の UI 設定では、左右（Duo は列の上下と左右）の働きが入れ替わる。Studio の表示も見た目の位置に揃える。

### 修正

- `stream-session-v2.md` を `stream-session.md` に改名し、「v1 / v2」を Stream Gen 1（セッションなし方式）/ Stream Gen 2（セッション方式）に改めた。fixture `stream-session-v2.json` は各 SDK のテストが参照しているため名前を変えていない。
- `message-format.md`: パケットの上限（送信側 1472 bytes 以下、受信側 1500 bytes まで）、BEGIN は 28 bytes 以上で target は NUL を含め 64 bytes 以内、STREAM 系の seq の扱い。
- `stream-session.md`: lease の追い出しは最後の PING が最も古いもの、greater END の意図、DATA は 1 byte 以上の音声を持つ、前提（同時に 1 session、PING と stream は同じ socket）。
