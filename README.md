# agentfront

AIエージェントが事業者を見つけ、比較し、見積依頼や問い合わせまで進めるためのカタログです。運営者がURLと短い説明を入れると、業種ごとの項目を提案してカタログを作り、エージェント向けのHTML / JSON-LD / Markdown と MCP の両方で公開します。人向けの見た目のサイトではありません。

初期データとして、架空の設計事務所「株式会社青葉設計室」と、架空の映像制作「合同会社光枠フィルム」が入っています。APIキーが無くても、この2件の公開ページとMCP検索は動きます。

## 起動

Docker と Docker Compose v2 が必要です。

```bash
docker compose up --build
```

| 画面 | URL |
| --- | --- |
| 運営者画面 | http://localhost:3410 |
| エージェント向けカタログ | http://localhost:8765 |
| MCP（streamable HTTP） | http://localhost:8765/mcp |
| 受信メール（Mailpit） | http://localhost:8025 |
| MinIO コンソール | http://localhost:19001 （`catalog` / `catalogsecret`） |

APIキーは任意です。無いまま起動でき、生成を押したときだけ「キーが未設定」と出ます。生成する場合はリポジトリ直下に `.env` を置きます。

```bash
cp .env.example .env
# .env の OPENCODE_API_KEY を埋めてから
docker compose up --build
```

`backend` と `worker` の両方にキーが渡ります。キーを変えたあとは `docker compose up -d` で再作成してください。

## 環境変数

| 変数 | 既定 | 意味 |
| --- | --- | --- |
| `OPENCODE_API_KEY` | 空 | OpenCode Go のキー。`Authorization: Bearer` で送ります |
| `LLM_API_KEY` | 空 | こちらが空でなければ `OPENCODE_API_KEY` より優先します |
| `LLM_API_BASE` | `https://opencode.ai/zen/go/v1` | OpenAI互換のチャットAPI。同じサービスは `https://opencode.ai/inference/go/openai/v1` でも届きます。`native` にすると LiteLLM の標準プロバイダ（OpenAI など）を使います |
| `LLM_MODEL` | `deepseek-v4.1-flash` | Go のモデルID。代替は `grok-4.7` や `glm-5.3-flash`。ほかに `grok-4.6`、`glm-5.3`、`deepseek-v4-pro` があります |
| `ADMIN_TOKEN` | 空 | 空なら管理APIは無認証。入れると `/api` は `X-Admin-Token` が必要。フロントのプロキシが同じ値を付けます |
| `CRAWL_BACKEND` | `auto` | `auto` / `trafilatura` / `crawl4ai` |
| `DIAGNOSTICS_ALLOW_PRIVATE` | `false` | `true` にすると、エージェント可視性診断でローカル・プライベートなアドレスも対象にします。開発やテスト用です |
| `CREDENTIALS_KEY` | 開発用の固定鍵 | アダプタ資格情報の Fernet 鍵。本番では必ず別の鍵にする |
| `PUBLIC_BASE_URL` | `http://localhost:8765` | 公開URLとJSON-LDの起点。トンネル利用時は外向けのURLに合わせる |
| `INTERNAL_BASE_URL` | `http://backend:8765` | ワーカーが自分のフィクスチャを取りに行くときの起点 |

Compose ファイルが Postgres・MinIO・SMTP の接続先を埋めています。アプリ単体の既定値は `backend/app/config.py` にあります。

OpenCode Go で DeepSeek（既定の `deepseek-v4.1-flash` を含む）を使うときは、OpenCode ワークスペースのプライバシー設定で **Global リージョンを有効**にしてください。無効のままだと、そのモデルへのリクエストは拒否されます。

OpenAI など別プロバイダにする例:

```bash
LLM_API_BASE=native
LLM_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=sk-...
```

`LLM_API_BASE=https://api.openai.com/v1` かつ `LLM_MODEL=gpt-4o-mini` でも、同じ OpenAI 互換の経路で呼べます。Anthropic や Gemini は `LLM_API_BASE=native` と `anthropic/...` や `gemini/...`、対応するキーです。

## 運営者の流れ

1. http://localhost:3410 を開く。
2. 「事業者を登録」でURLと説明を入れる。サンプルボタンは `http://localhost:8765/fixtures/aoba` と `.../kogaku` を入れます。これは起動直後から読める固定ページです。
3. 詳細画面が生成の完了を待ちます。失敗すると日本語の理由が出ます。キー未設定もここです。
4. レビューで、左に取得した原文、右に抽出したカタログが出ます。業種スキーマ（JSON Schema）と値の両方を直せます。
5. 「保存して公開」でエージェント向けページとMCPの検索対象になります。公開中の事業者を再生成しても、公開を押すまで検索結果は前の内容のままです。

コンバージョン地点では、入力項目のJSON Schemaと、内部記録・メール・Webhook の送り先を選べます。届いた依頼は「受信した依頼」に、MCP呼び出しとページ取得は「計測」に出ます。

## シード

