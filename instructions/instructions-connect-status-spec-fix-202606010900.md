# instructions: message-format §0x20 CONNECT_STATUS の記述を実装に合わせて修正

- **起票元**: hapbeat-sdk-workspace（統括）セッション / 2026-06-01
- **関連**: DEC-032（ツール向け SDK 拡張）。新 SDK 群（python/web/godot/unreal）の CONNECT_STATUS 実装中に発見。

## 問題

`specs/message-format.md` の **§0x20 CONNECT_STATUS** のフィールド記述が、実機で動作している実装と乖離している。

現在の spec doc（§0x20）:

| フィールド | 型 | 説明 |
|---|---|---|
| app_name | null-terminated string | 接続元アプリ名 |
| device_name | null-terminated string | 対象デバイス名 |
| group | uint8 | グループ ID |

しかし**実機で動作している参照実装**（`hapbeat-unity-sdk/Runtime/HapbeatProtocol.cs` の `BuildConnectStatusPayload`、リリース済みで firmware が受理）の payload レイアウトは：

```
connected(uint8) + group(uint8) + app_name(null-term) + device_name(null-term)
```

差分:
1. spec doc に **`connected`(uint8) フィールドが無い**（実装には先頭にある）。
2. フィールド**順序が違う**（実装は connected, group, app_name, device_name の順）。

## 期待する対応

1. **firmware 側の実際のパース順を確認**（`hapbeat-device-firmware` の CONNECT_STATUS 受信処理）。`HapbeatProtocol.cs` がリリース済みで動作しているため、実装が正・spec doc が古いと推定。
2. `specs/message-format.md` §0x20 を**実装に合わせて修正**:
   - `connected`(uint8, 先頭) を追記
   - 順序を `connected, group, app_name, device_name` に統一
   - app_name の 16 文字上限（display-layout 由来）にも言及
3. 後方互換は不要（リリース前）。spec を実装に寄せるだけ。

## 影響

- これは **ドキュメント修正**（spec doc を実装に合わせる）。wire は既に全実装で一致しているため、firmware / Unity / Python / Web / Godot / Unreal SDK のコード変更は不要。
- 新 SDK 群（python-sdk `protocol.py` / web-sdk `protocol.ts` / godot `protocol.gd` / unreal `HapbeatProtocol.cpp`）は既に `HapbeatProtocol.cs` レイアウト（connected, group, appName, deviceName）に合わせて実装済み。

## 補足（任意・別件として検討可）

DEC-032 で OSC を「transport (`/hapbeat/*`、§6 既定) と app 固有 bridge (VRChat 等)」の 2 階建てに整理した。§6 付近に「`/hapbeat/*` は汎用 transport であり、VRChat 等のアプリ固有 OSC スキーマは各 bridge が変換する」旨の 1 段落を追記すると、OSC 周りの設計意図が明確になる（必須ではない）。
