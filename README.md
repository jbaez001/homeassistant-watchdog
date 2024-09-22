# Home Assistant Watchdog

[![Docker Image Version (latest semver)](https://img.shields.io/docker/v/fafson/homeassistant-watchdog?sort=semver)](https://hub.docker.com/r/fafson/homeassistant-watchdog)
[![Docker Image Size (latest semver)](https://img.shields.io/docker/image-size/fafson/homeassistant-watchdog?sort=semver)](https://hub.docker.com/r/fafson/homeassistant-watchdog)
[![Docker Pulls](https://img.shields.io/docker/pulls/fafson/homeassistant-watchdog)](https://hub.docker.com/r/fafson/homeassistant-watchdog)
[![Docker Stars](https://img.shields.io/docker/stars/fafson/homeassistant-watchdog)](https://hub.docker.com/r/fafson/homeassistant-watchdog)

This is a Python script that checks if entities of type "person" from homeassistant have sent an update within a given
threshold or not.

If the entity has not sent an update within the threshold, the script will print a log and also send a telegram.

## Running the Script

The script expects the following environmental variables:

- `VERIFY_SSL`: (optional) Whether to verify the SSL certificate of the Home Assistant API. Default is `true`.
- `KEEPALIVE_THRESHOLD`: (optional) The threshold for the keepalive. Default is `days=7,hours=0,minutes=0`.
- `MAX_CONCURRENT_REQUESTS`: (optional) The maximum number of concurrent requests to the Home Assistant API. Default is
  `4`.
- `HOMEASSISTANT_API_URL`: The URL of the Home Assistant API.
- `HOMEASSISTANT_API_TOKEN`: The token to authenticate with the Home Assistant API.
- `TELEGRAM_BOT_TOKEN`: (optional) The token of the Telegram bot.
- `TELEGRAM_CHAT_ID`: (optional) The chat id of the Telegram chat.
- `TELEGRAM_TIMEOUT`: (optional) The timeout (in seconds) for the Telegram requests. Default is `60`.

Alternatively these variables can be defined in the `.env` file and then mounted over at
`/opt/homeassistant-watchdog/.env`.
If no `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` are provided, the script will not send any messages and merely log the
output.

### Console

```bash
# Install requirements
pip install -r requirements.txt

# Run script (assumes that either the .env file exists
# or that the environmental variables have been set)
python homeassistant_watchdog.py
```

### Docker

```bash
# Using .env file
docker run --rm  \
    -v $(pwd)/.env:/opt/homeassistant-watchdog/.env \
    --restart no \
    fafson/homeassistant-watchdog:latest

# Using environmental variables
docker run --rm  \
    -e VERIFY_SSL=false \
    -e KEEPALIVE_THRESHOLD='days=1,hours=0,minutes=0' \
    -e HOMEASSISTANT_API_URL='https://yourhomeassistant.com/api' \
    -e HOMEASSISTANT_API_TOKEN='your_homeassistant_api_token' \
    -e TELEGRAM_BOT_TOKEN='your_telegram_bot_token' \
    -e TELEGRAM_CHAT_ID='your_telegram_chat_id' \
    --restart no \
    fafson/homeassistant-watchdog:latest
```

### Docker Compose

```yaml
# docker-compose.yml - Using .env file
services:
  homeassistant-watchdog:
    image: fafson/homeassistant-watchdog:latest
    restart: no
    volumes:
      - .env:/opt/homeassistant-watchdog/.env
```

```yaml
# docker-compose.yml - Using environmental variables
services:
  homeassistant-watchdog:
    image: fafson/homeassistant-watchdog:latest
    restart: no
    environment:
      - VERIFY_SSL=false
      - KEEPALIVE_THRESHOLD=days=1,hours=0,minutes=0
      - HOMEASSISTANT_API_URL=https://yourhomeassistant.com/api
      - HOMEASSISTANT_API_TOKEN=your_homeassistant_api_token
      - TELEGRAM_BOT_TOKEN=your_telegram_bot_token
      - TELEGRAM_CHAT_ID='your_telegram_chat_id'
```

### Helm

```bash
# copy the values.yaml file to my-values.yaml
# please edit the my-values.yaml file to match your configuration
cp ./chart/values.yaml my-values.yaml

# install the helm chart
helm install -n default -f my-values.yaml my-homeassistant-watchdog ./chart
```

## Building Custom Image with Self-Signed Certificate

```bash
# Define the custom repository
CUSTOM_REPOSITORY=registry.local/user/homeassistant-watchdog

# Using docker to build single-arch image
docker build -t ${CUSTOM_REPOSITORY}:custom .
docker push ${CUSTOM_REPOSITORY}:custom

# Using BuildKit to build multi-arch image
docker buildx create --use --name homeassistant-watchdog

# Enter the buildx builder; you may need to replace "buildx_buildkit_homeassistant-watchdog0" with the correct name
docker exec -it buildx_buildkit_homeassistant-watchdog0 /bin/sh

# Copy the certificate to the builder
scp username@yourserver:/path/to/ca.crt /usr/local/share/ca-certificates/ca.crt

# Update the certificates
update-ca-certificates

# Exit the builder
exit

# Restart the builder; you may need to replace "buildx_buildkit_homeassistant-watchdog0" with the correct name
docker restart buildx_buildkit_homeassistant-watchdog0

# Build the image
docker buildx build --platform linux/amd64,linux/arm64,linux/386,linux/ppc64le,linux/s390x \
    --output "type=image,push=true" \
    --tag ${CUSTOM_REPOSITORY}:custom  \
    --builder homeassistant-watchdog .

# Remove the buildx builder (if no longer needed)
docker buildx rm homeassistant-watchdog
```
