FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y \
    socat entr  gcc musl-dev libffi-dev python3-dev \
    curl libcurl4-openssl-dev

# Set the working directory
WORKDIR /app

COPY requirements.txt /app

# Install Python dependencies
RUN pip install --upgrade setuptools wheel && \
    pip install -r requirements.txt

COPY . /app

# run entrypoint.sh script
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
