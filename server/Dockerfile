FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV LLM_PROVIDER=mock
ENV APP_MODULE=app:app
ENV PORT=5000

# Run the application
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 4 ${APP_MODULE}"]
