# Deployment Guide — FYP Used-Car Valuation API

**Project:** Machine Learning-Based Predictive Valuation System for Second-Hand Vehicles
**Author:** Syed Shayaan Ali Ali (STU195050)
**Module:** CMP6200 — Final Year Project, Arden University

This guide covers four deployment routes. Pick the one that matches the host environment available to you.

---

## 0. Prerequisites (all routes)

The following files must be present in the repository root:

```
src/                         # application source
frontend/                    # static SPA
wsgi.py                      # WSGI entry-point
requirements.txt             # full dev+prod dependency pin
deploy/
├── Procfile                 # Heroku/Render/Railway process spec
├── Dockerfile               # Container image
├── .dockerignore
├── requirements-production.txt
└── DEPLOYMENT.md            # (this file)
```

The trained model artefact `src/models/best_model.pkl` must exist before any route below will work. If the file is `.gitignore`'d (it is, by default), regenerate it locally with:

```bash
python -m src.models.train
```

then either commit the `.pkl` to a release branch, upload it via the host's filesystem, or bake it into the Docker image (recommended — see Route C).

---

## Route A — Arden School of Computing (SoC) shared web server

The SoC lab issues each L6 student a `~/public_html/` directory served through Apache.

1. SSH into the SoC server (credentials are in your module welcome email).
2. Create a Python virtual environment in your home directory:
   ```bash
   python3.12 -m venv ~/.venvs/fyp
   source ~/.venvs/fyp/bin/activate
   pip install -r requirements-production.txt
   ```
3. Clone or `scp` the project to `~/fyp/`.
4. Run the server behind `gunicorn`:
   ```bash
   cd ~/fyp
   gunicorn --bind 0.0.0.0:8000 --workers 2 --daemon wsgi:app
   ```
5. Ask the SoC sysadmin to add an Apache `ProxyPass` from your subpath to `localhost:8000`. The standard incantation is:
   ```apacheconf
   ProxyPass        /stu195050/  http://localhost:8000/
   ProxyPassReverse /stu195050/  http://localhost:8000/
   ```
6. Confirm `https://soc.arden.ac.uk/stu195050/health` returns `{"status":"ok","model_loaded":true}`.

> **Note:** The SoC server changes between cohorts. If the above hostname or path is wrong, use the URL printed on the module landing page in iLearn.

---

## Route B — Free PaaS (Render / Railway / Fly.io)

These hosts read the `Procfile` directly.

1. Push the repo to a public GitHub repository.
2. Create a new "Web Service" on https://render.com (or equivalent) and point it at the repo.
3. Settings:
   - **Build command:** `pip install -r deploy/requirements-production.txt`
   - **Start command:** *(leave blank — read from `Procfile`)*
   - **Environment:** `Python 3.12`
4. Deploy. Render will give you a `https://<your-app>.onrender.com` URL.

Free tiers spin down after inactivity — the first request after a quiet period takes ~10 s.

---

## Route C — Docker (any host with Docker)

```bash
# Build (from project root)
docker build -t fyp-valuation:latest -f deploy/Dockerfile .

# Run locally
docker run --rm -p 8000:8000 fyp-valuation:latest

# Tag and push (e.g. to Docker Hub)
docker tag fyp-valuation:latest <dockerhub-user>/fyp-valuation:1.0
docker push <dockerhub-user>/fyp-valuation:1.0
```

Note: the Dockerfile expects `src/models/best_model.pkl` to be present in the build context. Run `python -m src.models.train` first if it isn't.

---

## Route D — Local demo to the supervisor

For the viva or a live demo, no deployment is required:

```bash
python -m src.models.train          # one-off; produces best_model.pkl + vocab.json
python wsgi.py                       # serves on http://localhost:8000
```

Open http://localhost:8000/ in a browser. The frontend is at the root, the API at `/predict`, `/vocab`, `/health`.

---

## Smoke tests

After any deployment, run the three-call smoke test against the live URL:

```bash
BASE=https://your-deployed-url

curl $BASE/health
# => {"status":"ok","model_loaded":true}

curl $BASE/vocab | head -c 200
# => {"brands":["audi","bmw",...

curl -X POST $BASE/predict \
  -H "Content-Type: application/json" \
  -d '{"brand":"bmw","model":"3 Series","year":2019,"mileage":28000,"transmission":"Automatic","fuelType":"Diesel","engineSize":2.0}'
# => {"predicted_price":22488.0,"currency":"GBP"}
```

If all three return the expected shape, the deployment is healthy.

---

## Security & operational notes

- The `/predict` endpoint is unauthenticated by design (no PII, no transactions). For production use behind a corporate firewall, add an API key or move behind an identity proxy.
- CORS is permissive (`*`) for the academic demo. Tighten to specific origins for any real deployment.
- The model is loaded once at process start; restart the worker after any `best_model.pkl` refresh.
- The live scraper (`src/scraper/autotrader_scraper.py`) is **not** wired into the deployed API. It is a CLI tool, run on demand from the developer's laptop.
