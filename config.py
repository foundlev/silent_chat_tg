DEBUG_MODE = True  # FALSE

ADMINS: list[int] = []
ADMIN_ID: int = 0
ANON_BOT_ID: int = 0
IGNORED_IDS: list[int] = [0]


# Ссылки.
# Общая на чат.
REF_BASE_CHAT: str = ""
# Ссылка на начальное сообщение.
REF_MSG_RULE: str = ""
# Ссылка на сообщение с правилами голосования.
REF_POLL_RULE: str = ""
# Ссылка на сообщение с командами.
REF_MSG_COMMANDS: str = ""
# Ссылка на инструкцию.
REF_MAIN_MANUAL: str = ""


# Флаги.
# Нужно ли формировать квитанцию после перевода.
NEED_RECEIPT = False


# Временные интервалы.
# Принятия соглашения (секунды).
TIME_TO_AGREED = 3600  # 1 час
# С последних обнимашек (секунды).
COOLDOWN_FROM_HUG = 3600 * 3  # 3 часа
# С последних обнимашек одного и того же пользователя (секунды).
COOLDOWN_FROM_HUG_SAME = 3600 * 10  # 10 часов
# C последнего опроса, чтобы началось голосование (секунды).
COOLDOWN_USER_POLL = 3600 * 12  # 3600 * 12 - 12 часов | 86400 * 2 - 2 дня
# На протяжении которого можно голосовать.
TIME_TO_POLL = 3600 * 12
# С последней жалобы (секунды) от пользователя.
COOLDOWN_REPORT = 45 * 60  # 45 * 60 - 45 минут
# Время неактивности в чате, за которое пользователь будет исключен.
TIME_USER_MAX_INACTIVE = 86400 * 4  # 4 дня
# С последнего награждения за общение.
COOLDOWN_CHAT_REWARD = 120  # 2 минуты
# С последней отправки приглашения одному и тому же пользователю.
COOLDOWN_INVITE_SAME = 1800  # 30 минут


# Вознаграждения (только целые числа).
# Ежечасное.
REWARD_CHATING = 9
# От обнимашек.
REWARD_HUG = 75
# За жалобу.
REWARD_REPORT = 100


# Комиссии (в %).
# Открытие счета.
FEE_BANK = 20
# Неудачный ввод пароля счета.
FEE_UNBANK = 0.3
# Перевод другому пользователю.
FEE_SEND = 5
# Нахождение в чате сутки.
FEE_CHAT_DAILY = 1


# Начисление процентов (в %).
# Начисление процентов на банковский счет в день.
BET_BANK_DAILY_DEFAULT = 5
# Шанс успешной попытки взлома (в %).
HACK_PERCENT_DEFAULT = 50

# Минимальный баланс участника, меньше кого начисляется штраф лидеру.
MIN_MEMBER_BALANCE = 1_000

# Количество кристаллов, которое будет начислено (каждому пользователю).
LUCKY_CRYSTALS_PER_USER_COUNT_MAX = 3
# Максимальное количество пользователей, которое получит кристаллы.
LUCKY_USERS_MAX = 5

