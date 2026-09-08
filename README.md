# WhistleVault

WhistleVault is an anonymous whistleblowing platform built with Flask,
PostgreSQL, SQLAlchemy, Jinja templates, and vanilla JavaScript.

Users create accounts for verification, posting, and account management, but
public posts and comments do not expose usernames, email addresses, or user
IDs. Administrators have a private moderation view for reviewing reports,
community flags, AI triage results, comments, and account identity.

## Features

### Accounts and authentication

- Signup with username and email validation.
- Live username and email availability checks.
- Email verification through one-time passwords.
- Login with username or email.
- Bcrypt password hashing.
- Forgot-password flow with signed, expiring, single-use reset links.
- Session-based user and administrator access control.

### Anonymous reports

- Required title and report body.
- Category selection with AI-assisted category suggestions.
- Up to three image attachments per post.
- Public feed and post detail views without author identity.
- Threaded comments and replies.
- Upvotes and private bookmarks.
- Community reporting with controlled reasons, including:
  - Information is not true or misleading
  - Copyright infringement or already published elsewhere
  - Pornographic or sexually explicit content
  - Hate speech or abusive content
  - Personal information or doxxing
  - Spam or advertising
  - Threats or illegal content
  - Other
- Permanent post deletion by the post owner or an administrator. Deletion
  removes the database record and stored image objects.

### Categories

The current categories are:

- Corporate Fraud
- Workplace Harassment
- Government & Public Sector
- Environmental
- Financial Misconduct
- Safety Violation
- Corruption & Bribery
- Data Privacy & Security
- Healthcare & Medical
- Academic & Research
- Consumer Protection
- Human Rights
- Conflicts of Interest
- Other

### Administration

The administrator dashboard provides:

- Active post and user statistics.
- Search by post title.
- AI-flagged and community-reported post filtering.
- Post detail moderation with internal author identity.
- Community report reasons and timestamps.
- Post status changes: Open, Under Review, and Resolved.
- Comment removal.
- User deactivation.
- Permanent post removal with media cleanup.

### Optional AI assistance

When `GROQ_API_KEY` is configured, Groq is used for:

- Category suggestions.
- Server-side moderation triage.
- Privacy warnings for sensitive information.

AI is best-effort. It does not block a post when unavailable, times out, or
returns invalid data. Names and organization names are allowed; the prompt is
intended to identify phone numbers, email addresses, addresses, government IDs,
bank or account numbers, license plates, passwords, and access tokens.

## Technology

- Python 3.11+
- Flask
- Flask-SQLAlchemy and PostgreSQL
- Flask-Migrate and Alembic
- Flask-Bcrypt
- Flask-WTF CSRF protection
- Flask-Limiter
- Gunicorn
- Jinja templates
- Tailwind CSS via CDN
- Vanilla JavaScript
- Groq API, optional
- S3-compatible object storage for hosted media

## Project structure

```text
app.py                 Flask application factory and error handlers
config.py              Environment-based configuration
constants.py           Categories, report reasons, statuses, and limits
extensions.py          Flask extension instances
models.py              SQLAlchemy models
requirements.txt       Python dependencies
Procfile               Generic Gunicorn process definition
render.yaml            Render web-service blueprint
.env.example           Environment variable template
migrations/            Alembic migration scripts
blueprints/auth/       Signup, verification, login, password reset
blueprints/posts/      Posts, comments, votes, bookmarks, reports, media
blueprints/admin/      Moderation dashboard and admin APIs
blueprints/main/       Public feed, dashboard, profile, health check
templates/             Jinja templates
static/css/            Application stylesheet
static/js/             Browser-side JavaScript
utils/ai.py            Groq integration
utils/email.py         Console, SMTP, or SendGrid API email delivery
utils/storage.py       Local or S3-compatible media storage
utils/security.py      Security headers and auth decorators
```

## Requirements

- Python 3.11 or newer.
- PostgreSQL, such as Neon PostgreSQL.
- An S3-compatible object store for persistent hosted images.
- SMTP credentials or a SendGrid API key for production email delivery.

The application does not use a local SQLite database in development or
production. SQLite is retained only for the explicit automated test
configuration.

## Local setup

