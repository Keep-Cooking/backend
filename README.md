# Keep Cooking Backend Configuration

---

## Services

* **api**
  Image: `keep-cooking-api:latest`
  Built from: `docker/Dockerfile.api` (Python 3.13 slim)
  Exposes: container port `8000` (HTTP or HTTPS if enabled)

* **frontend**
  Image: `keep-cooking-frontend:latest`
  Built from: `docker/Dockerfile.frontend` (Node 25 alpine)
  Exposes: container port `3000` (served by `npm run dev`)

---

## Configuration

### `api` config

| Variable             | Type            |                 Default | Purpose                                                                                 |
| -------------------- | --------------- | ----------------------: | --------------------------------------------------------------------------------------- |
| `API_HOST`           | string          |               `0.0.0.0` | Address the API binds to in the container.                                              |
| `API_PORT`           | number          |                  `8000` | Port the API listens on **inside** the container.                                       |
| `FLASK_STAGE`        | `dev \| prod`   |                  `dev` | Switch between development and production environments.                        |
| `CORS_ALLOW_ORIGINS` | comma-sep list  |                    `""` | Allowed origins for cross-origin requests. Takes precedence over `FRONTEND_URL` if set. |
| `FRONTEND_URL`       | string (URL)    | `http://localhost:3000` | Fallback origin if `CORS_ALLOW_ORIGINS` is empty.                                       |
| `SSL_ENABLE`         | `true \| false` |                 `false` | Enable HTTPS served **by the api container itself**.                                    |
| `SSL_CERT_PATH`      | string (path)   |  `/certs/fullchain.pem` | Cert path **inside** the container. Requires a bind-mount.                              |
| `SSL_KEY_PATH`       | string (path)   |    `/certs/privkey.pem` | Key path **inside** the container. Requires a bind-mount.                               |
| `JWT_SECRET`       | string (optional)   |    Random key | JWT secret key, uses random key if unused. Specify to prevent invalid tokens on server reset. |

**Ports mapping (host ↔ container)**
Defined in `docker-compose.yml` under `services.api.ports`:

* **HTTP mode** (`SSL_ENABLE: "false"`):
  `- "8000:8000"` → host `http://localhost:8000`
* **HTTPS mode** (`SSL_ENABLE: "true"`):
  Replace with `- "443:8000"` to expose **HTTPS** on host `https://localhost`

**If enabling HTTPS, also bind-mount the certs with:**
```yaml
volumes:
    - /host/path/fullchain.pem:/certs/fullchain.pem:ro
    - /host/path/privkey.pem:/certs/privkey.pem:ro
```
---

### `frontend` config

| Key                   | Where     | Default                                    | Purpose                                                                   |
| --------------------- | --------- | ------------------------------------------ | ------------------------------------------------------------------------- |
| `LOCAL_FRONTEND_REPO` | build arg | `https://github.com/Keep-Cooking/frontend` | Git repo to clone for the frontend.                                            |
| `API_BASE`       | build arg | `http://localhost:8000/api`                | API base URL baked at build time. |
| `FRONTEND_PORT`       | build arg       | `3000`                                     | Port the app's `npm run prod` binds to **inside** the container.          |

## Deploying

### API Only (frontend hosted on GitHub Pages)

```bash
docker compose up -d --build api
```

### API + Frontend (frontend hosted locally)

```bash
docker compose up -d --build
```

### Tear Down

Stop and remove all containers, networks, and volumes created by this compose file:

```bash
docker compose down
```

### Testing

Run `pytest -q` in the package root directory to test the backend. Tests are located in `src/tests/`