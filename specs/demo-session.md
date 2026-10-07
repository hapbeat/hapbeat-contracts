# Demo Session

Quest 上の独立 demo runtime（Unity / Unreal の別 APK）を、体験者が自分で順番に進めるための契約。Hub runtime が「プラン」を組み、**セッション票**（session ticket）を launch context として 1 本目に渡す。各 demo は完了時に終了パネルを出し、体験者の操作で次の demo を直接起動する。自動では遷移しない。

[Demo Switch control protocol](demo-switch-control.md)（UDP 7710）とは独立して動作する。Demo Switch は operator 用の外部操作として併存し、セッション票の有無に関係なく従来どおり使える。

## 用語

- **descriptor**: demo APK が自分自身を説明する JSON。Hub はこれを読んでカタログとオプション UI を作る。
- **plan**: Hub 上で編集する step の並び。Hub 内に保存される（形式は Hub 実装の内部仕様）。
- **step**: plan の 1 要素。1 つの demo を 1 回体験する単位（例: 「Volley ブロック 3 点先取」）。同じ demo を複数 step に置いてよい。
- **session ticket**: 実行中 plan の不変部分と現在位置を持つ JSON。runtime 間を Intent extra で受け渡す。

## Descriptor

- demo APK は Android assets の root に `hapbeat-demo-session.json` を同梱する（Unity は `Assets/StreamingAssets/`、Unreal は UPL で `assets/` へ copy）。UTF-8、最大 16384 bytes。
- Schema: [`demo-session-descriptor.schema.json`](../schemas/demo-session-descriptor.schema.json)。例: [`sample-demo-session.json`](../fixtures/sample-demo-session.json) の `descriptor_*`。
- `demo_id` は Demo Switch と同じ identifier 規則（`[a-z0-9][a-z0-9._-]{0,63}`）。
- `options` は列挙型だけを持つ。各 option は `id`、`label`、`values`（`value` と `label`）、`default` を持つ。`value` は文字列。`when` を持つ option は、指定した別 option の値がいずれかに一致するときだけ有効で、それ以外では ticket に含めない。
- `supports.haptics_toggle` が true の demo は、実行中の触覚 ON/OFF（下記）を実装する。
- `minutes` は 1 step の目安時間（分、表示用）。

Hub は package / activity を **descriptor から取らない**。PackageManager で launcher activity を列挙し、各 package の assets から descriptor を読めたものだけをカタログに載せ、起動先 component は PackageManager の解決結果を使う。

## Session ticket

- Android Intent の String extra `com.hapbeat.demo_session.ticket` に JSON 文字列 1 本として載せる。UTF-8、最大 16384 bytes。
- Schema: [`demo-session-ticket.schema.json`](../schemas/demo-session-ticket.schema.json)。

```json
{"version":1,"session_id":"0f3a9c2e7b1d4a56","index":1,"haptics_ui":false,
 "steps":[
  {"demo_id":"volley","title":"バレー ブロック 3点","package":"jp.hapbeat.volley","activity":"com.unity3d.player.UnityPlayerGameActivity","options":{"scene":"block","points":"3"},"retry":true},
  {"demo_id":"trex-encounter","title":"T-Rex","package":"com.hapbeat.trexencounter","activity":"com.epicgames.unreal.GameActivity","options":{},"retry":false}],
 "finish":{"package":"jp.hapbeat.demohub","activity":"com.unity3d.player.UnityPlayerGameActivity"}}
```

- `index` は起動される側の step 位置（0 始まり）。`index == len(steps)` は「全 step 完了」を表し、`finish` の runtime（Hub）だけが受け取る。
- `title` は終了パネルの「次へ：<title>」表示に使う。
- `options` は該当 descriptor の有効 option をすべて含む。受け手は未知 option・未知 value を既定値に置き換えて続行し、警告ログを出す（体験を止めない）。
- `retry` が true の step だけ、終了パネルに「もう一度」を出す。
- `haptics_ui` は触覚 ON/OFF ボタンの表示状態。session 全体で引き継ぐ。
- `recenter_ui`（任意、既定 false）は「視線をリセット」ボタンの表示状態。`haptics_ui` と同じく session 全体で引き継ぐ。
- `hand_style`（任意）は共通の手の見た目（`ghost` / `skin`）。Hub の管理画面で選び、共通の手を使う runtime だけが従う。自前の手を持つ runtime は無視してよい。省略時は各 runtime の既定。

### 受け取り

