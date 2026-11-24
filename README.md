# Santo: the AI agent for any business or domain

**heysanto.ai** · *Meet Santo, the AI agent woven from everything your business knows.*

**No API key needed.** Santo runs its own open-source AI model (Qwen 2.5 or Llama 3 via Ollama) on your server, so there are no AI accounts and no per-message fees. If the model server is ever down, a built-in engine keeps answering from your documents and still captures leads and bookings.

Santo is both the platform and its own AI agent: the homepage greets visitors with Santo (`agents/santo.yaml`), and the same platform builds Santo-powered agents for any business.

Santo is a complete full-stack product in one deployable service:

| Page | URL | What it does |
|---|---|---|
| Marketing site | `/` | Brand, live demo, industries, FAQ, sign-up form |
| Agent builder | `/builder` | Create and publish agents without code, from 8 industry templates |
| Console | `/console` | Chat with any agent and get its embed and API code |
| Dashboard | `/admin` | Messages over time, per-agent usage, conversations, sign-ups |
| API docs | `/docs` | Interactive OpenAPI reference |

Behind those pages, a **YAML file plus a folder of documents** becomes a working AI agent, available in four ways at once:

| Surface | URL | Who uses it |
|---|---|---|
| Web chat UI | `/console` | Staff, demos, internal users |
| Embeddable widget | `<script src="/widget.js" data-agent="...">` | Customers on any website (WordPress, Shopify, Wix, React…) |
| REST API + OpenAPI docs | `/api/agents/{id}/chat`, `/docs` | Mobile apps, backends, Slack/Teams bots, Zapier/n8n |
| MCP server | `/mcp` | Other AI agents (Claude, Cursor, Copilot, custom agent frameworks) |

You don't write any code to add a new business. You add `agents/<id>.yaml` and `knowledge/<id>/*.md`, and the agent is live.

---

## 1. Run it (no API key)

```bash
cp .env.example .env            # nothing to fill in for AI; optionally set API_KEYS (admin password)
docker compose up -d            # starts Santo + its own open-source AI model
```
The first start downloads the AI model once (about 2 GB). Then open http://localhost:8000. Visit `/health` to confirm `"ai_engine": "ollama"`.

**Server size:** the default `qwen2.5:3b` model needs about 4 GB of RAM in total. For smarter answers, set `OLLAMA_MODEL=qwen2.5:7b` or `llama3.1:8b` in `.env` (8 GB or more). A GPU makes replies much faster. Uncomment the GPU block in `docker-compose.yml` to use it.

**Without Docker:**
```bash
# install Ollama from ollama.com, then:
ollama pull qwen2.5:3b && ollama pull nomic-embed-text
pip install -r requirements.txt
OLLAMA_URL=http://localhost:11434 uvicorn app.main:app
```

**No model at all** (for example, free hosting with little memory): just run `uvicorn app.main:app`. Santo uses its built-in engine. It answers from your documents, handles greetings, collects bookings and saves leads, with no model and no key.

### Built-in AI features (all keyless)
| Feature | What it does |
|---|---|
| Open-source chat model | Natural conversation, follows each assistant's instructions |
| Tool use | The model decides when to search knowledge, save a lead, request a booking or call your APIs |
| Semantic search | Finds answers by meaning (local `nomic-embed-text` embeddings) blended with keyword search |
| Lead capture | `save_lead` stores contact details from any chat in the dashboard |
| Booking requests | `request_booking` stores table, appointment or viewing requests, with status you can update |
| Answers every question | Business facts from your documents; general questions from the model, free Wikipedia/DuckDuckGo lookups, a calculator and the clock. Set `answer_mode: business` to limit an assistant to business topics |
| Automatic fallback | If the model is slow or down, the built-in engine answers instead of showing an error |
| Conversation memory | Multi-turn sessions, logged for review in the dashboard |

## 2. Create an agent for any business

**No code:** open `/builder`, pick an industry template (or start blank), paste your FAQs and click **Publish agent**. You can test it straight away and copy its website, API and MCP code.

**As files (for developers):**
```bash
cp agents/TEMPLATE.yaml.example agents/dental-clinic.yaml
mkdir knowledge/dental-clinic && cp ~/docs/*.md knowledge/dental-clinic/
curl -X POST localhost:8000/api/admin/reload -H "X-API-Key: $KEY"   # no restart needed
```

