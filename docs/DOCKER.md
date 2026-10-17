# Running HearNarro in Docker

One image, one service (`api`): the server answers the API and serves the built web app at `/`
(Technical Design D21, D30; PRD "Packaging"). It needs a container runtime with Compose v2.

## Build and run

From the repository root:

```sh
docker compose up --build        # build the image and start the server (Ctrl-C stops it)
```

Then open <http://localhost:8765/> in the browser. Check the API with
`curl -i http://localhost:8765/documents` (expect `200`).

The default host port is 8765. To use another host port, create an optional, git-ignored
`docker-compose.override.yml` next to `docker-compose.yml`, for example:

```yaml
services:
  api:
    ports: !override
      - "8766:8765"
```

To run it in the background instead: `docker compose up --build -d`, and `docker compose down` to stop.

## Volumes

| Mount | Kind | Holds |
| --- | --- | --- |
| `./data` → `/data` | bind mount (`HEARNARRO_DATA_DIR=/data`) | SQLite database, uploaded PDFs, audio cache. Created next to `docker-compose.yml` on first run. |
| `hf_home` → `/hf_home` | named volume (`HF_HOME=/hf_home`) | Hugging Face downloads (the Kokoro-82M model). Survives rebuilds; `docker compose down -v` deletes it. |

## First run

The first time the Kokoro backend loads, the server downloads `hexgrad/Kokoro-82M` at the revision
pinned in `api/hearnarro/settings.py` (`HEARNARRO_KOKORO_REVISION` in `docker-compose.yml`) into the
`hf_home` volume. This needs network access and takes a minute or two; later starts reuse the volume
and run offline. The image build itself also needs network (npm and pip packages, CPU-only PyTorch).

## Settings

Environment variables in `docker-compose.yml`: `HEARNARRO_TTS_BACKEND` (`kokoro`, or `fake` for a
silent test backend), `HEARNARRO_KOKORO_REVISION`, `HEARNARRO_AUDIO_FORMAT` (`opus` default: audio is
served as Ogg Opus, and the image installs the `opus` extra; set `HEARNARRO_AUDIO_FORMAT=wav` to opt out).
