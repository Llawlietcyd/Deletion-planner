FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5001

# Set environment variables
ENV LLM_PROVIDER=mock
ENV PORT=5001

# Run the application with uvicorn (FastAPI)
CMD ["sh", "-c", "uvicorn api_v2.main:app --host 0.0.0.0 --port ${PORT} --workers 4"]