| 事業者 | スラッグ | 公開ページ |
| --- | --- | --- |
| 株式会社青葉設計室（木造住宅の設計・監理、鎌倉） | `aoba-sekkei` | http://localhost:8765/b/aoba-sekkei |
| 合同会社光枠フィルム（ブランド映像、世田谷） | `kogaku-film` | http://localhost:8765/b/kogaku-film |

青葉の見積は場所・延床面積・予算・時期、光枠の見積は目的・長さ・納期・予算・参考映像を必須にしています。見積のメールは Mailpit に届きます。

ほかの公開物:

- http://localhost:8765/llms.txt
- http://localhost:8765/agents.md （全事業者の agents.md へのリンク）
- http://localhost:8765/.well-known/ucp （プラットフォーム全体のUCPプロファイル）
- http://localhost:8765/feed.json
- http://localhost:8765/sitemap.xml
- http://localhost:8765/robots.txt （GPTBot や ClaudeBot などを許可）
- 各事業者の `.../b/{slug}.md`
- 各事業者の `.../b/{slug}/agents.md` と `.../b/{slug}/.well-known/ucp`

## エージェント向けファイル

`agents.md` は、サイト全体と事業者ごとの両方で公開します。サイト全体の `agents.md` は各事業者へのリンク集で、事業者ごとのファイルは問い合わせ方法、提供内容、コンバージョン地点、入力スキーマをまとめます。`/.well-known/ucp` も同じ構成で、UCP の `version` と `services` を返します。

| 対象 | agents.md | UCPプロファイル |
| --- | --- | --- |
| サイト全体 | http://localhost:8765/agents.md | http://localhost:8765/.well-known/ucp |
| 事業者ごと | http://localhost:8765/b/{slug}/agents.md | http://localhost:8765/b/{slug}/.well-known/ucp |

MCP の `get_business` も、事業者ごとの `agents_md_url` と `ucp_url` を返します。

## 必須項目と充足率

業種ごとの買い手向け必須項目は `backend/app/domain/required_fields.yaml` のプロファイルで定義します。`services` と `goods` を基本に、`verticals` で業種を追加・継承でき、コードを変えずに反映されます。生成・保存・公開のたびにカタログとの充足率を計算し、管理画面のレビューと事業者詳細に未設定・空欄の警告を出します。

| API | 内容 |
| --- | --- |
| `GET /api/required-fields` | プロファイル定義一式 |
| `GET /api/businesses/{id}/completeness` | 対象事業者の充足率レポート（再計算して保存） |

## エージェント可視性診断

任意の公開URLを、AIエージェントから見た可視性で採点します。robots.txt でのAIクローラ許可、JSON-LD、本文の読み取りやすさ、title と description、`llms.txt`、`agents.md`、UCPプロファイルを確認し、スコアと改善案を返します。JavaScriptは実行しません。

- 管理画面: http://localhost:3410/diagnostics の「エージェント可視性診断」
- API: `POST /api/diagnostics` に `{"url": "https://example.com/"}` を送ります。履歴は `GET /api/diagnostics`
- MCP: `diagnose_agent_visibility`（`url`、任意の `agent_name`）
- 設定: `backend/app/diagnostics/config.yaml`（対象クローラ、確認するファイル、配点、タイムアウトなど）
- `DIAGNOSTICS_ALLOW_PRIVATE=true` のときだけ、ローカル・プライベートなアドレスも診断できます。既定ではホスト名の解決結果がプライベートなら拒否し、リダイレクト先や robots.txt / agents.md などの追加取得も同じように検査します

## MCPクライアント

ツールは6つです。意味検索はありません。条件の解釈はエージェント側です。

- `search_businesses` … 名前、タグ、エリア、価格、種別
- `get_business` … 事業者の全項目（業種拡張を含む）
- `get_offering` … 提供内容と、それに使えるコンバージョン
- `list_conversion_points` … 入力スキーマ
- `submit_conversion` … スキーマ検証のあと、設定したアダプタへ送る
- `diagnose_agent_visibility` … URLのエージェント可視性を採点する

### MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

Transport は **Streamable HTTP**、URL は `http://localhost:8765/mcp` です。ステートレスで、JSONレスポンスを返します。接続後に `search_businesses` の `area` に `鎌倉` を渡すと青葉設計室が返ります。

### Claude Desktop