1. runtime は起動時（cold start）に extra を読み、schema 検証し、自分の `demo_id` と `steps[index].demo_id` が一致する場合だけ session mode に入る。不一致・不正なら警告ログを出し、extra が無い場合と同じ通常動作にする。
2. 読み取った extra は Intent から削除する。session mode は process 内でだけ保持し、永続化しない。
3. session mode では `steps[index].options` を適用し、demo の自動再開（試合の自動リスタート等）を止め、完了時に終了パネルを出す。

### 次の runtime の起動

- 起動側は ticket の `index` を 1 進め、`haptics_ui` を現在値に更新した ticket を付けて、`steps[index+1]`（最後なら `finish`）の component を **明示 Intent**（`setClassName`）、flags `FLAG_ACTIVITY_NEW_TASK | FLAG_ACTIVITY_CLEAR_TASK` で起動する。
- 起動要求が成功したら、自分の触覚・音・7710 listener を止めて自分の task を終了する（`finishAndRemoveTask` 相当）。次の runtime は毎回 cold start で ticket を読む前提とする。
- 起動に失敗したら終了パネルにエラーを表示し、自分は終了しない。
- 起動先 component は ticket（= Hub が端末内で解決した値）だけから取る。network command から package / activity を受け取らない原則（Demo Switch）は維持する。

## 終了パネル

session mode の runtime は、demo 固有の完了イベントで、体験者の正面に終了パネルを出す。

- 表示: 見出し「体験完了」、`<index+1> / <len(steps)>`、ボタン。
- ボタン: `retry` が true なら「もう一度」。次 step があれば「次へ：<次 step の title>」、最後なら「デモを終了」。
- 表示後 1.0 秒間はボタンを受け付けない（誤操作防止）。パネル表示中はゲーム入力を止める。
- 入力: 人差し指先のポーク（ハンドトラッキング）と、コントローラの ray + trigger の両方。
- 「もう一度」は同じ step を demo 内で再開する（process 再起動ではない）。終了パネルを閉じる。

- 置く位置は runtime ごとに指定できる（Unity: scene の `DemoSessionPanelAnchor`、Unreal: `UHapbeatDemoSessionPanelAnchor`）。指定が無ければ HMD 正面。表示後は空間に固定し、頭に追従させない。

## 共通の一時停止

- 自前のメニューを持たない runtime は、共通の一時停止パネル（再開 / 最初からやり直す / Hub に戻る）を持つ。自前のメニューを持つ runtime はそちらを使い、共通の一時停止は無効にする。
- 開閉は左手の Quest 標準メニュー操作（ハンドトラッキングの system menu gesture）とコントローラの ≡ ボタン。設定で「左手のひらを顔に向けて親指と人差し指をつまみ 2 秒保持」に切り替えられる。
- 一時停止中はゲーム進行・音（ナビ音声を含む）・触覚を止める。パネルは HMD 正面に出して固定する。「Hub に戻る」は Hub がインストールされているときだけ出す。

## 触覚 ON/OFF

- step 開始時の触覚は常に ON。
- `supports.haptics_toggle` の demo は、`haptics_ui` が true の間、視界の左下に触覚 ON/OFF ボタンを常時表示する。表示文言は「Haptics / ON」「Haptics / OFF」（位置は「視線をリセット」節）で、どちらでも幅は変えない。ボタンはポークとコントローラ ray で切り替える。
- OFF は Hapbeat への出力だけを止める。音・映像は変えない。OFF にした時点で再生中のループ・Stream も止める。
- `haptics_ui` の初期値は Hub の plan 設定（既定 false）。実行中は Demo Switch の `CONTROL` `haptics_ui_show` / `haptics_ui_hide` で変更でき、次の step へ引き継ぐ。触覚自体の ON/OFF は `haptics_on` / `haptics_off` で外部から指定でき、step を跨いで引き継がない。
- session mode でなくても、descriptor が `haptics_toggle` を宣言した demo は同じ CONTROL を受け付ける（`haptics_ui` の初期値 false）。

## 視線をリセット

- すべての runtime（Hub を含む）は、視界の左下に頭へ追従する「視線をリセット」ボタンを持つ（触覚ボタンと横並び、視線をリセットが左。目から 0.45 m・下 30°、左 19.5° / 左 5°、各 88×64 mm、英語 2 行ラベル Reset / View・Haptics / ON・OFF。頭の水平の向きへゆっくり追従し、上下の傾きは無視）。既定は非表示。表示は ticket の `recenter_ui`（Hub の管理画面で設定）と、Demo Switch の `CONTROL` `recenter_ui_show` / `recenter_ui_hide` で切り替え、次の step へ引き継ぐ。
- 押すと（または `CONTROL` `recenter`）、体験者の今の頭の位置と向きを、その runtime の開始位置・正面として合わせ直す（アプリ空間のリセンター。OS の再センタリングは使わない）。表示中の共通パネル（Hub・終了・一時停止）も正面へ置き直す。床の高さは変えない。
- Quest の Meta ボタン長押し（OS のリセンター）を検知したときも、表示中の共通パネルを正面へ置き直す。

