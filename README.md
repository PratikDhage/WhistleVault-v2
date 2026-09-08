# WhistleVault

WhistleVault is an anonymous whistleblowing platform built with Flask,
PostgreSQL, SQLAlchemy, Jinja templates, and vanilla JavaScript. Users can
submit reports without exposing their account identity publicly. Moderators
can review reports, community flags, AI triage results, comments, and the
associated account internally.

## Features

- Email verification with one-time passwords at signup.
- Login with username or email.
- Password recovery through expiring, single-use email reset links.
- Fast username and email availability feedback during signup.
- Anonymous posts with up to three image attachments.
- Categories for corporate fraud, workplace harassment, government and public
  sector, environmental issues, financial misconduct, safety violations,
  corruption and bribery, data privacy and security, healthcare and medical
  issues, academic and research concerns, consumer protection, human rights,
  conflicts of interest, and other reports.
- Threaded comments, replies, upvotes, and private bookmarks.
- Standard report reasons such as misleading information, copyright
  infringement, pornography, hate or abusive content, doxxing, spam, and
  threats or illegal content.
- Admin moderation dashboard with report counts, report reasons, AI flags,
  status changes, comment moderation, user deactivation, and post removal.
- Post deletion permanently removes the database record and its stored media.
- Optional Groq AI assistance for category suggestions, moderation triage,
  and privacy warnings. AI is best-effort and never blocks submissions.

## Architecture

```text
app.py                 Flask application factory and error handlers
config.py              Environment-based configuration
constants.py           Categories, report reasons, statuses, and limits
extensions.py          Flask extension instances
models.py              SQLAlchemy models
blueprints/auth/       Signup, verification, login, password reset
blueprints/posts/      Posts, comments, votes, bookmarks, reports, media
blueprints/admin/      Moderation dashboard and admin APIs
blueprints/main/       Public feed, dashboard, profile, health check
templates/             Jinja pages
static/                CSS and vanilla JavaScript
utils/ai.py            Groq integration
utils/email.py         Console or SMTP email delivery
utils/storage.py       Local or S3-compatible media storage
utils/security.py      CSRF, authentication, RBAC, and security headers
migrations/            Alembic database migrations
render.yaml            Render web-service blueprint
```

## Requirements

- Python 3.11 or newer
- PostgreSQL, such as Neon PostgreSQL
- An S3-compatible object store for durable hosted media

SQLite is not used by the application outside the explicit test configuration.
The application requires `DATABASE_URL` in development and production.

## Local development

Create a virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy the environment template and set the required values:

```bash
cp .env.example .env
```

At minimum, configure:

- `DATABASE_URL` with a PostgreSQL connection string.
- `SECRET_KEY` with a long random value.
- `ADMIN_USERNAME`.
- `ADMIN_PASSWORD_HASH` containing a Werkzeug password hash.
- `STORAGE_BACKEND=s3` and the S3 connection values for persistent media.

For local-only attachment testing, `STORAGE_BACKEND=local` may be used with
`MEDIA_FOLDER`. Local files are not suitable for a multi-instance deployment.

Apply migrations and start Flask:

```bash
flask --app app db upgrade
flask --app app run --debug
```

The application is available at `http://127.0.0.1:5000`.

With `MAIL_PROVIDER=console`, verification and password-reset messages are
written to the application log. Set `MAIL_PROVIDER=smtp` and the `MAIL_*`
variables to deliver real email.

## Environment configuration

`.env.example` contains the complete configuration reference. Important
settings include:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string; SSL is enforced for PostgreSQL URLs |
| `SECRET_KEY` | Signs sessions, CSRF tokens, and password-reset links |
| `ADMIN_USERNAME` | Admin login name |
| `ADMIN_PASSWORD_HASH` | Hashed admin password |
| `STORAGE_BACKEND` | `s3` for durable media or `local` for local testing |
| `S3_BUCKET`, `S3_REGION`, `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` | S3-compatible media storage |
| `MAIL_PROVIDER` | `console` or `smtp` |
| `GROQ_API_KEY` | Optional AI features; blank disables AI calls |
| `RATELIMIT_STORAGE_URI` | Rate-limit backend; use shared Redis when scaling instances |

For Supabase Storage, set `S3_ENDPOINT` to
`https://PROJECT_REF.storage.supabase.co/storage/v1/s3`, use the exact bucket
name in `S3_BUCKET`, and use Supabase S3 access-key credentials rather than the
Supabase database password or anon key.

## Database migrations

The schema is managed with Flask-Migrate and Alembic. Do not edit the database
manually.

```bash
flask --app app db upgrade
```

After changing a model, create and apply a migration:

```bash
flask --app app db migrate -m "describe the change"
flask --app app db upgrade
```

## Security and privacy

- Passwords use bcrypt; reset tokens are signed, expiring, hashed at rest, and
  invalidated after use.
- Mutating routes use Flask-WTF CSRF protection and rate limits are applied to
  authentication, posting, comments, reports, and AI requests.
- SQLAlchemy handles database access; no raw SQL is used by application code.
- Security headers include CSP, HSTS on HTTPS responses, frame protection,
  MIME sniffing protection, referrer restrictions, and cross-origin policies.
- Public post and comment responses never include author usernames, emails, or
  user IDs. Identity is available only in admin moderation responses.
- Uploaded filenames are replaced with random storage keys and media deletion
  removes the corresponding object from the configured storage backend.
- AI calls are optional. When enabled, post title and body text are sent to
  Groq for analysis; returned category, moderation, and privacy results are
  stored, not the provider response.

The platform provides application-level anonymity, not guaranteed anonymity
from the hosting provider or database operator. Review the threat model before
using it for highly sensitive sources.

## Health check

`GET /health` returns the service health response used by the web platform.

## License

No license has been declared for this project yet.
