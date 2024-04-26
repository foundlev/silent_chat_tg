import asyncio
import sys
import random

import logging

from aiogram import Bot, Dispatcher, types, executor
import datetime

import entities
import keyboards
import tg
import db
import config
import utils

logging.basicConfig(level=logging.INFO, filename=config.LOG_FILENAME)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(bot)
storage = db.Storage(dp.loop)
temp_storage = entities.TempStorage()
lock_market = asyncio.Lock()

BOT_PROFILE: types.User
COMMANDS = ["start", "help", "hug", "bank", "unbank", "mybank", "coins", "users", "send", "tasks",
            "report", "fees", "top", "worst", "stop", "test", "topbanks", "casino",
            "sell", "buy", "market", "deletereports", "myid", "profile",
            "creategroup", "mygroup", "renamegroup", "invite", "grouptax", "removemember", "sendcrystals",
            "hack", "anoncode", "msg", "changebank", "ad", "random"]
HTML = "html"


@dp.message_handler(commands=COMMANDS, content_types=types.ContentTypes.TEXT)
async def message_func(message: types.Message):
    try:
        if message.from_user.id in config.IGNORED_IDS:
            return

        utils.convert_command(message)

        cm, *args = message.text.split()
        user = entities.User(storage, **utils.unpack_message(message))

        if user.user_id == config.ANON_BOT_ID:
            return

        await user.load_from_db()

        availability = await tg.check_availability(bot, message, user)
        if not availability.result:
            if availability.delete:
                await message.delete()
            return

        await user.update()

        if cm in ('/start', '/help', '/fees'):
            await tg.help_menu(message)

        # Подача жалобы на пользователя.
        elif cm == "/report":
            if message.reply_to_message:
                args = [message.reply_to_message.from_user.id]

            if not args:
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Отправка жалобы на пользователя. После команды напишите ник / ID пользователя "
                        "или ответьте командой на сообщение пользователя.\n"
                        "<u>Команда:</u> <code>/report [пользователь]</code>")
                await message.answer(text, parse_mode=HTML)
                return

            await tg.process_report(message, user, args, bot_profile=BOT_PROFILE)

        # Показать доступные задания.
        elif cm == "/tasks":
            await tg.show_tasks(message, user)

        # Казино.
        elif cm == "/casino":
            if not args:
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Игра на удачу в казино. При вводе команды нужно указать ставку в монетках."
                        " Чем выше сложность игры, тем больше потенциальный выигрыш и меньше его шанс.\n"
                        "<u>Команда:</u> <code>/casino [ставка в монетках]</code>")
                await message.answer(text, parse_mode=HTML)
                return

            await tg.show_casino(message, user)

        # Создание группы.
        elif cm == "/creategroup":
            if not args:
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Создает новую группу, в которой вы сразу станете лидером.\n"
                        "<u>Команда:</u> <code>/creategroup [название группы]</code>")
                await message.answer(text, parse_mode=HTML)
                return
            await tg.show_group_creating(message, user)

        # Отправляем приглашение вступить в группу.
        elif cm == "/invite":
            if not args and not message.reply_to_message:
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Отправляет приглашение указаному пользователю.\n"
                        "<u>Команда:</u> <code>/invite [пользователь]</code>")
                await message.answer(text, parse_mode=HTML)
                return
            await tg.show_group_inviting(message, user, BOT_PROFILE)

        # Просмотр группы пользователя.
        elif cm == "/mygroup":
            await tg.show_user_group(message, user)

        elif cm == "/renamegroup":
            if not args:
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Переименование своей группы.\n"
                        "<u>Команда:</u> <code>/renamegroup [новое название]</code>")
                await message.answer(text, parse_mode=HTML)
                return
            await tg.rename_group(message, user)

        # Удаление участника из группы.
        elif cm == "/removemember":
            if not args and not message.reply_to_message:
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Удаляет участника из группы.\n"
                        "<u>Команда:</u> <code>/removemember [пользователь]</code>")
                await message.answer(text, parse_mode=HTML)
                return
            await tg.removing_user_from_group(message, user, BOT_PROFILE)

        # Изменение суммы ежедневного взноса.
        elif cm == "/grouptax":
            if not args:
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Устанавливает сумму ежедневного взноса в монетках для участников группы.\n"
                        "<u>Команда:</u> <code>/grouptax [сумма в монетках]</code>")
                await message.answer(text, parse_mode=HTML)
                return
            await tg.group_tax_control(message, user)

        # Выставить кристаллы на продажу.
        elif cm == "/sell":
            if len(args) != 2:
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Выставление на биржу какое-то количество кристаллов по определенной цене.\n"
                        "<u>Команда:</u> <code>/sell [кол-во кристаллов] [цена за 1 кристалл]</code>")
                await message.answer(text, parse_mode=HTML)
                return
            await tg.process_market_command(message, user)

        # Создать заявку на покупку кристаллов.
        elif cm == "/buy":
            if len(args) != 2:
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Создание заявки на покупку кристаллов на бирже "
                        "по определенной цене.\n"
                        "<u>Команда:</u> <code>/buy [кол-во кристаллов] [цена за один]</code>")
                await message.answer(text, parse_mode=HTML)
                return
            await tg.process_market_command(message, user)

        # Открыть биржу кристаллов.
        elif cm == "/market":
            await tg.show_market(message, user)

        # Удалить все репорты.
        elif cm == "/deletereports":
            text = ("<b>Вы уверены, что хотите удалить все жалобы на вас?</b>\n"
                    f"Стоимость: <b>{config.PRICE_DELETE_REPORTS_CRYSTALS} 💎</b>")
            await message.answer(text, parse_mode=HTML, reply_markup=keyboards.delere_reports_menu(user.user_id))

        # Беднейшие пользователи по балансу.
        elif cm == "/worst":
            users_count = await storage.get_users_count(include_muted=True)
            balances = await storage.get_worst_balances()
            balances.reverse()

            text = "🤕 <b>Самые бедные участники</b>\n"
            for idx, balance in enumerate(balances):
                place = users_count - len(balances) + idx + 1
                text += f"\n{place}) Баланс: <b>{utils.format_balance(balance)} 🪙</b>"

            await message.answer(text, parse_mode=HTML)

        # Остановка бота.
        elif cm == "/stop" and user.user_id == config.ADMIN_ID:
            await message.answer("⏹️ Остановка Бота")
            dp.stop_polling()
            asyncio.get_event_loop().stop()
            sys.exit()

        # Тестовая функция.
        elif cm == "/test" and user.user_id == config.ADMIN_ID:
            print()

        # Топ пользователей по балансу.
        elif cm == "/top":
            balance_task = asyncio.create_task(storage.get_top_balances())
            crystal_balance_task = asyncio.create_task(storage.get_top_crystal_balances())
            total_market_crystals_task = asyncio.create_task(storage.get_market_total_crystals())
            top_groups_task = asyncio.create_task(storage.get_top_groups())

            balances = await balance_task
            crystal_balances = await crystal_balance_task

            total_market_crystals = await total_market_crystals_task
            top_groups = await top_groups_task

            total_balance = int(sum(balances))
            total_top_balance = int(sum(balances[:10]))
            total_crystal_balance = int(sum(crystal_balances))

            existing_crystals = int(total_crystal_balance + total_market_crystals)

            text = "🏆 <b>Самые богатые участники</b>\n\n🪙 <u>По накопленным монеткам</u>"

            for idx, balance in enumerate(balances[:10]):
                formatted_balance = utils.format_balance(utils.round_balance(balance))
                prize = int(balance / total_top_balance * 10_000)
                percentage = int(balance / total_top_balance * 100)
                text += f"\n{idx + 1}) ~<b>{formatted_balance}</b> ({percentage}% - {prize}₽)"

            text += (f"\nВсего: <b>{utils.format_balance(total_balance)}</b> 🪙"
                     f"\n\n💎 <u>По накопленным кристаллам</u>")

            for idx, crystal_balance in enumerate(crystal_balances[:10]):
                percentage_crystals = int(crystal_balance / existing_crystals * 100)
                text += f"\n{idx + 1}) <b>{utils.format_balance(crystal_balance)}</b> ({percentage_crystals}%)"

            text += (f"\nВсего: <b>{utils.format_balance(existing_crystals)}</b> 💎"
                     "\n\n🔖 <i>В скобках написана сумма потенциального выигрыша 31 декабря 2023 г. ТОП монеток составлен "
                     "с учетом сбережений на банковских счетах.</i>")

            text += "\n\n👥 <b>Топ влиятельных групп</b>\n"

            for numb, group in enumerate(top_groups[:5], start=1):
                formatted_group_balance = utils.format_balance(utils.round_balance(group['balance']))
                formatted_group_crystals = utils.format_balance(utils.round_balance(group['crystals']))
                group_name: str = group['caption']
                text += (f"\n{numb}) <b>{group_name.capitalize()}</b> ("
                         f"~<b>{formatted_group_balance}</b> 🪙, <b>{formatted_group_crystals}</b> 💎)")

            await message.answer(text, parse_mode=HTML)

        # Отображение списка пользователей.
        elif cm == "/users":
            await tg.show_all_users(message, user)

        # Получение собственного ID.
        elif cm == "/myid":
            text = f"🆔 Ваш ID: <code>{user.user_id}</code>"
            await message.reply(text, parse_mode=HTML)

        # Отправка объятий другому пользователю.
        elif cm == "/hug":
            if not args and not message.reply_to_message:
                await tg.answer_bad_command(message)
                return

            if message.reply_to_message:
                search_text = message.reply_to_message.from_user.id
            else:
                search_text = args[0]
            to_user = await tg.search_user(storage, message, search_text, check_mute=True, bot_profile=BOT_PROFILE)

            if to_user:

                if to_user.user_id == user.user_id:
                    text = "❌ Нельзя обнимать себя"
                    await message.answer(text)
                    return

                # Проверяем время последних обнимашек.
                last_hug = await storage.last_hug(from_id=user.user_id)
                now_time = datetime.datetime.now()

                if not last_hug or now_time.timestamp() - last_hug.timestamp() > config.COOLDOWN_FROM_HUG:
                    # Проверяем время последних обнимашек с конкретным пользователем.
                    last_hug_user = await storage.last_hug_user(from_id=user.user_id, to_id=to_user.user_id)
                    if not (
                            not last_hug_user or now_time.timestamp() - last_hug_user.timestamp() > config.COOLDOWN_FROM_HUG_SAME):
                        time_left = config.COOLDOWN_FROM_HUG_SAME - (now_time.timestamp() - last_hug_user.timestamp())
                        time_left_string = utils.format_time(int(time_left))

                        text = (f"❌ <b>Вы уже обнимали этого пользователя недавно</b>\n"
                                f"Подождите еще {time_left_string}")
                        await message.answer(text, parse_mode=HTML)

                        return

                    # Добавляем запись в БД и увеличиваем баланс другого пользователя.
                    await storage.add_hug(from_id=user.user_id, from_balance=user.balance, to_id=to_user.user_id)
                    current_hug_reward = utils.calc_hug_reward(user.balance)

                    text = f"<b>💖 Вы обняли другого пользователя</b>\n{to_user}"
                    await message.answer(text, parse_mode=HTML)

                    text_2 = (f"💖 <b>Вам кто-то отправил обнимашки</b>\n"
                              f"Начислено: <b>{utils.format_balance(current_hug_reward)} 🪙</b>")
                    try:
                        await bot.send_message(to_user.user_id, text_2, parse_mode=HTML)
                    except:
                        pass

                    if not config.DEBUG_MODE:
                        notif_text = f"💖 <b>Отправка обнимашек</b>\n\n{user}\n\n{to_user}"
                        await tg.notify(bot, notif_text)
                else:
                    time_left = config.COOLDOWN_FROM_HUG - (now_time.timestamp() - last_hug.timestamp())
                    time_left_string = utils.format_time(int(time_left))

                    text = (f"❌ <b>С последних обнимашек прошло слишком мало времени</b>\n"
                            f"Подождите еще {time_left_string}")
                    await message.answer(text, parse_mode=HTML)

        # Открытие банковского счёта.
        elif cm == "/bank":
            if not args or not args[0].isdigit():
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Создание банковского счета. Пароль, который нужно придумать должен быть до "
                        "6-ти символов длину. Можно использовать латинские буквы (a-z) и цифры. "
                        "Регистр символов игнорируется.\n"
                        "<u>Команда:</u> <code>/bank [количество монеток] [пароль]</code>")
                await message.answer(text, parse_mode=HTML)
                return

            try:
                amount = int(args[0])
                password = args[1].lower()

                if not (10 <= amount <= config.MAX_INT_UNSIGNED):
                    text = ("❌ Нельзя открыть банковский счет меньше чем на 10 "
                            "и больше чем на 4.2 млрд монеток")
                    await message.answer(text, parse_mode=HTML)
                    return

                fee_sum = utils.calc_fee(amount, config.FEE_BANK, config.PRICE_BANK)
                amount_with_fee = int(amount + fee_sum)
                # Проверяем баланс.
                if user.balance >= amount_with_fee:
                    user_banks = await user.get_banks()

                    if len(user_banks) < config.MAX_BANKS_COUNT:
                        if utils.is_text_cleared(password) and len(password) <= 6:
                            try:
                                await storage.create_bank(user, amount, amount_with_fee, password)
                                text = (f"💰 <b>Банковский счет создан</b>\n"
                                        f"Сумма: <b>{utils.format_balance(amount)} 🪙</b>\n"
                                        f"Пароль: <tg-spoiler>***{password[-2:]}</tg-spoiler>")
                                await message.answer(text, parse_mode=HTML)

                            except:
                                text = (f"❌ Ошибка - что-то пошло не так. Возможно у кого-то уже есть банковский "
                                        f"счет с таким паролем.")
                                await message.answer(text)

                        else:
                            text = (f"❌ Пароль может состоять только из букв латинского алфавита (abcde...) и "
                                    f"цифр (0123...) и должен быть не больше 6-ти символов в длину.")
                            await message.answer(text)

                    else:
                        text = (f"❌ Нельзя создать больше {config.MAX_BANKS_COUNT} банковских счетов. \n"
                                f"Обналичьте один существующий счет, чтобы создать новый.")
                        await message.answer(text)
                else:
                    text = ("❌ <b>Не хватает монеток</b>\n"
                            f"С учетом комиссии <b>{config.FEE_BANK}%</b> вам нужно <b>{utils.format_balance(amount_with_fee)} монеток</b>\n"
                            f"Ваш текущий баланс: <b>{utils.format_balance(user.balance)} монеток</b>")
                    await message.answer(text, parse_mode=HTML)
            except:
                text = (f"❌ Ошибка - что-то пошло не так. Проверьте правильность вашей "
                        f"введенной команды.")
                await message.answer(text)

        elif cm == "/random":
            if not args or not args[0].isdigit() or not (1 < int(args[0]) <= 10_000_000):
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Генерация случайного числа. Аюми сгенерирует случайное число "
                        "от 1 до введенного числа. Введенное число должно быть "
                        "больше 1 и не больше 10 млн.\n"
                        "<u>Команда:</u> <code>/random [число]</code>")
                await message.answer(text, parse_mode=HTML, disable_web_page_preview=True)
                return

            upper_number = int(args[0])

            new_number = random.randint(1, upper_number)
            date = datetime.datetime.now().strftime("%H:%M:%S %m.%d.%Y")
            text = (f"🎲 <b>Получено случайное число</b>\n"
                    f"Условия: от <code>1</code> до <code>{upper_number}</code>\n"
                    f"<b>Число:</b> <code>{new_number}</code>\n"
                    f"Дата: <code>{date}</code>")
            await message.answer(text, parse_mode=HTML, disable_web_page_preview=True)

        # Публикация сообщений.
        elif cm == "/ad":
            ad_text = message.text[4:].replace("<", "").replace(">", "")

            if len(ad_text) > 3000:
                await message.answer("❌ Максимальный размер объявления - 3000 символов.")
                return

            text = (f"📢 <b>Проверьте текст вашего объявления</b>\n\n"
                    f"Стоимость публикации: <b>{config.PRICE_POST_AD} 🪙</b>\n\n")
            text += ad_text
            await message.answer(text, parse_mode=HTML, reply_markup=keyboards.post_ad_menu(user.user_id),
                                 disable_web_page_preview=True)

            temp_storage.value(user, "adText", ad_text)

        # Смена пароль на банковском счете.
        elif cm == "/changebank":
            if len(args) != 2:
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Смена пароля для существующего банковского счета.\n"
                        f"Стоимость: {config.PRICE_CHANGE_BANK_CRYSTALS} 💎\n"
                        "<u>Команда:</u> <code>/changebank [старый пароль] [новый пароль]</code>")
                await message.answer(text, parse_mode=HTML, disable_web_page_preview=True)
                return

            try:
                old_password = args[0].lower()
                new_password = args[1].lower()

                assert user.crystals >= config.PRICE_CHANGE_BANK_CRYSTALS, "У вас не хватает кристаллов"
                assert utils.is_text_cleared(old_password) and len(old_password) <= 6, (
                    f"Пароль может состоять только из букв латинского алфавита (abcde...) и "
                    f"цифр (0123...) и должен быть не больше 6-ти символов в длину."
                )
                assert utils.is_text_cleared(new_password) and len(new_password) <= 6, (
                    f"Пароль может состоять только из букв латинского алфавита (abcde...) и "
                    f"цифр (0123...) и должен быть не больше 6-ти символов в длину."
                )

                fee = utils.calc_fee(user.balance, config.FEE_UNBANK, config.PRICE_UNBANK)
                bank_result = await user.change_bank_password(old_password, new_password, fee)

                if bank_result:
                    text = ("☑️ <b>Пароль банковского счета изменен</b>\n"
                            f"Номер счета: <b>{bank_result['account_id']}</b>\n"
                            f"Старый пароль: <tg-spoiler>***{old_password[-2:]}</tg-spoiler>\n"
                            f"Новый пароль: <tg-spoiler>***{new_password[-2:]}</tg-spoiler>\n\n"
                            f"Списано с баланса: <b>{config.PRICE_CHANGE_BANK_CRYSTALS} 💎</b>")
                    await message.answer(text, parse_mode=HTML)

                    try:
                        if bank_result['user_id'] != user.user_id:
                            text_2 = ("⚠️ <b>Кто-то изменил пароль счета</b>\n"
                                      f"Номер счета: <b>{bank_result['account_id']}</b>")
                            await bot.send_message(bank_result['user_id'], text_2, parse_mode=HTML)
                    except:
                        pass

                else:
                    text = ("❌ <b>Банковского счета с таким паролем не существует</b>\n"
                            f"В качестве компенсации банк списал с вашего баланса <b>{fee} монеток</b>")
                    await message.answer(text, parse_mode=HTML)

            except Exception as e:
                text = f"❌ {e}"
                await message.answer(text, parse_mode=HTML)

        # Обналичивание банковского счёта.
        elif cm == "/unbank":
            if not args:
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Вывод монеток с банковского счета на баланс. Стоимость услуги "
                        f"смотрите в <a href='{config.REF_MAIN_MANUAL}'>инструкции чата</a>.\n"
                        "<u>Команда:</u> <code>/unbank [пароль]</code>")
                await message.answer(text, parse_mode=HTML, disable_web_page_preview=True)
                return

            try:
                password = args[0].lower()
                if user.balance >= config.PRICE_UNBANK:
                    if not (user.crystals >= config.PRICE_UNBANK_CRYSTALS):
                        text = (f"❌ <b>У вас не хватает кристаллов для этой операции</b>\n"
                                f"Требуется: <b>{config.PRICE_UNBANK_CRYSTALS} 💎</b>.")
                        await message.answer(text, parse_mode=HTML)
                        return

                    if utils.is_text_cleared(password) and len(password) <= 6:

                        fee = utils.calc_fee(user.balance, config.FEE_UNBANK, config.PRICE_UNBANK)

                        bank_result = await user.get_bank_by_password(password, fee)
                        if bank_result:
                            owner_id = bank_result['user_id']
                            owner = await entities.get_user_by_id(user.get_storage(), owner_id)

                            start_sum: int = bank_result['balance']
                            now_sum: int = bank_result['unbankSum']
                            bank_id: int = bank_result['account_id']

                            created_time: datetime.datetime = bank_result['created']
                            time_passed: int = int(datetime.datetime.now().timestamp() - created_time.timestamp())
                            show_time = utils.format_time(time_passed)

                            text = (f"💳 <b>Банковский счет</b>\n"
                                    f"ID счета: <b>{bank_id}</b>\n"
                                    f"Пароль: <code>{password}</code>\n"
                                    f"При открытии: <b>{utils.format_balance(start_sum)} 🪙</b>\n"
                                    f"Сейчас: <b>{utils.format_balance(now_sum)} 🪙</b>\n"
                                    f"Прошло: <i>{show_time}</i>\n\n"
                                    f"👤 <b>Владелец счета</b>\n{owner}\n\n"
                                    f"🏧 <b>Стоимость услуг</b>\n"
                                    f"Снять со счета: <b>{config.PRICE_UNBANK_CRYSTALS} 💎</b>\n"
                                    f"Привязать к себе: <b>{config.PRICE_LINK_CRYSTALS} 💎</b>\n"
                                    f"Поменять пароль: <b>{config.PRICE_CHANGE_BANK_CRYSTALS} 💎</b>")
                            await message.answer(text, parse_mode=HTML,
                                                 reply_markup=keyboards.unbank_menu(user.user_id, password))

                        else:
                            text = ("❌ <b>Банковского счета с таким паролем не существует</b>\n"
                                    f"В качестве компенсации банк списал с вашего баланса <b>{fee} монеток</b>")
                            await message.answer(text, parse_mode=HTML)

                    else:
                        text = (f"❌ Пароль может состоять только из букв латинского алфавита (abcde...) и "
                                f"цифр (0123...) и должен быть не больше 6-ти символов в длину.")
                        await message.answer(text)

                else:
                    text = (f"❌ На вашем балансе должно быть более <b>{config.PRICE_UNBANK} монеток</b>, "
                            f"чтобы выполнить это действие.")
                    await message.answer(text, parse_mode=HTML)

            except:
                text = (f"❌ Ошибка - что-то пошло не так. Проверьте правильность вашей "
                        f"введенной команды.")
                await message.answer(text, parse_mode=HTML)

        # Просмотр топа банковских счетов.
        elif cm == "/topbanks":
            try:
                banks = await storage.get_top_banks()

                if banks:
                    text = "💰 <b>Топ банковских счетов</b>"

                    for numb, bank in enumerate(banks[:10]):
                        text += (f"\n\n{numb + 1}) <u>Счет #{bank['account_id']}</u>\n"
                                 f"Процент владельца: <b>{bank['ownerPercent']}%</b>\n"
                                 f"При открытии: <b>{utils.format_balance(bank['balance'])} 🪙</b>\n"
                                 f"Сейчас: <b>{utils.format_balance(bank['unbankSum'])} 🪙</b>")

                else:
                    text = "ℹ️ Нет банковских счетов"
            except Exception as e:
                await bot.send_message(config.ADMIN_ID, f"[topbanks]: {e}")
                text = (f"❌ Ошибка - что-то пошло не так. Проверьте правильность вашей "
                        f"введенной команды.")
            await message.answer(text, parse_mode=HTML)

        # Просмотр банковских счетов.
        elif cm == "/mybank":
            rpl = None
            private_mode = (message.chat.id == user.user_id)
            try:
                banks_task = asyncio.create_task(user.get_banks())
                user_bank_perecent_task = asyncio.create_task(user.get_bank_percent())

                group = user.get_group()
                group_level_task = asyncio.create_task(group.get_level())

                banks = await banks_task
                user_bank_percent = await user_bank_perecent_task
                group_level = await group_level_task

                if banks:
                    total_balance = sum([b['unbankSum'] for b in banks])
                    hack_percentage = utils.calc_hack_percentage(user.protect_level, group_level)
                    text = ("🏦 <b>Ваши банковские счета</b>\n\n"
                            f"⬆️ Начисление в день: <b>{user_bank_percent}%</b>\n"
                            f"🛡️ Уровень защиты: <b>{user.protect_level}</b>\n"
                            f"🛰️ Шанс успешной атаки: <b>{hack_percentage}%</b>\n"
                            f"💰 В банке: <b>{utils.format_balance(total_balance)}</b> 🪙")

                    now = datetime.datetime.now()
                    for bank in banks:
                        created_time: datetime.datetime = bank['created']
                        time_passed: int = int(now.timestamp() - created_time.timestamp())
                        show_time = utils.format_time(time_passed)

                        text += (f"\n\n<u>Счет #{bank['account_id']}</u>\n"
                                 f"При открытии: <b>{utils.format_balance(bank['balance'])} 🪙</b>\n"
                                 f"Сейчас: <b>{utils.format_balance(bank['unbankSum'])} 🪙</b>\n"
                                 f"Прошло: <i>{show_time}</i>")
                        if private_mode:
                            text += f"\nПароль: <tg-spoiler>***{bank['a_password'][-2:]}</tg-spoiler>"

                    if not config.DEBUG_MODE:
                        notif_text = f"💰 <b>Просмотр банковских счетов</b>\n{user}"
                        await tg.notify(bot, notif_text)

                else:
                    text = "ℹ️ У вас нет банковских счетов"
                rpl = keyboards.mybank_menu(user.user_id, False)
            except:
                text = (f"❌ Ошибка - что-то пошло не так. Проверьте правильность вашей "
                        f"введенной команды.")
            await message.answer(text, parse_mode=HTML, reply_markup=rpl)

        # Проверка баланса монеток.
        elif cm == "/coins":
            text = (f"<u>Сбережения пользователя</u>\n"
                    f"🪙 <b>{utils.format_balance(user.balance)} монеток</b>\n"
                    f"💎 <b>{utils.format_balance(user.crystals)} кристаллов</b>")
            await message.answer(text, parse_mode=HTML)

        # Просмотр профиля.
        elif cm == "/profile":
            place_info = await user.get_top_place_info()

            place: int = place_info["place"]
            total_count: int = place_info["total"]
            banks: list = place_info["banks"]

            place_symbol = "🏆" if int(place) <= 10 else "🗂"
            banks_profile_info = await user.get_banks_profile_info(banks=banks)

            bank_total_balance: int = banks_profile_info["balance"]
            banks_count: int = banks_profile_info["count"]

            # Подгружаем обновленные балансы.
            await user.load_balance_from_db()

            # Подгружаем информацию о группе.
            group = user.get_group()
            # Загружаем информацию о группе.
            await group.update_info()

            tax_list = []

            # Вычисляем информацию о сборах и взносах.
            daily_tax = utils.calc_daily_fee(user.balance, user.in_group())
            tax_list.append(f"Пребывание в чате: <b>{utils.format_balance(daily_tax)} 🪙</b>")
            if group.exists() and not (await group.is_leader(user.user_id)):
                group_tax = await group.get_tax()
                tax_list.append(f"Взнос в группу: <b>{utils.format_balance(group_tax)} 🪙</b>")

            if tax_list:
                tax_info = "\n\n<u>Ежедневные платежи</u>\n" + '\n'.join(tax_list)
            else:
                tax_info = ""

            if group.exists():
                group_info = (f"\n\n<u>Участник объединения</u>\n"
                              f"Группа: <b>{group.get_name()}</b>\n"
                              f"Должность: <b>{group.get_user_post(user.user_id)}</b>")
            else:
                group_info = ""

            if user.policy == 1:
                policy_info = "\n\n☑️ Вам могут переводить все пользователи"
            else:
                policy_info = "\n\n🛂 Вам могут переводить только пользователи из вашей группы"

            user_bank_percent_task = asyncio.create_task(user.get_bank_percent())
            group_level_task = asyncio.create_task(group.get_level())

            user_bank_percent = await user_bank_percent_task
            group_level = await group_level_task
            hack_percentage = utils.calc_hack_percentage(user.protect_level, group_level)

            text = (f"{place_symbol} Место в ТОП: <b>{place} из {total_count}</b>\n"
                    f"🆔 Ваш ID: <code>{user.user_id}</code>\n"
                    f"🕒 Дней в проекте: <b>{user.get_days()}</b>\n\n"
                    f"<u>Отображаемые балансы</u>\n"
                    f"🪙 <b>{utils.format_balance(user.balance)} монеток</b>\n"
                    f"💎 <b>{utils.format_balance(user.crystals)} кристаллов</b>\n\n"
                    f"<u>Банковские счета</u>\n"
                    f"🏦 Процент в банке: <b>{user_bank_percent}%</b>\n"
                    f"🛡️ Успешность атаки: <b>{hack_percentage}%</b> \n"
                    f"🪙 <b>{utils.format_balance(bank_total_balance)} монеток</b> (счетов: {banks_count})"
                    + tax_info + group_info + policy_info)
            await message.reply(text, parse_mode=HTML, reply_markup=keyboards.change_policy_menu(user.user_id))

        # Перевод монеток другому пользователю.
        elif cm == "/send":
            if len(args) < 2:
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Перевод монеток другому пользователю. Поле комментарий "
                        "указывать необязательно. Если комментарий указан, его увидит получатель. "
                        f"Комиссия за перевод составляет {config.FEE_SEND}%\n"
                        "<u>Команда:</u> <code>/send [пользователь] [кол-во монеток] {комментарий}</code>")
                await message.answer(text, parse_mode=HTML)
                return
            await tg.show_sending_procedure(message, user, args, bot_profile=BOT_PROFILE)

        # Перевод кристаллов другому пользователю.
        elif cm == "/sendcrystals":
            if len(args) < 2:
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Перевод кристаллов другому пользователю. Поле комментарий "
                        "указывать необязательно. Если комментарий указан, его увидит получатель. "
                        "Комиссия за перевод не взимается.\n"
                        "<u>Команда:</u> <code>/sendcrystals [пользователь] [кол-во кристаллов] {комментарий}</code>")
                await message.answer(text, parse_mode=HTML)
                return
            await tg.show_sending_crystals_procedure(message, user, args, bot_profile=BOT_PROFILE)

        # Подбор пароля к банковскому счету.
        elif cm == "/hack":
            if len(args) < 2:
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Позволяет подобрать пароль к банковскому счету, зная только его номер. "
                        "Необходимо ввести предположительный пароль и следовать подсказкам. Пароль "
                        "может быть от 1 до 6 символов (a-z, цифры). Регистр игнорируется (не важно большие или "
                        "маленькие буквы)."
                        f"Стоимость попытки: <b>{config.PRICE_HACK_CRYSTALS} 💎</b>.\n"
                        "<u>Команда:</u> <code>/hack [номер счета] [предполагаемый пароль]</code>")
                await message.answer(text, parse_mode=HTML)
                return
            await tg.hack(message, user)

        # Настройка анонимного кода.
        elif cm == "/anoncode":
            await tg.control_anon_code(message, user)

        # Отправка сообщения / просмотр уникального кода.
        elif cm == "/msg":
            if len(args) < 2 and not (message.reply_to_message and args):
                text = ("❌ <b>Команда введена неправильно</b>\n"
                        "<u>Описание:</u> Отправляйте анонимное сообщение любому пользователю. "
                        "Получатель не видит отправителя. Текст сообщения "
                        "не должен быть больше 512-ти символов в длину. Чтобы ответить на данное сообщение, "
                        "смахните его в Telegram влево и отправьте команду без указания получателя.\n"
                        f"Стоимость отправки: <b>{config.PRICE_MSG_SEND} 🪙</b>.\n"
                        "<u>Команда:</u> <code>/msg [получатель] [текст сообщения]</code>")
                await message.answer(text, parse_mode=HTML)
                return
            await tg.send_msg(message, user, BOT_PROFILE)

    except Exception as e:
        await message.answer("☢️ Программная ошибка [CMD], сообщите разработчику @reireireime.")

        try:
            await message.forward(config.ADMIN_ID)
        except:
            pass
        await bot.send_message(config.ADMIN_ID, str(e))


