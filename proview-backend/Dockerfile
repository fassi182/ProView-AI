# 1. Use a lightweight base image
FROM python:3.11-slim

# 2. Set working directory
WORKDIR /app

# 3. Copy dependencies and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy your app code
COPY . .

# 5. Expose the port FastAPI uses
EXPOSE 8000

# 6. Run the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]