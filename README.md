# Atlas Quest

Atlas Quest is a geography-trivia game served by Django. It keeps the original responsive game interface, draws each round from a 6,400-fact question bank, and stores each player's progress in a local SQLite database.

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

Vercel detects this Django project from `manage.py` and its WSGI setting. `pyproject.toml` and `.python-version` pin the Vercel Python runtime to 3.12, which is supported by the project's Django 4.2 dependency. If the build still selects another Python version, set Python Version to 3.12 in the Vercel project's settings as well. `vercel.json` intentionally does not declare a `functions` pattern: Vercel's Django integration creates the application function itself, and a custom pattern for `atlasquest/wsgi.py` does not match an `api/` function. Before deploying, configure these environment variables for the Vercel project:

- `DJANGO_SECRET_KEY`: a long, random secret value. Generate one with `python -c 'import secrets; print(secrets.token_urlsafe(50))'`.
- `DATABASE_URL`: the connection URL from a persistent PostgreSQL provider/integration. `POSTGRES_URL` is also accepted. Vercel's build command runs `scripts/vercel_build.py` to apply database migrations, so the database URL must be available to the deployment build as well as the function.
- `DJANGO_ALLOWED_HOSTS` (optional): comma-separated custom host names if you use a domain outside `*.vercel.app`.

The preview and production deployments should use their intended database environment variables. SQLite is only the local-development default: serverless Vercel filesystems are not durable, so a SQLite file cannot reliably preserve player progress there. If the Vercel page shows an API error, inspect the Vercel function/build logs; the game now includes the HTTP status and a short sanitized response detail when an API responds with HTML instead of JSON.

## Gameplay

- The first screen introduces the expedition and its five-question quiz format. Choose **Begin your journey** to open the rotating globe and level selector.
- The home screen is an interactive, mouse- and touch-rotatable globe. Select a lit continent pin or its accessible region button to open that continent's quiz.
- The globe uses 1:50-million-scale Natural Earth coastline, lake, and international-boundary geometry, rendered on an orthographic projection with graticule lines. Natural Earth map data is public domain; the bundled geometry is in `static/world-land.json`, `static/world-lakes.json`, and `static/world-borders.json`.
- The campaign progresses through Africa, Asia, Europe, North America, South America, Oceania, and Antarctica. Each quiz has five randomly selected questions and requires four correct answers to unlock the next continent.
- The globe and level list distinguish ready, attempted, passed, and perfect destinations. A best result of 4/5 is amber; a perfect 5/5 is green. Best results persist and passed quizzes can be replayed to earn a perfect score.
- Clearing all seven continents unlocks the World Challenge. Cleared quizzes can be replayed, and missed rounds can be retried with a fresh selection.
- Existing saves keep their score and streak stats, while their old theme-based unlocks restart at Africa so continent progress stays accurate.
- Every correct answer awards 100 points. Current and best consecutive-answer streaks are tracked.
- One hint per round removes two incorrect choices without a score penalty.
- The browser sends answer selections to Django; the correct answer and explanation are not included in the question-delivery response.

## Question pool and editing

- `data/facts.json` is the fact source: 64 authored geography facts plus 6,336 distinct populated-place facts from GeoNames, for 6,400 total (100 times the original bank). The six inhabited-continent quizzes have 800 facts each, Antarctica retains its eight authored facts, and the World Challenge has 1,592.
- `data/questions.json` is the compact runtime bank with one entry per distinct fact. Prompt framing and answer order are randomized when a round starts, avoiding a large pre-generated variants file while keeping five different facts per round.
- To refresh the GeoNames facts, run:

  ```bash
  python scripts/import_geonames_questions.py
  ```

- The importer downloads GeoNames `cities5000.zip`, `countryInfo.txt`, and `admin1CodesASCII.txt` from the [GeoNames export dump](https://download.geonames.org/export/dump/). GeoNames data is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); the imported facts retain their GeoNames IDs and source labels. The imported choices use the correct country and plausible country distractors from the same continent, or from around the world in the World Challenge.
- To edit facts, update `data/facts.json`; then rebuild the runtime bank with:

  ```bash
  python scripts/generate_question_bank.py
  ```

  Each fact uses `id`, `level` (zero-based), `continent`, `name`, `region`, `icon`, `prompt`, four `options`, `answer_index` for a single correct option or `answer_indices` for multiple correct options, and `explanation`. Answer indices are zero-based. Keep at least five facts in each level so a round can be generated without repeating a fact.
- `index.html` contains the game template and `static/game.js` contains its interactive client. `game/views.py` implements the JSON API; `game/models.py` stores player progress.

GeoNames is a geographic database of populated places and administrative regions. The imported questions ask players to identify the country containing a named place; they supplement, rather than replace, the authored landmark, physical-geography, and Antarctica questions.

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

The tests cover the 6,400 distinct facts and their level distribution, round selection, locked-level access, answer scoring, continent and world challenge unlocking, duplicate answer rejection, and progress reset.
# Atlas-Quest
