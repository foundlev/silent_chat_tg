from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config
import utils


def agreement_menu(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text='☑️ Я принимаю правила', callback_data=f"agree_{user_id}"))
    return kb


def rename_group_menu(leader_id: int, group_name: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    group_name = group_name.replace(" ", "-")
    kb.add(InlineKeyboardButton(text='☑️ Переименовать группу', callback_data=f"renamegroup_{leader_id}_{group_name}"))
    kb.add(InlineKeyboardButton(text='❎ Отмена', callback_data=f"cancel_{leader_id}"))
    return kb


def create_group_menu(leader_id: int, group_name: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    group_name = group_name.replace(" ", "-")
    kb.add(InlineKeyboardButton(text='☑️ Создать группу', callback_data=f"newgroup_{leader_id}_{group_name}"))
    kb.add(InlineKeyboardButton(text='❎ Отмена', callback_data=f"cancel_{leader_id}"))
    return kb


def unbank_menu(user_id: int, password: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()

    kb.add(InlineKeyboardButton(text='💸 Снять монетки', callback_data=f"unbank_{user_id}_{password}"))
    kb.add(InlineKeyboardButton(text='🔗 Привязать к себе', callback_data=f"relinkbank_{user_id}_{password}"))
    kb.add(InlineKeyboardButton(text='🔑 Сменить пароль', callback_data=f"changebank_{user_id}"))
    kb.add(InlineKeyboardButton(text='❎ Отмена', callback_data=f"cancel_{user_id}"))

    return kb


def up_protect_menu(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()

    kb.add(InlineKeyboardButton(text='💷 Оплатить и улучшить', callback_data=f"doupprotect_{user_id}"))
    kb.add(InlineKeyboardButton(text='❎ Отмена', callback_data=f"cancel_{user_id}"))

    return kb


def post_ad_menu(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()

    kb.add(InlineKeyboardButton(text='💷 Оплатить и опубликовать', callback_data=f"create_ad_{user_id}"))
    kb.add(InlineKeyboardButton(text='❎ Отмена', callback_data=f"cancel_{user_id}"))

    return kb


def mybank_menu(user_id: int, confirmed: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    if confirmed:
        kb.add(InlineKeyboardButton(text='💷 Оплатить и улучшить', callback_data=f"doupmybank_{user_id}"))
        kb.add(InlineKeyboardButton(text='❎ Отмена', callback_data=f"cancel_{user_id}"))
    else:
        kb.add(InlineKeyboardButton(text='🆙 Увеличить процент', callback_data=f"upmybank_{user_id}"))
        kb.add(InlineKeyboardButton(text='⏬ Уменьшить процент', callback_data=f"backupgrade_{user_id}"))
        kb.add(InlineKeyboardButton(text='🛡️ Защита от взлома', callback_data=f"upprotect_{user_id}"))
    return kb


def answer_letter_menu(from_id: int, user_id: int, dialog_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()

    kb.add(InlineKeyboardButton(text='💬 Ответить', callback_data=f"answ_{from_id}_{user_id}_{dialog_id}"))

    return kb


def back_upgrading_mybank_menu(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()

    kb.add(InlineKeyboardButton(text='⏮️ Откатить улучшение', callback_data=f"dobackupgrade_{user_id}"))
    kb.add(InlineKeyboardButton(text='❎ Отмена', callback_data=f"cancel_{user_id}"))

    return kb


def invite_group_menu(to_user_id: int, group_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text='💵 Оплатить и вступить', callback_data=f"joingroup_{to_user_id}_{group_id}"))
    return kb


def change_policy_menu(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text='🏧 Изменить режим переводов', callback_data=f"changepolicy_{user_id}"))
    return kb


def cancel_menu(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text='❎ Отмена', callback_data=f"cancel_{user_id}"))
    return kb


def leader_group_menu(leader_id: int, group_id: int, confirmed: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()

    if confirmed:
        kb.add(
            InlineKeyboardButton(text='💵 Оплатить и повысить', callback_data=f"doupgroup_{leader_id}_{group_id}"),
            InlineKeyboardButton(text='❌ Отмена', callback_data=f"cancel_{leader_id}")
        )
    else:
        kb.add(InlineKeyboardButton(text='🆙 Повысить уровень', callback_data=f"upgroup_{leader_id}_{group_id}"))
        kb.add(InlineKeyboardButton(text='📑 Список участников', callback_data=f"memberslist_{leader_id}_{group_id}"))
        kb.add(InlineKeyboardButton(text='🚮 Удалить группу', callback_data=f"removegroup_{leader_id}_{group_id}"))

    return kb


def removing_group_menu(leader_id: int, group_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(text='🚮 Удалить группу', callback_data=f"doremovegroup_{leader_id}_{group_id}"),
        InlineKeyboardButton(text='❎ Отмена', callback_data=f"cancel_{leader_id}")
    )
    return kb


def msg_code_menu(user_id: int, has_code: bool, confirmed: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)

    if has_code:
        if confirmed:
            kb.add(
                InlineKeyboardButton(text='🔄 Создать код', callback_data=f"dorecreate_msg_code_{user_id}"),
                InlineKeyboardButton(text='❌ Отмена', callback_data=f"cancel_{user_id}")
            )
        else:
            kb.add(InlineKeyboardButton(text='🔄 Пересоздать код', callback_data=f"recreate_msg_code_{user_id}"))
    else:
        kb.add(InlineKeyboardButton(text='🔄 Создать код', callback_data=f"create_msg_code_{user_id}"))

    return kb


def hack_menu(user_id: int, bank_id: int, mb_password: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text='🔎 Проверить пароль', callback_data=f"hack_{user_id}_{bank_id}_{mb_password}"))
    return kb


def user_group_menu(user_id: int, group_id: int, confirmed: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()

    if confirmed:
        kb.add(
            InlineKeyboardButton(text='⭕️ Покинуть', callback_data=f"doexitgroup_{user_id}_{group_id}"),
            InlineKeyboardButton(text='❎ Отмена', callback_data=f"cancel_{user_id}")
        )
    else:
        kb.add(InlineKeyboardButton(text='↩️ Покинуть группу', callback_data=f"exitgroup_{user_id}_{group_id}"))

    return kb


def member_removing_menu(to_user_id: int, group_id: int, from_user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(text='⭕️ Исключить', callback_data=f"removemember_{to_user_id}_{group_id}"),
        InlineKeyboardButton(text='❎ Отмена', callback_data=f"cancel_{from_user_id}")
    )
    return kb


def crystal_buy_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text='💸 Купить 1 кристалл', callback_data="buy_crystal"))
    return kb


def market_menu(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(text='💸 Купить', callback_data=f"buy_crystals_{user_id}"),
        InlineKeyboardButton(text='💰 Продать', callback_data=f"sell_crystals_{user_id}")
    )
    kb.add(
        InlineKeyboardButton(text='💎 Вернуть кристаллы', callback_data=f"getback_crystals_{user_id}"),
        InlineKeyboardButton(text='🪙 Вернуть монетки', callback_data=f"getback_coins_{user_id}")
    )
    return kb


def return_market_crystals_menu(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(text='↩️ Вернуть кристаллы', callback_data=f"getback_crystals_{user_id}"))
    return kb


def return_market_coins_menu(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(text='↩️ Вернуть монетки', callback_data=f"getback_coins_{user_id}"))
    return kb


def market_offers_menu(user_id: int, offers: tuple | list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    buttons = []

    if not offers:
        buttons.append(InlineKeyboardButton(text=f"ℹ️ Нет доступных предложений",
                                            callback_data="empty"))
        buttons.append(InlineKeyboardButton(text="↩️ Назад", callback_data=f"back_market_{user_id}"))
        kb.add(*buttons)
        return kb

    other_users_offers = [o for o in offers if o['user_id'] != user_id]

    if not other_users_offers:
        buttons.append(InlineKeyboardButton(text=f"❌ На бирже только ваши предложения",
                                            callback_data="empty"))

    for offer in offers[:10]:
        offer: dict

        price: int = offer["price"]
        crystals: int = offer["crystals"]

        direction = offer["direction"]

        assert direction in ('sell', 'buy'), "Неправильное направление у ордера на бирже"

        if direction == "sell":
            if not buttons and other_users_offers:
                best_offer = other_users_offers[0]
                buttons.append(InlineKeyboardButton(text=f"Купить сейчас 1 💎 за {utils.format_balance(best_offer['price'])} 🪙",
                                                    callback_data=f"offer_{best_offer['offer_id']}_{user_id}"))

            buttons.append(InlineKeyboardButton(text=f"Цена: {utils.format_balance(price)} 🪙 "
                                                     f"| Наличие: {utils.format_balance(crystals)} 💎",
                                                callback_data="market_info_buy"))
        else:
            if not buttons and other_users_offers:
                best_offer = other_users_offers[0]
                buttons.append(InlineKeyboardButton(text=f"Продать сейчас 1 💎 за {utils.format_balance(best_offer['price'])} 🪙",
                                                    callback_data=f"offer_{best_offer['offer_id']}_{user_id}"))

            buttons.append(InlineKeyboardButton(text=f"Цена: {utils.format_balance(price)} 🪙 "
                                                     f"| Требуется: {utils.format_balance(crystals)} 💎",
                                                callback_data="market_info_sell"))

    buttons.append(InlineKeyboardButton(text="↩️ Назад", callback_data=f"back_market_{user_id}"))
    kb.add(*buttons)
    return kb


def delere_reports_menu(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text="♻️ Удалить все жалобы", callback_data=f"deletereports_{user_id}"))
    return kb


def casino_menu(user_id: int, bet_amount: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=3)

    game_code = utils.generate_phrase(lenght=6)
    modes = (
        ("verylow", config.GAME_VERY_LOW_MULTIPLIER),
        ("low", config.GAME_LOW_MULTIPLIER),
        ("middle", config.GAME_MIDDLE_MULTIPLIER),
        ("high", config.GAME_HIGH_MULTIPLIER),
        ("veryhigh", config.GAME_VERY_HIGH_MULTIPLIER),
    )

    buttons = [
        InlineKeyboardButton(text=f"x{mode[1]}", callback_data=f"game_{mode[0]}_{game_code}_{user_id}_{bet_amount}")
        for mode in modes
    ]
    kb.add(*buttons)

    return kb


def poll_menu(poll_id: int, votes_balance_distribution: dict | None = None,
              votes_count_distribution: dict | None = None) -> InlineKeyboardMarkup:
    if votes_balance_distribution is None:
        votes_balance_distribution = {}

    if votes_count_distribution is None:
        votes_count_distribution = {}

    percentage = utils.calc_votes_percentage(votes_balance_distribution)

    percent_fine = percentage.get("fine", "-")
    percent_mute = percentage.get("mute", "-")
    percent_ban = percentage.get("ban", "-")
    percent_mercy = percentage.get("mercy", "-")

    count_fine = votes_count_distribution.get("fine", "0")
    count_mute = votes_count_distribution.get("mute", "0")
    count_ban = votes_count_distribution.get("ban", "0")
    count_mercy = votes_count_distribution.get("mercy", "0")

    kb = InlineKeyboardMarkup()

    kb.add(InlineKeyboardButton(text=f'💰 Изъять монетки [{count_fine} - {percent_fine}%]',
                                callback_data=f"poll_1_fine_{poll_id}"))
    kb.add(InlineKeyboardButton(text=f'🔇 Выдать мут [{count_mute} - {percent_mute}%]',
                                callback_data=f"poll_1_mute_{poll_id}"))
    kb.add(InlineKeyboardButton(text=f'⛔️ Исключить [{count_ban} - {percent_ban}%]',
                                callback_data=f"poll_1_ban_{poll_id}"))
    kb.add(InlineKeyboardButton(text=f'😇 Помиловать [{count_mercy} - {percent_mercy}%]',
                                callback_data=f"poll_1_mercy_{poll_id}"))

    return kb


def poll_url_menu(message_id) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text='🔗 Перейти к опросу', url=config.REF_BASE_CHAT + str(message_id)))
    return kb
