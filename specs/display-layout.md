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
| `ip_address` | 10x1 | デバイスの IP アドレスを表示 |
| `firmware_version` | 8x1 | ファームウェアバージョンを表示 |
| `device_name` | 8x1 | デバイス名を表示 |
| `custom_text` | 可変 | 任意のテキストを表示（サイズはテキスト長に依存） |
| `gain` | 3x1 | ゲイン値を数値で表示 |
| `group_id` | 3x1 | グループ ID を表示 |

### サイズの変更

各要素のサイズはデフォルト値から変更可能である。`size` フィールドで `[width, height]` を明示的に指定した場合、デフォルト値を上書きする。

### custom_text

`custom_text` タイプの場合、`text` フィールドで表示する文字列を指定する。サイズはデフォルトを持たないため、必ず `size` を指定すること。

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

ディスプレイレイアウト設定は Pack 内に格納される。

- ファイル名: `display-layout.json`
- 配置先: Pack ルート直下
- デバイスは Pack 読み込み時にこのファイルを解釈し、ディスプレイ表示に反映する

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
        { "type": "firmware_version", "position": [8, 0], "size": [8, 1] },
        { "type": "ip_address", "position": [0, 1], "size": [10, 1] },
        { "type": "connection_status", "position": [12, 1], "size": [4, 1] }
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
