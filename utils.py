import re
import random

import datetime
from PIL import Image, ImageDraw, ImageFont
from aiogram import types

import config


def format_time(from_time: datetime.datetime | int) -> str:
    if not from_time:
        return "0 сек"

    if isinstance(from_time, datetime.datetime):
        from_time = from_time.timestamp()

    days = int(from_time / 86400)
    from_time -= days * 86400

    hours = int(from_time / 3600)
    from_time -= hours * 3600

    minutes = int(from_time / 60)
    from_time -= minutes * 60

    seconds = int(from_time)

    x = (("дн", days), ("ч", hours), ("мин", minutes), ("сек", seconds))
    return " ".join([f"{value} {name}" for name, value in x if value])


def calc_casino_profit(game_mode: str, bet_amount: int) -> int:
    data = {
        "verylow": (config.GAME_VERY_LOW_MULTIPLIER, config.GAME_VERY_LOW_PERCENTAGE),
        "low": (config.GAME_LOW_MULTIPLIER, config.GAME_LOW_PERCENTAGE),
        "middle": (config.GAME_MIDDLE_MULTIPLIER, config.GAME_MIDDLE_PERCENTAGE),
        "high": (config.GAME_HIGH_MULTIPLIER, config.GAME_HIGH_PERCENTAGE),
        "veryhigh": (config.GAME_VERY_HIGH_MULTIPLIER, config.GAME_VERY_HIGH_PERCENTAGE)
    }
    multiplier, percentage = data[game_mode]

    percentage: int | float
    multiplier: int

    number = random.random() * 100
    if config.DEBUG_MODE:
        print(f"CASINO | NUMBER: {number} | PERCENTAGE: {percentage}")
    if number <= percentage:
        profit = int(multiplier * bet_amount)
    else:
        profit = 0

    return profit


def generate_phrase(lenght: int) -> str:
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return "".join([random.choice(chars) for _ in range(lenght)])


def calc_daily_fee(balance: int, in_group: bool) -> int:
    fee = balance * config.FEE_CHAT_DAILY / 100
    if fee < config.PRICE_CHAT_DAILY:
        if in_group:
            fee = 0
        else:
            fee = config.PRICE_CHAT_DAILY
    return int(fee)


def calc_hug_reward(from_balance: int) -> int:
    reward = int(from_balance / 200)
    if reward < config.REWARD_HUG:
        reward = config.REWARD_HUG
    return reward


def convert_command(message: types.Message):
    if message.text.startswith("/"):
        pattern = r'^/[a-z]+@[a-zA-Z_]+$'

        command = message.text.split()[0]
        if re.match(pattern, command):
            message.text = command.split("@")[0] + message.text.replace(command, "", 1)


def calc_bank_balance(balance: int, user_percent: int, opened: datetime.datetime) -> int:
    now = datetime.datetime.now()
    seconds = int(now.timestamp() - opened.timestamp())

    return int(balance * (1 + user_percent / 100) ** (seconds / 86400))


def follow_cooldown(from_time: datetime.datetime | int | None, cooldown_seconds: int) -> bool:
    if from_time is None:
        return True

    if isinstance(from_time, datetime.datetime):
        from_time = from_time.timestamp()

    now_time = datetime.datetime.now().timestamp()

    return now_time - from_time >= cooldown_seconds


def is_msg_code(text: int | str) -> bool:
    return len(str(text)) == 4 and str(text)[0].isdigit()


def calc_seconds_left(from_time: datetime.datetime | int, cooldown_seconds: int) -> int:
    if isinstance(from_time, datetime.datetime):
        from_time = from_time.timestamp()

    now_time = datetime.datetime.now().timestamp()
    return int(cooldown_seconds - (now_time - from_time))


def is_text_cleared(text: str, extra: str = "") -> bool:
    chars = "abcdefghijklmnopqrstuvwxyz0123456789" + extra

    for c in text:
        if not (c.lower() in chars):
            return False
    return True


