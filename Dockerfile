FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir gspread pandas google-auth requests fastapi uvicorn
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
