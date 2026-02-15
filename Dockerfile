# Python 3.10 ကို အခြေခံထားပါတယ်
FROM python:3.10-slim

# လိုအပ်တဲ့ system tools များသွင်းခြင်း
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# လုပ်ငန်းခွင် folder သတ်မှတ်ခြင်း
WORKDIR /app

# Library များသွင်းခြင်း
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# File အားလုံးကို copy ကူးခြင်း
COPY . .

# Bot ကို run ရန်
CMD ["python", "main.py" "data.py"]
