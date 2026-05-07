# Applied Note: app_name 要素に 16 文字実用上限を明記

**適用日:** 2026-05-07
**起点セッション:** workspace `objective-ishizaka-2ddfb6` worktree (unity-sdk リリース整理セッション)
**関連 DEC:** DEC-029 (display-layout に app_name 要素追加)
**関連:** `hapbeat-unity-sdk` 側で `HapbeatConfig.MaxAppNameLength = 16` を導入したのに合わせた仕様補足

## 変更ファイル

| ファイル | 変更概要 |
|---|---|
| `specs/display-layout.md` | `### app_name の挙動` セクションに「実用上限 = 16 文字」を明記 / 文字幅条件を `1〜16x1` に厳密化 / 旧 `8 文字推奨` の注記を削除し「16 文字超は別要素型で扱う」運用方針に書換 |

## 横断的な背景

`HapbeatConfig.appName` の最大文字数を SDK 側で 16 にハードキャップした (`OnValidate` で truncate + `BuildConnectStatusPayload` でも belt-and-suspenders truncate)。理由:

- display grid の最大幅 = 16 cols
- protocol (CONNECT_STATUS) は 64B 許容だが、本要素はディスプレイ表示専用
- ユーザーが Inspector で長文を入れても、device 表示が破綻するだけで意味がない
- 将来「client_id 等の長文識別子」が必要になったら別要素型を作る

contracts 側の spec 注記が古い「8 文字推奨」のままだったので、SDK と仕様が齟齬を起こさないよう updateしました。

## 検証状況

- `specs/display-layout.md` の他箇所と矛盾しないことを目視確認済み
- schema (`schemas/display-layout.schema.json`) 側は element type enum しか持たないので変更不要
- DEC-029 の本文との整合性も問題なし

## 当該 repo エージェントへのアクション

- 内容を確認し、問題なければ本 note を `instructions/completed/` に移動
- 16 文字 cap の運用方針 (将来 `client_id` 等を別要素にする) は workspace 側 `docs/decision-log.md` の DEC-029 にも反映するか検討