What the YAML controls:

- **Persona and rules** (`system_prompt`, `greeting`, `theme_color`, `suggested_questions`)
- **Knowledge** (`knowledge:` folder). Drop in `.md` or `.txt` files such as FAQs, policies, menus or price lists. Search uses built-in BM25, so you don't need a vector database.
- **Actions** (`http_tools:`). Connect any REST API or webhook: CRM, booking, orders, ticketing, Zapier/n8n/Make.
  `{arg}` is replaced from the AI's arguments. `${ENV_VAR}` is replaced from secrets, so tokens never sit in YAML.
- **Model** (`provider` / `model`). Each agent can use a different one.

Three examples are included: e-commerce support (Acme), restaurant host (Bella Bistro) and an internal HR helpdesk (Northwind).

## 3. Use it

**Website widget** (the "Integrate" tab in the UI generates this for you):
```html
<script src="https://your-host/widget.js" data-agent="acme-support"></script>
```

**REST:**
```bash
curl -X POST https://your-host/api/agents/acme-support/chat \
  -H "Content-Type: application/json" -H "X-API-Key: $KEY" \
  -d '{"message":"Where is order A-10023?","session_id":null}'
# → {"reply": "...", "session_id": "...", "tool_calls": [...], "provider": "...", "model": "..."}
```
Send the returned `session_id` with later messages to keep the conversation's memory.

**MCP (agent-to-agent):** add `https://your-host/mcp` as a remote MCP server with header `Authorization: Bearer <API_KEY>`. Each agent shows up as a tool named `ask_<agent_id>`, so an orchestrator agent can delegate to your business agents.

## 4. Deploy (live on your domain)

The AI model needs a server with at least 4 GB of RAM, so use a VPS rather than a free web host.

| Option | Notes |
|---|---|
| **Oracle Cloud Always Free (Arm)** | Free. Since June 2026 the free allowance is 2 OCPUs and 12 GB RAM, enough for `qwen2.5:3b` |
| **Hetzner, DigitalOcean, Vultr, Linode** | Low-cost VPS. Pick 8 GB RAM for the 7B/8B models |
| **A GPU server** (RunPod, Lambda, your own PC) | Fastest replies, for busy sites |
| Render / Railway free tier | Website works with the built-in engine only (`LLM_PROVIDER=local`) |

**On any Ubuntu VPS:**
```bash
curl -fsSL https://get.docker.com | sh
git clone https://github.com/<you>/santo.git && cd santo
cp .env.example .env && nano .env        # set API_KEYS, SITE_URL, CORS_ORIGINS
docker compose up -d
```
**HTTPS and your domain:** point an `A` record for `heysanto.ai` (and `www`) at the server's IP in Cloudflare DNS. Then put Caddy in front for automatic SSL:
```bash
sudo apt install -y caddy
echo 'heysanto.ai, www.heysanto.ai {
  reverse_proxy localhost:8000
}' | sudo tee /etc/caddy/Caddyfile && sudo systemctl reload caddy
```
Open ports 80 and 443 in the server's firewall (on Oracle Cloud, also open them in the VCN security list).

### Deploy on GoDaddy Web Hosting (cPanel)
Shared hosting can't run Docker or an AI model, so Santo runs with its **built-in engine** here. It answers from your documents, looks up general facts, does math, and captures bookings and leads, all with no API key. For full AI conversation, use a GoDaddy VPS with Docker instead.

1. Buy a GoDaddy **Web Hosting (cPanel)** plan and attach your domain.
2. cPanel > **Git Version Control** > Create: clone `https://github.com/santhosh-dataops/santo.git` into `santo` (or upload the zip with File Manager and extract it into `/home/<user>/santo`).
3. cPanel > **Setup Python App** > Create Application: Python **3.10 or newer**, Application root `santo`, Application URL your domain (`/`), Startup file `passenger_wsgi.py`, Entry point `application`.
4. In the same screen add environment variables `API_KEYS` (your admin password), `SITE_URL=https://heysanto.ai` and `CORS_ORIGINS=https://heysanto.ai`, then click **Run Pip Install** with `requirements.txt`, then **Restart**.
5. cPanel > **SSL/TLS Status** > Run AutoSSL so the site gets HTTPS.
6. To update later: Git Version Control > Manage > **Update from Remote**, then Setup Python App > Restart.

