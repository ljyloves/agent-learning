# Database migrations

Apply every migration from the backend container:

```bash
alembic upgrade head
```

For a fresh Compose database:

```bash
docker compose run --rm backend alembic upgrade head
```