@dp.message_handler(content_types=types.ContentTypes.DICE)
async def handle_random(message: types.Message):
    if message.chat.id == config.CHAT_ID:
        await message.delete()
        await message.answer("🎰 <b>Вы можете попытать удачу в казино</b>\n"
                             "Команда: <code>/casino [ставка в монетках]</code>", parse_mode=HTML)


@dp.message_handler(content_types=types.ContentTypes.STICKER)
async def handle_media(message: types.Message):
    try:
        user = entities.User(storage, **utils.unpack_message(message))

        if user.user_id == config.ANON_BOT_ID:
            return

        await user.load_from_db()

        availability = await tg.check_availability(bot, message, user)
        if not availability.result:
            if availability.delete:
                await message.delete()
            return

        await user.update()
        await tg.check_bad_habits(message, user)
    except Exception as e:
        print(f"TXT E: {e}")
        await message.answer("☢️ Программная ошибка [TXT], сообщите разработчику @reireireime.")


@dp.message_handler()
async def handle_message(message: types.Message):
    try:
        user = entities.User(storage, **utils.unpack_message(message))

        if user.user_id == config.ANON_BOT_ID:
            return

        await user.load_from_db()

        availability = await tg.check_availability(bot, message, user)
        if not availability.result:
            if availability.delete:
                await message.delete()
            return

        await user.update()
        await tg.check_bad_habits(message, user)
    except Exception as e:
        print(f"TXT E: {e}")
        await message.answer("☢️ Программная ошибка [TXT], сообщите разработчику @reireireime.")


