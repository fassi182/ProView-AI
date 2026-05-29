# 1. Use an official lightweight Python image
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Install system-level dependencies required for some AI/ML libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# 5. Install the Python dependencies
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# 6. Copy the rest of your backend code into the container
COPY . .

# 7. Expose the port that FastAPI will run on
EXPOSE 8000

# 8. Define the command to start your application
# Ensure 'main:app' matches your filename 'main.py' and your FastAPI instance 'app'
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]