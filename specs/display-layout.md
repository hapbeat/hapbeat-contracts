# ディスプレイレイアウト仕様

## 概要

Hapbeat デバイスに搭載される OLED ディスプレイ（128x64 ピクセル）の表示レイアウトを定義する設定フォーマットである。ユーザーは Hapbeat Studio（Web アプリ）上でブロック配置方式により視覚的にレイアウトを編集し、JSON 形式でエクスポートする。

## グリッドシステム

ディスプレイ領域をグリッドに分割し、各要素をグリッド単位で配置する。

### デフォルトグリッド

- **デフォルト**: 16 列 x 2 行（128x64 OLED の場合、1セル = 8x32 ピクセル相当）
- グリッドサイズは設定可能であるが、デバイスのディスプレイ解像度との整合性を考慮すること
- `grid` フィールドで `[cols, rows]` の形式で指定する

### 座標系

- 左上が原点 `[0, 0]`
- `x` は列方向（右方向に増加）、`y` は行方向（下方向に増加）
- 各要素は `position: [x, y]` で配置位置を指定する

## 要素タイプ

レイアウトに配置可能な要素タイプと、そのデフォルトサイズを以下に定義する。サイズは `[width, height]`（グリッド単位）で表す。

| タイプ | デフォルトサイズ | 説明 |
|--------|------------------|------|
| `channel` | 4x1 | 再生中のチャンネル番号を表示 |
| `volume` | 3x2 | 音量レベルをバーまたは数値で表示 |
| `battery` | 4x1 | バッテリー残量をアイコンまたはパーセントで表示 |
| `wifi_status` | 6x1 | Wi-Fi 接続状態（SSID、信号強度）を表示 |
| `connection_status` | 4x1 | デバイスの接続状態（接続中 / 切断）を表示 |
| `mqtt_status` | 4x1 | MQTT ブローカー接続状態を `[OK]` / `[NG]` で表示（ブローカーに正常接続している時だけ `[OK]`、Wi-Fi 未接続を含む他は `[NG]`） |
| `ip_address` | 10x1 | デバイスの IP アドレスを表示 |
| `firmware_version` | 8x1 | ファームウェアバージョンを表示 |
| `device_name` | 8x1 | デバイス名を表示 |
| `app_name` | 8x1 | 接続中のクライアントアプリ名（`CONNECT_STATUS` payload の `app_name` を表示） |
| `custom_text` | 可変 | 任意のテキストを表示（サイズはテキスト長に依存） |
| `gain` | 3x1 | ゲイン値を数値で表示 |
| `group_id` | 3x1 | グループ ID を表示 |
| `pwm_bias_state` | 8x1（compact: 4x1） | Band Wireless PWM 実験用。保存済みの固定バイアス有効状態を表示。 |
| `pwm_bias_value` | 8x1（compact: 4x1） | Band Wireless PWM 実験用。ISRにより実際に適用中のバイアス率を表示。 |
| `average_power` | 8x1（compact: 4x1） | 直近最大1分の平均推定放電電力を表示。MAX17048ではCRATE換算の推定値なので `P~` 接頭辞を用いる。 |
| `estimated_runtime` | 8x1（compact: 4x1） | SOC と直近最大1分の平均推定放電電流から算出する推定残り稼働時間を分単位で表示。標準表示は `T~245m`、compact 表示は `245m`。充電中・取得不能時は `--`。 |

### サイズの変更

各要素のサイズはデフォルト値から変更可能である。`size` フィールドで `[width, height]` を明示的に指定した場合、デフォルト値を上書きする。

### custom_text

`custom_text` タイプの場合、`text` フィールドで表示する文字列を指定する。サイズはデフォルトを持たないため、必ず `size` を指定すること。

### app_name の挙動

`app_name` 要素は `CONNECT_STATUS` (0x20) ペイロードの `app_name` フィールド（null-terminated, 最大 64B）を表示する。

