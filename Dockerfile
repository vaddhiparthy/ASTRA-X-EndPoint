FROM python:3.10-slim

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definitions first to leverage Docker layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code.  Our source resides under the
# ``ASTRA-X-Aggregator`` directory in the build context.  Copy the
# ``app`` and ``static`` folders into the working directory.
COPY ASTRA-X-Aggregator/app/ app/
COPY ASTRA-X-Aggregator/static/ static/
# Copy configuration and private folders.  These directories contain
# editable settings and secrets; see config/settings.py for details.
COPY ASTRA-X-Aggregator/config/ config/
COPY ASTRA-X-Aggregator/private/ private/

# Expose port for FastAPI
EXPOSE 12000

# Default command runs Uvicorn with the FastAPI application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "12000"]