@dp.callback_query_handler()
async def inline_touch(call: types.CallbackQuery):
    try:
        if call.message.from_user.id in config.IGNORED_IDS:
            return

        user = entities.User(storage, **utils.unpack_message(call))

        if user.user_id == config.ANON_BOT_ID:
            return

        await user.load_from_db()

        availability = await tg.check_availability(bot, call.message, user, call=call, ignore_agree=True)
        if not availability.result:
            return

        await user.update()

        if config.DEBUG_MODE:
            print(f"CALL.DATA: {call.data}")

        # Принятие правил чата.
        if call.data.startswith("agree_"):
            try:
                person_id = int(call.data.replace("agree_", ""))

                if person_id == user.user_id:
                    await user.set_agreed(new_value=True)
                    await call.message.edit_reply_markup()

                    text = ("<b>🎉 Отлично! Наслаждайтесь общением.</b>\n\n"
                            f"Настоятельно советую прочитать правила, чтобы выжить в этом чате: {config.REF_MSG_RULE}, "
                            f"это не так просто как кажется на первый взгляд. У тебя только один шанс.\n\n"
                            f"⚠️ <b>Все сообщения с описаниями обновлений механик чата закреплены. Прочитайте их все.</b>\n\n"
                            f"Также не забудь <a href='https://t.me/controlkids_bot'>написать мне лс</a>, чтобы я могла в будущем отправлять тебе различные уведомления "
                            f"(о переводах и тд).")
                    await call.message.edit_text(text, parse_mode=HTML)

                    if not config.DEBUG_MODE:
                        notif_text = f"📋 <b>Правила приняты</b>\n{user}"
                        await tg.notify(bot, notif_text)

                else:
                    text = ("❌ Ошибка. Данное сообщение адресовано не вам. Чтобы принять правила чата, можете "
                            "написать Аюми (боту) в лс.")
                    await call.answer(text, show_alert=True)
            except:
                text = ("❌ Какая-то ошибка. Чтобы принять правила чата, можете "
                        "написать Аюми (боту) в лс.")
                await call.answer(text, show_alert=True)

        # Проверка пароля.
        elif call.data.startswith("hack_"):
            await tg.hack(call, user)

        # Отмена действия.
        elif call.data.startswith("cancel_"):
            if int(call.data.split("_")[1]) != user.user_id:
                await call.answer("❌ Сообщение адресовано не вам", show_alert=True)
                return
            await call.message.delete()

        # Голосование на первом этапе.
        elif call.data.startswith("poll_"):
            await tg.process_vote(call, user)

        # Публикация объявления.
        elif call.data.startswith("create_ad_"):
            await tg.create_ad(call, user, temp_storage)

        # Игра в казино.
        elif call.data.startswith("game_"):
            await tg.show_casino(call, user)

        # Принятие приглашения в группу.
        elif call.data.startswith("joingroup_"):
            await tg.show_group_inviting(call, user, None)

        # Подтверждение исключения участника группы.
        elif call.data.startswith("removemember_"):
            await tg.removing_user_from_group(call, user, BOT_PROFILE)

        elif call.data.startswith("upmybank_") or call.data.startswith("doupmybank_"):
            await tg.mybank_upgrade(call, user)

        elif call.data.startswith("backupgrade_") or call.data.startswith("dobackupgrade_"):
            await tg.back_mybank_upgrading(call, user)

        elif call.data.startswith("upprotect_") or call.data.startswith("doupprotect_"):
            await tg.protect_mybank(call, user)

        # Изменение политики переводов.
        elif call.data.startswith("changepolicy_"):
            person_id = int(call.data.split("_")[-1])

            if person_id != user.user_id:
                await call.answer("❌ Сообщение адресовано не вам", show_alert=True)
                return

            await user.change_policy()

            text = "🏧 Режим переводов изменен"
            await call.message.edit_text(text)

        # Удаление репортов.
        elif call.data.startswith("deletereports_"):
            person_id = int(call.data.split("_")[1])

            if user.user_id != person_id:
                await call.answer("❌ Сообщение адресовано не вам", show_alert=True)
                return

            if not (user.crystals >= config.PRICE_DELETE_REPORTS_CRYSTALS):
                text = (f"❌ У вас не хватает кристаллов для этой операции.\n"
                        f"Требуется: {config.PRICE_DELETE_REPORTS_CRYSTALS} 💎")
                await call.answer(text, show_alert=True)
                return

            reports_deleted = await user.delete_reports()
            if reports_deleted:
                text = (f"☑️ Удалено жалоб: <b>{reports_deleted}</b>\n"
                        f"Списано с баланса: <b>{config.PRICE_UNBANK_CRYSTALS} 💎</b>")
            else:
                text = ("☑️ <b>На вас не было жалоб</b>\n"
                        f"Списано с баланса: <b>{config.PRICE_UNBANK_CRYSTALS} 💎</b>")
            await call.message.edit_text(text, parse_mode=HTML)

        # Переход на разные разделы в  маркете.
        elif (call.data.startswith("buy_crystals_") or call.data.startswith("sell_crystals_") or
              call.data.startswith("getback_crystals_") or call.data.startswith("getback_coins_") or
              call.data.startswith("back_market_") or call.data.startswith("offer_")):
            await tg.process_market_click(call, user)

        elif call.data == "market_info_buy":
            text = ("🛃 Вы можете быстро купить 1 кристалл по нажатию на верхнюю кнопку или "
                    "создать заявку через команду /buy")
            await call.answer(text, show_alert=True)

        elif call.data == "market_info_sell":
            text = ("🛃 Вы можете быстро продать 1 кристалл по нажатию на верхнюю кнопку или "
                    "выставить на продажу через команду /sell")
            await call.answer(text, show_alert=True)

        elif call.data.startswith("answ_"):
            text = ("📨 Чтобы ответить на данное сообщение, смахните его в Telegram влево "
                    "и отправьте команду без указания получателя /msg [ваш текст].")
            await call.answer(text, show_alert=True)

        # Создание новой группы.
        elif call.data.startswith("newgroup_"):
            await tg.show_group_creating(call, user)

        # Переименование группы.
        elif call.data.startswith("renamegroup_"):
            await tg.rename_group(call, user)

        # Просмотр участников группы.
        elif call.data.startswith("memberslist_"):
            await tg.show_group_members(call, user)

        # Запрос / подтверждение на выход из группы.
        # Запрос / Подтвеждение на повышение уровня группы.
        elif (call.data.startswith("exitgroup_") or call.data.startswith("doexitgroup_") or
              call.data.startswith("upgroup_") or call.data.startswith("doupgroup_")):
            await tg.show_user_group(call, user)

        # Удаление группы.
        elif call.data.startswith("removegroup_") or call.data.startswith("doremovegroup_"):
            await tg.removing_group(call, user)

        # Установка / отображение анонимного кода.
        elif (call.data.startswith("dorecreate_msg_code_") or call.data.startswith("recreate_msg_code_") or
              call.data.startswith("create_msg_code_")):
            await tg.control_anon_code(call, user)

        # Снятие монеток со счета в банке.
        elif call.data.startswith("unbank_"):
            await tg.unbank(call, user)

        # Привязка счета к своему акканту.
        elif call.data.startswith("relinkbank_"):
            await tg.relink_bank(call, user)

        # Поменять пароль к счету.
        elif call.data.startswith("changebank_"):
            person_id = int(call.data.split("_")[-1])

            if person_id != user.user_id:
                await call.answer("❌ Сообщение адресовано не вам", show_alert=True)
                return

            text = ("🔑 <b>Смена пароля счета</b>\n"
                    "<u>Описание:</u> Смена пароля для существующего банковского счета.\n"
                    f"Стоимость: {config.PRICE_CHANGE_BANK_CRYSTALS} 💎\n"
                    "<u>Команда:</u> <code>/changebank [старый пароль] [новый пароль]</code>")
            await call.message.edit_text(text, parse_mode=HTML,
                                         reply_markup=keyboards.cancel_menu(user.user_id))

    except Exception as e:
        print(f"INL E: {e}")
        await call.answer("☢️ Программная ошибка [INL], сообщите разработчику @reireireime.", show_alert=True)


