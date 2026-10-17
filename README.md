# Atlas Quest

Atlas Quest is a geography-trivia game served by Django. It keeps the original responsive game interface, draws each round from a separate 12,288-entry question pool, and stores each player's progress in a local SQLite database.

## Start the game

Python 3.9 or newer is required. From the project directory:

```bash
source ./setup.sh
python manage.py migrate
python manage.py runserver
```

`setup.sh` creates `.venv`, installs `requirements.txt`, and activates the environment in the current terminal. Source it (rather than running `./setup.sh`) so activation remains in your shell. Open <http://127.0.0.1:8000/> while the Django development server is running. Stop the server with Ctrl+C. The database file (`db.sqlite3`) and the browser's session cookie keep progress available across server restarts in that browser. A different browser session has its own player progress. Use **Reset** to clear the current player's progress.

Open the game at the Django URL above, not by opening `index.html` directly. The game needs Django to serve its API and static client files; opening the HTML as a local file will not connect to the game server.

For a LAN-accessible development server, run `python manage.py runserver 0.0.0.0:8000` and add the host address to `ALLOWED_HOSTS` in `atlasquest/settings.py`. The included settings and secret key are for local development, not public deployment.

## Deploying to Vercel

Vercel detects this Django project from `manage.py` and its WSGI setting. `.python-version` pins the Vercel runtime to Python 3.12, which is supported by the project's Django 4.2 dependency. `vercel.json` intentionally does not declare a `functions` pattern: Vercel's Django integration creates the application function itself, and a custom pattern for `atlasquest/wsgi.py` does not match an `api/` function. Before deploying, configure these environment variables for the Vercel project:

- `DJANGO_SECRET_KEY`: a long, random secret value. Generate one with `python -c 'import secrets; print(secrets.token_urlsafe(50))'`.
- `DATABASE_URL`: the connection URL from a persistent PostgreSQL provider/integration. `POSTGRES_URL` is also accepted. Vercel's build command runs `scripts/vercel_build.py` to apply database migrations, so the database URL must be available to the deployment build as well as the function.
- `DJANGO_ALLOWED_HOSTS` (optional): comma-separated custom host names if you use a domain outside `*.vercel.app`.

The preview and production deployments should use their intended database environment variables. SQLite is only the local-development default: serverless Vercel filesystems are not durable, so a SQLite file cannot reliably preserve player progress there. If the Vercel page shows an API error, inspect the Vercel function/build logs; the game now includes the HTTP status and a short sanitized response detail when an API responds with HTML instead of JSON.

## Gameplay

- There are eight themed destinations. Each round has five randomly selected questions and requires four correct answers to clear.
- Every correct answer awards 100 points. Current and best consecutive-answer streaks are tracked.
- One hint per round removes two incorrect choices without a score penalty.
- Clearing a level unlocks the next destination. Unlocked destinations are replayable; missed rounds can be retried with a fresh selection.
- The browser sends answer selections to Django; the correct answer and explanation are not included in the question-delivery response.

## Question pool and editing

- `data/facts.json` is the authored source set: 64 underlying geography facts, eight per level.
- `data/questions.json` is the separate, ready-to-serve pool of 12,288 question instances. Each fact has eight prompt framings and all 24 answer-choice orders, so rounds can select different question variants while avoiding duplicate facts in the same round.
- To edit or add facts, update `data/facts.json`, then rebuild the pool with:

  ```bash
  python scripts/generate_question_bank.py
  ```

  Each fact uses `id`, `level` (zero-based), `name`, `region`, `icon`, `prompt`, four `options`, `answer_index` for a single correct option or `answer_indices` for multiple correct options, and `explanation`. Answer indices are zero-based. Keep at least five facts in each level so a round can be generated without repeating a fact.
- `index.html` contains the game template and `static/game.js` contains its interactive client. `game/views.py` implements the JSON API; `game/models.py` stores player progress.

The 12,288 pool entries are answer-order/prompt variants of the 64 authored facts, not 12,288 independent geographic facts. This keeps the pool large and varied without inventing unverified trivia.

## Database and API

Player progress is associated with Django's browser session and persisted in the `PlayerProgress` SQLite table. Django's session table stores the active round. The database remains local to the project in `db.sqlite3`; do not delete it if progress should be retained.

- `GET /api/progress/` returns the current player's stats and level map.
- `GET /api/round/?level=0` starts a round for an unlocked level.
- `POST /api/answer/` validates and scores an answer for the active round.
- `POST /api/reset/` resets the current player's progress.

## Checks

Run the automated tests with:

```bash
python manage.py test
```

The tests cover the question pool size and uniqueness, round selection, locked-level access, answer scoring, level unlocking, duplicate answer rejection, and progress reset.
# Atlas-Quest
