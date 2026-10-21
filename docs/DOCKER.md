# Running YomiKoe in Docker

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
| `yomikoe_data` → `/data` | named volume (`YOMIKOE_DATA_DIR=/data`) | SQLite database, uploaded PDFs, audio cache. Upload PDFs through the page or `curl -F`; export the library with `docker compose cp api:/data ./data-export`. A bind mount (`./data:/data`) is an option on Linux hosts; the failure first seen with a bind mount on Colima was the same fork race (fork-inherited SQLite connection, fixed by the spawn start method, D9 amendment, commit 016616b, `_agent/results/596`), not the filesystem; the named volume stays the default for portability. |
| `hf_home` → `/hf_home` | named volume (`HF_HOME=/hf_home`) | Hugging Face downloads (the Kokoro-82M model). Survives rebuilds; `docker compose down -v` deletes it. |

## First run

The first time the Kokoro backend loads, the server downloads `hexgrad/Kokoro-82M` at the revision
pinned in `api/yomikoe/settings.py` (`YOMIKOE_KOKORO_REVISION` in `docker-compose.yml`) into the
`hf_home` volume. This needs network access and takes a minute or two; later starts reuse the volume
and run offline. The image build itself also needs network (npm and pip packages, CPU-only PyTorch).

## Settings

Environment variables in `docker-compose.yml`: `YOMIKOE_TTS_BACKEND` (`kokoro`, or `fake` for a
silent test backend), `YOMIKOE_KOKORO_REVISION`, `YOMIKOE_AUDIO_FORMAT` (`opus` default: audio is
served as Ogg Opus, and the image installs the `opus` extra; set `YOMIKOE_AUDIO_FORMAT=wav` to opt out).
