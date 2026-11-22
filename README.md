# TrackGrow MVP

A starter Flask application for a Telegram campaign landing-page and click-tracking SaaS.

## Included
- Client registration and login
- Client campaign dashboard
- Basic campaign landing page creation
- Unique campaign tracking links
- Click event logging and UTM source capture
- Health endpoint at `/health`

## Not yet included
Telegram bot membership verification, Meta Conversions API, billing, admin moderation, production-grade database migrations, and persistent production storage. The dashboard deliberately does not count clicks as verified joins.

## Run locally
1. `python -m venv .venv`
2. Activate the environment.
3. `pip install -r requirements.txt`
4. `python app.py`
5. Open `http://127.0.0.1:5000`

For deployment, set a strong `SECRET_KEY`. SQLite on many free hosting plans may be ephemeral; use a persistent PostgreSQL database before relying on customer data.
