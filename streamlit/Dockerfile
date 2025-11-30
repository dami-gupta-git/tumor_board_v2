FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install tumorboard package
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Copy and install streamlit requirements
COPY streamlit/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy streamlit app
COPY streamlit/ ./streamlit/

WORKDIR /app/streamlit

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]