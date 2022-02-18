import logging
import os
import sys
import telegram
import requests
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
        logger.error(f'Сбой при отправке сообщения "{message}" в Telegram.')
    else:
        logger.info(f'Бот отправил сообщение "{message}"')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException:
        logger.error(
            f'Сбой при запросе к эндпоинту: {ENDPOINT}'
        )
    else:
        if response.status_code != HTTPStatus.OK.value:
            logger.error(
                f'Сбой в работе программы: '
                f'Эндпоинт {ENDPOINT} недоступен. '
                f'Код ответа API: {response.status_code}'
            )
            raise requests.exceptions.RequestException(
                'Статус код ответа API не равен 200'
            )
        return response.json()


def check_response(response):
    """Проверяет ответ API и возвращает список домашних работ."""
    try:
        homeworks = response['homeworks']
    except KeyError as key:
        logger.error(f'Ожидаемый ключ {key} отсутствует в ответе API')
        raise KeyError(f'Ключ {key} отсутствует в ответе API.')
    else:
        if not isinstance(homeworks, list):
            logger.error(
                f'В ответе API содержится некорректный тип: {type(homeworks)}'
            )
            raise TypeError(
                f'В ответе API содержится некорректный тип: {type(homeworks)}'
            )
        if not homeworks:
            logger.debug('Статус домашних работ не изменился.')
        return homeworks


def parse_status(homework):
    """Извлекает из домашней работы статус и возвращает вердикт."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    except KeyError as key:
        logger.error(f'Ожидаемый ключ {key} отсутствует в ответе API.')
        raise KeyError(f'Ключ {key} отсутствует в ответе API.')
    else:
        if homework_status not in HOMEWORK_STATUSES:
            logger.error(
                f'Статус {homework_status} работы '
                f'"{homework_name}" недокументирован.'
            )
        verdict = HOMEWORK_STATUSES[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    environment = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for variable, variable_value in environment.items():
        if not variable_value:
            logger.critical(
                f'Отсутствует обязательная переменная окружения: {variable}.'
            )
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
            for homework in homeworks:
                verdict = parse_status(homework)
                send_message(bot, verdict)
        except Exception as error:
            try:
                if error != last_error:
                    send_message(bot, str(error))
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                logger.error(message)
            else:
                last_error = str(error)
        else:
            current_timestamp = response['current_date']
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
