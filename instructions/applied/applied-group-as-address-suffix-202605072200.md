# Applied Note: アドレス末尾に group_<N> セグメントを追加

**適用日:** 2026-05-07
**起点セッション:** workspace `objective-ishizaka-2ddfb6` worktree (unity-sdk リリース直前 QA)
**関連:** unity-sdk 側で EventMap window に Group field を追加 (BuildTargetFromParts / ParseTarget が group_<N> を末尾セグメントとして扱う)

## 変更ファイル

| ファイル | 変更概要 |
|---|---|
| `specs/device-addressing.md` | §2 アドレス構造に `[/group_{M}]` を末尾追加可能と明記 / §2.1 example に "グループ分離" 行追加 / §2.2 制約: "末尾2セグメント必ず player/position" → "player/position の順序不変、その後ろに group_<N> 1段だけ追加可" / §2.3 表に group_{M} 行追加 / §4.2 マッチング例に group ありパターンを 4 件追加 |

## 経緯

最初のリリース直前 QA で「EventMap UI に group field がほしい」という user 要望に対し、私が一旦 `[prefix/]group_<N>/player_<M>/...` で実装したが (commit 9b44ec1, revert 4ea6fa8)、user の指摘で **prefix 領域に group を入れると衝突する** ため不適切と判断。

「アドレスに含めるなら pos の後ろが望ましい」という user 指針に従い、spec を改定 + SDK を再実装した。

## 横断的な背景

- contracts: §2 アドレス構造に group_<N> を末尾セグメントとして追加 (任意・1段まで)
- unity-sdk: ParseTarget/BuildTargetFromParts が group_<N> を末尾に encode/decode (`HapbeatEventMapWindow.cs`)
- device-firmware: addressMatch は純粋な文字列セグメント比較なので変更不要。device 側 address に group_<N> を含めて運用すればそのまま動く
- Studio: 今後 device address 設定 UI に group_<N> 入力枠を追加すべき (現状 device-firmware の `set_address` コマンド経由で文字列を直書きすれば動作)

## 検証状況

- `specs/device-addressing.md` の他箇所と矛盾しないことを目視確認済み
- §4.2 マッチング例に新規パターン (group 一致 / group 不一致 / group 指定なし=全 group / wildcard で group のみ指定) を追加し、addressMatch アルゴリズムが変更不要なことを確認

## 当該 repo エージェントへのアクション

- 内容を確認し、問題なければ本 note を `instructions/completed/` に移動
- DEC-030 候補: device-addressing に group_<N> suffix 追加 (workspace docs/decision-log.md)
- Studio 側 device address 設定 UI への group 入力枠追加は別タスク
