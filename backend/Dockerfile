# Dockerfile
FROM python:3.11-slim

# Prevent Python from writing .pyc files & enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libnss3 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    librsvg2-bin \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency list
COPY requirements_prod.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements_prod.txt

# Copy app code
COPY . .

# Make startup scripts executable
RUN chmod +x startup_checks.sh docker-entrypoint.sh

EXPOSE 8016

# Use the entrypoint script to run startup checks and start the app
CMD ["./docker-entrypoint.sh"]
