FROM python:3.11-slim

# منع مشاكل التفاعل
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# system dependencies (important for scraping + lxml + playwright later)
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    git \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# install python deps first (for caching)
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Hugging Face + datasets layer (explicit ensure)
RUN pip install huggingface_hub datasets

# copy project
COPY . .

# default shell for development
CMD ["bash"]
