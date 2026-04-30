# PartnerTrack — Stock & Revenue

A Flask web app for tracking inventory and calculating monthly earnings splits between two business partners (AL and KALI).

## Features

- **Dashboard** — monthly overview: stock count, low-stock alerts, partner earnings
- **Stock Master** — manage inventory items with purchase cost and selling price
- **Sales Log** — record sales by month; revenue computed automatically
- **Partner Rules** — configure earning-split rules per product category (Fixed Per Unit, Shared 50/50, Fixed Per Job, Fixed Per Service)
- **Summary** — monthly breakdown of AL vs KALI earnings by category

## Stack

- **Backend**: Python / Flask, SQLAlchemy, PostgreSQL
- **Frontend**: Single-page HTML/JS (`backend/templates/index.html`)

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables in `.env`:
   ```
   DATABASE_URL=postgresql://user:password@localhost/partnertrack
   API_KEY=your-api-key
   ```

4. Run the backend:
   ```bash
   flask run --port 5000
   ```

5. Open `backend/templates/index.html` in a browser (or serve via Flask).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/stock` | List or create stock items |
| GET/PUT/DELETE | `/api/stock/<id>` | Get, update, or delete a stock item |
| GET/POST | `/api/sales` | List or record sales (`?month_year=YYYYMM`) |
| GET/POST | `/api/rules` | List or create partner rules |
| PUT | `/api/rules/<id>` | Update a partner rule |
| GET | `/api/dashboard` | Summary stats for the latest month |
| GET | `/api/summary/<month>` | Partner earnings breakdown for a month |
| GET | `/api/summary/months` | List all months that have sales data |
