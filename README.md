# Wallapop Auto-Publisher

> Autonomous listing publisher for Wallapop — Spain's leading peer-to-peer marketplace.

## Overview

An AI-powered agent skill that fetches products from a Notion inventory database and automatically publishes listings on Wallapop, handling the full flow from form completion to photo upload and post-publish tracking.

## Features

- **Notion integration** — pulls unpublished products from inventory database (checks "Wallapop Posted" field)
- **Shadow DOM navigation** — handles Wallapop's complex web component structure
- **AI-assisted listing** — Wallapop's AI auto-generates title, description, and category from product summary
- **Photo upload** — injects images directly into the upload input
- **Location handling** — sets correct city/postal code via map dialog
- **Anti-bot protection** — randomized delays, human-like interaction patterns
- **Post-publish URL capture** — writes listing URL back to Notion

## Architecture

```
Notion DB → fetch_product_for_wallapop.py
          → Browser (OpenClaw profile) → es.wallapop.com/app/catalog/upload
          → inject_photo_wallapop.py
          → Wallapop AI auto-fill (title/description/category)
          → update_notion_wallapop.py → Notion DB
```

## Requirements

- Python 3.10+
- Notion API Key (`NOTION_API_KEY` env variable)
- OpenClaw browser profile (pre-authenticated Wallapop session)

## Usage

```bash
# Fetch next unpublished product from Notion
python fetch_product_for_wallapop.py

# Inject product photo into upload input
python inject_photo_wallapop.py

# Update Notion with published listing URL
python update_notion_wallapop.py <notion_page_id> <listing_url>
```

## Anti-Bot Rules

- Max 3–5 publications per day
- 60–120 second pause between listings
- Human-like typing with `slowly=True`
- No night-time publishing

## Agent Skill

This is an **OpenClaw agent skill** — triggered on demand or via cron, executes the full Wallapop publish pipeline autonomously.

---

*Part of the AI automation toolkit for e-commerce operations (MixMix Spain).*
