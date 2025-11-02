# Mapalyst

A simple geospatial analysis tool with dedicated ML Backend running [Grounding Dino](https://huggingface.co/IDEA-Research/grounding-dino-base) to analyze objects from satellite imagery that we fetch from a hidden Google Maps API.

> [!WARNING]
> The undocumented Google Maps API endpoint this project uses has changed in the meantime and doesn't allow anymore to get older satellite images sadly. Hence, the images shown in the tool, even if more than one, will be (most probably) the same ones. I still think it is fun to play with and shows the potential of it :D
> So please forgive us on that one, a proper satellite imagery source [is just really expensive](https://app.skyfi.com/tasking?s=DAY&r=VERY+HIGH&aoi=POLYGON+%28%28-97.71707461991977+30.28934572636869%2C+-97.71708649530422+30.244242480134297%2C+-97.76903510469577+30.244242480134297%2C+-97.76904698008022+30.28934572636869%2C+-97.71707461991977+30.28934572636869%29%29)

## Good Examples to use

-> Most other examples probably will have problems with the coordinates as the LLM will not have accurate data on that; Mistral's Conversation/Agent API sadly [errored out while developing this](https://github.com/mistralai/client-ts/issues/141), so adding a tool wasn't possible.

- JFK Airport - "Can you analyze the current amount and trend of airplanes at JFK Airport?"
- Chrysler Car Factory Detroit - "Please analyze the current trend and amount of cars at the GM Chrysler Factory"
- Amsterdam Airport Schiphol - "Analyze the amount of airplanes at Amsterdam Schiphol Airport"

## Setup

### Prerequisites

- Docker & Docker Compose (recommended)
- Or: Python 3.11+, Node 20+, pnpm 9+

### Quick Start (Docker)

The easiest way to run the application is via Docker. Environment variables can be passed directly through your deployment platform or via a `.env` file for local development.

1. **Configure environment variables:**

   For local development, create a `.env` file in the project root:

   ```bash
   # Backend Configuration
   ANALYZER_TYPE=replicate
   REPLICATE_API_TOKEN=your_replicate_token_here
   BOX_THRESHOLD=0.2
   TEXT_THRESHOLD=0.2
   MAX_IMAGE_DIMENSION=2048
   IMAGE_QUALITY=60
   DATA_DIR=data
   PROCESSED_DATA_DIR=processed_data

   # Frontend Configuration
   NODE_ENV=production
   MISTRAL_API_KEY=your_mistral_api_key_here
   BACKEND_URL=http://backend:8000
   SKIP_ENV_VALIDATION=0
   ```

2. **Build and start:**

   ```bash
   make docker-build
   make docker-up
   ```

3. **Access the application:**

   - Frontend (Next.js): http://localhost:3000
   - Backend API (FastAPI): http://localhost:8000

4. **Stop everything:**
   ```bash
   make docker-down
   ```

### Local Development (without Docker)

**Backend:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
./start.sh
```

**Frontend:**

```bash
pnpm install
pnpm dev
```

## Configuration

All environment variables can be set via a `.env` file (for local development) or passed directly through your deployment platform.

### Backend Variables

| Variable              | Default          | Description                              |
| --------------------- | ---------------- | ---------------------------------------- |
| `ANALYZER_TYPE`       | `replicate`      | ML model backend: `replicate` or `local` |
| `REPLICATE_API_TOKEN` | -                | **Required** for Replicate API access    |
| `BOX_THRESHOLD`       | `0.2`            | Object detection confidence threshold    |
| `TEXT_THRESHOLD`      | `0.2`            | Text detection confidence threshold      |
| `MAX_IMAGE_DIMENSION` | `2048`           | Max image size for processing            |
| `IMAGE_QUALITY`       | `60`             | JPEG quality for compression (1-100)     |
| `DATA_DIR`            | `data`           | Directory for storing downloaded images  |
| `PROCESSED_DATA_DIR`  | `processed_data` | Directory for analyzed images            |

### Frontend Variables

| Variable              | Default               | Description                                          |
| --------------------- | --------------------- | ---------------------------------------------------- |
| `NODE_ENV`            | `production`          | Environment: `development`, `test`, or `production`  |
| `MISTRAL_API_KEY`     | -                     | **Required** Mistral API key for LLM features        |
| `BACKEND_URL`         | `http://backend:8000` | Backend API URL (Local dev: `http://localhost:8000`) |
| `SKIP_ENV_VALIDATION` | `0`                   | Skip env validation (useful for Docker builds)       |

<details>
<summary><b>Why these models and temperatures?</b></summary>

We use **Mistral Small** for both query extraction and findings synthesis because it offers the best balance of speed, cost, and capability for this demo, no over-engineering with reasoning models needed here.

**Temperature choices:**

- **Query Extraction (0.3)**: Structured extraction task requiring consistent coordinate/location parsing with minimal variability.
- **Findings Synthesis (0.7)**: Analytical task benefiting from slightly higher creativity for richer, more nuanced insights without going off the rails.

</details>

### Hosted Instance

A hosted demo instance is available for testing without requiring API keys:

**Demo URL:** http://mapalyst-demo.flawn.eu

> **Note:** This is a shared demo environment. For production use or extended testing, please deploy your own instance with your API credentials 🤲