- **未受信時**: 空文字または `--` 表示（実装依存。device 側で fallback を選ぶ）
- **更新タイミング**: `CONNECT_STATUS` 受信ごとに更新（Unity SDK は ping_interval 秒ごとに送信）
- **タイムアウト**: 最終受信から `ping_interval × 3` 経過で空文字表示に戻すことを推奨（device 側で実装）
- **文字幅**: デフォルト 8x1。`size` で 1〜16x1 の範囲で拡張可能（device 側で末尾切り詰め）
- **実用上限**: **16 文字**（display grid の最大幅）。protocol は 64B 許容だが、本要素は表示専用なので SDK 側（Unity SDK `HapbeatConfig.MaxAppNameLength = 16`）で 16 文字に cap している

> 16 文字を超える長文を表示したくなった場合は、SDK 側 cap を緩めるか、別の要素型（`client_id` など）を新設して用途分離すること。本要素はあくまで「ディスプレイで人が読むアプリ名」用途。

## ページシステム

ディスプレイ表示は複数のページに分割できる。ユーザーはデバイス上のボタン操作によりページを切り替える。

### ページ構成

- `pages` 配列に各ページの定義を格納する
- 各ページは `id`（文字列）、`name`（表示名）、`elements`（配置要素の配列）を持つ
- ページ数に上限はないが、実用的には 2〜4 ページ程度を推奨する
- 起動時は `pages` 配列の先頭ページが表示される

### ページの例

```json
{
  "id": "main",
  "name": "メイン",
  "elements": [
    { "type": "channel", "position": [0, 0] },
    { "type": "volume", "position": [4, 0] },
    { "type": "battery", "position": [12, 0] },
    { "type": "wifi_status", "position": [0, 1] },
    { "type": "group_id", "position": [7, 1] }
  ]
}
```

## ボタンアクション

デバイス上の物理ボタンに対して、以下のアクションを割り当て可能である。

| アクション | 説明 |
|------------|------|
| `short_press` | 短押し（200ms 以下） |
| `long_press` | 長押し（1000ms 以上） |
| `double_press` | ダブルクリック（400ms 以内に2回押し） |

### ボタンアクション設定

`button_actions` オブジェクトでアクションと動作を紐づける。

```json
{
  "button_actions": {
    "short_press": "next_page",
    "long_press": "toggle_display",
    "double_press": "previous_page"
  }
}
```

### 利用可能な動作

| 動作 | 説明 |
|------|------|
| `next_page` | 次のページに切り替える（末尾の場合は先頭に戻る） |
| `previous_page` | 前のページに切り替える（先頭の場合は末尾に移動） |
| `toggle_display` | ディスプレイの表示/非表示を切り替える |
| `none` | 何もしない |

この節の `button_actions` は Kit の `display-layout.json` に書く、機器全体で 1 組の割り当てである。ボタンごとの割り当ては、次節の UI 設定に書く。

## UI 設定のボタンと画面の向き

Hapbeat Studio が機器へ書き込む UI 設定（ui-config。TCP の `write_ui_config`、USB シリアルの `ui_config_begin` / `ui_config_chunk` / `ui_config_commit`）の `display` に、画面の向きとボタンごとの割り当てを書く。

```json
{
  "display": {
    "orientation": "flipped",
    "button_actions": {
      "btn_l": { "short_press": "group_dec",   "hold": "volume_down", "hold_mode": "latch" },
      "btn_c": { "short_press": "toggle_page", "hold": "wifi_select", "hold_mode": "latch" },
      "btn_r": { "short_press": "group_inc",   "hold": "volume_up",   "hold_mode": "latch" }
    }
  }
}
```

### 画面の向き

`orientation` は `"normal"`（既定）または `"flipped"`（画面を 180° 回して表示する）。

### ボタンの ID は見た目の位置

`button_actions` のキー（ボタンの ID）は、**画面の文字が正しい向きに読める状態で、利用者から見たボタンの位置**を表す。物理的なスイッチの番号ではない。機器は `orientation` に応じて、それぞれの位置にある物理スイッチへ割り当てる。画面を 180° 回して使っても、割り当ては見た目の位置に付いていく（例: 「右 = プラス」は回しても右のボタンに付く）。

