# バージョニング・互換性ルール仕様書

## 1. 概要

本書は Hapbeat の全製品（デバイスファーム、送信機ファーム、各 SDK、hapbeat-helper、Hapbeat Studio、本 contracts）の版の付け方と、製品間の互換の判定方法を定める（DEC-096）。

要点は次の 3 つである。

1. **major は全製品で揃え、major が通信の互換の系列を表す。** 「SDK・helper の major がファームの major 以上なら全機能が動く」（§3.3）。
2. **同じ major の中は追加だけ。** 機能の有無は機体の能力申告で判定し、minor の大小比較で判定しない（§3.4、§5）。
3. **通信の方式は「世代（Gen）」の番号で呼ぶ。** 例: Stream Gen 1 / Stream Gen 2（§4）。

## 2. 版の形式

- [Semantic Versioning](https://semver.org/) の `MAJOR.MINOR.PATCH` を用いる。manifest・release feed・PONG・get_info に載せる版は先頭に `v` を付けない正準形とする。
- 開発版は、UPM・npm では `<次の版>-d<N>`、Python パッケージのメタデータ（`pyproject.toml`）では PEP 440 の `<次の版>.dev<N>`、ファームの `FIRMWARE_VERSION` と、実行時に表示するだけの版の文字列（helper の `__version__` など）では `<次の版>d<N>` とする。比較の前に接尾辞を除く（`release-feed.md` §4）。
- MAJOR・MINOR・PATCH の意味は §3 と §6 で定める。semver の「MAJOR = 互換の無い公開 API の変更」に対し、Hapbeat では通信の形（本 contracts の仕様）と各 SDK の公開 API の両方を公開 API とする。

## 3. major の規則

### 3.1 対象

| 製品 | 版の定義箇所 |
|---|---|
| デバイスファーム（全 env。band_v4_pwm・atoms3_broker・atom_lite_sensor を含む） | `firmware-versions.json`（env ごと、DEC-035） |
| 送信機ファーム | `firmware-versions.json`（env ごと） |
| Unity / Unreal / Python / JS / Arduino / Godot SDK | 各 repo のパッケージ定義 |
| hapbeat-helper | `pyproject.toml` |
| Hapbeat Studio（Web・デスクトップ） | `package.json` |
| hapbeat-contracts | tag `vX.Y.Z` と `CHANGELOG.md`（§3.7） |

TouchDesigner / VRChat 連携は Python SDK の版に従う。

### 3.2 major は contracts が決める

contracts の major が、全製品の major を決める。全製品はその major で話す通信の系列を表す。1.0（§10）で全製品が major 1 になる。それまでは全製品が 0.x であり、0.x の間の互換は §9 の移行表で判断する。

### 3.3 互換の規則

**SDK・helper の major がファームの major 以上なら、全機能が動く。**

- SDK・helper は、1 つ前の major のファームへ自動で合わせる（例: SDK 2.x は 1.x のファームに 1.x の方式で送る）。2 つ前以前は対象外とする。
- ファームは、古い major の SDK の送信を受け付けないことがある。
- SDK は、自分の major より大きい major の機体を見つけたら、SDK の更新を促す警告を 1 回出す（判定は能力申告の `generation`、§5.2）。

| ファーム | SDK・helper | 結果 |
|---|---|---|
| N.x | N.x | 全部動く。minor の組み合わせは問わない |
| (N−1).x | N.x | 動く。SDK が (N−1).x の方式で送る |
| N.x | (N−1).x | 一部が動かないことがある。SDK・helper を N.x にする |

### 3.4 同じ major の中は追加だけ

- 同じ major の中では、どの minor の組み合わせでも、以前の版でできたことは動き続けなければならない。
- 新しい機能は、機体の能力申告（§5.2）で有無を判定してから使う。SDK・helper・Studio は、minor・patch の大小比較で機能を判定してはならない。
- 機種ごと・SDK ごとの「この機能はファーム X.Y 以上」という表は作らない。

### 3.5 major の上げ方

- major は、通信の方式のどれかが互換の無い新しい世代に変わるときに、**全製品で一斉に**上げる。製品単独で major を上げてはならない。
- 新しい世代を旧い世代と並べて受け付け、能力申告でどちらを使うか選ぶ形にできる場合は、互換を壊さないので minor で足りる（§4.3）。
- SDK の公開 API（C#・C++・Python・TypeScript・GDScript の関数・型・引数）を壊す整理は、非推奨（deprecated）にして残し、次の major で削除する。minor・patch で公開 API を削除・変更してはならない。

### 3.6 ファームの env 別の版

- env ごとの独立した版（DEC-035）は、minor・patch の範囲で続ける。
- `firmware-versions.json` の各 env の major は、repo 全体の major と一致しなければならない。firmware repo の CI はこれを検査し、不一致なら release を止める。
- 機能の有無を版から推測してはならない（env ごとに minor が違うため）。能力申告で判定する。

### 3.7 contracts の版

- contracts は tag `vX.Y.Z` と `CHANGELOG.md` を持つ。major は §3.2 の全製品の major、minor は追加だけの仕様変更（新コマンド、新しい能力、末尾への項目追加、新しい世代の並行追加）、patch は意味を変えない文言の修正とする。
- 各製品の CHANGELOG は、その版が対応する contracts の版を書く。

## 4. 方式の世代（Gen）

### 4.1 定義

通信の方式（stream など）のうち、互換の無い変更で作り直したものを「世代」と呼び、`Gen <番号>` で表す。番号はパケットの中の値と一致させる。

| 世代 | 日本語 | 英語 | 通信上の値 | 受け付けるファーム |
|---|---|---|---|---|
| Stream Gen 1 | ストリーム第 1 世代（セッションなし方式） | Stream Gen 1 (sessionless) | 0x30–0x32 の header `protocol_version=1`、envelope なし | 0.4.x 以前 |
| Stream Gen 2 | ストリーム第 2 世代（セッション方式） | Stream Gen 2 (session) | 0x30–0x32 の header `protocol_version=2`、16 byte の envelope、PONG の印 `HBS2` | 0.5.0 以降（1.x を含む） |

Stream Gen 2 の仕様は [stream-session.md](stream-session.md)、Stream Gen 1 の形式は [message-format.md](message-format.md) の「Stream Gen 1」節に置く。

### 4.2 呼び方の規則

- 「世代（Gen）」は方式ごとの番号にだけ使う。全製品の番号は major（例「1.x 系」）と呼ぶ。世代番号を 2 種類作らない。
- 「v1 / v2」「旧方式 / 新方式」とは呼ばない。旧い世代も、その特徴を表す名前（例: セッションなし方式）で呼ぶ。
- コードの識別子（例 `StreamSessionV2`）は、その箇所を次に変更するときに `Gen2` 等へ揃える。通信上の値（`protocol_version`、`HBS2`）は変えない。

### 4.3 新しい世代の入れ方

1. 新しい世代を、旧い世代を受け付けたまま追加できるなら（受信側が両方を受け、送信側は能力申告で選ぶ）、minor で入れる。
2. 旧い世代の受け付けをやめるなら、互換を壊すので major を一斉に上げる（§3.5）。SDK は §3.3 のとおり、1 つ前の major のファームには旧い世代で送る。
3. ESP-NOW（`espnow-stream.md`）も同じ規則に従う。`0xAA` の mode_id の追加は、旧受信機が未知の mode を無視するので追加として扱う。

## 5. 互換の判定の仕方

### 5.1 版の比較は major だけ

製品間の互換を版で判定してよいのは major の比較だけである（§3.3）。minor・patch の比較で機能や互換を判定してはならない。

### 5.2 能力申告

機体は自分の能力を次の 2 か所で同じ内容として申告する。

| 経路 | 仕様 | 主な読み手 |
|---|---|---|
| UDP の `CAPS_REQ` (0x12) → `CAPS` (0x13) | `message-format.md` §4 | SDK |
| serial / TCP の `get_info` の `caps` object | `serial-config.md` §4.1 | helper、Studio |

能力申告を持たない機体（0.x のファーム）は、`CAPS_REQ` に応答しない。読み手は応答が無いことを「`generation` 0、追加機能なし」として扱う。

### 5.3 Stream の世代の判定

Stream の世代は、能力申告ではなく、拡張 PING への照合済みの PONG で判定する（`stream-session.md` の Receiver classification）。この判定規則は 0.5.0 以降の全 SDK が持っているため、1.x の間は変えない。能力申告の `stream_gens` は表示と診断に使う。

### 5.4 ツールの判定

- Studio は、ファームを書き込む前に、書き込む image の major と機体の現在の major を比べ、異なる場合は互換の変化を案内する（書込みは止めない）。
- Kit を書き込むツールは、`caps` の `kit_schema` と `kit_clip_formats` を Kit と照合し、対応しない Kit は書き込まない（§11）。
- helper と Studio の間の互換も、版ではなく helper が申告する能力で判定する（helper と Studio の間の申告の形式は別途定める）。

### 5.5 表を写さない

互換の表は本書 §9 の移行表だけとし、他の文書・コードに写さない。ツールは major と能力申告で判定する。

## 6. 変更の分類（追加か破壊か）

contracts を変更するときは、まず次の表で分類し、commit message と `CHANGELOG.md` に分類を書く。

| 変更 | 分類 | 扱い |
|---|---|---|
| 新しいコマンドの追加 | 追加 | minor。旧受信機は無視する（§7.1） |
| 既存コマンドの末尾への省略可能な項目の追加（例: PLAY の `pan`） | 追加 | minor。`message-format.md` §4.0 の規則に従う |
| 能力申告への新しい種別・項目の追加 | 追加 | minor |
| JSON への省略可能な項目の追加 | 追加 | minor |
| 新しい世代を旧い世代と並べて追加 | 追加 | minor（§4.3） |
| enum・語彙への値の追加 | 追加（読み手が未知の値を無視できる場合） | minor。無視できない場合は破壊 |
| 既存の項目の意味・単位・既定値の変更 | 破壊 | major |
| 必須項目の追加、省略可能だった項目の必須化 | 破壊 | major |
| 項目の削除、位置の変更、型の変更 | 破壊 | major |
| **受信側の検査を厳しくすること**（長さの完全一致の要求、未知の値の拒否など） | 破壊 | major。将来の追加を拒否する検査は最初から入れない |
| 凍結した形式（§7.4）への追加 | 破壊 | major |
| 世代の受け付けをやめる | 破壊 | major（§4.3） |
| 意味を変えない文言の修正 | 修正 | patch |

## 7. 無視する規則と拒否する規則

### 7.1 無視する（must-ignore）

読み手は次を無視し、エラーにしてはならない。

- 既存コマンドの、定義より後ろにある余りの byte。ただし次の 2 つは除く: PING（payload の長さで意味が決まり、16 bytes 以外は探索だけの PING として扱う）と、Stream Gen 2 のパケット（payload と datagram の長さを厳密に検査する）。§7.4。
- 予約された flag の bit、予約された値の領域。
- 未知のコマンド（受信側は状態を変えない。応答は §7.2）。
- 能力申告・TLV の未知の種別。既知の種別の値が定義より長い場合は、定義された先頭部分だけを読む。
- JSON の未知の項目。
- header の `payload_length` より後ろの datagram の byte（Stream Gen 2 のパケットを除く）。

### 7.2 拒否する（must-reject）

読み手は次を拒否し、状態を変えない。機体は送信元へ ERROR を返す（`message-format.md` §0xFF。頻度は抑える）。

- 知っているコマンドで、知らない `protocol_version` のもの（`UNSUPPORTED_VERSION`）。
- 知らないコマンド（`UNKNOWN_COMMAND`）。
- 必須項目の欠落、長さの不足、範囲外の値（`MALFORMED`）。
- 知らない major の形式（例: Kit manifest の `schema_version` の major が対応範囲外）。

### 7.3 schema との関係

`schemas/` の `additionalProperties: false` は、書き手が自分の出力を検査するためのものである。読み手は、未知の項目があることを理由に拒否してはならない（§7.1）。

### 7.4 凍結している形式

次の形式は 1.x の間は変更しない。拡張は新しいコマンドか能力申告で行う。

- PING（payload 8 byte と 16 byte）と PONG（直接応答と unsolicited の両方）。`message-format.md` §0x10・§0x11。
- Stream Gen 2 のパケット（`stream-session.md`）。長さを厳密に検査する。拡張は新しい世代で行う。
- header の `protocol_version` の値（非 stream は 1、stream は 2）。

## 8. 永続データの版

- 機体に保存するデータ（音声領域、NVS、Kit manifest、`ui.json` など）は、自分の形式の版を持つ。
- 起動時に版が一致しない場合、機体はデータを消去・初期化してはならない。そのデータを使わずに起動し、`get_info` の `storage_incompatible` で報告する（`serial-config.md` §4.1）。データを消すのは、利用者が明示的に初期化を指示したときだけとする。
- これは新しいファームから古いファームへの書き戻しでも、古いファームから新しいファームへの更新でも同じである。

## 9. 0.x から 1.x への移行表

0.x の間は、製品ごとに版の系列が違ったため、次の表で互換を判断する。この種の表はこれを最後とし、1.x 以降は §3.3 の規則だけで判断する。

**ファーム**

| ファーム | Stream の世代 | 備考 |
|---|---|---|
| 0.4.x 以前 | Gen 1 | |
| 0.5.0 以降の 0.x（band_v4_pwm 以外） | Gen 2 | Gen 1 の stream は受け付けない |
| band_v4_pwm | 公開版 0.1.0 は Gen 1。Gen 2 の実装（2026-09-23）以後の開発ビルドと、次の公開版 0.2.0 は Gen 2 | 別系列のため版の値では判定できない。照合済みの PONG で判定する |
| 1.x | Gen 2 | |

**SDK・helper**

| 製品 | Gen 2 を送る最初の版 | それ以前（Gen 1 のみ）の最後の公開版 |
|---|---|---|
| Unity SDK（UPM） | 0.6.0 | 0.5.1 |
| Unreal SDK | 0.2.0 | 0.1.0 |
| Python SDK（`hapbeat-python-sdk`） | 0.3.0 | 0.2.0 |
| JS SDK（`@hapbeat/sdk`） | 0.4.0 | 0.3.0 |
| hapbeat-helper | 0.5.0 | 0.4.0 |

- Gen 2 を送る SDK は、Gen 1 のファームにも Gen 1 で送る（`stream-session.md` の Legacy receiver fallback）。したがって上表の版以降の SDK は、全ファームで stream が動く。
- それより前の SDK のアプリは、ファーム 0.5.0 以降（1.x を含む）の機体で stream（clip・stream）が無音になる。PLAY（Kit のイベント）は動く。
- Arduino SDK・Godot SDK は Gen 2 に未対応で、0.x のまま置く。Gen 2 に対応した版を 1.0 とする。TouchDesigner / VRChat 連携は Python SDK の版に従う。
- 0.x 同士の組み合わせで、上の 2 表から外れる互換の約束はしない。

## 10. 1.0 の条件

全製品を一斉に 1.0.0 にする（DEC-096）。条件は次のとおりである。

1. 本書と、能力申告（`CAPS`・`get_info.caps`）、ERROR の返送、凍結の規則が contracts に入っている。
2. それらと Stream Gen 2 の修正（`stream-session.md` の 1.x 要件）が、ファーム・Unity / Unreal / Python / JS SDK・helper・Studio に実装されている。
3. 利用者（Hapbeat）の実機検証が済んでいる。

Arduino SDK はできる範囲で Gen 2 を入れ、入った時点で 1.0 とする。Godot SDK は未公開のため 0.x のまま置く。

## 11. Kit とファームの互換

- Kit manifest の `schema_version` の major が、機体の `caps.kit_schema` の範囲外なら、Kit を書き込むツールと機体は拒否する（§7.2）。
- Kit の音声の形式は、機体の `caps.kit_clip_formats` に含まれるものだけを使う。
- `target_device.firmware_version_min` は major の下限として扱う（§5.1 の「major だけを比べる」に従う）。1.x の書き手は `<major>.0.0`（例 `1.0.0`）を書き、1.x の読み手は major だけを比べて、Kit の major が機体の major 以下なら受け付ける。既存の Kit の `0.1.0` などは major 0 なので、1.x の機体は受け付ける。0.x のファームは semver 全体で比べるため、`1.0.0` と書いた Kit を拒否する（古いファームに新しい Kit を入れない）。
- 新しい機能に依存する Kit は、版ではなく能力（`caps.kit_clip_formats` など）で判定する（§3.4）。
- `target_device.firmware_version_max` は照合しない（読み手は無視する。書き手は書かない）。

## 12. 変更履歴

### 2026-10-18 — 全面改訂（DEC-096）

- major を全製品で揃え、通信の互換の系列を表すことにした。互換の規則、同じ major の中は追加だけ、製品単独で major を上げない、を定めた。
- 方式の世代（Stream Gen 1 / Gen 2）の呼び方を定めた。
- 変更の分類表、無視する規則と拒否する規則、凍結している形式、永続データの版の規則を追加した。
- 旧 stream-session-v2.md（`stream-session.md` に改名）の Minimum versions を §9 の移行表へ移した。
- 旧 §4.2「wire bytes を変えたら `protocol_version` を上げる」を廃止した（実際には PLAY の `pan`、PONG の tail、PING の拡張はいずれも版を上げずに追加された。版を上げると旧受信機が全コマンドを捨てる）。拡張の方法は `message-format.md` §4.0 に定める。
- 旧 §7「0.x の間は破壊的変更を minor で行う」（DEC-082）を §3.5 と §10 で置き換えた。

### 2026-04-25 — pack → kit 命名統一

- `pack-manifest.schema.json` → `kit-manifest.schema.json`
- `specs/pack-format.md` → `specs/kit-format.md`
- `specs/pack-install-protocol.md` → `specs/kit-install-protocol.md`
- payload field: `pack_id` → `kit_id`
- TCP/プロトコルコマンド名: `pack_list` / `pack_delete` / `pack_transfer` → `kit_*`
- 関連 repo（pack-tools / firmware / manager / studio / SDK）は順次追従
- 旧名の alias は残さない（破壊的変更）
