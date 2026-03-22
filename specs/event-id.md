# Event ID 仕様

バージョン: 0.1.0（ドラフト）

## 概要

Event ID は、Hapbeat エコシステム全体で触覚イベントを一意に識別するための文字列識別子である。
SDK から Bridge へ再生指示を送る際、また Pack 内で clip と触覚パターンを紐づける際の共通キーとして機能する。

## 設計原則

1. **人間可読性** — 開発者がコード内で直接読み書きできる文字列であること
2. **プラットフォーム中立** — Unity / Unreal / TouchDesigner / Max のいずれでも同じ ID 体系を使える
3. **階層的整理** — カテゴリ / サブカテゴリによる論理的グルーピングが可能
4. **衝突回避** — Pack 間、コンテンツ間で ID が衝突しない仕組みを持つ
5. **オフライン解決** — デバイス上でローカルに ID → clip の解決ができる

## ID フォーマット

### 基本形式

```
<category>.<name>
```

### 拡張形式（サブカテゴリあり）

```
<category>.<subcategory>.<name>
```

### 名前空間付き形式（Pack 間衝突回避）

```
<namespace>/<category>.<name>
<namespace>/<category>.<subcategory>.<name>
```

### 構文規則

| 要素 | 規則 |
|------|------|
| 区切り文字（カテゴリ内） | `.`（ドット） |
| 区切り文字（名前空間） | `/`（スラッシュ） |
| 使用可能文字 | 英小文字 `a-z`、数字 `0-9`、ハイフン `-`、アンダースコア `_` |
| 大文字 | 使用不可（正規化のため小文字のみ） |
| 先頭文字 | 英字で始まること（数字・記号始まり不可） |
| 各セグメント最小長 | 1 文字 |
| 各セグメント最大長 | 64 文字 |
| 最大階層深度 | 名前空間を含めて 4 セグメントまで |
| ID 全体最大長 | 255 文字 |

### 正規表現

```
^([a-z][a-z0-9_-]{0,63}/)?[a-z][a-z0-9_-]{0,63}(\.[a-z][a-z0-9_-]{0,63}){1,3}$
```

## カテゴリ体系

### 標準カテゴリ

以下は Hapbeat が公式に定義する標準カテゴリである。コンテンツ開発者はこれらを利用するか、独自カテゴリを定義できる。

| カテゴリ | 用途 | 例 |
|----------|------|-----|
| `impact` | 衝撃・打撃系 | `impact.hit`, `impact.explosion` |
| `vibration` | 振動・持続系 | `vibration.engine`, `vibration.rumble` |
| `texture` | テクスチャ・表面触感系 | `texture.rough`, `texture.smooth` |
| `ambient` | 環境・雰囲気系 | `ambient.wind`, `ambient.rain` |
| `ui` | UI フィードバック系 | `ui.click`, `ui.confirm` |
| `custom` | 汎用カスタム | `custom.my-effect` |

### 予約プレフィックス

以下のプレフィックスは Hapbeat 公式用途に予約されている。コンテンツ開発者は使用してはならない。

| プレフィックス | 用途 |
|----------------|------|
| `hapbeat/` | Hapbeat 公式 Pack の名前空間 |
| `system.` | システム内部イベント（デバイス状態通知等） |
| `test.` | テスト用イベント |

## Event ID の使用例

### SDK からの再生指示

```
// Unity C# の場合（イメージ）
HapbeatManager.Play("impact.hit");
HapbeatManager.Play("vibration.engine", targetTime: 1500);
HapbeatManager.Play("my-content/impact.sword-slash");
```

### Pack manifest 内での参照

```json
{
  "events": {
    "impact.hit": {
      "clip": "clips/hit_01.wav",
      "description": "基本的な衝撃"
    },
    "impact.explosion": {
      "clip": "clips/explosion_01.wav",
      "description": "爆発衝撃"
    }
  }
}
```

### OSC メッセージでの使用

```
/hapbeat/play impact.hit
/hapbeat/play vibration.engine 1500
```

## Event ID のライフサイクル

### 定義

- Event ID は Pack の manifest 内で定義される
- 1つの Pack 内で同一 Event ID の重複定義は禁止
- 名前空間を使うことで、異なる Pack 間の ID 衝突を回避する

### 解決

- デバイス側で Event ID → clip ファイルへの解決を行う
- 解決は Pack install 時にインデックスを構築し、再生時はインデックス参照で行う
- 未解決の Event ID を受信した場合、デバイスはエラーログを記録し、無視する

### 変更

- **既存 Event ID の中身（紐づく clip）変更** — Pack 差し替えのみで可能。アプリ再ビルド不要
- **Event ID の新規追加** — Pack manifest への追記で可能
- **Event ID の名前変更 / 削除** — 公開インターフェースの破壊的変更となる。バージョニング方針に従うこと

## 命名のベストプラクティス

1. **具体的な名前を使う** — `effect1` ではなく `impact.sword-slash`
2. **英語で命名する** — 多言語環境での一貫性のため
3. **ハイフン区切りを推奨** — 複合語は `sword-slash`（ハイフン区切り）
4. **動詞ではなく名詞で** — `hitting` ではなく `hit`
5. **過度に深い階層を避ける** — 3 段階以内を推奨
