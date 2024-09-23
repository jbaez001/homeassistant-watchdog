"""HomeAssistantWatchdog"""
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import requests
import urllib3
from dotenv import load_dotenv
from homeassistant_api import Client, EndpointNotFoundError, Entity

# load environment variables
load_dotenv()

# environment variables
ENV_SYSLOG_FILE = os.getenv('SYSLOG_FILE', 'homeassistant_watchdog.log')
ENV_VERIFY_SSL = os.getenv('VERIFY_SSL', 'true').lower() == 'true'
ENV_KEEPALIVE_THRESHOLD = os.getenv('KEEPALIVE_THRESHOLD', 'days=30,hours=0,minutes=0')
ENV_MAX_CONCURRENT_REQUESTS = int(os.getenv('MAX_CONCURRENT_REQUESTS', '4'))

ENV_HOMEASSISTANT_API_URL = os.getenv('HOMEASSISTANT_API_URL')
ENV_HOMEASSISTANT_API_TOKEN = os.getenv('HOMEASSISTANT_API_TOKEN')
ENV_HOMEASSISTANT_ENTITY_ID = os.getenv('HOMEASSISTANT_ENTITY_ID')

ENV_TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ENV_TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ENV_TELEGRAM_TIMEOUT = int(os.getenv('TELEGRAM_TIMEOUT', '60'))

if ENV_VERIFY_SSL is False:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# global variables
PATTERN_KEEPALIVE_THRESHOLD = re.compile(r'days=(\d+),hours=(\d+),minutes=(\d+)')
KEEP_ALIVE_LAST_UPDATE_THRESHOLD = timedelta(days=30)
TELEGRAM_ENABLED = False


def setup_logger(level: int = logging.WARNING) -> None:
    """Setup the logger

    Args:
        level (int, optional): logging level. Defaults to logging.WARNING.
    """
    log_format = logging.Formatter('[%(asctime)s - %(pathname)s:%(lineno)s - %(funcName)s - %(levelname)s] %(message)s')
    logging.basicConfig(filename=ENV_SYSLOG_FILE,
                        format='[%(asctime)s - %(pathname)s:%(lineno)s - %(funcName)s - %(levelname)s] %(message)s',
                        encoding='utf-8',
                        level=level)

    console_logger = logging.StreamHandler()
    console_logger.setFormatter(log_format)
    logging.getLogger().addHandler(console_logger)


def send_telegram_message(message: str,
                          telegram_bot_token: str = ENV_TELEGRAM_BOT_TOKEN,
                          telegram_chat_id: str = ENV_TELEGRAM_CHAT_ID,
                          telegram_timeout: int = ENV_TELEGRAM_TIMEOUT) -> requests.Response | None:
    """send a message to Telegram

    Args:
        message (str): message to send
        telegram_bot_token (str, optional): Telegram bot token. Defaults to ENV_TELEGRAM_BOT_TOKEN.
        telegram_chat_id (str, optional): Telegram chat id. Defaults to ENV_TELEGRAM_CHAT_ID.
        telegram_timeout (int, optional): Telegram timeout. Defaults to ENV_TELEGRAM_TIMEOUT

    Returns:
        requests.Response | None: response object
    """

    if not TELEGRAM_ENABLED:
        return None

    url = f'https://api.telegram.org/bot{telegram_bot_token}/' + \
          f'sendMessage?chat_id={telegram_chat_id}&text={message}'

    response = requests.get(url, timeout=telegram_timeout)
    if response.status_code != 200:
        logging.error('Failed to send message to Telegram: %s', x.text)
        return

    return response


def check_variables():
    """Check if required environment variables are set

    Raises:
        ValueError: if required environment variables are not set
    """

    # pylint: disable=global-statement
    global KEEP_ALIVE_LAST_UPDATE_THRESHOLD
    global TELEGRAM_ENABLED

    if ENV_HOMEASSISTANT_API_URL is None:
        raise ValueError('HOMEASSISTANT_API_URL is not set')

    if ENV_HOMEASSISTANT_API_TOKEN is None:
        raise ValueError('HOMEASSISTANT_API_TOKEN is not set')

    if ENV_HOMEASSISTANT_ENTITY_ID is None:
        logging.info('HOMEASSISTANT_ENTITY_ID is not set; will check all entities of kind "person"')

    if ENV_TELEGRAM_BOT_TOKEN is not None and ENV_TELEGRAM_CHAT_ID is not None:
        TELEGRAM_ENABLED = True

    # parse the keepalive threshold
    match = PATTERN_KEEPALIVE_THRESHOLD.match(ENV_KEEPALIVE_THRESHOLD)
    if match is None:
        print('KEEPALIVE_THRESHOLD:', ENV_KEEPALIVE_THRESHOLD)
        raise ValueError('Invalid KEEPALIVE_THRESHOLD format')

    KEEP_ALIVE_LAST_UPDATE_THRESHOLD = timedelta(
        days=int(match.group(1)),
        hours=int(match.group(2)),
        minutes=int(match.group(3))
    )

    logging.info('KEEPALIVE_THRESHOLD set to: %s', KEEP_ALIVE_LAST_UPDATE_THRESHOLD)