Create a virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy the environment template:

```bash
cp .env.example .env
```

Set at least the following values in `.env`:

```dotenv
FLASK_ENV=development
SECRET_KEY=replace-with-a-long-random-value
DATABASE_URL=postgresql://user:password@host:5432/whistlevault
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=replace-with-a-werkzeug-password-hash
```

Generate an administrator password hash with:

```bash
./venv/bin/python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('YOUR_ADMIN_PASSWORD'))"
```

Apply migrations:

```bash
flask --app app db upgrade
```

Start the development server:

```bash
flask --app app run --debug
```

Open `http://127.0.0.1:5000` in a browser.

## Email configuration

Email delivery runs asynchronously so signup and password-reset requests do
not wait for the mail provider to respond.

### Console mode

Useful for local development:

```dotenv
MAIL_PROVIDER=console
```

OTP and reset messages are written to the Flask log. They are not sent to a
real inbox.

### SendGrid API mode

Recommended for Render because it uses HTTPS instead of SMTP ports:

```dotenv
MAIL_PROVIDER=sendgrid_api
MAIL_USERNAME=apikey
MAIL_PASSWORD=your-sendgrid-api-key
MAIL_DEFAULT_SENDER=verified-sender@example.com
MAIL_TIMEOUT_SECONDS=8
```

The sender address must be verified in SendGrid. The SendGrid API key must
have permission to send mail. Never commit it to GitHub.

### SMTP mode

For another SMTP provider:

```dotenv
MAIL_PROVIDER=smtp
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-smtp-username
MAIL_PASSWORD=your-smtp-password
MAIL_DEFAULT_SENDER=verified-sender@example.com
MAIL_TIMEOUT_SECONDS=8
```

## Supabase Storage setup

The application uses Supabase only as an S3-compatible media provider. The
application database remains PostgreSQL on Neon.

### Create the bucket

1. Open the Supabase project.
2. Open **Storage**.
3. Create a bucket, for example `whistlevault-media`.
4. Make the bucket public if using the current public-object URL behavior.

The current `S3Storage.url_for()` implementation creates URLs in this form:

```text
https://PROJECT_REF.supabase.co/storage/v1/object/public/BUCKET/OBJECT
```

A private bucket will upload successfully but images will not display through
these public URLs. To use a private bucket, the URL generation code must be
changed to generate Supabase-compatible signed URLs. The S3 API endpoint and
the public object URL intentionally use different hosts.

### Create S3 credentials

In Supabase Storage S3 settings, create or copy the S3 access key and secret
key. Do not use the Supabase database password, anon key, or service-role key
as S3 credentials.

### Local Supabase configuration

Add these values to `.env`:

```dotenv
STORAGE_BACKEND=s3
S3_BUCKET=whistlevault-media
S3_REGION=us-east-1
S3_ENDPOINT=https://PROJECT_REF.storage.supabase.co/storage/v1/s3
S3_ACCESS_KEY=your-supabase-s3-access-key
S3_SECRET_KEY=your-supabase-s3-secret-key
```

Use the exact S3 endpoint shown by Supabase for your project. Do not add a
trailing slash. The client uses S3 v4 signatures and path-style addressing,
which are required for Supabase compatibility.

### Local storage testing

For local-only testing, use:

```dotenv
STORAGE_BACKEND=local
MEDIA_FOLDER=./media
```

Local media is not durable on most hosted web services and is not suitable for
multiple application instances.

## Render deployment configuration

The repository includes `render.yaml` for the Flask web service. It defines:

- Python runtime.
- Gunicorn start command.
- Automatic database migration during build.
- `/health` health check.
- Production secure cookies.
- SendGrid API email mode.
- Supabase S3-compatible storage settings.
- Optional Groq configuration.

Create a Render Blueprint from the GitHub repository, then set the secret
values in the Render environment settings.

### Required Render variables

```text
DATABASE_URL
ADMIN_USERNAME
ADMIN_PASSWORD_HASH
MAIL_PASSWORD
MAIL_DEFAULT_SENDER
S3_BUCKET
S3_REGION
S3_ENDPOINT
S3_ACCESS_KEY
S3_SECRET_KEY
```

