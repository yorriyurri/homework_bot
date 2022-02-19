import json
import logging
import os
import requests
import sys
import telegram
import time

from http import HTTPStatus
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

SEND_MESSAGE_INFO = 'Бот отправил сообщение "{message}".'
SEND_MESSAGE_ERROR = 'Сбой при отправке сообщения "{message}" в Telegram.'
API_STATUS_CODE_ERROR = 'Сбой в работе программы: Код ответа API: {code}.'
API_ERROR = 'Сбой при запросе к эндпоинту: {ENDPOINT}.'
KEY_ERROR = 'Ожидаемый ключ {key} отсутствует в ответе API.'
RESPONSE_ERROR = 'В ответе API содержится некорректный тип: {type}.'
RESPONSE_DEBUG = 'Статус домашних работ не изменился.'
PARSE_STATUS_ERROR = 'Статус {status} работы "{name}" недокументирован.'
STATUS_VERDICT = 'Изменился статус проверки работы "{name}". {verdict}'
TOKEN_ERROR = 'Отсутствует обязательная переменная окружения: {variable}.'
COMMON_ERROR = 'Сбой в работе программы: {error}.'
JSON_RESPOND_ERROR = 'Ответ API не преобразован в json.'


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат, определенный TELEGRAM_CHAT_ID."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.TelegramError:
        logger.error(SEND_MESSAGE_ERROR.format(message=message))
        raise telegram.TelegramError
    else:
        logger.info(SEND_MESSAGE_INFO.format(message=message))


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException:
        logger.error(API_ERROR.format(ENDPOINT=ENDPOINT))
        raise requests.exceptions.RequestException(
            API_ERROR.format(ENDPOINT=ENDPOINT)
        )
    else:
        if response.status_code != HTTPStatus.OK.value:
            logger.error(API_STATUS_CODE_ERROR.format(
                code=response.status_code)
            )
            raise API_STATUS_CODE_ERROR.format(
                code=response.status_code
            )
        try:
            return response.json()
        except json.decoder.JSONDecodeError:
            raise JSON_RESPOND_ERROR


def check_response(response):
    """Проверяет ответ API и возвращает список домашних работ."""
    try:
        homeworks = response['homeworks']
    except KeyError as key:
        logger.error(KEY_ERROR.format(key=key))
        raise KeyError(KEY_ERROR.format(key=key))
    else:
        if not isinstance(homeworks, list):
            logger.error(RESPONSE_ERROR.format(type(homeworks)))
            raise TypeError(RESPONSE_ERROR.format(type(homeworks)))
        if not homeworks:
            logger.debug(RESPONSE_DEBUG)
        return homeworks


def parse_status(homework):
    """Извлекает из домашней работы статус и возвращает вердикт."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    except KeyError as key:
        logger.error(KEY_ERROR.format(key=key))
        raise KeyError(KEY_ERROR.format(key=key))
    else:
        if homework_status not in HOMEWORK_STATUSES:
            logger.error(
                PARSE_STATUS_ERROR.format(
                    status=homework_status,
                    name=homework_name
                )
            )
            raise (PARSE_STATUS_ERROR.format(
                   status=homework_status,
                   name=homework_name))
        verdict = HOMEWORK_STATUSES[homework_status]
        return STATUS_VERDICT.format(name=homework_name, verdict=verdict)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    environment = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for variable, variable_value in environment.items():
        if not variable_value:
            logger.critical(TOKEN_ERROR.format(variable=variable))
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_error = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                verdict = parse_status(homeworks[0])
                send_message(bot, verdict)
        except Exception as error:
            message = COMMON_ERROR.format(error=error)
            logger.error(COMMON_ERROR.format(error=error))
            if message != last_error:
                send_message(bot, message)
                last_error = message
        else:
            current_timestamp = response['current_date']
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
