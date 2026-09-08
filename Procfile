web: gunicorn app:app --workers 4 --threads 2 --timeout 60 --bind 0.0.0.0:$PORT
# NOTE: Render does NOT execute a Heroku-style "release:" line from this
# file. On Render, database migrations run either as part of the Build
# Command (works on every plan, including Free -- see render.yaml) or,
# on paid instance types only, via Render's separate "Pre-Deploy Command"
# setting. This Procfile's web: line is kept for portability to other
# Procfile-based platforms; Render itself is configured via render.yaml.
