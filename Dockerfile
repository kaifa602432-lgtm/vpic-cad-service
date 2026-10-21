FROM python:3.11-slim

WORKDIR /app

# Cài đặt các gói hệ thống hỗ trợ biên dịch CAD
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ code vào container
COPY . .

EXPOSE 8000

# Khởi chạy dịch vụ FastAPI qua Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]