| 機種 | ID | 位置 |
|------|----|------|
| Band（`band_wl_v3`〜`band_wl_v5`） | `btn_l` / `btn_c` / `btn_r` | 左 / 中央 / 右 |
| Band（`band_wl_v2`） | `btn_l` / `btn_r` | 左 / 右（中央のスイッチは起動用で使えない） |
| Duo（`duo_wl_v3`、`duo_wl_v4`） | `btn_1` / `btn_2` / `btn_3` | 3 個並んだ列の 上 / 中 / 下 |
| | `btn_4` / `btn_5` | 2 個並んだ列の 上 / 下 |

Duo の 3 個並んだ列は、`normal` では左側、`flipped` では右側に来る。どちらの向きでも、上・中・下は利用者から見た上下である。

機器は `normal` の向きでの物理スイッチとの対応を機種ごとに持ち、`flipped` では次のように入れ替える。

| 機種 | `flipped` での入れ替え |
|------|------------------------|
| Band | `btn_l` ⇄ `btn_r`（`btn_c` はそのまま） |
| Duo | `btn_1` ⇄ `btn_3`、`btn_4` ⇄ `btn_5`（`btn_2` はそのまま） |

UI 設定を適用するときは、`orientation` を先に反映してから `button_actions` を割り当てる。`orientation` を省いた UI 設定は、機器の今の向きのまま割り当てる。

### Wi-Fi 選択画面の操作

`wifi_select` で入る保存済み Wi-Fi の選択画面の操作は、機器が位置で固定する（UI 設定では変えない）。端まで進めると反対の端へ戻る。

| 機種 | 次へ | 前へ | 決定 |
|------|------|------|------|
| Band（v3〜v5） | `btn_r` | `btn_l` | `btn_c` |
| Band（v2） | `btn_r` | （なし） | `btn_l` |
| Duo | `btn_3`（下） | `btn_1`（上） | `btn_2`（中） |

## テンプレート

よく使われるレイアウトパターンをテンプレートとして提供する。ユーザーはテンプレートを選択してからカスタマイズすることで、効率的にレイアウトを作成できる。

### テンプレート形式

テンプレートは通常のレイアウト設定と同じ JSON 形式であり、`template` メタデータフィールドを追加で持つ。

```json
{
  "template": {
    "id": "default-2page",
    "name": "標準2ページ",
    "description": "チャンネル・音量・バッテリーをメインに、詳細情報をサブページに配置"
  },
  "grid": [16, 2],
  "pages": [...]
}
```

### 組み込みテンプレート

| テンプレート ID | 説明 |
|----------------|------|
| `default-2page` | 標準2ページ構成（メイン + 詳細） |
| `minimal` | 最小構成（チャンネルとバッテリーのみ） |
| `debug` | デバッグ用（IP、ファームウェア、接続状態を全表示） |

## JSON スキーマ

設定ファイルの検証には `schemas/display-layout.schema.json`（JSON Schema draft-07）を使用する。Hapbeat Studio はエクスポート時にこのスキーマで検証を行い、不正なレイアウトの書き出しを防止する。

## 設定ファイルの配置

ディスプレイレイアウト設定は Kit 内に格納される。

- ファイル名: `display-layout.json`
- 配置先: Kit ルート直下
- デバイスは Kit 読み込み時にこのファイルを解釈し、ディスプレイ表示に反映する

## 設定例

```json
{
  "grid": [16, 2],
  "pages": [
    {
      "id": "main",
      "name": "メイン",
      "elements": [
        { "type": "channel", "position": [0, 0], "size": [4, 1] },
        { "type": "volume", "position": [5, 0], "size": [3, 2] },
        { "type": "battery", "position": [12, 0], "size": [4, 1] },
        { "type": "wifi_status", "position": [0, 1], "size": [6, 1] },
        { "type": "group_id", "position": [9, 1], "size": [3, 1] }
      ]
    },
    {
      "id": "info",
      "name": "情報",
      "elements": [
        { "type": "device_name", "position": [0, 0], "size": [8, 1] },
        { "type": "app_name", "position": [8, 0], "size": [8, 1] },
        { "type": "firmware_version", "position": [0, 1], "size": [8, 1] },
        { "type": "ip_address", "position": [8, 1], "size": [8, 1] }
      ]
    }
  ],
  "button_actions": {
    "short_press": "next_page",
    "long_press": "toggle_display",
    "double_press": "previous_page"
  }
}
```
