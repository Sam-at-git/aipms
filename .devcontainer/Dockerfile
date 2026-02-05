FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# Install Python 3.12 and Node.js 20
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.12 \
        python3.12-venv \
        python3.12-dev \
        python3-pip \
        build-essential \
        libffi-dev \
        libssl-dev \
        curl \
        git \
        sqlite3 \
        nano \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Set Python 3.12 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# Create user 'sam' with password and sudo privileges
RUN useradd -m -s /bin/bash sam && \
    echo "sam:Insigma+123" | chpasswd && \
    usermod -aG sudo sam && \
    echo "sam ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Install uv for user sam
USER sam
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/home/sam/.local/bin:$PATH"

# Verify installations
RUN python --version && node --version && npm --version && uv --version

# Set working directory
WORKDIR /workspace

# Expose ports
EXPOSE 3020 8020
