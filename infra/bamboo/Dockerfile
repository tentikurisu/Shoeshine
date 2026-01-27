# Bamboo CI image for Shoeshine
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    unzip \
    wget \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Terraform 1.7.0
RUN wget -q https://releases.hashicorp.com/terraform/1.7.0/terraform_1.7.0_linux_amd64.zip && \
    unzip -q terraform_1.7.0_linux_amd64.zip -d /usr/local/bin && \
    rm terraform_1.7.0_linux_amd64.zip

# Install AWS CLI v2
RUN curl -sL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o awscliv2.zip && \
    unzip -q awscliv2.zip -d /opt && \
    /opt/aws/install --bin-dir /usr/local/bin && \
    rm -rf awscliv2.zip

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default command for Bamboo
CMD ["bash"]
