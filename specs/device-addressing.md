# デバイスアドレッシング仕様書

## 1. 概要

Hapbeat デバイスは **パスベースのアドレス文字列** を持ち、SDK からの送信コマンドは **ターゲット文字列** でフィルタリングされる。

これにより、1人1台のシンプルな構成から、チーム制・小隊・複数部位装着の大規模構成まで、同一のプロトコルで対応できる。

## 2. アドレス構造

```
デバイスアドレス（正準形）: [自由プレフィックス/] player_{N} / {position} / group_{M}
ターゲット（送信側）      : [自由プレフィックス/] player_{N} / {position} [/group_{M}]
```

**デバイス側アドレスは常に group セグメントまで含むフル正準形を保持する**（DEC-048）。
送信側ターゲットは前方一致でマッチするため group（や position 以降）を省略してよく、
省略した場合は全 group に届く。「group 未設定のデバイス」という状態は存在しない
（未設定相当は既定値 `group_1`）。

| 部分 | デバイス側 | ターゲット側 | 形式 | 例 | 設定方法 |
|------|-----------|-------------|------|---|---------|
| プレフィックス | 任意（0段以上） | 任意 | 自由文字列 | `red/alpha` | Desktop アプリ |
| **Player** | **必須** | 任意（前方一致） | `player_{数字}` | `player_1` | Desktop / デバイスボタン |
| **Position** | **必須** | 任意（前方一致） | 定義済み語彙 | `chest` | Desktop / デバイスボタン |
| **Group** | **必須（常時保持・既定 1）** | 任意（省略 = 全 group） | `group_{数字}` | `group_5` | Desktop / デバイスボタン |

### 2.1 アドレス例

デバイスアドレスは常に group まで含む。ターゲットは必要な深さまでで打ち切ってよい。

| 構成 | デバイスアドレス | ターゲット例 |
|------|----------------|-------------|
| シンプル（1人1台） | `player_1/chest/group_1` | `player_1/chest` |
| マルチプレイヤー | `player_1/chest/group_1`, `player_2/left_upper_arm/group_1` | `player_2` |
| チーム制 | `red/player_1/chest/group_1` | `red` |
| チーム＋小隊 | `red/alpha/player_3/chest/group_1` | `red/alpha` |
| アプリ混在 | `app_a/player_1/chest/group_1` | `app_a` |
| グループ分離 | `player_1/chest/group_1`, `player_1/chest/group_2` | `*/*/group_2` |

### 2.2 制約

- 区切り文字: `/`（スラッシュ）
- セグメントに使用可能な文字: `[a-zA-Z0-9_-]`
- 最大長: 64 bytes（null 終端含む）
- `player_{N}` と `{position}` の順序は不変。**`player_{N}/{position}`** が必ず連続して現れる
- `group_{M}` は **`{position}` の直後** に置く（自由プレフィックスの使い方と衝突しない位置）。前後に他のセグメントを置くことはできない
- **デバイスは受け取ったアドレスを正準形に正規化して保持・永続化する**: `set_address` やボタン操作の結果、group セグメントが無いアドレスを受けた場合、デバイスは現在の group（初期値は既定 `group_1`）を付与して正準化する。プレフィックスは正規化で失われない

### 2.3 Player / Group 番号の範囲

**Player 番号 `{N}` および Group 番号 `{M}` は `1..99` の整数** とする。

| 項目 | 範囲 | 備考 |
|------|------|-----|
| `player_{N}` | `1..99` | デバイスボタン (`player_inc` / `player_dec`) は 99 → 1 / 1 → 99 で wrap-around |
| `group_{M}` | `1..99` | デバイスアドレス末尾の必須セグメント（DEC-048、既定 `group_1`）。ターゲットでは省略可。デバイスボタン (`group_inc` / `group_dec`) は saturate（wrap しない）。`group_id` 表示要素は OLED 上 `Gr:01` 〜 `Gr:99` (2 桁ゼロ埋め) で表示し、値はアドレスの `group_{M}` 由来 |

技術的には `uint8_t` (0..255) で保持しているため 100 以上も格納可能だが、現実的なユースケース (= ローカルマルチプレイ最大数十人規模) で 99 あれば充分という判断で **当面 1..99 に制限** する。