@dp.chat_join_request_handler()
async def user_join_request(update: types.ChatJoinRequest):
    """Пользователь подал заявку на вход в чат."""
    try:
        if update.chat.id != config.CHAT_ID:
            return

        user = entities.User(storage, **utils.unpack_message(update))

        if user.user_id == config.ANON_BOT_ID:
            return

        await user.load_from_db()

        # Если пользователь не заблокирован, то принимаем заявку, иначе - отклоняем.
        if user.banned and not user.admin():
            await update.decline()
        else:
            await update.approve()
            # Создаем запись в БД.
            await user.update()

            if not config.DEBUG_MODE:
                notif_text = f"➡️ <b>Заявка принята</b>\n{user}"
                await tg.notify(bot, notif_text)
    except Exception as e:
        print(f"RINV E: {e}")


@dp.message_handler(content_types=[types.ContentType.NEW_CHAT_MEMBERS])
async def user_joined_chat(message: types.Message):
    """Пользователь вступил в чат."""

    try:
        if message.chat.id != config.CHAT_ID:
            return

        user = entities.User(storage, **utils.unpack_message(message))

        if user.user_id == config.ANON_BOT_ID:
            return

        await user.load_from_db()

        if not user.admin():
            # Если пользователь заблокирован в БД.
            if user.banned:
                # Блокируем его в чате.
                await bot.ban_chat_member(config.CHAT_ID, user.user_id)
                return
        try:
            await message.reply(
                f"✋ <b>Добро пожаловать.</b>\n"
                f"Напиши любое сообщение и затем прими правила чата "
                f"в течение {utils.format_time(config.TIME_TO_AGREED)}, чтобы "
                "не быть исключенным.",
                parse_mode=HTML
            )
        except:
            pass

    except Exception as e:
        print(f"INV E: {e}")


