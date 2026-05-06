# display-layout に `app_name` 要素型を追加

**作成日:** 2026-05-07
**起点セッション:** workspace `objective-ishizaka-2ddfb6` worktree (unity-sdk リリース整理セッションから派生)
**優先度:** 高 (device firmware 側との同時実装で機能完成 / 関連 DEC-029)
**関連リポ:** `hapbeat-device-firmware/instructions/instructions-display-app-name-element-202605071200.md` (device 側実装)

---

## 背景

Unity SDK 側は既に `CONNECT_STATUS` (0x20) ペイロードに `app_name` (null-terminated, 最大 64B) を載せて定期送信している (`HapbeatConfig.appName` / `HapbeatManager` ping ループ)。

device firmware 側も `connect_status.cpp` で `appName[64]` をパース・保持済み。ただし**ディスプレイレイアウトに `app_name` 要素型が定義されていない**ため、ユーザーがレイアウトの一要素として配置できない。現在は `connection_status` 要素の表示文字列に "OK" + 先頭 8 文字を埋め込む形でしか露出していない (`display_manager.cpp:223`)。

ユーザー要件: **「Hapbeat デバイスのディスプレイに、今接続している Unity アプリ名を独立した要素として表示できるようにしたい」**。

CONNECT_STATUS の payload 仕様自体は既に `specs/message-format.md:101` で定義済みなので、本指示書のスコープは **`specs/display-layout.md` への要素型追加のみ**。

---

## 変更ファイル

### `specs/display-layout.md`

#### 1. 要素タイプ表 (行 27〜40 付近) に追加

既存表 (`channel` / `volume` / `battery` / ...) の `device_name` 行の直下に `app_name` を追加:

```diff
 | `device_name` | 8x1 | デバイス名を表示 |
+| `app_name` | 8x1 | 接続中のクライアントアプリ名 (`CONNECT_STATUS` payload の `app_name` を表示) |
 | `custom_text` | 可変 | 任意のテキストを表示（サイズはテキスト長に依存） |
```

#### 2. 仕様補足セクションを追加

要素タイプ表の直後 (`### サイズの変更` セクションの前) に、以下のセクションを新設:

```markdown
### app_name の挙動

`app_name` 要素は `CONNECT_STATUS` (0x20) ペイロードの `app_name` フィールド (null-terminated, 最大 64B) を表示する。

- **未受信時**: 空文字または `--` 表示 (実装依存。device 側で fallback を選ぶ)
- **更新タイミング**: `CONNECT_STATUS` 受信ごとに更新 (Unity SDK は ping_interval 秒ごとに送信)
- **タイムアウト**: 最終受信から `ping_interval × 3` 経過で空文字表示に戻すことを推奨 (device 側で実装)
- **文字幅**: デフォルト 8x1 だが、`size` で拡張すれば長いアプリ名も表示可能 (device 側で末尾切り詰め)

> Unity SDK の `HapbeatConfig.appName` は最大 8 文字を推奨しているが、protocol 上は 64B まで許容される。長いアプリ名を表示したい場合は要素サイズを 16x1 等に拡張すること。
```

#### 3. ページ例 (行 167〜174) の Info ページ例に追加 (任意)

既存の info ページサンプルに `app_name` を追加する例を入れておくと、device 実装者の参考になる:

```diff
 {
   "id": "info",
   "name": "情報",
   "elements": [
     { "type": "device_name", "position": [0, 0], "size": [8, 1] },
+    { "type": "app_name", "position": [8, 0], "size": [8, 1] },
     { "type": "firmware_version", "position": [0, 1], "size": [8, 1] },
     { "type": "ip_address", "position": [0, 2], "size": [10, 1] },
     { "type": "connection_status", "position": [12, 1], "size": [4, 1] }
   ]
 }
```

---

## 検証

- `specs/display-layout.md` を読み返して `app_name` の挙動 (未受信時 / タイムアウト / 文字幅) が device 実装者にとって曖昧でないか確認
- 他の spec (message-format.md / serial-config.md 等) との整合性: `app_name` の長さや文字エンコーディング (UTF-8 / ASCII) が `message-format.md:101` の CONNECT_STATUS 仕様と齟齬がないか確認

---

## decision-log への追記

`docs/decision-log.md` に以下の DEC エントリを追加してください (workspace root の docs/):

```markdown
### DEC-029: ディスプレイレイアウトに `app_name` 要素型を追加 (2026-05-07)

**判断:** `specs/display-layout.md` の要素タイプに `app_name` を追加。`CONNECT_STATUS` (0x20) ペイロードの `app_name` を表示するレイアウト要素として独立化する。

**理由:**
- ユーザー要件: Hapbeat 実機のディスプレイで「今どの Unity アプリと接続しているか」を明示したい
- SDK 側 (Unity) は既に CONNECT_STATUS で app_name を送信済み (`HapbeatManager` ping ループ)
- device 側も既に受信・保持済みだが、`connection_status` 要素にしか出ない (限定的)
- レイアウトの一要素として独立させることで、ユーザーがページ構成を自由に設計できる

**影響範囲:**
- `hapbeat-contracts/specs/display-layout.md`: `app_name` 要素型追加
- `hapbeat-device-firmware`: `DisplayElementType::APP_NAME` 追加 + parser / renderer 実装 (instructions/applied/ で別途追従)
- `hapbeat-unity-sdk`: 変更不要 (SDK 側は既に実装済み)
- `hapbeat-studio`: layout editor を持つ場合は要素タイプ選択肢に `app_name` を追加 (今後)
```