**将来的に 100 以上が必要になった場合の拡張容易性:**
- 内部表現は `uint8_t` のまま 1..255 へ拡張可能 (= NVS / 通信プロトコル変更不要)
- 修正必要箇所は以下のみ:
  - firmware: `DEVICE_GROUP_MAX` (`hapbeat_config.h`) と `actionPlayerInc / actionPlayerDec` の wrap 上限値
  - Studio: OLED 表示 element サイズ (`group_id` `[5,1]` → `[6,1]` で 3 桁化、`player_number` 同様) およびシミュレータの zero-pad 桁数
  - 256 以上が必要な場合のみ contracts / 通信フォーマットの型 (uint8 → uint16) 拡張も伴う

**バリデーション:** 範囲外の値を受信した場合の挙動は実装依存だが、推奨は **境界値にクランプして ok 応答** か **error 応答**。silent-drop はしない。



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
3. **`*` ワイルドカード**: 1セグメントの任意の値にマッチ。**セグメント全体が `*` の場合のみ**有効で、`pos_*` のような部分ワイルドカードは通常の文字列として比較される（実装 `address_match.cpp` は `t_len == 1 && *tp == '*'` で判定）
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
| `"player_1/pos_*"` | `player_1/pos_neck` | ✗ | **部分ワイルドカードは非対応**（`pos_*` は文字列そのものとして比較される）。全 position を対象にするならセグメント全体を `*` にする → `"player_1/*"` |
| `"red"` | `red/player_1/pos_neck` | ✓ | 前方一致 |
| `"red/*/player_1"` | `red/alpha/player_1/pos_neck` | ✓ | ワイルドカード + 前方一致 |
| `"player_1/pos_neck/group_1"` | `player_1/pos_neck/group_1` | ✓ | group まで完全一致 |
| `"player_1/pos_neck/group_1"` | `player_1/pos_neck/group_2` | ✗ | group 不一致 |
| `"player_1/pos_neck"` | `player_1/pos_neck/group_1` | ✓ | 前方一致（group 指定なし = 全 group） |
| `"*/*/group_1"` | `player_2/pos_chest/group_1` | ✓ | player/position をワイルドカード、group のみ指定 |
| `"player_1/pos_neck/group_1"` | `player_1/pos_neck` | ✗ | デバイス側セグメント不足（非正準アドレス）。正準形デバイスでは発生しない — デバイスは boot / `set_address` 時に group を付与して自己修復する（§2.2） |

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
  "group": 1,
  "address": "player_1/pos_chest/group_1",
  "fw": "0.2.0",
  "mac": "AA:BB:CC:DD:EE:FF",
  "wifi_connected": true,
  "wifi_ip": "192.168.1.50"
}
```

※ 正準レスポンス形（全フィールド）は `serial-config.md` §4.1 が正。`group` はアドレスの `group_{M}` セグメント由来の**導出フィールド（表示用）**。**source of truth は address であり、`group` フィールドはルーティングに関与しない**（DEC-048）。mDNS TXT の `group` レコードも同じ導出値。

### 6.3 NVS キー変更

| namespace | key | 型 | 説明 |
|-----------|-----|-----|------|
| hapbeat | address | string (max 64) | デバイスアドレス |

※ `group_id` (uint8) を `address` (string) に置き換え。

## 7. デバイスボタンでの設定

デバイスのボタンでは **player 番号 / position / group** を変更可能（`player_inc/dec`・`position_inc/dec`・`group_inc/dec` アクション）。プレフィックスは Desktop 専用。

ボタンで変更した場合、アドレスは正準形 `{既存プレフィックス}/player_{N}/{position}/group_{M}` に更新され、そのままアドレス文字列として NVS に永続化される（group 専用の NVS キーは存在しない）。プレフィックスが未設定の場合は `player_{N}/{position}/group_{M}` となる。

## 8. デフォルト値

- 出荷時アドレス: DuoWL = `player_1/pos_neck/group_1`, BandWL = `player_1/pos_r_wrist/group_1`（正準形・group まで含む）
- ターゲット未指定時: `""` (全台マッチ)
