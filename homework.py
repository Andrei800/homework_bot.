import logging
import os
import time
import requests
import telegram


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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

logger = logging.getLogger(__name__)



class UnexpectedStatusError(Exception):
    """Неожиданный статус домашней работы."""

def send_message(bot, message):
    """Отправка сообщения в Телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение отправлено')
    except telegram.error.TelegramError:
        logger.error('Сообщение не отправлено')


def get_api_answer(current_timestamp):
    """Выполняет запрос к API Практикум."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.ConnectTimeout as error:
        logger.error(f'Превышено время ожидания ответа сервера {error}')
        raise
    except requests.exceptions.RequestException as error:
        logger.error(f'Произошла ошибка соединения {error}')
        raise error
    if response.status_code != HTTPStatus.OK:
        logger.error(f'Сбой в программе: Эндпоинт {ENDPOINT} недоступен.'
                     f'Недоступен. Код ответа API: {response.status_code}')
        raise requests.HTTPError('Неверный код ответа сервера. '
                                 f'{response.status_code}')
    try:
        return response.json()
    except ValueError as error:
        logger.error(error)
        raise ValueError('Ответ не содержит валидный JSON')


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        message = 'Ответ не является словарем!'
        logger.error(message)
        raise TypeError(message)
    if 'homeworks' not in response:
        message = 'Ключа homeworks нет в словаре.'
        logger.error(message)
        raise KeyError(message)
    if not isinstance(response['homeworks'], list):
        message = 'Домашние работы не являются списком!'
        logger.error(message)
        raise TypeError(message)
    return response['homeworks']


def parse_status(homework):
    """Извлекает из информации о домашней работы статус этой работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status is None:
        message = 'Ключа homework_status нет в словаре.'
        logger.error(message)
        raise KeyError(message)
    if not isinstance(homework, dict):
        message = 'Ответ не является словарем!'
        logger.error(message)
        raise TypeError(message)
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except UnexpectedStatusError:
        message = 'Неожиданный статус домашней работы'
        raise UnexpectedStatusError(message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность TOKEN."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True
    logger.critical('Отсутствует обязательная переменная окружения')
    return False


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Переменные окружения заданы '
                         'некорректно или отсутсвуют')
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    status = 'reviewing'
    errors = True
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = parse_status(response)
            if homework and status != homework['status']:
                message = parse_status(homework)
                send_message(bot, message)
                status = homework['status']
            logger.info(
                f'Изменений нет, {RETRY_TIME} секунд, проверяем API')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if errors != errors:
                logger.error(message)
        else:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
