FROM python:3.8.10

# Set the working directory
WORKDIR /app

# Define build arguments
ARG CONFIG_SSH_PRIVATE_KEY

# Install dependencies for SSH
RUN apt-get update && apt-get install -y openssh-client git && rm -rf /var/lib/apt/lists/*

# Setup SSH Key (Only during build)
RUN mkdir -p ~/.ssh && \
    echo "$CONFIG_SSH_PRIVATE_KEY" > ~/.ssh/id_rsa && \
    chmod 600 ~/.ssh/id_rsa && \
    ssh-keyscan github.com > ~/.ssh/known_hosts

# Copy and install dependencies
COPY ./requirements /app/requirements
RUN python -m pip install --upgrade pip && \
    pip install -r /app/requirements/run.txt && \
    pip install -r /app/requirements/deployment.txt && \
    pip install -r /app/requirements/dev.txt

# Copy the application code (submodules already cloned by GitHub Actions)
COPY . /app