@dp.message_handler(content_types=[types.ContentType.LEFT_CHAT_MEMBER])
async def user_left_chat(message: types.Message):
    """Пользователь вышел с чата."""
    try:
        if message.chat.id != config.CHAT_ID:
            return

        user_id = message.left_chat_member.id
        user = entities.User(storage, user_id)
        await user.load_from_db()

        # Блокируем пользователя.
        if not user.admin():
            if not user.banned:
                await bot.ban_chat_member(config.CHAT_ID, user.user_id)

                users = await storage.get_users()
                random_user = random.choice(users)

                to_user = entities.User(storage, random_user["user_id"])
                to_user.load_from_dict(data=random_user)

                await user.pay(user.balance)
                await storage.increase_user_balance(to_user.user_id, user.balance)

                text = (f"⛔️ <b>Пользователь добавлен в ЧС</b>\n{user}\nБаланс: <b>{utils.format_balance(user.balance)} монеток</b>\n\n"
                        f"Причина: вышел из чата.\n\n"
                        f"💸 <b>Баланс переведен случайному участнику</b>\n{to_user}")

                await message.reply(text, parse_mode=HTML)
                await user.ban()

            if not config.DEBUG_MODE:
                notif_text = (f"⬅️ <b>Покинул чат</b>\n{user}\n"
                              f"Баланс: <b>{utils.format_balance(user.balance)} монеток</b>")
                await tg.notify(bot, notif_text)

    except Exception as e:
        print(f"EXT E: {e}")