### Deploy with GitHub (recommended)
1. Create a **private** repository named `santo` on github.com (no README or .gitignore, since the project already has them).
2. On your computer, inside the `santo` folder:
   ```bash
   git remote add origin https://github.com/santhosh-dataops/santo.git
   git push -u origin main
   ```
3. On the server, once: `git clone https://github.com/santhosh-dataops/santo.git && cd santo`, then continue with `.env` and `docker compose up -d`.
4. Auto-deploy: in GitHub > Settings > Secrets and variables > Actions, add `SERVER_HOST`, `SERVER_USER` and `SERVER_SSH_KEY`. From then on, every push to `main` runs the tests (`.github/workflows/ci.yml`) and, if they pass, updates the server (`.github/workflows/deploy.yml`).

For a private repo, the server needs permission to pull: either add the server's public key (`ssh-keygen -t ed25519` on the server, then `cat ~/.ssh/id_ed25519.pub`) as a **Deploy key** in the repo settings and clone with `git@github.com:santhosh-dataops/santo.git`, or make the repo public.

## 5. AI engines

| Provider | Env vars |
|---|---|
| **Ollama (default, no key)** | `OLLAMA_URL`, `OLLAMA_MODEL` (set automatically by docker-compose) |
| **Built-in engine (no key, no model)** | Used automatically when no model server is reachable |
| Anthropic Claude (optional) | `ANTHROPIC_API_KEY` |
| OpenAI (optional) | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| Azure OpenAI | `OPENAI_BASE_URL=.../deployments/<name>`, `OPENAI_API_VERSION`, `OPENAI_AUTH_HEADER=api-key` |
| Groq / Together / Ollama / vLLM / LM Studio | `OPENAI_BASE_URL` pointing at their OpenAI-compatible endpoint |

There are no vendor SDKs. Everything uses plain HTTPS, so upgrading a provider never breaks the build.

## 6. Security checklist for production

- Set `API_KEYS`. It protects `/mcp`, `/api/admin/*`, and any agent not listed in `PUBLIC_AGENTS`.
- `PUBLIC_AGENTS`: only customer-facing agents should be keyless (for the widget). Keep internal ones (HR, finance) private.
- `CORS_ORIGINS`: restrict this to your customers' domains.
- `RATE_LIMIT_PER_MIN` is applied per IP. Put a WAF or CDN in front for public traffic.
- Sessions are in-memory. If you run more than one instance, swap `SESSIONS` in `app/main.py` for Redis.
- Sign-ups and conversation logs go to SQLite at `DATABASE_PATH` (default `data/santo.db`). Mount `data/` on a persistent volume (already set up in `docker-compose.yml`, `render.yaml` and `fly.toml`). To scale out, move to Postgres.
- Back up `data/`, `agents/` and `knowledge/`. They hold everything that's specific to your business.

## 7. Project layout

```
app/main.py        REST API, MCP endpoint, builder/admin/leads endpoints, auth, rate limiting, pages
app/db.py          SQLite: sign-ups and conversation logs, dashboard stats
app/llm.py         Anthropic / OpenAI-compatible / mock providers with a tool-calling loop
app/tools.py       built-in tools + YAML-declared HTTP tools
app/knowledge.py   BM25 search over knowledge/<agent>/
app/config.py      YAML loader and schema
agents/*.yaml      one file per agent
knowledge/<id>/    documents per agent
static/index.html  marketing site with live demo
static/builder.html, admin.html, console.html
static/widget.js   embeddable chat bubble
static/css, fonts, img   design system, self-hosted Archivo font, logo files
scripts/make_logo.py     regenerates the logo SVGs
BRAND.md           name, domain guide, logo, colours, type, voice
tests/             pytest suite (runs offline): `pytest -q`
```

## 8. Roadmap ideas

- Streaming responses (SSE)
- Vector search (pgvector/Qdrant) for large document sets, plus PDF/DOCX ingestion
- Edit existing agents in the builder (create and delete already work)
- Subscriptions and billing (see "Adding pricing later")
- Email notification when a new sign-up arrives
- Postgres conversation logs and an analytics dashboard
- Human handoff (email/Slack) when the agent escalates
- Multi-tenant mode (tenant ID → agents/knowledge/keys)

## Adding pricing later
The site launches without plans or prices. When you're ready, `future/pricing-section.html` holds the finished pricing section (three plans, styles included) with instructions for putting it back.
