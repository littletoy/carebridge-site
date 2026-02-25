import os

# 1. Define the FastAPI (Robot) Configuration
dockerfile_content = """FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir gspread pandas google-auth requests fastapi uvicorn
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
"""

# 2. Write the file with correct encoding
with open("Dockerfile", "w", encoding="utf-8") as f:
    f.write(dockerfile_content)
    print("✅ Backend Dockerfile created successfully.")