def is_comment_cleared(text: str) -> bool:
    chars = "abcdefghijklmnopqrstuvwxyz0123456789абвгдеёжзийклмнопрстуфхцчшщъыьэюя .,:;?!()-"

    for c in text:
        if not (c.lower() in chars):
            return False
    return True


def get_win_vote(votes_distribution: dict) -> str:
    def do_random() -> bool:
        return random.choice([True, False])

    win_decision = ""
    win_decision_balance = 0

    for decision, from_balance in votes_distribution.items():
        if from_balance >= win_decision_balance:
            # Если равны, то определяем случайно.
            if from_balance == win_decision_balance:
                if do_random():
                    continue
            # Меняем локального победителя.
            win_decision_balance = from_balance
            win_decision = decision

    return win_decision


def calc_votes_total(votes_distribution: dict) -> int:
    total_balance = 0
    for from_balance in votes_distribution.values():
        total_balance += from_balance

    return total_balance


def calc_votes_percentage(votes_distribution: dict) -> dict:
    total_balance = calc_votes_total(votes_distribution)

    result = {}
    for decision, from_balance in votes_distribution.items():
        decision_percent = int(from_balance / total_balance * 100)
        result[decision] = decision_percent

    return result


def calc_fee(amount: int, percent: int | float, min_fee: int = 1) -> int:
    fee_sum = int(amount / 100 * percent)
    if fee_sum < min_fee:
        fee_sum = min_fee
    return fee_sum


def calc_part_of(amount: int, percent: int, min_count: int = 1) -> int:
    return calc_fee(amount, percent, min_count)


def unpack_message(message: types.Message | types.CallbackQuery | types.ChatMemberUpdated | types.ChatJoinRequest) -> dict:
    if isinstance(message, (types.ChatMemberUpdated, types.ChatJoinRequest)):
        user = message.from_user
    else:
        user = message['from']

    user_id = user.id
    username = user.username
    first_name = user.first_name.replace("<", "").replace(">", "")
    last_name = user.last_name
    if last_name:
        last_name = last_name.replace("<", "").replace(">", "")

    return {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name
    }


def message_interaction(message):
    if message['from']["is_bot"]:
        return message.edit_text
    else:
        return message.answer


def create_receipt(to_id: int | str, payment_sum: int, fee_sum: int, payment_time: datetime.datetime, payment_id: int):
    image = Image.open("data/receipt.jpg")

    font_regular = ImageFont.truetype("data/JetBrainsMono-Regular.ttf", 36)
    font_bold = ImageFont.truetype("data/JetBrainsMono-Bold.ttf", 36)

    total_sum = int(payment_sum + fee_sum)
    payment_time_string = payment_time.strftime("%H:%M %d.%m.%Y")

    drawer = ImageDraw.Draw(image)
    drawer.text((662, 185), str(payment_sum).rjust(7), font=font_bold, fill='black')
    drawer.text((662, 255), str(fee_sum).rjust(7), font=font_regular, fill='black')
    drawer.text((662, 325), str(total_sum).rjust(7), font=font_regular, fill='black')

    drawer.text((464, 536), payment_time_string.rjust(16), font=font_regular, fill='black')
    drawer.text((464, 606), str(to_id).rjust(16), font=font_regular, fill='black')
    drawer.text((464, 676), str(payment_id).rjust(16), font=font_regular, fill='black')

    image.save(f"receipts/receipt_{payment_id}.jpg")


