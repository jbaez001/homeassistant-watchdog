# Dockerfile
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /opt/homeassistant-watchdog

# Copy the scripts
COPY . /opt/homeassistant-watchdog

# Install dependencies
RUN pip install -r requirements.txt

# Run the Python script
CMD ["python", "homeassistant_watchdog.py"]