`SECRET_KEY` is generated by the Render blueprint. The following values are
configured by `render.yaml`:

```text
FLASK_ENV=production
SESSION_COOKIE_SECURE=true
MAIL_PROVIDER=sendgrid_api
MAIL_USERNAME=apikey
MAIL_PORT=587
MAIL_USE_TLS=true
STORAGE_BACKEND=s3
MAIL_TIMEOUT_SECONDS=8
OTP_EXPIRY_MINUTES=10
PASSWORD_RESET_EXPIRY_MINUTES=30
```

Never place secrets directly in `render.yaml` or commit `.env` to GitHub.

## Database migrations

The database schema is managed with Flask-Migrate and Alembic.

Apply existing migrations:

```bash
flask --app app db upgrade
```

After changing a model, create a migration:

```bash
flask --app app db migrate -m "describe the change"
flask --app app db upgrade
```

Always commit new files under `migrations/versions/`.

## Routes

### Public routes

- `GET /` - public feed.
- `GET /health` - health check.
- `GET /posts/<post_id>` - post detail page.
- `GET /api/feed` - feed API.

### Authentication routes

- `GET, POST /auth/signup`
- `GET, POST /auth/login`
- `POST /auth/logout`
- `GET, POST /auth/verify-otp`
- `POST /auth/resend-otp`
- `GET, POST /auth/forgot-password`
- `GET, POST /auth/reset-password/<token>`
- `GET /auth/api/check-availability`

### User post routes

- `GET, POST /posts/create`
- `GET /posts/<post_id>/api`
- `POST /posts/<post_id>/upvote`
- `POST /posts/<post_id>/bookmark`
- `POST /posts/<post_id>/report`
- `POST /posts/<post_id>/comments`
- `POST /posts/<post_id>/delete`
- `GET /posts/bookmarked`
- `GET /posts/mine`

### Admin routes

- `GET /admin/dashboard`
- `GET /admin/api/posts`
- `GET /admin/api/posts/<post_id>`
- `GET /admin/api/stats`
- `POST /admin/posts/<post_id>/status`
- `POST /admin/posts/<post_id>/delete`
- `POST /admin/comments/<comment_id>/delete`
- `POST /admin/users/<user_id>/deactivate`

## Upload troubleshooting

If the website displays:

```text
The image could not be uploaded. Check storage configuration and try again.
```

check the following:

1. `STORAGE_BACKEND=s3` is set on Render.
2. `S3_BUCKET` exactly matches the Supabase bucket name.
3. `S3_ENDPOINT` uses the S3 endpoint, for example:
   `https://PROJECT_REF.storage.supabase.co/storage/v1/s3`.
4. `S3_ACCESS_KEY` and `S3_SECRET_KEY` are Supabase S3 credentials.
5. The bucket exists and accepts uploads.
6. The bucket is public if using the current public image URL behavior.
7. The file is PNG, JPG, JPEG, GIF, or WEBP.
8. No more than three images are selected.
9. Each upload is within the application’s 8 MB request limit.
10. Render logs do not show an S3 authentication, bucket, region, or endpoint
    error.

The upload route rolls back the post transaction and removes already-uploaded
objects when one attachment fails, preventing orphaned files.

## Security and privacy

- Passwords are hashed with bcrypt.
- Reset tokens are signed, time-limited, stored only as hashes, and cleared
  after successful use.
- CSRF protection is enabled for mutating routes.
- Authentication, posting, comments, reports, and AI requests are rate-limited.
- SQLAlchemy is used for application database access.
- Security headers include CSP, HSTS on HTTPS, frame protection, MIME sniffing
  protection, referrer restrictions, and cross-origin policies.
- Public serializers omit author identity. Admin serializers expose identity
  only behind administrator access control.
- Uploaded filenames are replaced with random storage keys.
- Never commit `.env`, API keys, database URLs, SMTP passwords, or S3 secrets.
- Rotate any credential that has been exposed in chat, logs, screenshots, or
  source control.

Application-level anonymity does not prevent the hosting provider or database
operator from identifying accounts. Review the threat model before using the
platform for highly sensitive sources.

## Health check

`GET /health` returns the service health response used by Render.

## License

No license has been declared for this project yet.