async def process_chat_tasks():
    time_info = {}

    def can_process(key: str, seconds_cooldown: int, allow_none: bool = False) -> bool:
        now_time = datetime.datetime.now()
        last_time: datetime.datetime = time_info.get(key)

        if not last_time and not allow_none:
            time_info[key] = now_time
            return False

        if not last_time or now_time >= last_time + datetime.timedelta(seconds=seconds_cooldown):
            time_info[key] = now_time
            return True
        return False

    while True:
        try:
            await asyncio.sleep(10)
            if config.DEBUG_MODE:
                print("updated")

            if can_process("clear_inactive", 600) and not config.DEBUG_MODE:
                # Чистим от неактивных пользователей.
                await tg.clear_from_inactive_users(bot, storage)

            elif can_process("clear_disagreed", 600) and not config.DEBUG_MODE:
                # Чистим от пользователей, кто не принял соглашение.
                await tg.clear_from_disagreed_users(bot, storage)

            elif can_process("pay_chat", 180) and not config.DEBUG_MODE:
                now = datetime.datetime.now()

                day = datetime.timedelta(seconds=86400)
                notif_before_time = 3600
                notif_period = datetime.timedelta(seconds=int(notif_before_time))
                notif_period_double = datetime.timedelta(seconds=int(notif_before_time * 2))

                # Проверяем когда было предыдущее списание (timestamp).
                last_paying = await storage.get_temp_storage("lastPaying")
                if config.DEBUG_MODE:
                    print(f"last_paying: {last_paying}")

                # Если прошло больше суток или нет прошлого времени.
                if not last_paying or now >= datetime.datetime.fromtimestamp(int(last_paying)) + day:
                    # Отмечаем новое время.
                    await storage.update_temp_storage("lastPaying", int(now.timestamp()))

                    # Получаем список пользователей.
                    users = await storage.get_users()
                    good = 0
                    bad = 0
                    paid = 0

                    users_will_bad = [1 for u in users if
                                      u['balance'] and u['balance'] < config.PRICE_CHAT_DAILY and not u['team_id']]

                    text = ("☢️ <b>Вот-вот начнётся чистка</b>\n"
                            f"Участников будет проверено: <b>{len(users)}</b>\n"
                            f"Будет удалено: <b>~{len(users_will_bad)}</b>\n\n"
                            f"У вас есть 10 секунд перед её началом. По всем вопросам: @reireireime")
                    await bot.send_message(config.CHAT_ID, text, parse_mode=HTML)
                    await asyncio.sleep(10)

                    for user_note in users:
                        try:
                            user = entities.User(storage, user_note["user_id"], user_note["username"],
                                                 user_note["first_name"], user_note["last_name"])
                            user.balance = user_note["balance"]
                            user.team_id = user_note["team_id"]

                            # Вычисляем сумму сбора.
                            user_fee = utils.calc_daily_fee(user.balance, user.in_group())

                            # Проверяем хватит ли у пользователя баланса.
                            if user.balance >= user_fee:
                                # Списываем сбор.
                                await user.pay(user_fee)
                                good += 1
                                paid += user_fee

                                if config.DEBUG_MODE:
                                    print(f"USER: {user.user_id} - paid")

                            elif not user.in_group():
                                # Исключаем пользователя.
                                await user.ban()
                                try:
                                    await bot.ban_chat_member(config.CHAT_ID, user.user_id)
                                except:
                                    pass

                                await asyncio.sleep(3)
                                text = (
                                    f"⛔️ <b>Пользователь исключен</b>\n{user}\nБаланс: <b>{utils.format_balance(user.balance)} монеток</b>\n\n"
                                    f"Причина: неуплата ежедневного сбора в {utils.format_balance(user_fee)} монеток.")
                                await bot.send_message(config.CHAT_ID, text, parse_mode=HTML)

                                await asyncio.sleep(3)
                                try:
                                    text = (f"⛔️ <b>Вы были исключены из чата</b>\n"
                                            f"Причина: неуплата ежедневного сбора в {utils.format_balance(user_fee)} монеток.")
                                    await bot.send_message(user.user_id, text, parse_mode=HTML)
                                except:
                                    pass
                                bad += 1

                                if config.DEBUG_MODE:
                                    print(f"USER: {user.user_id} - banned from paying")
                        except Exception as ee:
                            await bot.send_message(config.ADMIN_ID, f"[цикл2]: {ee}")

                    text = ("📝 <b>Ежедневное списание сбора завершено</b>\n"
                            f"Всего было списано: <b>{utils.format_balance(int(paid))} 🪙</b>\n"
                            f"Оплативших сбор: <b>{good}</b>\n"
                            f"Исключенных: <b>{bad}</b>\n\n"
                            f"По всем вопросам: @reireireime")
                    await bot.send_message(config.CHAT_ID, text, parse_mode=HTML)

                elif now >= datetime.datetime.fromtimestamp(int(last_paying)) + day - notif_period:
                    # Проверяем когда было предыдущее уведомление (timestamp).
                    last_paying_notif = await storage.get_temp_storage("lastPayingNotif")

                    if config.DEBUG_MODE:
                        print(f"last_paying_notif: {last_paying_notif}")

                    if not last_paying_notif or now >= datetime.datetime.fromtimestamp(
                            int(last_paying_notif)) + notif_period_double:
                        # Отмечаем новое время.
                        await storage.update_temp_storage("lastPayingNotif", int(now.timestamp()))
                        seconds_left = (datetime.datetime.fromtimestamp(int(last_paying)) + day - now).seconds

                        # Уведомляем пользователей.
                        text = ("🛂 <b>Скоро произойдет ежедневное списание</b>\n"
                                f"Каждые 24 часа с баланса каждого пользователя списывается <b>{config.FEE_CHAT_DAILY}%</b>, но не менее "
                                f"<b>{config.PRICE_CHAT_DAILY} монеток</b>. Если пользователь состоит в группе, то "
                                f"с него будет списываться только налог, превышающий минимальный.\n\n"
                                f"⚠️ Если на этот момент пользователь будет не в силах оплатить налог, то "
                                f"он будет <b>навсегда исключен из чата</b>. Убедитесь, что вы в состоянии оплатить сбор. "
                                f"По всем вопросам: @reireireime\n\n"
                                f"Cписание состоится через: <b>{utils.format_time(seconds_left)}</b>")
                        await bot.send_message(config.CHAT_ID, text, parse_mode=HTML)

            elif can_process("get_lucky_crystals", 600) and not config.DEBUG_MODE:
                try:
                    now = datetime.datetime.now()
                    last_controlling = await storage.get_temp_storage("lastGetLuckyCrystals")
                    day = datetime.timedelta(seconds=86400)

                    # Если прошло больше суток или нет прошлого времени.
                    if not last_controlling or now >= datetime.datetime.fromtimestamp(int(last_controlling)) + day:

                        # Отмечаем новое время.
                        await storage.update_temp_storage("lastGetLuckyCrystals", int(now.timestamp()))

                        if random.randint(1, 4) == 2:
                            text = (f"🍀 <b>Ежедневная раздача</b>\n"
                                    f"Ой, не повезло. Сегодня раздачи не будет.")
                            await bot.send_message(config.CHAT_ID, text, parse_mode=HTML)
                            return

                        users = await storage.get_users()

                        users_count = len(users)
                        if users_count > config.LUCKY_USERS_MAX:
                            users_count = config.LUCKY_USERS_MAX

                        lucky_users_count = random.randint(1, users_count)
                        crystals_per_user_max = config.LUCKY_CRYSTALS_PER_USER_COUNT_MAX

                        text = (f"🍀 <b>Ежедневная раздача</b>\n"
                                f"Через несколько секунд <b>{lucky_users_count}</b> случайных пользователей "
                                f"чата получат случайное количество кристаллов\n\n"
                                f"По всем вопросам: @reireireime")
                        await bot.send_message(config.CHAT_ID, text, parse_mode=HTML)

                        await asyncio.sleep(5)

                        spread_crystals = 0
                        # Получаем список счастливых пользователей.
                        lucky_users = (await storage.get_random_users(lucky_users_count))[:]
                        for user in lucky_users:
                            crystals_per_user = random.randint(1, crystals_per_user_max)
                            spread_crystals += crystals_per_user
                            await storage.add_user_crystals(user['user_id'], crystals_per_user)
                            try:
                                text = ("🎉 <b>Ваш баланс пополнен</b>\n"
                                        f"Поздравляем! Вам начислено <b>{crystals_per_user}</b> 💎 "
                                        f"с ежедневной раздачи.")
                                await bot.send_message(user['user_id'], text, parse_mode=HTML)
                            except:
                                pass
                            await asyncio.sleep(3)

                        text = (f"🎉 Раздача окончена! Было раздано "
                                f"<b>{int(spread_crystals)} 💎</b>. Проверьте сообщения от Аюми.")
                        await bot.send_message(config.CHAT_ID, text, parse_mode=HTML)
                except Exception as e:
                    await bot.send_message(config.ADMIN_ID, f"[цикл-раздача]: {e}")

            elif can_process("groups_control", 600) and not config.DEBUG_MODE:
                now = datetime.datetime.now()
                last_controlling = await storage.get_temp_storage("lastGroupControl")
                day = datetime.timedelta(seconds=86400)

                if config.DEBUG_MODE:
                    print(f"last_controlling: {last_controlling}")

                # Если прошло больше суток или нет прошлого времени.
                if not last_controlling or now >= datetime.datetime.fromtimestamp(int(last_controlling)) + day:

                    # Отмечаем новое время.
                    await storage.update_temp_storage("lastGroupControl", int(now.timestamp()))

                    # Получаем список группы.
                    groups_list = await storage.get_groups()

                    if not groups_list:
                        continue

                    total_members = 0  # Общее количество участников
                    members_paid = 0  # Сумма платежей участников группы лидеру.
                    leaders_paid = 0  # Сумма платежей (штрафов) со стороны лидера.

                    members_good = 0  # Количество участников, которые оплатили взнос.
                    members_bad = 0  # Количество участников, которые НЕ оплатили взнос.
                    members_poor = 0  # Количество участников, за которых начисляется штраф (низкий баланс).

                    text = ("📖 <b>Начинается списания взносов в группах</b>\n"
                            f"Групп будет обработано: <b>{len(groups_list)}</b>\n\n"
                            f"По всем вопросам: @reireireime")
                    await bot.send_message(config.CHAT_ID, text, parse_mode=HTML)
                    await asyncio.sleep(3)

                    for group_info in groups_list:
                        try:
                            group = entities.Group(storage, group_info['team_id'])
                            group.load_from_dict(group_info)

                            # Загружаем информацию о пользователях группы.
                            await group.update_members()

                            # Получаем величину взноса в группу.
                            tax = int(group.tax)
                            # Вычисляем сумму штрафа.
                            fine_from_tax = int(group.tax * 1.1)

                            assert tax >= config.PRICE_GROUP_DAILY, f'Неправильный налог для группы: {tax}'
                            assert group.leader_id, f'Отсутствует лидер у группы: {group.group_id}'

                            group_members_paid = 0  # Сумма платежей участников группы лидеру.
                            group_leaders_paid = 0  # Сумма платежей (штрафов) со стороны лидера.

                            group_members_good = 0  # Количество участников, которые оплатили взнос.
                            group_members_bad = 0  # Количество участников, которые НЕ оплатили взнос.
                            group_members_poor = 0  # Количество участников, за которых начисляется штраф (низкий баланс).

                            # Получаем лидера группы.
                            leader = await group.get_leader()

                            for member_info in group.members:
                                member = entities.User(storage, user_id=member_info['user_id'])
                                member.load_from_dict(member_info)

                                # Если участник не является лидером группы.
                                if member.user_id != group.leader_id:
                                    try:
                                        # Проверяем хватит ли у пользователя баланса.
                                        if member.balance >= tax:
                                            # Списываем сумму взноса.
                                            await member.pay(tax)
                                            # Начисляем его лидеру.
                                            await leader.earn(tax)
                                            # Регистриуем оплату пользователя.
                                            await storage.add_payment(member.user_id, group.leader_id,
                                                                      db.PaymentType.group_member_tax,
                                                                      tax, db.Currency.coins)
                                            group_members_paid += tax
                                            group_members_good += 1
                                        else:
                                            group_members_bad += 1

                                        # Увеличиваем сумму штрафа, если у пользователя меньше {MIN_MEMBER_BALANCE} (1000 монеток).
                                        if member.balance < config.MIN_MEMBER_BALANCE:
                                            group_members_poor += 1
                                            # Увеличиваем сумму штрафа на fine_from_tax (110% от tax).
                                            group_leaders_paid += fine_from_tax

                                    except Exception as e:
                                        await bot.send_message(config.ADMIN_ID, f"[цикл-группа-участник]: {e}")

                            # Списываем штраф с лидера, если он есть.
                            if group_leaders_paid > 0:
                                fine = leader.balance if group_leaders_paid > leader.balance else group_leaders_paid
                                fine = int(fine)
                            else:
                                fine = 0

                            if fine:
                                await leader.pay(fine)
                                await storage.add_payment(leader.user_id, None, db.PaymentType.group_leader_fine,
                                                          fine, db.Currency.coins)

                            profit = int(group_members_paid - fine)

                            # Начисляем общие характеристики.
                            total_members += (len(group.members) - 1)
                            members_paid += group_members_paid  # Сумма платежей участников группы лидеру.
                            leaders_paid += fine  # Сумма платежей (штрафов) со стороны лидера.

                            members_good += group_members_good  # Количество участников, которые оплатили взнос.
                            members_bad += group_members_bad  # Количество участников, которые НЕ оплатили взнос.
                            members_poor += group_members_poor  # Количество участников, за которых начисляется штраф (низкий баланс).

                            # Формируем уведомление для лидера.
                            text = ("📁 <b>Отчет о списаниях взноса</b>\n"
                                    f"Всего участников: <b>{len(group.members)}</b>\n\n"
                                    f"Оплатили взнос: <b>{int(group_members_bad)}</b>\n"
                                    f"Не смогли оплатить взнос: <b>{int(group_members_bad)}</b>\n"
                                    f"С низким балансом: <b>{int(group_members_poor)}</b>\n\n"
                                    f"Начислено: <b>{int(group_members_paid)}</b> 🪙\n"
                                    f"Списано штрафов: -<b>{int(fine)}</b> 🪙\n"
                                    f"Итого: <b>{profit}</b> 🪙")
                            try:
                                await bot.send_message(leader.user_id, text, parse_mode=HTML)
                            except:
                                pass
                            await asyncio.sleep(3)
                        except Exception as e:
                            await bot.send_message(config.ADMIN_ID, f"[цикл-группа]: {e}")

                    # Формируем уведомление в чат.
                    text = ("🗄️ <b>Списания взносов завершено</b>\n"
                            f"Всего участников: <b>{int(total_members)}</b>\n\n"
                            f"Оплатили взнос: <b>{int(members_good)}</b>\n"
                            f"Не смогли оплатить взнос: <b>{int(members_bad)}</b>\n"
                            f"С низким балансом: <b>{int(members_poor)}</b>\n\n"
                            f"Начислено лидерам: <b>{int(members_paid)}</b> 🪙\n"
                            f"Списано штрафов лидерам: -<b>{int(leaders_paid)}</b> 🪙\n"
                            f"Общая выручка: <b>{int(members_paid - leaders_paid)}</b> 🪙\n\n"
                            f"По всем вопросам: @reireireime")
                    await bot.send_message(config.CHAT_ID, text, parse_mode=HTML)

        except Exception as e:
            await bot.send_message(config.ADMIN_ID, f"[цикл]: {e}")


async def start_chat_tasks(_):
    global BOT_PROFILE
    BOT_PROFILE = await bot.get_me()
    asyncio.create_task(process_chat_tasks())


if __name__ == '__main__':
    executor.start_polling(dp, on_startup=start_chat_tasks)