def choose_win_decision_two(win_decision_one: str) -> int | datetime.datetime:
    if win_decision_one == "fine":
        # Штраф. Генерируем процент от баланса.
        return int(random.random() * (99 - 10) + 10)
    elif win_decision_one == "mute":
        # Мут. Генерирует строк от 30 минут до 1-й недели.
        time_sector = random.choice([1, 1, 1, 1, 1, 2, 2, 3])

        # Сектора: 1) 30 мин - 24 часа 2) 1-2 дня 3) 2-3 дней
        time_30_min = 1800
        time_24_hours = 86400
        time_2_days = 86400 * 2
        time_3_days = 86400 * 3
        # time_4_days = 86400 * 4
        # time_7_days = 86400 * 7

        seed = random.random()
        mute_time = {
            1: int(seed * (time_24_hours - time_30_min) + time_30_min),
            2: int(seed * (time_2_days - time_24_hours) + time_24_hours),
            3: int(seed * (time_3_days - time_2_days) + time_2_days)
        }
        return datetime.datetime.now() + datetime.timedelta(seconds=mute_time[time_sector])

    raise


def calc_reward(group_level: int) -> int:
    try:
        if not group_level:
            raise

        reward = config.REWARD_CHATING * (1 + group_level)
        if reward < config.REWARD_CHATING:
            raise
        return reward
    except:
        return config.REWARD_CHATING


def calc_upgrade_hack_protect_price(now_protect_level: int) -> int:
    """Возвращает стоимость в кристаллах"""
    return int(1.2 ** (now_protect_level + 1) * 3)


def calc_hack_percentage(now_protect_level: int, group_percent: int | None = None) -> int:
    """Возвращает шанс успешной попытки взлома в %."""
    hack_percentage = config.HACK_PERCENT_DEFAULT
    for _ in range(now_protect_level):
        hack_percentage = int(hack_percentage * 0.93)

    if group_percent is None:
        group_percent = 0
    hack_percentage = int(hack_percentage - group_percent)

    if hack_percentage < 3:
        hack_percentage = 3

    return hack_percentage


def can_hack(bank_protect_level: int, group_level: int | None = None) -> bool:
    # Например: 40 % (вероятность попытки взлома.)
    hack_percentage = calc_hack_percentage(bank_protect_level, group_level)
    number = random.randint(1, 100)
    if config.DEBUG_MODE:
        print(f"can hack: {number} <= {hack_percentage}")
    return number <= hack_percentage


def calc_upgrade_mybank_price(user_bank_percent: int) -> int:
    """Возвращает стоимость в кристаллах"""
    extra_percent = user_bank_percent - config.BET_BANK_DAILY_DEFAULT
    return int(1.4 ** (extra_percent + 1))


def check_password_user(password: str, mb_password: str) -> dict:
    chars = "abcdefghijklmnopqrstuvwxyz"
    report = []

    for i, mb_c in enumerate(mb_password):
        i: int
        mb_c: str

        if i + 1 > len(password):
            symbol = "♻️"
        else:
            c = password[i]
            if c == mb_c:
                symbol = "☑️"
            elif (mb_c.isdigit() and not c.isdigit()) or (c.isdigit() and not mb_c.isdigit()):
                symbol = "❌"
            elif mb_c.isdigit() and c.isdigit():
                symbol = "⬇️" if int(mb_c) > int(c) else "⬆️"
            else:
                symbol = "⬇️" if chars.index(mb_c) < chars.index(c) else "⬆️"
        report.append((mb_c, symbol))

    return {
        "description": " | ".join([f"{x[0].upper()} {x[1]}" for x in report]),
        "result": password == mb_password
    }


def create_msg_code(used_codes: tuple | list) -> str:
    chars = "abcdefghijklmnopqrstuvwxyz".upper()
    digits = "1234567890"

    while True:
        code = random.choice(digits) + "".join([random.choice(chars + digits) for _ in range(3)])
        if not (code.lower() in used_codes):
            return code


def round_balance(balance: int) -> int:
    chars = len(str(balance))
    if chars > 2:
        a = chars - 2
        rounded_balance = round(balance / (10 ** a)) * (10 ** a)
    else:
        rounded_balance = balance
    return rounded_balance


def format_balance(balance: int | str) -> str:
    if not isinstance(balance, int) and not balance.isdigit():
        return balance
    return f"{int(balance):,}"


def create_dialog_id() -> str:
    return str(random.randint(10_000, 99_999))