def format_timedelta(td: timedelta) -> str:
    """Format a timedelta object

    Args:
        td (timedelta): timedelta object

    Returns:
        str: formatted timedelta string
    """

    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} min{'s' if minutes > 1 else ''}")
    if seconds > 0:
        parts.append(f"{seconds} sec{'s' if seconds > 1 else ''}")

    return ' '.join(parts)


async def get_homeassistant_async_client() -> Client:
    """Get a Home Assistant client object

    Returns:
        Client: Home Assistant client object (async)
    """
    return Client(
        ENV_HOMEASSISTANT_API_URL,
        ENV_HOMEASSISTANT_API_TOKEN,
        verify_ssl=ENV_VERIFY_SSL,
        use_async=True,
        async_cache_session=None,
    )


async def check_if_entity_last_updated_within_threshold(client: Client, entity_id: str,
                                                        last_update_threshold: timedelta) -> bool:
    """Check if an entity has been updated within a certain threshold

    Args:
        client (Client): client object
        entity_id (str): entity id to check
        last_update_threshold (timedelta): time delta to check

    Raises:
        ValueError: if entity not found
        ValueError: if last update not found

    Returns:
        bool: True if entity has been updated within the threshold, False otherwise
    """

    try:
        entity = await client.async_get_entity(entity_id=entity_id)
        if entity is None:
            raise ValueError('Entity not found')

    except EndpointNotFoundError as exc:
        logging.error('Entity %s not found', entity_id)
        raise ValueError('Entity not found') from exc

    current_time = datetime.now(timezone.utc)
    last_update = entity.state.last_updated
    if last_update is None:
        raise ValueError('Last update not found') if last_update is None else None

    within_threshold = last_update >= (current_time - last_update_threshold)

    logging.info('[%s] Current time: %s, Last update: %s, Within thresholds: %s',
                 entity_id, current_time, last_update, within_threshold)

    if within_threshold is False:
        # pylint: disable=line-too-long
        length_of_time = format_timedelta(current_time - last_update)
        _msg = f'{entity.slug} has not sent any updates for {length_of_time}. Last update was on {last_update},' + \
               f' which exceeds the threshold of {KEEP_ALIVE_LAST_UPDATE_THRESHOLD}.'

        logging.critical(_msg)
        if TELEGRAM_ENABLED:
            send_telegram_message(_msg)

    return within_threshold


async def get_entities_to_check(client: Client, entity_kind: str) -> list[Entity] | None:
    """Get a list of entities to check"""

    results = await client.async_get_entities()

    if entity_kind in results:
        return list(results['person'].entities.values())

    return None


async def check_entities():
    """Check entities
    """

    client = await get_homeassistant_async_client()

    entities_to_check: list[str] | list[Entity] | None = ENV_HOMEASSISTANT_ENTITY_ID.split(
        ',') if ENV_HOMEASSISTANT_ENTITY_ID is not None else await get_entities_to_check(client, 'person')

    if entities_to_check is None:
        logging.info('No entities to check')
        return

    entity_ids_to_check = [entity if isinstance(entity, str) else entity.entity_id for entity in entities_to_check]

    logging.info('checking the following entities: %s', entity_ids_to_check)

    sem = asyncio.Semaphore(ENV_MAX_CONCURRENT_REQUESTS)

    async def _check_entity(entity_id: str):
        async with sem:
            try:
                await check_if_entity_last_updated_within_threshold(
                    client, entity_id, KEEP_ALIVE_LAST_UPDATE_THRESHOLD)

            except ValueError as exc:
                logging.error('Error checking entity %s: %s', entity_id, exc)
                return

    # run the tasks concurrently
    tasks = [_check_entity(entity) for entity in entity_ids_to_check]

    # wait for all tasks to complete
    await asyncio.gather(*tasks)

    # close the async cache session
    await client.async_cache_session.close()


async def main():
    """main entrypoint
    """

    # setup logger
    setup_logger(logging.INFO)

    # check if required environment variables are set
    check_variables()

    # block until all entities have been checked
    await check_entities()


if __name__ == '__main__':
    # run the main function
    asyncio.run(main())
