# Instagram AI Bot

Automated Instagram carousel generator. Researches trending topics, generates content with LLMs, designs carousel images, and publishes via the Instagram Graph API. Includes a React dashboard for monitoring and control.

## Architecture

```
main_pipeline.py       Orchestrator: research → content → design → engage → publish
dashboard.py           Flask dashboard entry point

config/                Settings, API keys, templates
modules/               Core pipeline modules
  researcher.py        Multi-source trending research (NewsAPI, RSS, Reddit, Tavily)
  content_generator.py OpenAI text generation (slides, captions)
  image_generator.py   Image generation (Gemini / xAI Grok)
  carousel_designer.py Compose text + backgrounds into carousel images
  engagement.py        Engagement strategy
  publisher.py         Instagram Graph API publishing
  post_store.py        SQLAlchemy ORM (PostgreSQL / SQLite)
  prompt_director.py   Content direction via LLM
  prompt_loader.py     Load custom prompts from data/prompts/

dashboard/             Flask REST API dashboard
  routes/              API endpoints (pipeline, posts, research, scheduler, etc.)
  services/            Business logic (scheduler, pipeline runner, env manager)

frontend/              React 18 + TypeScript + Vite + Tailwind
  src/components/      25+ React components (pipeline, content, posts, scheduler)
  src/hooks/           Custom React hooks
  src/api/             API client
  src/types/           TypeScript type definitions
```

## Commands

```bash
# Backend
ruff check .                         # Lint Python
ruff format .                        # Format Python
ruff check --fix .                   # Auto-fix lint issues
python main_pipeline.py              # Run full pipeline
python main_pipeline.py --dry-run    # Dry run (no publish)
python dashboard.py                  # Start dashboard (port 8000)

# Frontend
cd frontend
npm run lint                         # ESLint check
npm run lint:fix                     # ESLint auto-fix
npm run format                       # Prettier format
npm run format:check                 # Prettier check (CI)
npm run dev                          # Vite dev server
npm run build                        # Vite build
```

## Code Conventions

### Python
- Formatter/linter: **Ruff** (config in `pyproject.toml`)
- Line length: 120
- Imports: sorted by isort rules (stdlib → third-party → local)
- Target: Python 3.12+
- Use type hints for function signatures
- Docstrings: module-level and public functions
- `modules/researcher.py` is a large research module — excluded from linting/formatting
- First-party packages: `config`, `modules`, `dashboard`

### TypeScript/React (frontend/)
- Linter: **ESLint** with typescript-eslint + react-hooks
- Formatter: **Prettier** (config in `.prettierrc`)
- Semicolons: yes
- Quotes: double
- Indent: 2 spaces
- Functional components with hooks
- Types in `src/types/`

### General
- Always run linters before committing (pre-commit hooks handle this automatically)
- No secrets in code — use `.env` (see `.env.example`)
- Keep functions focused and small
