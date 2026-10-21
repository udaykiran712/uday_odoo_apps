# Partner Logo Enrichment (Logo.dev) — Odoo 18.0

Automatically fetch and enrich Odoo 18 Partner (`res.partner`) records with high-resolution logos using the **Logo.dev API** based on a partner's website or email domain.

## Key Features

- **Automatic Domain Extraction:** Extracts clean domains from `website` (stripping schemes, `www.`, ports, and paths) or falls back to `email` addresses (`@domain.com`).
- **1-Click API Connection Tester:** Includes a built-in **Test Connection** button directly in **Settings -> General Settings -> Contacts** that auto-saves your `pk_...` key, validates it live against `img.logo.dev`, and displays an instant status toast notification.
- **Dual Execution Modes:**
  - **Background Cron Mode (Default):** Queues new/updated partners (`logo_fetch_pending`) and processes them asynchronously every 15 minutes in bounded batches (`limit=50`) so the UI never blocks.
  - **Immediate Fetch Mode (Optional):** Enable **Immediate Logo Fetch** in General Settings to fetch logos synchronously on partner creation or save.
- **One-Click Smart Button:** Click **Fetch Logo** directly on any Partner Form view to fetch or refresh a logo on demand with instant toast feedback and automatic view reload.
- **Bulk Server Action:** Select multiple contacts in the Partner List view and run **Action -> Fetch Partner Logos** to enrich existing records in bulk.
- **404 & Error Resilience:** Tracks lookup status (`pending`, `fetched`, `not_found`, `failed`) and clears the pending flag on `404 Not Found` responses to prevent infinite retry loops.

## Configuration

1. Install **Partner Logo Enrichment (Logo.dev)** (`partner_logo_enrichment`).
2. Obtain a free Publishable API Key (`pk_...`) from [https://www.logo.dev](https://www.logo.dev).
3. Navigate to **Settings -> General Settings -> Contacts**.
4. Paste your key into **Logo.dev API Key** and click **Test Connection** to verify your key (it automatically persists the key and confirms connectivity with a green toast notification).
5. Optionally enable **Immediate Logo Fetch** and click **Save**.

## Usage

- **Mandatory Fields on Contact:**
  - **Name** (`name`)
  - **Website** (e.g., `starbucks.com` or `https://www.stripe.com`) **OR** **Email** (e.g., `info@starbucks.com` or `user@gmail.com`).
- Click **Fetch Logo** in the top smart button box (or save the record with **Immediate Logo Fetch** enabled).

## Technical Details

- **Module Name:** `partner_logo_enrichment`
- **Version:** `18.0.1.0.0`
- **License:** LGPL-3
- **Dependencies:** `base`, `base_setup`
- **Author:** Uday Odoo Apps ([LinkedIn](https://www.linkedin.com/in/udaykirangardas/))