[mcp-remote](https://www.npmjs.com/package/mcp-remote) でローカルのHTTPエンドポイントへつなぎます。

```json
{
  "mcpServers": {
    "agentfront": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8765/mcp"]
    }
  }
}
```

### 一時的に外へ出す（Cloudflare Tunnel）

ChatGPT や Gemini から手元のMCPを叩くとき、トンネルで backend を公開します。

```bash
cloudflared tunnel --url http://localhost:8765
```

表示された `https://<host>.trycloudflare.com/mcp` がMCPのURL、`https://<host>.trycloudflare.com/b/aoba-sekkei` がエージェント向けページです。JSON-LDのURLを外向きにしたいときは、`PUBLIC_BASE_URL` をそのホストにして backend と worker を上げ直してください。

このトンネルは管理API（`/api`）も一緒に出します。外に出す前に `ADMIN_TOKEN` を設定してください。認証はトークンだけで、OAuthはありません。

ChatGPT のカスタムコネクタや一部のGemini連携は、リモートMCPにOAuthを要求します。このMVPはOAuthを実装していないので、そこでは接続できないことがあります。手元での確認は MCP Inspector と Claude Desktop を使ってください。

## アーキテクチャ

中心は Pydantic の `BusinessCatalog` です。名前、売り手、対応エリア、価格帯、提供内容、実績、コンバージョン地点を持ちます。業種ごとの追加項目はモデルに書かず、`extension` に入れます。HTML、JSON-LD、Markdown、`llms.txt`、フィード、MCP、管理画面のフォームは、保存時にこのモデルへ戻してから生成します。

業種スキーマは JSON Schema（Draft 2020-12）で、`vertical_schemas` に版付きで保存します。値は Postgres の JSONB です。項目を足すときはスキーマの版を上げるだけで、マイグレーションは要りません。

生成は Procrastinate（Postgresのキュー）がワーカーで実行します。

1. 取り込みアダプタがURLを取得する。既定は httpx + trafilatura。ページ内の JSON-LD / OGP は extruct が読む。画像は MinIO に置き、`/media/...` で配信する。
2. LLMが既存スキーマを見て、その業種向けの JSON Schema を提案するか、既存のものを選ぶ。
3. 同じスキーマで構造化抽出する。検証に失敗したら1回だけやり直す。
4. 運営者がレビューして公開する。公開時に offerings / works / conversion_points の行へ展開する。

LLMの既定は OpenCode Go（`https://opencode.ai/zen/go/v1`、モデル `deepseek-v4.1-flash`）です。LiteLLM からは OpenAI 互換として呼び、構造化出力は Instructor です。プロンプトは `backend/app/prompts/` のファイルです。キーが無いときはジョブが失敗し、管理画面に理由が出ます。プロセス自体は起動します。

コンバージョンの送信は pluggy のアダプタです。入口は `agentfront.adapters`。各アダプタは設定スキーマ、`send`、`status` を持ちます。地点ごとに複数選べ、資格情報は Fernet で暗号化して保存します。同梱は内部記録、SMTPメール、Webhook です。取り込みも同じ形で、MVPはURLクロールだけです（`agentfront.ingestion`）。

MCPは公式 Python SDK の streamable HTTP を FastAPI の `/mcp` に載せてあります。ツール呼び出し（引数と返したID）、エージェント向けページの取得（User-Agent を GPTBot、OAI-SearchBot、ChatGPT-User、Google-Extended、ClaudeBot、PerplexityBot などに分類）、コンバージョン（エージェント名と依頼文）を記録します。エージェントが内部でどう比較したかは分かりません。

## ライブラリの置き換え

提案どおりの構成を基本にしています。変えた点は次のとおりです。

- **クロール**: 既定のDockerイメージには Crawl4AI を入れていません。Playwright のブラウザが入るとイメージが重く、手元の確認が遅くなります。取得は httpx + tenacity + trafilatura、構造化メタデータは extruct です。Crawl4AI を使うときはイメージを作り直し、`pip install 'agentfront[crawl4ai]'` と `CRAWL_BACKEND=crawl4ai` を足してください。未インストールのときは trafilatura に落ちます。
- **オブジェクトストレージ**: アプリは MinIO の Python クライアントで S3 互換APIを使います。Docker Hub の `minio/minio` はログインなしでは取れなくなったため、Compose は同じAPIの `bitnamilegacy/minio` を起動します。コンソールは http://localhost:19001 です。
- **構造化抽出**: Instructor の JSON モード（OpenAI 互換の `response_format`）で、検証に失敗したら同じ呼び出しの中でやり直します。エンドポイントが JSON モードを拒んだときだけ tools モードに切り替えます。LiteLLM には `openai/<モデルID>` と `api_base` を渡し、毎回 `User-Agent: agentfront/0.1` と、生成ジョブごとに固定の `x-opencode-session` を `extra_headers` で付けます。このセッションヘッダが無いと OpenCode Go は `MissingSessionID` を返します。
- **ジョブ**: Procrastinate。Redis を足さず、Postgres だけでキューを持ちます。
- **アダプタ**: pluggy と entry points。送信用と取り込み用で同じ登録方法です。
- **管理画面**: Next.js、Refine、Ant Design。拡張項目とアダプタ設定は `@rjsf/antd` が JSON Schema から描画します。ブラウザは Next の `/backend-api` を経由し、APIの実体は backend です。
- **MCP**: 公式 `mcp` パッケージの `MCPServer`（旧 FastMCP）です。

## テスト

Postgres なしで、スキーマ拡張、コンバージョン入力の検証、アダプタのファンアウトを見ます。

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

## 本番に出す前に

開発用の `CREDENTIALS_KEY` はリポジトリに書いてあります。本番では新しい Fernet 鍵にしてください。`ADMIN_TOKEN` が空の管理APIをインターネットに出さないでください。決済、請求、意味検索、出品者のセルフサーブは入っていません。