## 共通パネルの描画

- 共通パネル（Hub・終了パネル・一時停止パネル・触覚ボタン・視線をリセット）は、シーンのモデルに隠れないよう常に最前面に描く。手（共通の手）がパネルより手前にあるときは手を前に描く。
- パネルの見た目（配色・フォント・ボタンの縦並び・大きさ）は Unity と Unreal で揃える。
- 一時停止中も手のトラッキングと手の表示は止めない（パネルを操作できるように）。

## 端末ごとの Hapbeat 宛先（device address file）

複数の HMD を同時に使う展示で、HMD ごとに触覚の宛先（player / group）を分けるための端末単位の設定。アプリを開いて個別に変える手間をなくすため、インストール時に operator の PC から書き込む。

- 置き場所: 各 demo runtime（Hub を含む）の app-specific external files directory 直下の `hapbeat-device.json`（Android の `Context.getExternalFilesDir(null)`。Quest では `/sdcard/Android/data/<package>/files/`）。runtime は追加の権限なしで読める。adb から `adb push` で書ける。
- 形式: `{"version":1,"player":<int>,"group":<int>}`。値は 1〜99、または -1（その軸は指定しない）。schema: [`demo-device-address.schema.json`](../schemas/demo-device-address.schema.json)。最大 1024 bytes。
- 適用: runtime は起動時、Hapbeat SDK の初期化後に 1 回読み、-1 でない軸を SDK の address override（`SetAddressOverride(player, group, persist: false)`）に設定する。ビルドで固定された軸（Unity `HapbeatConfig.buildOverride*`、Unreal `ForcedOverride*`）はそちらが優先し、ファイルでは変わらない。ファイルの値は、端末に保存された override（PlayerPrefs 等）より優先する。実行中に runtime の UI や API で変えるのは自由。
- ファイルが無い・壊れている場合は何もしない（不正なら警告ログ）。適用結果をログ `HAPBEAT_DEVICE_ADDRESS player=<n> group=<n>` で出す。
- Hub は自身のファイルを読み、待機画面に「この端末: player / group」を表示する（触覚は送らない）。
- session ticket はこの値を運ばない。各 runtime が自分のファイルを読む。

## Hub を外部から起動してセッションを始める

- Hub は起動 Intent の String extra `com.hapbeat.demo_hub.start` を受け付ける。値は JSON 1 個（最大 4096 bytes）:
  - `{"version":1,"preset":1}` … Hub のプリセット 1〜3 の plan で session を開始。
  - `{"version":1,"demo_id":"handdemo","options":{"tutorial":"on"}}` … そのデモ 1 本の session（options は省略可、未指定・未知値は descriptor の既定値、retry=true、finish=Hub、`haptics_ui` / `recenter_ui` / `hand_style` は Hub の管理画面の設定）。
  - `{"version":1,"steps":[{"demo_id":"handdemo","options":{"tutorial":"on"}},{"demo_id":"trex-encounter","retry":false}]}` … 外部（リモコン）で組んだ plan の session。`steps` は 1〜32 件、各 step は `demo_id`（必須）、`options`（任意、規則は 1 本指定と同じ）、`retry`（任意、既定 true）だけを持つ。`haptics_ui` / `recenter_ui` / `hand_style` と `finish` は 1 本指定と同じく Hub が決める。未インストール・不正な step が 1 つでもあれば全体を開始しない。Hub のプリセット 1〜3 は変えない（外部の plan は保存しない）。
  - `preset` / `demo_id` / `steps` はどれか 1 つだけ。未知フィールドは不正。
- 受け付けたら Hub は自分のトップ画面を出さずに ticket を作って 1 本目を起動する（起動遷移の規則は同じ）。不正・未インストールなら Hub のトップを開いてステータス行に理由を出す。
- 外部リモコンは Wi-Fi adb の `am start -n jp.hapbeat.demohub/com.unity3d.player.UnityPlayerGameActivity --es com.hapbeat.demo_hub.start '<json>'` でこれを使う。Demo Switch の `SWITCH`（UDP）は従来どおり ticket なしの直接起動で、session にはならない。

## Hub

- Hub は自身の `demo_id` を `demo_hub` とし、descriptor を持たない。
- ticket なしで起動された場合は待機 / plan 編集画面。`index == len(steps)` の ticket で起動された場合は終了画面（ヘッドセットを外す案内と、同じ plan での再開操作）を出す。
- plan の保存形式、プリセット数、編集 UI は Hub 実装に委ねる。
