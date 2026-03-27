# デバイスアドレッシング仕様書

## 1. 概要

Hapbeat デバイスは **パスベースのアドレス文字列** を持ち、SDK からの送信コマンドは **ターゲット文字列** でフィルタリングされる。

これにより、1人1台のシンプルな構成から、チーム制・小隊・複数部位装着の大規模構成まで、同一のプロトコルで対応できる。

## 2. アドレス構造

```
[自由プレフィックス/] player_{N} / {position}
```

| 部分 | 必須 | 形式 | 例 | 設定方法 |
|------|------|------|---|---------|
| プレフィックス | 任意（0段以上） | 自由文字列 | `red/alpha` | Desktop アプリ |
| **Player** | **必須** | `player_{数字}` | `player_1` | Desktop / デバイスボタン |
| **Position** | **必須** | 定義済み語彙 | `chest` | Desktop / デバイスボタン |

### 2.1 アドレス例

| 構成 | アドレス |
|------|---------|
| シンプル（1人1台） | `player_1/chest` |
| マルチプレイヤー | `player_1/chest`, `player_2/left_upper_arm` |
| チーム制 | `red/player_1/chest` |
| チーム＋小隊 | `red/alpha/player_3/chest` |
| アプリ混在 | `app_a/player_1/chest` |

### 2.2 制約

- 区切り文字: `/`（スラッシュ）
- セグメントに使用可能な文字: `[a-zA-Z0-9_-]`
- 最大長: 64 bytes（null 終端含む）
- 末尾2セグメントは必ず `player_{N}/{position}` の形式

## 3. Position 語彙

装着部位は以下の固定語彙から選択する。

| 値 | 意味 | 部位番号 | デフォルト機種 |
|---|-------|---------|-------------|
| `pos_neck` | 首 | 0 | DuoWL |
| `pos_chest` | 胸 | 1 | |
| `pos_abd` | 腹 | 2 | |
| `pos_l_arm` | 左上腕 | 3 | |
| `pos_r_arm` | 右上腕 | 4 | |
| `pos_l_wrist` | 左手首 | 5 | |
| `pos_r_wrist` | 右手首 | 6 | BandWL |
| `pos_hip` | 腰 | 7 | |
| `pos_l_thigh` | 左太もも | 8 | |
| `pos_r_thigh` | 右太もも | 9 | |
| `pos_l_ankle` | 左足首 | 10 | |
| `pos_r_ankle` | 右足首 | 11 | |

`pos_` プレフィックスにより部位セグメントであることが一目で判別できる。`pos_*` ワイルドカードで全部位指定が直感的に行える。

将来の部位追加はこの表に追記する形で行う。

## 4. ターゲット文字列（送信側）

SDK / Desktop が送信時に指定する。デバイスはこのターゲットと自身のアドレスを照合し、マッチしたコマンドのみ実行する。

### 4.1 マッチングルール

1. **空文字列 `""`**: 全デバイスにマッチ
2. **セグメント比較**: `/` で分割し、左から順に比較
3. **`*` ワイルドカード**: 1セグメントの任意の値にマッチ
4. **前方一致**: ターゲットのセグメント数がアドレスより少ない場合、一致した部分までで合格

### 4.2 マッチング例

| ターゲット | デバイスアドレス | 結果 | 理由 |
|-----------|----------------|------|------|
| `""` | 何でも | ✓ | 空 = 全台 |
| `"player_1"` | `player_1/pos_neck` | ✓ | 前方一致 |
| `"player_1"` | `player_2/pos_neck` | ✗ | player 不一致 |
| `"player_1/pos_neck"` | `player_1/pos_neck` | ✓ | 完全一致 |
| `"player_1/pos_neck"` | `player_1/pos_r_wrist` | ✗ | position 不一致 |
| `"*/pos_neck"` | `player_1/pos_neck` | ✓ | ワイルドカード |
| `"*/pos_neck"` | `player_2/pos_neck` | ✓ | ワイルドカード |
| `"player_1/pos_*"` | `player_1/pos_neck` | ✓ | 全部位ワイルドカード |
| `"red"` | `red/player_1/pos_neck` | ✓ | 前方一致 |
| `"red/*/player_1"` | `red/alpha/player_1/pos_neck` | ✓ | ワイルドカード + 前方一致 |

### 4.3 マッチングアルゴリズム（擬似コード）

```
function match(target, address):
    if target == "": return true

    t_segments = target.split("/")
    a_segments = address.split("/")

    for i in range(len(t_segments)):
        if i >= len(a_segments): return false  // ターゲットが長い = 不一致
        if t_segments[i] != "*" and t_segments[i] != a_segments[i]:
            return false

    return true  // 前方一致 or 完全一致
```

## 5. UDP パケットフォーマット変更

### 5.1 PLAY (0x01)

| フィールド | 型 | 説明 |
|-----------|-----|------|
| event_id | null-terminated string | 再生するイベント識別子 |
| target | null-terminated string | ターゲットアドレス（空 = 全台） |
| target_time | int64 | 再生開始時刻（マイクロ秒、0 = 即時） |
| gain | float32 | 再生ゲイン（0.0 〜 1.0） |

※ `target_group` (uint8) を `target` (string) に置き換え。

### 5.2 STOP (0x02)

| フィールド | 型 | 説明 |
|-----------|-----|------|
| event_id | null-terminated string | 停止するイベント識別子 |
| target | null-terminated string | ターゲットアドレス（空 = 全台） |

### 5.3 STOP_ALL (0x03)

| フィールド | 型 | 説明 |
|-----------|-----|------|
| target | null-terminated string | ターゲットアドレス（空 = 全台） |

### 5.4 PONG (0x11) デバイス拡張

| フィールド | 型 | 説明 |
|-----------|-----|------|
| timestamp | int64 | 元 PING のタイムスタンプ |
| server_time | int64 | デバイス送信時刻 |
| device_name | null-terminated string | デバイス名 |
| address | null-terminated string | デバイスアドレス |
| firmware_version | null-terminated string | ファームウェアバージョン |

※ `group` (uint8) を `address` (string) に置き換え。

## 6. Serial/TCP 設定コマンド変更

### 6.1 set_address（新規、set_group を置き換え）

**Request:**
```json
{"cmd": "set_address", "address": "red/player_1/chest"}
```

**Response:**
```json
{"status": "ok", "address": "red/player_1/chest"}
```

### 6.2 get_info レスポンス変更

```json
{
  "status": "ok",
  "name": "Hapbeat-A",
  "address": "player_1/chest",
  "firmware": "2.0.0",
  "mac": "AA:BB:CC:DD:EE:FF",
  "wifi_connected": true,
  "wifi_ip": "192.168.1.50"
}
```

※ `group` (uint8) → `address` (string) に置き換え。

### 6.3 NVS キー変更

| namespace | key | 型 | 説明 |
|-----------|-----|-----|------|
| hapbeat | address | string (max 64) | デバイスアドレス |

※ `group_id` (uint8) を `address` (string) に置き換え。

## 7. デバイスボタンでの設定

デバイスのボタンでは **player 番号** と **position** のみ変更可能。プレフィックスは Desktop 専用。

ボタンで変更した場合、アドレスは `{既存プレフィックス}/player_{N}/{position}` に更新される。プレフィックスが未設定の場合は `player_{N}/{position}` となる。

## 8. デフォルト値

- 出荷時アドレス: DuoWL = `player_1/pos_neck`, BandWL = `player_1/pos_r_wrist`
- ターゲット未指定時: `""` (全台マッチ)
