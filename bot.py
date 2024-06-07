import telebot
from PIL import Image, ImageOps
import io
from telebot import types
import os

# Получаем токен бота из переменных окружения
TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)

# Состояние пользователей
user_states = {}  # Словарь для хранения информации о действиях пользователя

# Набор символов по умолчанию для ASCII art
DEFAULT_ASCII_CHARS = '@%#*+=-:. '


def resize_image(image, new_width=100):
    """
    Изменяет размер изображения, сохраняя пропорции.

    :param image: Исходное изображение
    :param new_width: Новая ширина изображения
    :return: Измененное изображение
    """
    width, height = image.size
    ratio = height / width
    new_height = int(new_width * ratio)
    return image.resize((new_width, new_height))


def grayify(image):
    """
    Конвертирует изображение в оттенки серого.

    :param image: Исходное изображение
    :return: Изображение в оттенках серого
    """
    return image.convert("L")


def image_to_ascii(image_stream, ascii_chars, new_width=40):
    """
    Преобразует изображение в ASCII art.

    :param image_stream: Поток данных изображения
    :param ascii_chars: Набор символов для ASCII art
    :param new_width: Новая ширина изображения
    :return: Строка с ASCII art
    """
    image = Image.open(image_stream).convert('L')
    width, height = image.size
    aspect_ratio = height / float(width)
    new_height = int(aspect_ratio * new_width * 0.55)
    img_resized = image.resize((new_width, new_height))
    img_str = pixels_to_ascii(img_resized, ascii_chars)
    img_width = img_resized.width

    max_characters = 4000 - (new_width + 1)
    max_rows = max_characters // (new_width + 1)

    ascii_art = ""
    for i in range(0, min(max_rows * img_width, len(img_str)), img_width):
        ascii_art += img_str[i:i + img_width] + "\n"

    return ascii_art


def pixels_to_ascii(image, ascii_chars):
    """
    Преобразует пиксели изображения в символы ASCII.

    :param image: Изображение в оттенках серого
    :param ascii_chars: Набор символов для ASCII art
    :return: Строка с символами ASCII
    """
    pixels = image.getdata()
    characters = ""
    for pixel in pixels:
        characters += ascii_chars[pixel * len(ascii_chars) // 256]
    return characters


def pixelate_image(image, pixel_size):
    """
    Огрубляет изображение (пикселизация).

    :param image: Исходное изображение
    :param pixel_size: Размер пикселя
    :return: Пикселизированное изображение
    """
    image = image.resize((image.size[0] // pixel_size, image.size[1] // pixel_size), Image.NEAREST)
    image = image.resize((image.size[0] * pixel_size, image.size[1] * pixel_size), Image.NEAREST)
    return image


def invert_colors(image):
    """
    Инвертирует цвета изображения (создание негатива).

    :param image: Исходное изображение
    :return: Изображение с инвертированными цветами
    """
    return ImageOps.invert(image)


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """
    Обрабатывает команды /start и /help, отправляя приветственное сообщение.
    """
    bot.reply_to(message, "Send me an image, and I'll provide options for you!")


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """
    Обрабатывает полученные изображения, отправляя клавиатуру с опциями.
    """
    bot.reply_to(message, "I got your photo! Please choose what you'd like to do with it.",
                 reply_markup=get_options_keyboard())
    user_states[message.chat.id] = {'photo': message.photo[-1].file_id}


def get_options_keyboard():
    """
    Создает клавиатуру с опциями для обработки изображения.

    :return: Объект InlineKeyboardMarkup с кнопками
    """
    keyboard = types.InlineKeyboardMarkup()
    pixelate_btn = types.InlineKeyboardButton("Pixelate", callback_data="pixelate")
    ascii_btn = types.InlineKeyboardButton("ASCII Art", callback_data="ascii")
    custom_ascii_btn = types.InlineKeyboardButton("Custom ASCII Art", callback_data="custom_ascii")
    invert_btn = types.InlineKeyboardButton("Invert Colors", callback_data="invert")
    keyboard.add(pixelate_btn, ascii_btn, custom_ascii_btn, invert_btn)
    return keyboard


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    """
    Обрабатывает нажатия на кнопки клавиатуры.
    """
    if call.data == "pixelate":
        bot.answer_callback_query(call.id, "Pixelating your image...")
        pixelate_and_send(call.message)
    elif call.data == "ascii":
        user_states[call.message.chat.id]['ascii_chars'] = DEFAULT_ASCII_CHARS
        bot.answer_callback_query(call.id, "Converting your image to ASCII art with default characters...")
        ascii_and_send(call.message)
    elif call.data == "custom_ascii":
        bot.answer_callback_query(call.id, "Please provide a set of characters for ASCII art:")
        bot.send_message(call.message.chat.id, "Enter a set of characters for ASCII art (e.g., @%#*+=-:. ):")
        user_states[call.message.chat.id]['action'] = 'ascii_chars'
    elif call.data == "invert":
        bot.answer_callback_query(call.id, "Inverting colors of your image...")
        invert_and_send(call.message)


@bot.message_handler(func=lambda message: message.chat.id in user_states and 'action' in user_states[message.chat.id] and user_states[message.chat.id]['action'] == 'ascii_chars')
def handle_ascii_chars(message):
    """
    Обрабатывает ввод набора символов для ASCII art.
    """
    ascii_chars = message.text
    if not ascii_chars or any(ord(c) < 32 or ord(c) > 126 for c in ascii_chars):
        bot.reply_to(message, "Invalid set of characters. Please enter a valid set of printable ASCII characters.")
        return

    user_states[message.chat.id]['ascii_chars'] = ascii_chars
    bot.reply_to(message, "Converting your image to ASCII art with your custom characters...")
    ascii_and_send(message)


def pixelate_and_send(message):
    """
    Пикселизирует изображение и отправляет его пользователю.
    """
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)
    pixelated = pixelate_image(image, 20)

    output_stream = io.BytesIO()
    pixelated.save(output_stream, format="JPEG")
    output_stream.seek(0)
    bot.send_photo(message.chat.id, output_stream)


def ascii_and_send(message):
    """
    Преобразует изображение в ASCII art и отправляет его пользователю.
    """
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    ascii_chars = user_states[message.chat.id].get('ascii_chars', DEFAULT_ASCII_CHARS)
    ascii_art = image_to_ascii(image_stream, ascii_chars)
    bot.send_message(message.chat.id, f"```\n{ascii_art}\n```", parse_mode="MarkdownV2")


def invert_and_send(message):
    """
    Инвертирует цвета изображения и отправляет его пользователю.
    """
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)
    inverted = invert_colors(image)

    output_stream = io.BytesIO()
    inverted.save(output_stream, format="JPEG")
    output_stream.seek(0)
    bot.send_photo(message.chat.id, output_stream)


bot.polling(none_stop=True)
