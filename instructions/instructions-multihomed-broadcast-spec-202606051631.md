# 指示書: マルチホーム対応の broadcast 方式を仕様化（contracts 先行）

- **起点**: hapbeat-sdk-workspace セッション（2026-06-05）
- **マスター指示書**: `../../docs/instructions-multihomed-interface-selection-202606051631.md`（workspace ルート）
- **種別**: 仕様変更（transport）。workspace ルール「仕様変更はまず contracts」に従い本 repo が先行。

## 背景（要約）

L1 送信は現状すべて **limited broadcast `255.255.255.255`**。マルチホーム PC
（Wi-Fi=Hapbeat / 有線=別ネットワーク）では broadcast が優先 NIC（多くは有線）からしか
出ず、Hapbeat に届かない。探索も実再生も同経路なので両方影響する。詳細はマスター参照。

## このリポジトリでやること

1. `specs/bridge-api.md:450` 付近の記述を更新:
   - 現状: 「ブロードキャストアドレス（255.255.255.255:7700）に PING パケットを送信」
   - 変更後の趣旨:
     - 既定は limited broadcast `255.255.255.255:7700`。
     - マルチホーム環境では送信側が**送信元インターフェイスを選択**し、
       そのサブネット宛の **subnet-directed broadcast**（例 `192.168.10.255:7700`）を
       送ってよい。受信側 PONG は対称に同インターフェイスへ戻る。
     - 単一 NIC 環境では従来どおりの挙動（回帰なし）。
2. `docs/decision-log.md` に DEC を起票（日付・判断・理由・影響範囲）。
   - 判断: broadcast 方式に「送信元 NIC 選択 + subnet-directed broadcast」を許容。
   - 影響: helper / studio / unity-sdk / python-sdk / web-sdk / 他 SDK。
3. 設計の論点（方式・インターフェイス特定方法・互換）はマスター指示書の「設計の論点」を参照。

## 完了条件

- bridge-api.md と decision-log.md が更新され、各実装 repo が追従できる粒度になっている。
- 本書を `instructions/completed/` へ移動。