# Стоимость.
# Открытие счета (минимальная).
PRICE_BANK = 50
# Неудачный ввод пароля счета (минимальная).
PRICE_UNBANK = 1
# Стоимость снятия со счета.
PRICE_UNBANK_CRYSTALS = 1
# Стоимость привязывания к своему аккаунту.
PRICE_LINK_CRYSTALS = 3
# Смена пароля у счета.
PRICE_CHANGE_BANK_CRYSTALS = 2
# Перевод другому пользователю (минимальная)
PRICE_SEND = 1
# Нахождение в чате сутки.
PRICE_CHAT_DAILY = 110
# Удаление жалоб (кристаллы).
PRICE_DELETE_REPORTS_CRYSTALS = 10
# Создание организации.
PRICE_CREATE_GROUP = 10_000
PRICE_CREATE_GROUP_CRYSTALS = 5
# Переименование организации.
PRICE_RENAME_GROUP_CRUYSTALS = 3
# Минимальная цена для вступления в организацию.
PRICE_JOIN_GROUP = 500
# Цена за пребывание в организации.
PRICE_GROUP_DAILY = 50
# Цена за повышение уровеня группы.
PRICE_GROUP_UPGRADE = {
    2: {"coins": 30_000, "crystals": 10},
    3: {"coins": 50_000, "crystals": 20},
    4: {"coins": 100_000, "crystals": 30},
    5: {"coins": 150_000, "crystals": 50}
}
# Цена за 1 попытку подбора пароля к счета.
PRICE_HACK_CRYSTALS = 2
# Цена за изменение анонимного кода.
PRICE_MSG_CODE = 100
# Цена за отправку сообщения.
PRICE_MSG_SEND = 1
# Цена за размещение объявления.
PRICE_POST_AD = 1_000

# Максимальное количество банковских счетов.
MAX_BANKS_COUNT = 10
# Максимальное количество участников от уровня группы.
MAX_GROUP_MEMBERS = {
    1: 10,
    2: 20,
    3: 30,
    4: 40,
    5: 50
}
# Максимальное количество заявок на покупку кристаллов.
MAX_MARKET_BUY_CRYSTALS = 10

# Условия начала голосования для выбора наказания.
# Минимальное количество жалоб (если больше чем MIN_REPORT_PERCENT).
MIN_REPORTS_COUNT = 5
# Минимальный процент пользователей должно пожаловаться (в %).
MIN_REPORT_PERCENT = 20
# Множитель суммы балансов (user.balance * REPORT_BALANCE_MULTIPLIER = total_balance_to_poll)
REPORT_BALANCE_MULTIPLIER = 30

# Условия для перехода на следующую стадию голосования или вынесения вердикта.
# Минимальное количество голосов (если больше чем MIN_VOTES_PERCENT).
MIN_VOTES_COUNT = 10
# Минимальный процент пользователей должно проголосовать (в %).
MIN_VOTES_PERCENT = 30
# Множитель суммы балансов (user.balance * VOTES_BALANCE_MULTIPLIER = total_balance_to_finish_poll)
VOTES_BALANCE_MULTIPLIER = 40


# Процент пользователей, которым достанется изъятый баланс.
SHARE_TO_USERS_PERCENT = 10  # 10
# Процент, который будет удержан при изъятии баланса.
SHARE_TO_USERS_FEE_PERCENT = 15  # 15


# Казино (множитель суммы, процент выигрыша).
# Супер маленькая игра.
GAME_VERY_LOW_MULTIPLIER = 2
GAME_VERY_LOW_PERCENTAGE = 40
# Маленькая игра .
GAME_LOW_MULTIPLIER = 5
GAME_LOW_PERCENTAGE = 15
# Средняя игра.
GAME_MIDDLE_MULTIPLIER = 10
GAME_MIDDLE_PERCENTAGE = 5
# Большая игра.
GAME_HIGH_MULTIPLIER = 50
GAME_HIGH_PERCENTAGE = 1
# Супер большая игра.
GAME_VERY_HIGH_MULTIPLIER = 100
GAME_VERY_HIGH_PERCENTAGE = 0.5


LOGS_CHANNEL_ID = None

if DEBUG_MODE:
    LOG_FILENAME = None
    BOT_TOKEN: str = ""
    CHAT_ID: int = 0
else:
    LOG_FILENAME = "reports.log"
    BOT_TOKEN: str = ""
    CHAT_ID: int = 0


DB_DATABASE = ""
DB_USER = ""
DB_PASSWORD = ""

COMING_SOON_TEXT = "🛠️ В разработке, ожидайте обновлений"
MAX_INT_UNSIGNED = 4_200_000_000
