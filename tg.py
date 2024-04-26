import asyncio

import datetime

import aiofiles
import aiogram
from aiogram import Bot, types

import config
import utils
import db
import entities
import keyboards

HTML = "html"

lock_market = asyncio.Lock()


async def notify(bot: aiogram.Bot, text: str):
    try:
        if config.LOGS_CHANNEL_ID:
            await bot.send_message(config.LOGS_CHANNEL_ID, text, parse_mode=HTML)
    except:
        pass


async def relink_bank(event: types.CallbackQuery, user: entities.User):
    person_id = int(event.data.split("_")[1])
    password = event.data.split("_")[2]

    if person_id != user.user_id:
        await event.answer("❌ Сообщение адресовано не вам", show_alert=True)
        return

    if not (user.crystals >= config.PRICE_LINK_CRYSTALS):
        text = (f"❌ У вас не хватает кристаллов для этой операции\n"
                f"Требуется: {config.PRICE_LINK_CRYSTALS} 💎.")
        await event.answer(text, show_alert=True)
        return

    user_banks = await user.get_banks()
    if len(user_banks) >= config.MAX_BANKS_COUNT:
        text = (f"❌ Нельзя создать больше {config.MAX_BANKS_COUNT} банковских счетов. \n"
                f"Обналичьте один существующий счет, чтобы создать новый.")
        await event.answer(text, show_alert=True)
        return

    relinked_bank = await user.relink_bank(password)
    if relinked_bank:
        text = "☑️ Счет успешно привязан к вашему аккаунту"
        await event.message.edit_text(text)

        try:
            owner_id: int = relinked_bank['user_id']
            if owner_id != user.user_id:
                text_2 = ("⚠️ <b>Кто-то перепривязал ваш счет</b>\n"
                          f"Номер счета: <b>{relinked_bank['account_id']}</b>")
                await event.bot.send_message(owner_id, text_2, parse_mode=HTML)
        except:
            ...

    else:
        text = "❌ Не удалось привязать счет"
        await event.message.edit_text(text)


async def unbank(event: types.CallbackQuery, user: entities.User):
    person_id = int(event.data.split("_")[1])
    password = event.data.split("_")[2]

    if person_id != user.user_id:
        await event.answer("❌ Сообщение адресовано не вам", show_alert=True)
        return

    if user.balance >= config.PRICE_UNBANK:
        if not (user.crystals >= config.PRICE_UNBANK_CRYSTALS):
            text = (f"❌ У вас не хватает кристаллов для этой операции\n"
                    f"Требуется: {config.PRICE_UNBANK_CRYSTALS} 💎.")
            await event.answer(text, show_alert=True)
            return

    fee = utils.calc_fee(user.balance, config.FEE_UNBANK, config.PRICE_UNBANK)
    bank_result = await user.unbank(password, fee)

    if bank_result:
        owner_id = bank_result['user_id']
        owner = await entities.get_user_by_id(user.get_storage(), owner_id)

        start_sum: int = bank_result['balance']
        now_sum: int = bank_result['unbankSum']
        bank_id: int = bank_result['account_id']

        created_time: datetime.datetime = bank_result['created']
        time_passed: int = int(datetime.datetime.now().timestamp() - created_time.timestamp())
        show_time = utils.format_time(time_passed)

        text = (f"💸 <b>Счёт успешно обналичен</b>\n"
                f"ID счета: <code>{bank_id}</code>\n"
                f"Пароль: <code>{password}</code>\n"
                f"При открытии: <b>{utils.format_balance(start_sum)} 🪙</b>\n"
                f"Сейчас: <b>{utils.format_balance(now_sum)} 🪙</b>\n"
                f"Прошло: <i>{show_time}</i>\n\n"
                f"👤 <b>Владелец счета</b>\n{owner}")
        await event.message.edit_text(text, parse_mode=HTML)

        try:
            if bank_result['user_id'] != user.user_id:
                text_2 = ("⚠️ <b>Кто-то снял монетки со счета</b>\n"
                          f"Номер счета: <b>{bank_result['account_id']}</b>\n"
                          f"При открытии: <b>{utils.format_balance(bank_result['balance'])} 🪙</b>\n"
                          f"Итог: <b>{utils.format_balance(bank_result['unbankSum'])} 🪙</b>\n"
                          f"Пароль: <tg-spoiler>***{bank_result['a_password'][-2:]}</tg-spoiler>")
                await event.bot.send_message(bank_result['user_id'], text_2, parse_mode=HTML)
        except:
            ...

    else:
        text = ("❌ <b>Банковского счета с таким паролем не существует</b>\n"
                f"В качестве компенсации банк списал с вашего баланса <b>{fee} монеток</b>")
        await event.message.edit_text(text, parse_mode=HTML)


async def complete_offers(storage: db.Storage, bot: Bot):
    # Получаем все предложения с маркета.
    offers = await storage.get_market_offers()

    sell_offers = offers["sell"]
    buy_offers = offers["buy"]

    # Перебираем заявки на покупку, начиная с самой большой стоимости.
    for buy_offer in buy_offers:
        # Перебираем предложения на продажу, начиная с самой маленькой стоимости.
        for sell_offer in sell_offers:

            # Пропускаем пустые ордера.
            if not (sell_offer['crystals'] > 0 and buy_offer['crystals'] > 0):
                continue

            # Пропускаем, если UID совпадают.
            if sell_offer['user_id'] == buy_offer['user_id']:
                continue

            # Цена покупки больше или равна продажи.
            if buy_offer['price'] >= sell_offer['price']:
                # Кристаллов нужно купить.
                need_crystals_to_buy = buy_offer['crystals']
                # Кристаллов продаётся.
                can_buy_crystals = sell_offer['crystals']

                # Вычисляем сколько кристаллов покупаем по этому ордеру.
                crystals_to_buy = min([need_crystals_to_buy, can_buy_crystals])
                # Цену покупки.
                price = sell_offer['price']
                # Максимальная цена для покупки.
                max_price = buy_offer['price']
                # Общая стоимость.
                cost = int(price * crystals_to_buy)

                # Изменяем ордеры.
                buy_offer['crystals'] = int(buy_offer['crystals'] - crystals_to_buy)
                sell_offer['crystals'] = int(sell_offer['crystals'] - crystals_to_buy)

                # Записываем, чтобы изменить в БД.
                await storage.update_offer(buy_offer)
                await storage.update_offer(sell_offer)

                # Покупатель. Выдаем кристалл.
                await storage.add_user_crystals(buy_offer['user_id'], crystals_to_buy)

                # Если купили выгоднее, то возвращаем монетки.
                coins_back = int((max_price - price) * crystals_to_buy)
                if coins_back:
                    await storage.increase_user_balance(buy_offer['user_id'], coins_back)

                # Продавец. Увеличиваем баланс.
                await storage.increase_user_balance(sell_offer['user_id'], cost)

                # Регистрируем операции.
                for _ in range(crystals_to_buy):
                    await storage.add_payment(buy_offer['user_id'], sell_offer['user_id'],
                                              db.PaymentType.market, price, db.Currency.coins)

                # Уведомляем.
                # Покупатель.
                text = (f"💎 <b>Вы купили кристаллы</b>\n"
                        f"Количество: <b>{crystals_to_buy} 💎</b>\n"
                        f"Цена за кристалл: <b>{price} 🪙</b>")
                if coins_back:
                    text += (f"\nВозвращено: <b>{coins_back} 🪙</b>\n\n"
                             f"🎉 <i>Покупка обошлась дешевле</i>")

                try:
                    await bot.send_message(buy_offer['user_id'], text, parse_mode=HTML)
                except:
                    pass

                # Продавец.
                text = (f"💰 <b>Вы продали кристаллы</b>\n"
                        f"Количество: <b>{crystals_to_buy} 💎</b>\n"
                        f"Цена за кристалл: <b>{price} 🪙</b>\n"
                        f"Итого: <b>+{cost} 🪙</b>")
                try:
                    await bot.send_message(sell_offer['user_id'], text, parse_mode=HTML)
                except:
                    pass

                # В чат.
                text = ("🤝 <b>Новая сделка на бирже</b>\n"
                        f"Продано: <b>{utils.format_balance(crystals_to_buy)} 💎</b>\n"
                        f"Цена за кристалл: <b>{utils.format_balance(price)} 🪙</b>\n"
                        f"Сумма сделки: <b>{utils.format_balance(cost)} 🪙</b>")
                try:
                    await bot.send_message(config.CHAT_ID, text, parse_mode=HTML)
                except:
                    pass


async def process_market_click(call: types.CallbackQuery, user: entities.User):
    person_id = int(call.data.split("_")[-1])

    if person_id != user.user_id:
        text = "❌ Сообщение адресовано не вам"
        await call.answer(text, show_alert=True)
        return

    if call.data.startswith("back_market_"):
        await show_market(call, user)

    elif call.data.startswith("getback_crystals_"):
        returned_crystals = await user.return_crystals()
        if returned_crystals:
            text = f"☑️ Возвращено с биржи кристаллов: {returned_crystals}"
        else:
            text = "ℹ️ У вас нет кристаллов на бирже"
        await call.answer(text, show_alert=True)

    elif call.data.startswith("getback_coins_"):
        returned_coins = await user.return_coins()
        if returned_coins:
            text = f"☑️ Возвращено с биржи: {utils.format_balance(returned_coins)} 🪙"
        else:
            text = "ℹ️ У вас нет монеток на бирже"
        await call.answer(text, show_alert=True)

    elif call.data.startswith("buy_crystals_") or call.data.startswith("sell_crystals_"):
        buy_mode = call.data.startswith("buy_crystals_")

        offers_list = await user.get_storage().get_market_offers()
        if buy_mode:
            offers = offers_list["sell"]
        else:
            offers = offers_list["buy"]

        if buy_mode:
            text = ("💸 <b>Покупка кристаллов</b>\n\n"
                    "Ниже отображаются выставленные на продажу кристаллы. Вы можете "
                    "быстро купить 1 кристалл по нажатию на верхнюю кнопку за самую выгодную цену "
                    "на данный момент или создать заявку на покупку по своей цене:\n"
                    "<code>/buy [кол-во] [цена за шт]</code>")
        else:
            text = ("💰 <b>Продажа кристаллов</b>\n\n"
                    "Ниже отображаются заявки на покупку кристаллов. Вы можете "
                    "быстро продать 1 кристалл по нажатию на верхнюю кнопку за самую выгодную цену "
                    "на данный момент или выставить свои кристаллы на продажу по своей цене:\n"
                    "<code>/sell [кол-во] [цена за шт]</code>")
        await call.message.edit_text(text, parse_mode=HTML, reply_markup=keyboards.market_offers_menu(user.user_id,
                                                                                                      offers))

    elif call.data.startswith("offer_"):
        try:
            # Получаем информацию об ордере.
            offer_id = int(call.data.split("_")[1])
            offer = await user.get_storage().get_market_offer(offer_id)

            assert offer and offer['crystals'], "Предложение устарело"
            assert offer_id == offer["offer_id"], "Некорректный ID заявки"

            owner_id: int = offer["user_id"]
            crystals: int = offer["crystals"]
            price: int = offer["price"]
            direction: str = offer["direction"]  # sell, buy

            assert direction in ("sell", "buy"), "Некорректное направление заявки"
            assert price and crystals, "Пустая заявка"
            assert user.user_id != owner_id, "Нельзя взаимодействовать со своей же заявкой"

            if direction == "sell":
                # Пользователь покупает кристалл.
                assert user.balance >= price, "Недостаточно монеток на балансе"

            else:
                # Пользователь продаёт кристалл.
                assert user.crystals >= 1, "Недостаточно кристаллов на балансе"

            buy_crystal_confirm_cooldown = 5
            cooldown_name = f"buyCrystalOfferId{offer_id}"
            if user.cooldown(cooldown_name, buy_crystal_confirm_cooldown):
                await call.answer(
                    f"🆗 Подтвердите покупки вторым нажатием в течение {buy_crystal_confirm_cooldown} секунд")
                return
            user.reset_value(cooldown_name)

            if direction == "sell":
                # Пользователь покупает кристалл.
                await user.buy_crystals(1, price)
                text = (f"Вы создали заявку на покупку 1 💎 за {price} 🪙\n"
                        f"Аюми оповестит вас в лс, как только ваш запрос будет выполнен.")
            else:
                # Пользователь продаёт кристалл.
                await user.sell_crystals(1, price)
                text = (f"Вы создали заявку на продажу 1 💎 за {price} 🪙\n"
                        f"Аюми оповестит вас в лс, как только ваш запрос будет выполнен.")
            await call.answer(text, show_alert=True)

            async with lock_market:
                # Запускаем обработку всех заявок.
                await complete_offers(user.get_storage(), call.bot)

                # Обновляем сообщение.
                call.data = f"buy_crystals_{user.user_id}" if direction == "sell" else f"sell_crystals_{user.user_id}"
                await process_market_click(call, user)

        except Exception as e:
            await call.answer(f"❌ {e}", show_alert=True)


async def show_market(event: types.Message | types.CallbackQuery, user: entities.User):
    if isinstance(event, types.CallbackQuery):
        person_id = int(event.data.split("_")[-1])

        if person_id != user.user_id:
            text = "❌ Сообщение адресовано не вам"
            await event.answer(text, show_alert=True)
            return

    offers = await user.get_storage().get_market_offers()

    sell_offers = offers["sell"]
    buy_offers = offers["buy"]

    # Вычисляем характеристики.
    min_sell_price = min([o['price'] for o in sell_offers]) if sell_offers else '-'
    sell_offers_crystals = sum([o['crystals'] for o in sell_offers])

    max_buy_price = max([o['price'] for o in buy_offers]) if buy_offers else '-'
    buy_offers_crystals = sum([o['crystals'] for o in buy_offers])

    text = (f"💎 <b>Биржа кристаллов</b>\n\n"
            f"<u>Купить кристаллы</u>\n"
            f"Выставлено на продажу: <b>{utils.format_balance(sell_offers_crystals)} 💎</b>\n"
            f"Самое выгодное: <b>{utils.format_balance(min_sell_price)} 🪙</b>\n\n"
            f"<u>Продать кристаллы</u>\n"
            f"Спрос для покупку: <b>{utils.format_balance(buy_offers_crystals)} 💎</b>\n"
            f"Самое выгодное: <b>{utils.format_balance(max_buy_price)} 🪙</b>\n\n"
            f"<u>Выставление заявок на бирже</u>\n"
            f"Создать заявку на покупку:\n<code>/buy [кол-во] [цена за шт]</code>\n"
            f"Выставить на продажу:\n<code>/sell [кол-во] [цена за шт]</code>")

    rpl = keyboards.market_menu(user.user_id)
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, parse_mode=HTML, reply_markup=rpl)
    else:
        await event.reply(text, parse_mode=HTML, reply_markup=rpl)


async def process_market_command(message: types.Message, user: entities.User):
    try:
        cm = message.text.split()[0]
        crystals = message.text.split()[1]
        price = message.text.split()[2]

        assert cm in ("/buy", "/sell"), "Неверная команда"
        assert crystals.isdigit(), "Количество кристаллов должно быть числом"
        assert price.isdigit(), "Цена должна быть числом"

        crystals = int(crystals)
        price = int(price)

        assert 1 <= crystals <= config.MAX_INT_UNSIGNED, "Количество кристаллов должно быть от 1 до 4.2 млрд"
        assert 1 <= price <= config.MAX_INT_UNSIGNED, "Цена должна быть от 1 до 4.2 млрд монеток"

        assert (await user.can_send()), ("<b>Вы не можете покупать/продавать кристаллы</b>\n"
                                         f"С момента начала голосования по вашему вопросу "
                                         f"не прошло {utils.format_time(config.TIME_TO_POLL)}")

        if cm == "/buy":
            now_in_market = (await user.get_market_crystals_count())["buy"]
            assert crystals + now_in_market <= config.MAX_MARKET_BUY_CRYSTALS, (
                "Вы не можете оставить заявок на покупку "
                f"более чем <b>{config.MAX_MARKET_BUY_CRYSTALS} 💎</b>")

            # Выставляем заявку на покупку кристаллов.
            cost = int(price * crystals)
            assert user.balance >= cost, "У вас не хватает монеток"
            await user.buy_crystals(crystals, price)

            text = (f"📝 <b>Заявка на покупку создана</b>\n"
                    f"Количество: <b>{utils.format_balance(crystals)} 💎</b>\n"
                    f"Цена за кристалл: <b>{utils.format_balance(price)} 🪙</b>\n"
                    f"Для покупки заморожено: <b>{utils.format_balance(cost)} 🪙</b>")

        else:
            # Выставляем кристаллы на продажу.
            assert user.crystals >= crystals, "У вас не хватает кристаллов"
            await user.sell_crystals(crystals, price)

            text = (f"☑️ <b>Кристаллы выставлены на продажу</b>\n"
                    f"Количество: <b>{utils.format_balance(crystals)} 💎</b>\n"
                    f"Цена за кристалл: <b>{utils.format_balance(price)} 🪙</b>")

        await message.answer(text, parse_mode=HTML)
        async with lock_market:
            await complete_offers(user.get_storage(), message.bot)

    except Exception as e:
        await message.answer(f"❌ {e}", parse_mode=HTML)


async def group_tax_control(event: types.Message, user: entities.User):
    group = user.get_group()
    if not group.exists():
        text = "ℹ️ Вы не состоите в какой-либо группе"
        await event.answer(text, parse_mode=HTML)
        return

    if not (await group.is_leader(user.user_id)):
        text = "❌ Вы не являетесь лидером группы"
        await event.answer(text, parse_mode=HTML)
        return

    new_tax_string = event.text.split()[1]
    if not new_tax_string.isdigit():
        text = f"❌ Сумма взноса должна быть целым числом от {config.PRICE_GROUP_DAILY} до 4.2 млрд"
        await event.answer(text, parse_mode=HTML)
        return

    new_tax = int(new_tax_string)
    if not (config.PRICE_GROUP_DAILY <= new_tax <= config.MAX_INT_UNSIGNED):
        text = f"❌ Сумма взноса должна быть целым числом от {config.PRICE_GROUP_DAILY} до 4.2 млрд"
        await event.answer(text, parse_mode=HTML)
        return

    old_tax = await group.get_tax()
    # Обновляем взнос в группе.
    await group.set_tax(new_tax)
    text = ("🆗 <b>Сумма взноса изменена</b>\n"
            f"Значение: <b>{old_tax} -> {new_tax} 🪙</b>\n\n"
            f"📞 <i>Не забудьте оповестить участников группы об этом</i>")
    await event.answer(text, parse_mode=HTML)


async def create_ad(event: types.CallbackQuery, user: entities.User, temp_storage: entities.TempStorage):
    protect_client_id = int(event.data.split("_")[-1])

    if user.user_id != protect_client_id:
        text = "❌ Сообщение адресовано не вам"
        await event.answer(text, show_alert=True)
        return

    if user.balance < config.PRICE_POST_AD:
        text = "❌ Недостаточно средств на балансе"
        await event.answer(text, show_alert=True)
        return

    ad_text: str | None = temp_storage.value(user, "adText")
    temp_storage.reset(user)
    if not ad_text:
        text = "❌ Текст объявления не был найден"
        await event.answer(text, show_alert=True)
        return

    await user.post_ad(ad_text)
    text = (f"📰 <b>Новое анонимное объявление</b>\n\n{ad_text}\n\n"
            f"<i>Объявление опубликовано участником проекта и не относится каким-либо "
            f"образом к администрации.</i>")
    await event.bot.send_message(config.CHAT_ID, text, parse_mode=HTML, disable_web_page_preview=True)

    text = f"📰 <b>Объявление опубликовано</b>\n\n{ad_text}"
    await event.message.edit_text(text, parse_mode=HTML, disable_web_page_preview=True)


async def protect_mybank(event: types.CallbackQuery, user: entities.User):
    protect_client_id = int(event.data.split("_")[1])

    if user.user_id != protect_client_id:
        text = "❌ Сообщение адресовано не вам"
        await event.answer(text, show_alert=True)
        return

    group = user.get_group()
    group_level = await group.get_level()

    # Вычисляем стоимость повышения.
    protection_level = user.protect_level
    price = utils.calc_upgrade_hack_protect_price(protection_level)
    # Вычисляем текущий и следующий шанс взлома.
    now_hack_percentage = utils.calc_hack_percentage(protection_level, group_level)
    then_hack_percentage = utils.calc_hack_percentage(int(protection_level + 1), group_level)

    if now_hack_percentage <= 3:
        text = "❌ Вы достигли максимальной стадии улучшения защиты"
        await event.answer(text, show_alert=True)
        return

    if event.data.startswith("upprotect_"):
        text = ("🛡️ <b>Подтвердите покупку улучшения</b>\n"
                f"Текущих уровень защиты: <b>{protection_level}</b>\n"
                f"Шанс успешного подбора: <b>{now_hack_percentage}%</b>\n\n"
                f"Будет улучшено до: <b>{then_hack_percentage}%</b>\n"
                f"Стоимость улучшения: <b>{price} 💎</b>\n\n"
                f"🔖 <i>Шанс успешного подбора означает, что с этим шансом при попытке "
                f"подбора пароля через /hack у хакера <u>не</u> всплывёт ошибка помехи.</i>")
        await event.message.edit_text(text, parse_mode=HTML,
                                      reply_markup=keyboards.up_protect_menu(user.user_id))

    elif event.data.startswith("doupprotect_"):

        if not (user.crystals >= price):
            text = "❌ На вашем балансе недостаточно кристаллов"
            await event.answer(text, show_alert=True)
            return

        await user.upgrage_protection(price)

        text = ("🛡 <b>Защита банка повышена</b>\n"
                f"Измение: <b>{now_hack_percentage} -> {then_hack_percentage} %</b>\n"
                f"Списано с баланса: <b>{price} 💎</b>")
        await event.message.edit_text(text, parse_mode=HTML)


async def back_mybank_upgrading(event: types.CallbackQuery, user: entities.User):
    bank_client_id = int(event.data.split("_")[1])

    if user.user_id != bank_client_id:
        text = "❌ Сообщение адресовано не вам"
        await event.answer(text, show_alert=True)
        return

    if not user.extra_percent:
        text = "❌ Улучшения отсутствуют"
        await event.answer(text, show_alert=True)
        return

    # Вычисляем стоимость текущего повышения.
    now_percent_wo_group = await user.get_bank_percent(including_group=False)
    now_percent = await user.get_bank_percent(including_group=True)

    price = int(utils.calc_upgrade_mybank_price(now_percent_wo_group - 1) / 1.5)
    if price < 1:
        price = 1

    if event.data.startswith("backupgrade_"):
        text = ("🏦 <b>Подтвердите откат улучшения</b>\n"
                f"Текущих процент: <b>{now_percent} %</b>\n"
                f"Будет уменьшен до: <b>{int(now_percent - 1)}%</b>\n"
                f"Начислится на баланс: <b>{price} 💎</b>")
        await event.message.edit_text(text, parse_mode=HTML,
                                      reply_markup=keyboards.back_upgrading_mybank_menu(user.user_id))

    elif event.data.startswith("dobackupgrade_"):

        await user.deupgrade_bank(price)

        text = ("🏦 <b>Ваш процент в банке понижен</b>\n"
                f"Измение: <b>{now_percent} -> {int(now_percent - 1)} %</b>\n"
                f"Начислено на баланс: <b>{price} 💎</b>")
        await event.message.edit_text(text, parse_mode=HTML)


async def mybank_upgrade(event: types.CallbackQuery, user: entities.User):
    bank_client_id = int(event.data.split("_")[1])

    if user.user_id != bank_client_id:
        text = "❌ Сообщение адресовано не вам"
        await event.answer(text, show_alert=True)
        return

    # Вычисляем стоимость повышения.
    now_percent_wo_group = await user.get_bank_percent(including_group=False)
    now_percent = await user.get_bank_percent(including_group=True)
    price = utils.calc_upgrade_mybank_price(now_percent_wo_group)

    if event.data.startswith("upmybank_"):
        # upmybank_{user_id}

        text = ("🏦 <b>Подтвердите покупку улучшения</b>\n"
                f"Текущих процент: <b>{now_percent} %</b>\n"
                f"Будет улучшено до: <b>{int(now_percent + 1)}%</b>\n"
                f"Стоимость улучшения: <b>{price} 💎</b>")
        await event.message.edit_text(text, parse_mode=HTML,
                                      reply_markup=keyboards.mybank_menu(user.user_id, True))

    elif event.data.startswith("doupmybank_"):
        # doupmybank_{user_id}

        if not (user.crystals >= price):
            text = "❌ На вашем балансе недостаточно кристаллов"
            await event.answer(text, show_alert=True)
            return

        await user.upgrade_bank(price)

        text = ("🏦 <b>Ваш процент в банке повышен</b>\n"
                f"Измение: <b>{now_percent} -> {int(now_percent + 1)} %</b>\n"
                f"Списано с баланса: <b>{price} 💎</b>")
        await event.message.edit_text(text, parse_mode=HTML)


async def removing_user_from_group(event: types.Message | types.CallbackQuery, user: entities.User,
                                   bot_profile: aiogram.types.User):
    if isinstance(event, types.Message):
        search_text = event.text.split()[1]

        group = user.get_group()
        if not group.exists():
            text = "❌ Вы не состоите в какой-либо группе"
            await event.answer(text, parse_mode=HTML)
            return

        await group.update()
        if not (await group.is_leader(user.user_id)):
            text = "❌ Вы не являетесь лидером вашей группы"
            await event.answer(text, parse_mode=HTML)
            return

        if utils.is_msg_code(search_text):
            text = "❌ Нельзя исключать из группы по анонимному коду"
            await event.answer(text, parse_mode=HTML)
            return

        to_user = await search_user(user.get_storage(), event, search_text, True, bot_profile)
        if to_user:
            if to_user.user_id == user.user_id:
                text = "❌ Нельзя исключить себя из группы"
                await event.answer(text, parse_mode=HTML)
                return

            if not (await group.is_member(to_user.user_id)):
                text = "❌ Выбранный пользователь не состоит в вашей группе"
                await event.answer(text, parse_mode=HTML)
                return

            text = f"<b>Подтвердите удаление участника группы</b>\n{to_user}"
            await event.answer(text, parse_mode=HTML,
                               reply_markup=keyboards.member_removing_menu(to_user.user_id, group.group_id,
                                                                           user.user_id))

    else:
        # removemember_{to_user_id}_{group_id}
        to_user_id = event.data.split("_")[1]
        call_group_id = int(event.data.split("_")[2])

        group = user.get_group()
        if not group.exists():
            text = "❌ Вы не состоите в какой-либо группе"
            await event.answer(text, show_alert=True)
            return

        if group.group_id != call_group_id:
            text = "❌ Вы не состоите в этой группе"
            await event.answer(text, show_alert=True)
            return

        await group.update()
        if not (await group.is_leader(user.user_id)):
            text = "❌ Вы не являетесь лидером этой группы"
            await event.answer(text, show_alert=True)
            return

        to_user = await search_user(user.get_storage(), event, to_user_id, True, bot_profile)
        if to_user:
            # Исключаем участника группы.
            await to_user.exit_group(group.group_id)

            if not (await group.is_member(to_user.user_id)):
                text = "❌ Выбранный пользователь не состоит в вашей группе"
                await event.answer(text, show_alert=True)
                return

            # Оповещаем лидера.
            text = f"☑️ <b>Участник исключен</b>\n{to_user}"
            await event.message.edit_text(text, parse_mode=HTML)

            # Оповещаем пользователя.
            try:
                text = (f"😢 <b>Вы были исключены</b>\n"
                        f"Название группы: <b>{group.get_name()}</b>")
                await event.bot.send_message(to_user.user_id, text, parse_mode=HTML)
            except:
                pass


async def removing_group(call: types.CallbackQuery, user: entities.User):
    try:
        group = user.get_group()

        assert group.exists(), "Вы не состоите в какой-либо группе"

        # removegroup_{leader_id}_{group_id}
        msg_leader_id = int(call.data.split("_")[1])
        msg_group_id = int(call.data.split("_")[2])

        assert msg_leader_id == user.user_id, "Сообщение адресовано не вам"
        assert msg_group_id == group.group_id, "Группа недоступна"

        assert await group.is_leader(user.user_id), "Вы не являетесь лидером данной группы"

        if call.data.startswith("doremovegroup_"):
            members = await group.get_members()
            # Удаляем группу.
            await user.remove_group(group.group_id)

            text = ("🚮 <b>Группа удалена</b>\n"
                    f"Название: <b>{group.get_name()}</b>\n"
                    f"Участников: <b>{len(members)}</b>")
            await call.message.edit_text(text, parse_mode=HTML)

        else:
            text = (f"⚠️ <b>Вы уверены, что хотите удалить группу '{group.get_name()}'?</b>\n"
                    f"Все участники группы будут также исключены из неё. "
                    f"Это действие нельзя будет отменить.")
            await call.message.edit_text(text, parse_mode=HTML,
                                         reply_markup=keyboards.removing_group_menu(user.user_id, group.group_id))

    except Exception as e:
        await call.answer(f"❌ {e}", show_alert=True)


async def rename_group(event: types.Message | types.CallbackQuery, user: entities.User):
    group = user.get_group()
    if not group.exists():
        text = "❌ Вы не состоите в какой-либо группе"
        if isinstance(event, types.Message):
            await event.answer(text)
        else:
            await event.answer(text, show_alert=True)
        return

    if not (await group.is_leader(user.user_id)):
        text = "❌ Вы не являетесь лидером своей группы"
        if isinstance(event, types.Message):
            await event.answer(text)
        else:
            await event.answer(text, show_alert=True)
        return

    if isinstance(event, types.Message):
        group_name = " ".join(event.text.split()[1:]).lower()

        # Проверяем название группы.
        extra_symbols = " " + "абвгдеёжзийклмнопрстуфхцчшщъыьэюя'"
        if not utils.is_text_cleared(group_name, extra_symbols):
            text = ("❌ <b>Неправильное название для группы</b>\n"
                    f"Разрешено использовать символы латинского и русского алфавитов (a-z, а-я), цифры, "
                    f"знак пробела и знака одинарной кавычки.")
            await event.answer(text, parse_mode=HTML)
            return

        if not (3 <= len(group_name) <= 20):
            text = ("❌ <b>Неправильное название для группы</b>\n"
                    f"Оно должно быть длиннее 3-х и короче 20-ти символов.")
            await event.answer(text, parse_mode=HTML)
            return

        # Проверяем существование группы.
        if await user.get_storage().group_exists_by_name(group_name):
            text = ("❌ <b>Неправильное название для группы</b>\n"
                    f"Группа с таким названием уже существует.")
            await event.answer(text, parse_mode=HTML)
            return

        text = (f"🆕 <b>Подтвердите переименование группы</b>\n"
                f"Новое название: <b>{group_name}</b>\n"
                f"Стоимость: <b>{config.PRICE_RENAME_GROUP_CRUYSTALS} 💎</b>")
        await event.answer(text, parse_mode=HTML, reply_markup=keyboards.rename_group_menu(user.user_id, group_name))

    else:
        # renamegroup_{leader_id}_{group_name}
        leader_id = int(event.data.split("_")[1])
        group_name = event.data.split("_")[2].replace("-", " ")

        if user.user_id != leader_id:
            text = "❌ Сообщение адресовано не вам"
            await event.answer(text, show_alert=True)
            return

        # Проверяем баланс пользователя.
        if not (user.crystals >= config.PRICE_RENAME_GROUP_CRUYSTALS):
            text = ("❌ Недостаточно средств\n"
                    f"Стоимост переименования группы: {config.PRICE_RENAME_GROUP_CRUYSTALS} 💎")
            await event.answer(text, show_alert=True)
            return

        # Проверяем существование группы.
        if await user.get_storage().group_exists_by_name(group_name):
            text = "❌ Группа с таким названием уже существует"
            await event.answer(text, show_alert=True)
            return

        # Переименовываем группу.
        await user.rename_group(group_name)
        text = ("ℹ️ <b>Группа успешно переименована</b>\n"
                f"Новое название: <b>{group_name}</b>\n\n"
                f"💬 Отправить приглашение в группу:\n<code>/invite [пользователь]</code>")
        await event.message.edit_text(text, parse_mode=HTML)


async def show_user_group(event: types.Message | types.CallbackQuery, user: entities.User):
    group = user.get_group()
    if not group.exists():
        text = "ℹ️ Вы не состоите в какой-либо группе"
        if isinstance(event, types.Message):
            await event.answer(text)
        else:
            await event.answer(text, show_alert=True)
        return

    if isinstance(event, types.Message):
        await group.update()

        members = await group.get_members()
        leader = await group.get_leader()
        post = group.get_user_post(user.user_id)
        tax = await group.get_tax()

        max_members_count = await group.get_max_members_count()
        level = await group.get_level()

        text = (f"👥 <b>Информация о группе</b>\n"
                f"Название: <b>{group.get_name()}</b>\n"
                f"Уровень: <b>{level}</b>\n"
                f"Участников: <b>{len(members)} из {max_members_count}</b>\n"
                f"Ежедневный взнос: <b>{tax} 🪙</b>\n"
                f"Бонус к банку: <b>+{group.level}%</b>\n"
                f"Ваш статус: <b>{post}</b>\n\n"
                f"<u>Лидер группы</u>\n{leader}")

        if await group.is_leader(user.user_id):
            rpl = keyboards.leader_group_menu(user.user_id, group.group_id, False)
        else:
            rpl = keyboards.user_group_menu(user.user_id, group.group_id, False)

        await event.reply(text, parse_mode=HTML, reply_markup=rpl)

    else:
        msg_member_id = int(event.data.split("_")[1])
        msg_group_id = int(event.data.split("_")[2])

        if user.user_id != msg_member_id:
            text = "❌ Сообщение адресовано не вам"
            await event.answer(text, show_alert=True)
            return

        if group.group_id != msg_group_id:
            text = "❌ Группа недоступна"
            await event.answer(text, show_alert=True)
            return

        await group.update()

        # exitgroup_{user_id}_{group_id}
        if event.data.startswith("exitgroup_"):
            text = (f"⚠️ <b>Подтвердите действие</b>\n"
                    f"Вы уверены, что хотите покинуть группу <b>{group.get_name()}</b>?")
            await event.message.edit_text(text, parse_mode=HTML,
                                          reply_markup=keyboards.user_group_menu(user.user_id, group.group_id, True))

        elif event.data.startswith("doexitgroup_"):
            # doexitgroup_{user_id}_{group_id}

            # Убираем пользователя из группы.
            await user.exit_group(group.group_id)

            # Уведомляем пользователя.
            text = ("☑️ <b>Вы покинули группу</b>\n"
                    f"Название: <b>{group.get_name()}</b>")
            await event.message.edit_text(text, parse_mode=HTML)

            leader = await group.get_leader()
            # Уведомляем лидера группы.
            text = f"🚪 <b>Пользователь покинул группу</b>\n{user}"
            try:
                await event.bot.send_message(leader.user_id, text, parse_mode=HTML)
            except:
                pass

        elif event.data.startswith("upgroup_"):
            if group.level == 5:
                await event.answer("ℹ️ У вас максимальный уровень группы", show_alert=True)
                return

            price = config.PRICE_GROUP_UPGRADE[int(group.level + 1)]
            price_coins = price["coins"]
            price_crystals = price["crystals"]

            text = (f"🆙 <b>Подтвердите действие</b>\n"
                    f"Повышение до уровня: <b>{int(group.level + 1)}</b>\n"
                    f"Стоимость повышения группы: <b>{price_coins} 🪙 и {price_crystals} 💎</b>")
            await event.message.edit_text(text, parse_mode=HTML,
                                          reply_markup=keyboards.leader_group_menu(user.user_id, group.group_id, True))

        elif event.data.startswith("doupgroup_"):
            if not (await group.is_leader(user.user_id)):
                text = "❌ Вы не являетесь лидером группы"
                await event.answer(text, show_alert=True)
                return

            if group.level == 5:
                await event.answer("ℹ️ У вас максимальный уровень группы", show_alert=True)
                return

            price = config.PRICE_GROUP_UPGRADE[int(group.level + 1)]
            price_coins = price["coins"]
            price_crystals = price["crystals"]

            if not (user.balance >= price_coins and user.crystals >= price_crystals):
                text = "❌ Не хватает средств на балансе"
                await event.answer(text, show_alert=True)
                return

            # Повышаем уровень группы.
            new_level = await group.upgrade()
            new_max_members_count = config.MAX_GROUP_MEMBERS[new_level]
            members = await group.get_members()

            text = (f"🎉 <b>Уровень группы повышен</b>\n"
                    f"Новый уровень: <b>{new_level}</b>\n"
                    f"Участников: <b>{len(members)} из {new_max_members_count}</b>")
            await event.message.edit_text(text, parse_mode=HTML)


async def show_group_inviting(event: types.Message | types.CallbackQuery, user: entities.User,
                              bot_profile: aiogram.types.User | None):
    if isinstance(event, types.Message):
        if bot_profile is None:
            raise

        group = user.get_group()
        if not (await group.is_leader(user.user_id)):
            text = "❌ Вы не являетесь лидером какой-либо группы"
            await event.answer(text, parse_mode=HTML)
            return

        if not (await group.can_join()):
            text = ("❌ Группа недоступна или достигнуто максимальное количество "
                    "участников для данного уровня группы")
            await event.answer(text, parse_mode=HTML)
            return

        if event.reply_to_message:
            search_text = event.reply_to_message.from_user.id
        else:
            search_text = event.text.split()[1]

        if utils.is_msg_code(search_text):
            text = "❌ Нельзя отправлять приглашения по анонимному коду"
            await event.answer(text, parse_mode=HTML)
            return

        to_user = await search_user(user.get_storage(), event, search_text, True, bot_profile)

        if to_user:
            if user.user_id == to_user.user_id:
                text = "❌ Нельзя отправить приглашение самому себе"
                await event.answer(text, parse_mode=HTML)
                return

            if to_user.get_group().exists():
                text = "❌ Пользователь уже состоит в группе"
                await event.answer(text, parse_mode=HTML)
                return

            cd_key = f"inviteToUserId{to_user.user_id}"
            if not user.cooldown(cd_key, config.COOLDOWN_INVITE_SAME):
                last_time = user.get_cooldown_last_time(cd_key)
                time_left = utils.calc_seconds_left(last_time, config.COOLDOWN_INVITE_SAME)

                text = ("❌ <b>Вы недавно приглашали этого пользователя</b>\n"
                        f"Подождите еще {utils.format_time(time_left)}")
                await event.answer(text, parse_mode=HTML)
                return

            leader = await group.get_leader()
            tax = await group.get_tax()
            # Отправляем пользователю приглашение.
            text = (f"💌 <b>Вас приглашают в группу</b>\n"
                    f"Название: <b>{group.get_name()}</b>\n"
                    f"Участников: <b>{len(await group.get_members())}</b>\n\n"
                    f"<u>Лидер группы</u>\n{leader}\n\n"
                    f"<u>Стоимость</u>\n"
                    f"Вступление: <b>{config.PRICE_JOIN_GROUP} 🪙</b>\n"
                    f"Ежедневный взнос: <b>{tax} 🪙</b>")
            try:
                await event.bot.send_message(to_user.user_id, text, parse_mode=HTML,
                                             reply_markup=keyboards.invite_group_menu(to_user.user_id, group.group_id))
            except:
                pass

            text = f"📨 <b>Приглашение отправлено</b>\n{to_user}"
            await event.answer(text, parse_mode=HTML)
    else:
        # joingroup_{to_user_id}_{group_id}
        future_member_id = int(event.data.split("_")[1])
        group_id = int(event.data.split("_")[2])

        if user.user_id != future_member_id:
            text = "❌ Приглашение отправлено не вам"
            await event.answer(text, show_alert=True)
            return

        if user.get_group().exists():
            text = "❌ Вы уже состоите в группе"
            await event.answer(text, show_alert=True)
            return

        if not (user.balance >= config.PRICE_JOIN_GROUP):
            text = "❌ Недостаточно средств на балансе"
            await event.answer(text, show_alert=True)
            return

        # Проверяем существование группы.
        # Проверяем максимальное количество пользователей в группе.
        future_group = entities.Group(user.get_storage(), group_id)
        if not (await future_group.can_join()):
            text = ("❌ Группа недоступна или достигнуто максимальное количество "
                    "участников для данного уровня группы")
            await event.answer(text, show_alert=True)
            return

        # Получаем лидера группы.
        leader = await future_group.get_leader()
        members = await future_group.get_members()
        max_members_count = await future_group.get_max_members_count()

        # Вступаем в группу.
        await user.join_group(group_id)
        tax = await future_group.get_tax()

        text = (f"🆕 <b>Вы стали участником группы</b>\n"
                f"Название: <b>{future_group.get_name()}</b>\n"
                f"Участников: <b>{int(len(members) + 1)}</b>\n"
                f"Ежедневный взнос: <b>{tax} 🪙</b>\n\n"
                f"<u>Лидер группы</u>\n{leader}")
        await event.message.edit_text(text, parse_mode=HTML)

        # Оповещаем лидера группы.
        text = (f"🆕 <b>Приглашение принято</b>\n{user}\n\n"
                f"Участников: <b>{int(len(members) + 1)} из {max_members_count}</b>")
        try:
            await event.bot.send_message(leader.user_id, text, parse_mode=HTML)
        except:
            pass


async def show_group_creating(event: types.Message | types.CallbackQuery, user: entities.User):
    if isinstance(event, types.Message):  # Новая очень крутая группа 1234567
        group_name = " ".join(event.text.split()[1:]).lower()

        if user.get_group().exists():
            text = "❌ Вы уже состоите в группе"
            await event.answer(text, parse_mode=HTML)
            return

        # Проверяем название группы.
        extra_symbols = " " + "абвгдеёжзийклмнопрстуфхцчшщъыьэюя'"
        if not utils.is_text_cleared(group_name, extra_symbols):
            text = ("❌ <b>Неправильное название для группы</b>\n"
                    f"Разрешено использовать символы латинского и русского алфавитов (a-z, а-я), цифры, "
                    f"знак пробела и знака одинарной кавычки.")
            await event.answer(text, parse_mode=HTML)
            return

        if not (3 <= len(group_name) <= 20):
            text = ("❌ <b>Неправильное название для группы</b>\n"
                    f"Оно должно быть длиннее 3-х и короче 20-ти символов.")
            await event.answer(text, parse_mode=HTML)
            return

        # Проверяем существование группы.
        if await user.get_storage().group_exists_by_name(group_name):
            text = ("❌ <b>Неправильное название для группы</b>\n"
                    f"Группа с таким названием уже существует.")
            await event.answer(text, parse_mode=HTML)
            return

        text = (f"🆕 <b>Подтвердите создание группы</b>\n"
                f"Название: <b>{group_name}</b>\n"
                f"Стоимость создания: <b>{config.PRICE_CREATE_GROUP} 🪙 и {config.PRICE_CREATE_GROUP_CRYSTALS} 💎</b>")
        await event.answer(text, parse_mode=HTML, reply_markup=keyboards.create_group_menu(user.user_id, group_name))

    else:
        # newgroup_{leader_id}_{group_name}
        leader_id = int(event.data.split("_")[1])
        group_name = event.data.split("_")[2].replace("-", " ")

        if user.user_id != leader_id:
            text = "❌ Сообщение адресовано не вам"
            await event.answer(text, show_alert=True)
            return

        if user.get_group().exists():
            text = "❌ Вы уже состоите в группе"
            await event.answer(text, show_alert=True)
            return

        # Проверяем баланс пользователя.
        if not (user.balance >= config.PRICE_CREATE_GROUP and user.crystals >= config.PRICE_CREATE_GROUP_CRYSTALS):
            text = ("❌ Недостаточно средств\n"
                    f"Стоимост создания группы: {config.PRICE_CREATE_GROUP} 🪙 и {config.PRICE_CREATE_GROUP_CRYSTALS} 💎")
            await event.answer(text, show_alert=True)
            return

        # Проверяем существование группы.
        if await user.get_storage().group_exists_by_name(group_name):
            text = "❌ Группа с таким названием уже существует"
            await event.answer(text, show_alert=True)
            return

        # Создаем группу.
        await user.create_group(group_name)
        text = ("ℹ️ <b>Группа успешно создана</b>\n"
                f"Название: <b>{group_name}</b>\n\n"
                f"💬 Отправить приглашение в группу:\n<code>/invite [пользователь]</code>")
        await event.message.edit_text(text, parse_mode=HTML)


async def show_casino(event: types.Message | types.CallbackQuery, user: entities.User):
    if isinstance(event, types.Message):
        # Получаем аргумент.
        try:
            bet_amount = int(event.text.split()[1])
        except:
            text = "❌ Неправильная сумма ставки"
            await event.answer(text, parse_mode=HTML)
            return

        # Проверяем баланс пользователя.
        if user.balance < 2:
            text = ("❌ <b>Слишком низкий баланс</b>\n"
                    f"Ваш баланс должен составлять хотя бы 2 монетки")
            await event.answer(text, parse_mode=HTML)
            return

        min_casino_bet = int(user.balance * 0.1)
        if min_casino_bet < 1000:
            min_casino_bet = 1000

        if event.chat.id != user.user_id and bet_amount < min_casino_bet:
            min_casino_bet_shown = utils.format_balance(min_casino_bet)
            text = ("❌ Публично можно играть только на суммы "
                    "<b>не меньше чем 10% от баланса и не меньше 1000 🪙</b>\n\n"
                    f"Мин. публичная ставка: <b>{min_casino_bet_shown}</b> 🪙")
            await event.answer(text, parse_mode=HTML,
                               reply_markup=keyboards.cancel_menu(user.user_id))
            return

        if 2 <= bet_amount <= user.balance:
            text = ("🎰 <b>Добро пожаловать в казино</b>\n"
                    f"Игрок: <code>{user.user_id}</code> ({user.get_username()})\n"
                    f"Ваша ставка: <b>{utils.format_balance(bet_amount)} 🪙</b>\n\n"
                    "🕹️ <b>Выберите уровень игры</b>\n"
                    f"[Режим x{config.GAME_VERY_LOW_MULTIPLIER}] Выигрыш: <b>{utils.format_balance(int(config.GAME_VERY_LOW_MULTIPLIER * bet_amount))} 🪙</b> Шанс: <b>{config.GAME_VERY_LOW_PERCENTAGE}%</b>\n"
                    f"[Режим x{config.GAME_LOW_MULTIPLIER}] Выигрыш: <b>{utils.format_balance(int(config.GAME_LOW_MULTIPLIER * bet_amount))} 🪙</b> Шанс: <b>{config.GAME_LOW_PERCENTAGE}%</b>\n"
                    f"[Режим x{config.GAME_MIDDLE_MULTIPLIER}] Выигрыш: <b>{utils.format_balance(int(config.GAME_MIDDLE_MULTIPLIER * bet_amount))} 🪙</b> Шанс: <b>{config.GAME_MIDDLE_PERCENTAGE}%</b>\n"
                    f"[Режим x{config.GAME_HIGH_MULTIPLIER}] Выигрыш: <b>{utils.format_balance(int(config.GAME_HIGH_MULTIPLIER * bet_amount))} 🪙</b> Шанс: <b>{config.GAME_HIGH_PERCENTAGE}%</b>\n"
                    f"[Режим x{config.GAME_VERY_HIGH_MULTIPLIER}] Выигрыш: <b>{utils.format_balance(int(config.GAME_VERY_HIGH_MULTIPLIER * bet_amount))} 🪙</b> Шанс: <b>{config.GAME_VERY_HIGH_PERCENTAGE}%</b>\n")
            rpl = keyboards.casino_menu(user.user_id, bet_amount)
            await event.reply(text, parse_mode=HTML, reply_markup=rpl)

        else:
            text = ("❌ <b>Неправильная сумма ставки</b>\n"
                    f"Укажите целое число от 2 до {utils.format_balance(user.balance)} монеток")
            await event.answer(text, parse_mode=HTML)

    elif isinstance(event, types.CallbackQuery):
        # "game_low_{game_code}_{user_id}_{bet_amount}"
        game_mode, game_code, user_id, bet_amount = event.data.split("_")[1:]
        player_id = int(user_id)
        try:
            bet_amount = int(bet_amount)
        except:
            text = "❌ Неправильная сумма ставки"
            await event.answer(text, show_alert=True)
            return

        if user.user_id != player_id:
            text = "❌ Игра создана другим игроком"
            await event.answer(text, show_alert=True)
            return

        if user.value("lastGameCode") == game_code:
            text = "❌ Игра уже завершена"
            await event.answer(text, show_alert=True)
            return

        if user.balance < bet_amount:
            text = "❌ У вас не хватает монеток на балансе"
            await event.answer(text, show_alert=True)
            return

        # Списываем деньги у пользователя.
        await user.pay(bet_amount)

        # Проводим игру.
        profit = utils.calc_casino_profit(game_mode, bet_amount)
        # Регистрируем игру.
        await user.play_game(bet_amount, profit)

        if profit:
            await user.earn(profit)
            result = "Выигрыш"
        else:
            result = "Проигрыш"

        levels = {
            "verylow": (f"Режим x{config.GAME_VERY_LOW_MULTIPLIER}", config.GAME_VERY_LOW_PERCENTAGE),
            "low": (f"Режим x{config.GAME_LOW_MULTIPLIER}", config.GAME_LOW_PERCENTAGE),
            "middle": (f"Режим x{config.GAME_MIDDLE_MULTIPLIER}", config.GAME_MIDDLE_PERCENTAGE),
            "high": (f"Режим x{config.GAME_HIGH_MULTIPLIER}", config.GAME_HIGH_PERCENTAGE),
            "veryhigh": (f"Режим x{config.GAME_VERY_HIGH_MULTIPLIER}", config.GAME_VERY_HIGH_PERCENTAGE)
        }

        await event.message.edit_reply_markup()
        text = ("🎰 <b>Результаты проведенной игры</b>\n"
                f"Игрок: {user.user_id} ({user.get_username()})\n"
                f"Ставка: <b>{utils.format_balance(bet_amount)} 🪙</b>\n\n"
                f"Уровень игры: <u>{levels[game_mode][0]}</u>\n"
                f"Шанс: <b>{levels[game_mode][1]}%</b>\n"
                f"Результат: <b>{result}</b>\n"
                f"Получено: <b>{utils.format_balance(profit)} 🪙</b>")
        await event.message.edit_text(text, parse_mode=HTML)


async def clear_from_disagreed_users(bot: aiogram.Bot, storage: db.Storage):
    try:
        # Получаем пользователей, которые не принимают правила слишком долго.
        users = await storage.get_disagreed_users()

        if config.DEBUG_MODE:
            print(f"disagreed users: {users}")

        for user_id in users:
            # Если не админ.
            if not (user_id in config.ADMINS):
                await asyncio.sleep(3)
                # Блокируем.
                user = entities.User(storage, user_id)
                await user.load_from_db()
                await user.ban()
                try:
                    await bot.ban_chat_member(config.CHAT_ID, user_id)
                except:
                    pass

                # Уведомляем.
                text = (f"⛔️ <b>Пользователь исключен</b>\n{user}\nБаланс: <b>{utils.format_balance(user.balance)} 🪙</b>\n\n"
                        f"Причина: не подтвердил согласие с правилами группы в течение {utils.format_time(config.TIME_TO_AGREED)}.")
                await bot.send_message(config.CHAT_ID, text, parse_mode=HTML)

                await asyncio.sleep(3)

                try:
                    text = ("⛔️ Вы были заблокированы, так как не подтвердили согласие "
                            f"с правилами группы в течение {utils.format_time(config.TIME_TO_AGREED)}")
                    await bot.send_message(user_id, text, parse_mode=HTML)

                except:
                    pass

                if not config.DEBUG_MODE:
                    notif_text = (f"⛔️ <b>Бан за бездействие</b>\n{user}\n"
                                  f"Баланс: <b>{utils.format_balance(user.balance)} 🪙</b>")
                    await notify(bot, notif_text)
    except Exception as e:
        print(f"CLR DA: {e}")


async def clear_from_inactive_users(bot: aiogram.Bot, storage: db.Storage):
    try:
        # Получаем список неактивных пользователей.
        users = await storage.get_inactive_users()

        if config.DEBUG_MODE:
            print(f"inactive users: {users}")

        for user_id in users:
            # Если не админ.
            if not (user_id in config.ADMINS):
                await asyncio.sleep(0.04)
                # Блокируем.
                user = entities.User(storage, user_id)
                await user.load_from_db()
                await user.ban()
                try:
                    await bot.ban_chat_member(config.CHAT_ID, user_id)
                except:
                    pass

                await asyncio.sleep(3)
                # Уведомляем.
                text = (f"⛔️ <b>Пользователь исключен</b>\n{user}\nБаланс: <b>{utils.format_balance(user.balance)} 🪙</b>\n\n"
                        f"Причина: бездействие в течение {utils.format_time(config.TIME_USER_MAX_INACTIVE)}.")
                await bot.send_message(config.CHAT_ID, text, parse_mode=HTML)

                await asyncio.sleep(3)
                try:
                    text = (f"⛔️ Вы были исключены из чата, "
                            f"так как бездействовали в течение {utils.format_time(config.TIME_USER_MAX_INACTIVE)}.")
                    await bot.send_message(user_id, text, parse_mode=HTML)
                except:
                    pass

    except Exception as e:
        print(f"CLR E: {e}")


async def help_menu(message: types.Message):
    command = config.REF_MAIN_MANUAL
    text = (f"ℹ️ <b>Инструкция по чату: {command}</b>\n\n"
            f"/profile - Посмотреть свой профиль\n"
            f"/coins - Посмотреть только балансы\n"
            f"/top - Топ богатых пользователей\n"
            f"/worst - Самые бедные пользователи\n"
            f"/mybank - Просмотр своих банковских счетов\n"
            f"/topbanks - Топ банковских счетов\n"
            f"/fees - Просмотр текущих комиссии и вознаграждений.")
    await message.answer(text, parse_mode=HTML, disable_web_page_preview=True)


async def process_vote(call: types.CallbackQuery, user: entities.User):
    stage, decision, poll_id = call.data.replace("poll_", "").split("_")
    stage, poll_id = int(stage), int(poll_id)

    if not (stage in (1, 2)):
        text_error = "❌ Голосование завершено"
        await call.answer(text_error, show_alert=True)
        return

    if user.is_muted():
        text_error = "❌ Вы не можете принимать участие в опросе (мут)"
        await call.answer(text_error, show_alert=True)
        return

    # Получаем информацию о голосовании.
    poll = await user.get_storage().get_poll(poll_id, stage)

    # Нельзя голосовать, если ты обвиняемый.
    if user.user_id == poll["to_id"]:
        text_error = "❌ Обвиняемые не могут учавствовать в этом голосовании"
        await call.answer(text_error, show_alert=True)
        return

    # Вышло ли время голосования.
    poll_created_time = poll["created"]
    poll_created_time: datetime.datetime
    now_time = datetime.datetime.now()
    if now_time.timestamp() - poll_created_time.timestamp() > config.TIME_TO_POLL:
        text_error = "❌ Время для голосования истекло"
        await call.answer(text_error, show_alert=True)
        return

    # Пробуем получить текущий голос, если он уже существует.
    user_vote = await user.get_vote(poll_id, stage)
    if user_vote:
        text_error = "❌ Вы уже голосовали"
        await call.answer(text_error, show_alert=True)

    else:
        # Записываем голос в БД.
        await user.vote(poll_id, stage, decision)

        # Получаем распределение голосов dict[decision:total_decision_balance].
        poll_votes = await user.get_storage().get_poll_votes(poll_id, stage)
        votes_balance_distribution = poll_votes["balances"]
        votes_count_distribution = poll_votes["count"]
        if not votes_balance_distribution or not votes_count_distribution:
            raise

        # Получаем новую клавиатуру.
        rpl = keyboards.poll_menu(poll_id, votes_balance_distribution, votes_count_distribution)

        try:
            # Изменяем клавиатуру.
            await call.message.edit_reply_markup(rpl)
        except:
            pass

        # Получаем обвиняемого.
        to_user = entities.User(user.get_storage(), user_id=poll["to_id"])
        await to_user.load_from_db()

        # Определяем текущие условия.
        # Число голосов.
        votes_count = utils.calc_votes_total(votes_count_distribution)
        # votes_count = len(votes_balance_distribution)
        # Их общий "баланс".
        votes_sum = utils.calc_votes_total(votes_balance_distribution)

        # Определяем требуемые условия.
        # Требуемый общий "баланс" голосов.
        need_votes_sum = int(to_user.balance * config.VOTES_BALANCE_MULTIPLIER)
        # Минимальное количество голосов.
        users_count = await user.get_storage().get_users_count()
        min_votes_count = utils.calc_part_of(users_count, config.MIN_VOTES_PERCENT, config.MIN_VOTES_COUNT)

        # Проверяем переход к следующей стадии.
        if votes_count >= min_votes_count and votes_sum >= need_votes_sum:
            # Определяем вариант, который победил на 1 стадии.
            win_decision = utils.get_win_vote(votes_balance_distribution)
            win_decision_percent = int(votes_balance_distribution[win_decision] / votes_sum * 100)

            # Определяем подробности выбранного варианта.
            if win_decision == "fine":
                # Штраф. Определяем процент от баланса.
                fine_percent = utils.choose_win_decision_two(win_decision)
                fine_amount = int(to_user.balance * fine_percent / 100)

                # Записываем финал голосования в БД.
                await user.get_storage().finish_poll(poll_id, win_decision_1=win_decision,
                                                     win_decision_2=str(fine_amount))

                win_decision_name = f"Изъять {utils.format_balance(fine_amount)} 🪙"
                text_result = ("☑️ <b>Голосование завершено</b>\n"
                               f"{to_user}\n\n"
                               f"Выбрано: <b>{win_decision_name}</b>\n"
                               f"Голосов: <b>{win_decision_percent}%</b>\n\nПо всем вопросам: @reireireime")
                await call.message.answer(text_result, parse_mode=HTML)

                # Переводим монетки.
                await to_user.fine(fine_amount)

                # Уведомляем обвиняемого.
                text_accused = (f"🚨 На основании решения голосования у вас изъяли "
                                f"<b>{utils.format_balance(fine_amount)} 🪙</b>")
                try:
                    await call.message.bot.send_message(to_user.user_id, text_accused, parse_mode=HTML)
                except:
                    pass

                # Взимаем со штрафа комиссию перед распределением.
                fine_amount = int(fine_amount - int((fine_amount * config.SHARE_TO_USERS_FEE_PERCENT / 100)))
                if fine_amount < 0:
                    fine_amount = 0

                if fine_amount:
                    #  Распределяем монетки по пользователям.
                    tranfer_result = await user.get_storage().transfer_to_users_percent(config.SHARE_TO_USERS_PERCENT,
                                                                                        fine_amount)
                    if tranfer_result:
                        text_transfer_result = ("💸 <b>Изъятые монетки распределены</b>\n"
                                                f"Переведено: <b>{len(tranfer_result['users'])} участникам</b>\n"
                                                f"Каждому по: <b>{utils.format_balance(tranfer_result['amount_per_user'])} 🪙</b>")
                        await call.message.answer(text_transfer_result, parse_mode=HTML)

                        # Уведомляем пользователей.
                        for one_user in tranfer_result['users']:
                            try:
                                one_user_id = one_user["user_id"]
                                text = ("💵 <b>Входящий перевод</b>\n"
                                        f"Вы получили <b>{utils.format_balance(tranfer_result['amount_per_user'])} 🪙</b> из общей суммы изъятых.")
                                await call.message.bot.send_message(one_user_id, text, parse_mode=HTML)
                                await asyncio.sleep(0.04)
                            except:
                                pass

                    else:
                        text_transfer_result = ("♻️ Было изъято слишком мало монеток. Никто из участиков не получит "
                                                "перевод.")
                        await call.message.answer(text_transfer_result)
                else:
                    text_transfer_result = ("♻️ Было изъято слишком мало монеток. Никто из участиков не получит "
                                            "перевод.")
                    await call.message.answer(text_transfer_result)

            elif win_decision == "mute":
                # Мут. Определяем срок мута в секундах (до какого timestamp).
                till_date = utils.choose_win_decision_two(win_decision)
                await to_user.mute(till_date)

                # Записываем финал голосования в БД.
                await user.get_storage().finish_poll(poll_id, win_decision_1=win_decision,
                                                     win_decision_2=str(till_date.timestamp()))

                mute_duration = utils.format_time(int(till_date.timestamp() - now_time.timestamp()))
                win_decision_name = f"Выдать мут на {mute_duration}."

                text_result = ("☑️ <b>Голосование завершено</b>\n"
                               f"{to_user}\n\n"
                               f"Выбрано: <b>{win_decision_name}</b>\n"
                               f"Голосов: <b>{win_decision_percent}%</b>\n\nПо всем вопросам: @reireireime")
                await call.message.answer(text_result, parse_mode=HTML)

                # Уведомляем обвиняемого.
                text_accused = (f"🚨 На основании решения голосования вам был выдан мут "
                                f"на <b>{mute_duration}</b>.")
                try:
                    await call.message.bot.send_message(to_user.user_id, text_accused, parse_mode=HTML)
                except:
                    pass

            elif win_decision == "ban":
                win_decision_name = "Исключить"

                # Записываем финал голосования в БД.
                await user.get_storage().finish_poll(poll_id, win_decision_1=win_decision,
                                                     win_decision_2=None)

                text_result = ("☑️ <b>Голосование завершено</b>\n"
                               f"{to_user}\n"
                               f"Баланс: <b>{utils.format_balance(to_user.balance)} 🪙</b>\n\n"
                               f"Выбрано: <b>{win_decision_name}</b>\n"
                               f"Голосов: <b>{win_decision_percent}%</b>\n\nПо всем вопросам: @reireireime")
                await call.message.answer(text_result, parse_mode=HTML)

                await to_user.ban()
                await call.message.bot.ban_chat_member(config.CHAT_ID, to_user.user_id)

                # Уведомляем обвиняемого.
                text_accused = (f"🚨 На основании решения голосования вы были "
                                f"<b>исключены из чата</b>")
                try:
                    await call.message.bot.send_message(to_user.user_id, text_accused, parse_mode=HTML)
                except:
                    pass

            elif win_decision == "mercy":
                win_decision_name = "Помиловать"

                # Записываем финал голосования в БД.
                await user.get_storage().finish_poll(poll_id, win_decision_1=win_decision,
                                                     win_decision_2=None)

                text_result = ("☑️ <b>Голосование завершено</b>\n"
                               f"{to_user}\n\n"
                               f"Выбрано: <b>{win_decision_name}</b>\n"
                               f"Голосов: <b>{win_decision_percent}%</b>\n\nПо всем вопросам: @reireireime")
                await call.message.answer(text_result, parse_mode=HTML)

                # Уведомляем обвиняемого.
                text_accused = "🚨 На основании решения голосования вы были помилованы"
                try:
                    await call.message.bot.send_message(to_user.user_id, text_accused, parse_mode=HTML)
                except:
                    pass

            else:
                raise

            if not config.DEBUG_MODE:
                notif_text = (f"☑️ <b>Голосование завершено</b>\n{to_user}\n"
                              f"Баланс: <b>{user.balance} монеток</b>\n"
                              f"Решение: <b>{win_decision}</b>")
                await notify(call.message.bot, notif_text)

            # Удаляем сообщение с голосованием.
            await call.message.delete()


async def answer_bad_command(message: types.Message):
    text = (f"❌ <b>Команда введена неправильно</b>\n"
            f"Отсутсвуют аргументы после команды. Посмотри как правильно прописывать команды "
            f"в этом сообщении: {config.REF_MSG_COMMANDS}")
    await message.answer(text, parse_mode=HTML)


async def check_bad_habits(message: types.Message, user: entities.User):
    def check_include(t: str, ss: tuple) -> bool:
        for s in ss:
            if s in t:
                return True
        return False

    if message.chat.id != config.CHAT_ID:
        return

    alcohol_price = 10
    cigarettes_price = 50
    drugs_price = 100

    alcohol_emojies = ("🍺", "🍻", "🥂", "🍷", "🥃", "🍸", "🍹", "🍾")
    cigarettes_emojies = ('💨', '🚬', '😶‍🌫', '🌫')
    drugs_emojies = ('🌿',)

    if message.sticker:
        text = message.sticker.emoji
    else:
        text = message.text

    # Алкоголь.
    if check_include(text, alcohol_emojies):
        if user.balance >= alcohol_price:
            desc = ", ".join(alcohol_emojies)
            text = f"🧾 Вам выставлен счет за алкоголь ({desc}): <b>{alcohol_price} 🪙</b>"
            await user.pay(alcohol_price)
            await user.get_storage().add_payment(user.user_id, None, db.PaymentType.alcohol,
                                                 alcohol_price, db.Currency.coins)
            await message.reply(text, parse_mode=HTML)
        else:
            text = "❌ У вас недостаточно монеток, чтобы купить алкоголь."
            await message.reply(text)
            await message.delete()

    # Сигареты.
    elif check_include(text, cigarettes_emojies):
        if user.balance >= cigarettes_price:
            desc = ", ".join(cigarettes_emojies)
            text = f"📝 Вам выписан штраф за курение ({desc}): <b>{cigarettes_price} 🪙</b>"
            await user.pay(cigarettes_price)
            await user.get_storage().add_payment(user.user_id, None, db.PaymentType.cigarettes,
                                                 cigarettes_price, db.Currency.coins)
            await message.reply(text, parse_mode=HTML)
        else:
            text = "❌ У вас недостаточно монеток, чтобы оплатить штраф за курение."
            await message.reply(text)
            await message.delete()

    # Нарко.
    elif check_include(text, drugs_emojies):
        if user.balance >= drugs_price:
            desc = ", ".join(drugs_emojies)
            text = f"👮 Вам выписан штраф за пропаганду наркотиков ({desc}): <b>{drugs_price} 🪙</b>"
            await user.pay(drugs_price)
            await user.get_storage().add_payment(user.user_id, None, db.PaymentType.drugs,
                                                 drugs_price, db.Currency.coins)
            await message.reply(text, parse_mode=HTML)


async def process_report(message: types.Message, user: entities.User, args: list, bot_profile: aiogram.types.User):
    # Проверяем сколько прошло времени с последней жалобы.
    last_report_time = await user.get_last_report_time()
    if not utils.follow_cooldown(from_time=last_report_time, cooldown_seconds=config.COOLDOWN_REPORT):
        seconds_left = utils.calc_seconds_left(from_time=last_report_time, cooldown_seconds=config.COOLDOWN_REPORT)
        time_left = utils.format_time(seconds_left)

        await message.answer("❌ С момента отправки последней жалобы прошло слишком "
                             f"мало времени. Подождите еще <b>{time_left}</b>", parse_mode=HTML)
        return

    if utils.is_msg_code(args[0]):
        await message.answer("❌ Нельзя отправлять жалобы по анонимному коду.", parse_mode=HTML)
        return

    to_user = await search_user(user.get_storage(), message, args[0], check_mute=True, bot_profile=bot_profile)
    if to_user:
        if user.user_id == to_user.user_id:
            await message.answer("❌ Нельзя отправить жалобу на себя.", parse_mode=HTML)
            return

        # Проверяем, является ли он товарищем по группе.
        if user.team_id and to_user.team_id and user.team_id == to_user.team_id:
            await message.answer("❌ Нельзя отправить жалобу на товарища по группе.", parse_mode=HTML)
            return

        # Проверяем ограничение по времени с последнего проведенного опроса.
        last_poll_time = await to_user.get_last_poll_time()

        if not utils.follow_cooldown(from_time=last_poll_time, cooldown_seconds=config.COOLDOWN_USER_POLL):
            seconds_left = utils.calc_seconds_left(from_time=last_poll_time, cooldown_seconds=config.COOLDOWN_USER_POLL)
            time_left = utils.format_time(seconds_left)

            await message.answer("❌ С последнего голосования по вопросу искомого пользователя "
                                 f"прошло слишком мало времени. Подождите еще <b>{time_left}</b>", parse_mode=HTML)
            return

        comment = " ".join(args[1:])

        if comment and not utils.is_comment_cleared(comment):
            text = ("❌ Комментарий к жалобе может содержать только буквы русского и английского алфавита, цифры, "
                    "пробел, а также знаки <b>.,:;?!()-</b>")
            await message.answer(text, parse_mode=HTML)
            return

        if comment and len(comment) > 128:
            text = "❌ Комментарий не должен быть больше 128 символов"
            await message.answer(text, parse_mode=HTML)
            return

        try:
            # Отправляем жалобу.
            await user.report(to_user, comment)

            # Уведомляем.
            to_user_field = "Получатель неизвестен" if utils.is_msg_code(args[0]) else to_user
            text = (f"📑 <b>Жалоба отправлена</b>\n{to_user_field}\n\n"
                    f"<i>Вознаграждение начислено вам на баланс</i>")
            await message.answer(text, parse_mode=HTML)

            text_2 = "⚠️ <b>На вас отправлена жалоба</b>"

            if comment:
                text_2 += f"\n\n📝 Комментарий к жалобе: <code>{comment}</code>"

            text_2 += ("\n\n🔖 Это сделал кто-то из участников чата. Будьте осторожны, дальнейшее получение "
                       "жалоб может обернуться началом голосования по выбору вашего наказания.")
            try:
                await message.bot.send_message(to_user.user_id, text_2, parse_mode=HTML)
            except:
                pass

            if not config.DEBUG_MODE:
                notif_text = f"📑 <b>Жалоба отправлена</b>\n\n{user}\n\n{to_user}\n\n"
                await notify(message.bot, notif_text)

            # Определяем текущие условия.
            reports = await to_user.get_reports_sum()
            # Число жалоб.
            reports_count = reports["count"]
            # Их общий "баланс".
            reports_sum = reports["sum"]

            # Определяем условия для начала голосования.
            group = to_user.get_group()
            await group.update()
            if group.exists():
                group_balance = await group.get_total_balance()
                if group_balance and group_balance > to_user.balance:
                    calculated_balance = group_balance
                else:
                    calculated_balance = to_user.balance
            else:
                calculated_balance = to_user.balance

            if config.DEBUG_MODE:
                print(f"REPORT | CALC: {calculated_balance} | U: {to_user.balance}")

            # Требуемый общий "баланс" жалоб.
            need_reports_sum = int(calculated_balance * config.REPORT_BALANCE_MULTIPLIER)
            # Минимальное количество жалоб.
            users_count = await user.get_storage().get_users_count()
            min_reports_count = utils.calc_part_of(users_count, config.MIN_REPORT_PERCENT, config.MIN_REPORTS_COUNT)

            if config.DEBUG_MODE:
                print([reports_count, min_reports_count, reports_sum, need_reports_sum])
            # Определяем, выполнены ли условия для начала голосования.
            if reports_count >= min_reports_count and reports_sum >= need_reports_sum:

                # Регистрируем в БД новый опрос (удаляются все жалобы) и получаем его ID.
                poll_id = await to_user.register_poll()

                # Отправляем уведомления об голосовании.
                # В чат.
                text_3 = ("🗳️ <b>Голосование начинается</b>\n\n"
                          f"<u>Обвиняемый</u>\n{to_user}\n\n"
                          f"<b>Проголосуйте за один из вариантов ниже.</b> У вас есть {utils.format_time(config.TIME_TO_POLL)}. "
                          f"Вес вашего голоса пропорционален "
                          f"вашему балансу. Подробнее про голосования тут: {config.REF_POLL_RULE}. "
                          f"По всем вопросам: @reireireime")
                poll_message = await message.bot.send_message(config.CHAT_ID, text_3, parse_mode=HTML,
                                                              reply_markup=keyboards.poll_menu(poll_id),
                                                              disable_web_page_preview=True)
                # Закрепляем его.
                await poll_message.pin(disable_notification=False)

                # В лс обвиняемому.
                text_4 = ("🚨 <b>Голосование начинается</b>\n"
                          "По вашему вопросу в чате началось голосование. Советуем склонить на свою строну "
                          "побольше участников, чтобы избежать сурового наказания или хотя бы его смягчить.")
                try:
                    await message.bot.send_message(to_user.user_id, text_4, parse_mode=HTML,
                                                   reply_markup=keyboards.poll_url_menu(poll_message.message_id))
                except:
                    pass

                # В лс тому, кто пожаловался.
                text_5 = ("☑️ <b>Голосование начинается</b>\n"
                          "Ваша жалоба оказалась решающей.")
                try:
                    await message.bot.send_message(user.user_id, text_5, parse_mode=HTML,
                                                   reply_markup=keyboards.poll_url_menu(poll_message.message_id))
                except:
                    pass

                if not config.DEBUG_MODE:
                    notif_text = f"🗳️ <b>Голосование начинается</b>\n\n{user}\n\n{to_user}\n\n"
                    await notify(message.bot, notif_text)

            else:
                text_3 = ("🔖 Количество жалоб на данного пользователя недостаточно, чтобы начать голосование. "
                          "Попробуйте убедить других участников также пожаловаться на вашего оппонента.")
                await message.answer(text_3)

        except Exception as e:
            print(f"REPORT ERROR: {e}")
            text = (f"❌ Ошибка - что-то пошло не так. Возможно вы уже отправляли жалобу на данного "
                    f"пользователя.")
            await message.answer(text)


async def show_tasks(message: types.Message, _: entities.User):
    text = ("✴️ <b>Доступные задания</b>\n"
            "Предложи новую механику в чате и получи "
            "<b>от 100 до 500 монеток</b>.\n"
            "С предложениями писать <a href='https://t.me/reireireime'>разработчику</a>")
    await message.answer(text, parse_mode=HTML, disable_web_page_preview=True)


async def show_sending_crystals_procedure(message: types.Message, user: entities.User, args: list,
                                          bot_profile: aiogram.types.User):
    try:
        search_text = args[0]
        amount = int(args[1])
        comment = " ".join(args[2:])

        if not await user.can_send():
            text = ("❌ <b>Вы не можете выполнить перевод</b>\n"
                    f"С момента начала голосования по вашему вопросу не прошло {utils.format_time(config.TIME_TO_POLL)}")
            await message.answer(text, parse_mode=HTML)
            return

        if user.user_id != message.chat.id:
            await message.answer("❌ Нельзя выполнить перевод другому пользователю публично. "
                                 "Напиши мне в личные сообщения.", parse_mode=HTML)
            return

        if comment:
            comment = comment.replace("<", "").replace(">", "")

        if comment and len(comment) > 128:
            text = "❌ Комментарий не должен быть больше 128 символов"
            await message.answer(text, parse_mode=HTML)
            return

        if not (user.crystals >= amount):
            text = "❌ Не хватает кристаллов для перевода"
            await message.answer(text, parse_mode=HTML)
            return

        to_user = await search_user(user.get_storage(), message, search_text, check_mute=True, bot_profile=bot_profile)
        if to_user:
            if to_user.user_id == user.user_id:
                text = "❌ Нельзя выполнить перевод себе"
                await message.answer(text, parse_mode=HTML)
                return

            # Если не анон перевод и политика.
            if not utils.is_msg_code(search_text) and to_user.policy == 2:
                group = user.get_group()
                if not (await group.is_member(to_user.user_id)):
                    text = ("❌ Чтобы переводить этому пользователю, вы должны состоять с ним "
                            "в одной группе.")
                    await message.answer(text, parse_mode=HTML)
                    return

            # Выполняем перевод.
            await user.send_crystals(to_user, amount, comment)

            to_user_field = "Получатель неизвестен" if utils.is_msg_code(search_text) else to_user
            text = (f"⬆️ <b>Перевод выполнен</b>\n{to_user_field}\n"
                    f"Сумма: <b>{amount} 💎</b>")
            if comment:
                text += f"\nКомментарий: <code>{comment}</code>"
            await message.answer(text, parse_mode=HTML)

            text_2 = (f"⬇️ <b>Входящий перевод</b>\n"
                      f"Сумма: <b>{amount} 💎</b>")
            if comment:
                text_2 += f"\nКомментарий: <code>{comment}</code>"
            try:
                await message.bot.send_message(to_user.user_id, text_2, parse_mode=HTML)
            except:
                pass

    except:
        text = (f"❌ Ошибка - что-то пошло не так. Проверьте правильность вашей "
                f"введенной команды.")
        await message.answer(text, parse_mode=HTML)


async def show_sending_procedure(message: types.Message, user: entities.User, args: list,
                                 bot_profile: aiogram.types.User):
    try:
        search_text = args[0]
        amount = int(args[1])
        comment = " ".join(args[2:])

        if not await user.can_send():
            text = ("❌ <b>Вы не можете выполнить перевод</b>\n"
                    f"С момента начала голосования по вашему вопросу не прошло {utils.format_time(config.TIME_TO_POLL)}")
            await message.answer(text, parse_mode=HTML)
            return

        if user.user_id != message.chat.id:
            await message.answer("❌ Нельзя выполнить перевод другому пользователю публично. "
                                 "Напиши мне в личные сообщения.", parse_mode=HTML)
            return

        if comment:
            comment = comment.replace("<", "").replace(">", "")

        if comment and len(comment) > 128:
            text = "❌ Комментарий не должен быть больше 128 символов"
            await message.answer(text, parse_mode=HTML)
            return

        to_user = await search_user(user.get_storage(), message, search_text, check_mute=True, bot_profile=bot_profile)
        if to_user:
            if to_user.user_id == user.user_id:
                text = "❌ Нельзя выполнить перевод себе"
                await message.answer(text, parse_mode=HTML)
                return

            # Вычисляем комиссии при переводе.
            fee_sum = utils.calc_fee(amount, config.FEE_SEND, config.PRICE_SEND)
            amount_with_fee = int(amount + fee_sum)

            anon_transfer = utils.is_msg_code(search_text)

            # Если не анон перевод и политика.
            if not anon_transfer and to_user.policy == 2:
                group = user.get_group()
                if not (await group.is_member(to_user.user_id)):
                    text = ("❌ Чтобы переводить этому пользователю, вы должны состоять с ним "
                            "в одной группе.")
                    await message.answer(text, parse_mode=HTML)
                    return

            if user.balance >= amount_with_fee:
                if 0 < amount <= 9_000_000:
                    payment_id = await user.send(to_user, amount, fee_sum, comment)

                    to_user_field = "Получатель неизвестен" if anon_transfer else to_user
                    text = (f"💸 <b>Перевод выполнен</b>\n{to_user_field}\n"
                            f"Сумма: <b>{utils.format_balance(amount)} 🪙</b>\n"
                            f"Комиссия: <b>{utils.format_balance(fee_sum)} 🪙</b>")
                    if comment:
                        text += f"\nКомментарий: <code>{comment}</code>"
                    await message.answer(text, parse_mode=HTML)

                    text_2 = (f"💵 <b>Входящий перевод</b>\n"
                              f"ID транзакции: <code>{payment_id}</code>\n"
                              f"Сумма: <b>{utils.format_balance(amount)} 🪙</b>")
                    if comment:
                        text_2 += f"\nКомментарий: <code>{comment}</code>"
                    try:
                        await message.bot.send_message(to_user.user_id, text_2, parse_mode=HTML)
                    except:
                        pass

                    if config.NEED_RECEIPT:
                        await message.answer("📝 Формирую квитанцию...")

                        # Формируем квитанцию о переводе.
                        try:
                            if anon_transfer:
                                to_account_id = "неизвестно"
                            else:
                                to_account_id = to_user.user_id

                            utils.create_receipt(to_account_id, amount, fee_sum, datetime.datetime.now(), payment_id)
                            await message.answer_photo(types.InputFile(f"receipts/receipt_{payment_id}.jpg"))
                        except:
                            pass

                else:
                    text = "❌ Сумма перевода должна быть не менее 1 монетки и не более 9'000'000 монеток"
                    await message.answer(text, parse_mode=HTML)

            else:
                text = ("❌ <b>Не хватает монеток</b>\n"
                        f"С учетом комиссии <b>{config.FEE_SEND}%</b> вам нужно <b>{utils.format_balance(amount_with_fee)} 🪙</b>\n"
                        f"Ваш текущий баланс: <b>{utils.format_balance(user.balance)} 🪙</b>")
                await message.answer(text, parse_mode=HTML)
    except:
        text = (f"❌ Ошибка - что-то пошло не так. Проверьте правильность вашей "
                f"введенной команды.")
        await message.answer(text, parse_mode=HTML)


async def control_anon_code(event: types.Message | types.CallbackQuery, user: entities.User):
    try:
        if isinstance(event, types.Message):
            if user.msg_code:
                text = ("💬 <b>Управление анонимным кодов</b>\n\n"
                        f"Ваш анонимный код: <code>{user.get_msg_code()}</code>\n\n"
                        f"Его можно использовать при переводах, отправке сообщений и других видах "
                        f"взаимодействия вместо вашего ID или юзернейма для скрытия вашей личности.")
                await event.reply(text, parse_mode=HTML,
                                  reply_markup=keyboards.msg_code_menu(user.user_id, True))
            else:
                text = ("💬 <b>Управление анонимным кодов</b>\n\n"
                        f"Вы еще не создали ваш анонимный код.\n\n"
                        f"Его можно использовать при переводах, отправке сообщений и других видах "
                        f"взаимодействия вместо вашего ID или юзернейма для скрытия вашей личности.")
                await event.reply(text, parse_mode=HTML,
                                  reply_markup=keyboards.msg_code_menu(user.user_id, False))
        else:
            person_id = int(event.data.split("_")[-1])
            new_code_price = config.PRICE_MSG_CODE

            assert user.user_id == person_id, "Сообщение адресовано не вам"

            if event.data.startswith("create_msg_code_"):
                text = ("ℹ️ <b>Подтвердите создание кода</b>\n"
                        f"Стоимость: <b>{new_code_price} 🪙</b>")
                rpl = keyboards.msg_code_menu(user.user_id, has_code=True, confirmed=True)

            elif event.data.startswith("recreate_msg_code_"):
                text = ("ℹ️ <b>Подтвердите создание кода</b>\n\n"
                        "⚠️ <b>Ваш прошлый код перестанет действовать.</b> Если вы кому-то его сообщали, "
                        "тот пользователь не сможешь больше по нему с вами связаться.\n\n"
                        f"Стоимость: <b>{new_code_price} 🪙</b>")
                rpl = keyboards.msg_code_menu(user.user_id, has_code=True, confirmed=True)

            elif event.data.startswith("dorecreate_msg_code_"):
                assert user.balance >= new_code_price, "Недостаточно монеток"
                await user.create_msg_code()

                text = ("💬 <b>Управление анонимным кодов</b>\n\n"
                        f"Ваш анонимный код: <code>{user.get_msg_code()}</code>\n\n"
                        f"Его можно использовать при переводах, отправке сообщений и других видах "
                        f"взаимодействия вместо вашего ID или юзернейма для скрытия вашей личности.")
                rpl = keyboards.msg_code_menu(user.user_id, has_code=False, confirmed=False)

            else:
                raise "Неправильная команда"

            await event.message.edit_text(text, parse_mode=HTML, reply_markup=rpl)

    except Exception as e:
        text = f"❌ {e}"
        if isinstance(event, types.Message):
            await event.answer(text, parse_mode=HTML)
        else:
            await event.answer(text, show_alert=True)


async def send_msg(event: types.Message, user: entities.User, bot_profile: aiogram.types.User):
    try:
        try:
            if not event.reply_to_message:
                raise

            # answ_{from_id}_{user_id}_{dialog_id:5}
            load = event.reply_to_message.reply_markup.inline_keyboard[0][0].callback_data
            assert "answ_" in load

            to_search_text = load.split("_")[1]
            to_id = int(load.split("_")[2])

            if load.count("_") == 3:
                dialog_id = load.split("_")[3]
            else:
                dialog_id = utils.create_dialog_id()

            assert to_id == user.user_id, "Сообщение адресовано не вам"
            message_text = " ".join(event.text.split()[1:])
            replied = True
        except:
            dialog_id = utils.create_dialog_id()
            to_search_text = event.text.split()[1]
            message_text = " ".join(event.text.split()[2:])
            replied = False

        if config.DEBUG_MODE:
            print(f"to_search_text: {to_search_text}")

        message_text = message_text.replace("<", "").replace(">", "")
        assert message_text, "Пустое сообщение"

        assert 1 <= len(message_text) <= 512, ("Текст сообщения не может быть больше "
                                               "512-ти символов в длину.")

        assert user.balance >= config.PRICE_MSG_SEND, "Недостаточно монеток на балансе"

        to_user = await search_user(user.get_storage(), event, to_search_text, True, bot_profile)
        if to_user:
            await user.send_message(to_user, message_text, dialog_id)

            to_account = to_search_text
            if to_account[0].isdigit():
                to_account = to_account.upper()
            try:
                if replied:
                    text = (f"📩 <b>Ответное сообщение</b>\n\n"
                            f"ID диалога: <code>{dialog_id}</code>\n\n"
                            f"{message_text}")
                else:
                    text = (f"📩 <b>Входящее сообщение</b>\n\n"
                            f"ID диалога: <code>{dialog_id}</code>\n\n"
                            f"{message_text}")
                rpl = keyboards.answer_letter_menu(
                    from_id=user.user_id,
                    user_id=to_user.user_id,
                    dialog_id=dialog_id
                )
                await event.bot.send_message(to_user.user_id, text, parse_mode=HTML,
                                             reply_markup=rpl)
            except:
                text = (f"❌ <b>Не удалось отправить сообщение</b>\n"
                        f"Возможно у получателя нет диалога с Аюми или он заблокировал её.")
                await event.answer(text, parse_mode=HTML)
            else:
                show_to_account = "неизвестно" if replied else to_account
                text = (f"📧 <b>Сообщение отправлено</b>\nПолучатель: <code>{show_to_account}</code>"
                        f"\nID диалога: <code>{dialog_id}</code>"
                        f"\n\n{message_text}\n\n")
                await event.answer(text, parse_mode=HTML)

    except Exception as e:
        text = f"❌ {e}"
        await event.answer(text, parse_mode=HTML)


async def trade(event: types.Message | types.CallbackQuery, user: entities.User):
    try:
        # /offerbuy [user] [crystals] [coins]
        # /offersell [user] [crystals] [coins]
        ...


    except Exception as e:
        text = f"❌ {e}"
        if isinstance(event, types.Message):
            await event.answer(text, parse_mode=HTML)
        else:
            await event.answer(text, show_alert=True)


async def hack(event: types.Message | types.CallbackQuery, user: entities.User):
    try:
        if isinstance(event, types.Message):
            bank_id = event.text.split()[1]
            mb_password: str = event.text.split()[2].lower()

            assert bank_id.isdigit(), "Номер счета должен является целым числом"
            bank_id = int(bank_id)

            assert utils.is_text_cleared(mb_password) and len(mb_password) <= 6, (
                f"Пароль может состоять только из букв латинского алфавита (abcde...) и "
                f"цифр (0123...) и должен быть не больше 6-ти символов в длину."
            )

            bank = await user.get_storage().get_bank_by_id(bank_id)
            assert bank, "Банковского счета с таким номером не существует"
            assert bank['user_id'] != user.user_id, "Этот счет принадлежит вам"

            text = (f"💻 <b>Подтвердите проверку пароля</b>\n"
                    f"Номер выбранного счета: <b>{bank_id}</b>\n"
                    f"Предполагаемый пароль: <b>{mb_password.upper()}</b>\n"
                    f"Стоимость: <b>{config.PRICE_HACK_CRYSTALS} 💎</b>")
            await event.reply(text, parse_mode=HTML,
                              reply_markup=keyboards.hack_menu(user.user_id, bank_id, mb_password))

        else:
            # hack_{user_id}_{bank_id}_{mb_password}
            hacker_id = int(event.data.split("_")[1])
            bank_id = int(event.data.split("_")[2])
            mb_password = event.data.split("_")[3]

            assert hacker_id == user.user_id, "Сообщение адресовано не вам"
            assert user.crystals >= config.PRICE_HACK_CRYSTALS, "Не хватает кристаллов"

            bank = await user.get_storage().get_bank_by_id(bank_id)
            assert bank, "Банковского счета с таким номером не существует"
            bank_password = bank['a_password']

            bank_owner_id: int = bank['user_id']
            group = user.get_group()
            assert not (await group.is_member(bank_owner_id)), ("Владелец банковского счета "
                                                                "является вашим товарищем по группе")

            bank_owner = entities.User(user.get_storage(), bank_owner_id)
            await bank_owner.load_from_db()

            # Получаем уровень группы владельца счета.
            owner_group = bank_owner.get_group()
            owner_group_level = await owner_group.get_level()

            # Вычисляем успешная ли попытка.
            successfully = utils.can_hack(bank_owner.protect_level, owner_group_level)

            # Списываем кристаллы и регистрируем платеж.
            await user.get_storage().remove_user_crystals(user.user_id, config.PRICE_HACK_CRYSTALS)
            await user.get_storage().add_payment(user.user_id, None, db.PaymentType.hack,
                                                 config.PRICE_HACK_CRYSTALS, db.Currency.crystals)
            await user.add_hack_attempt(bank_id, mb_password, bank_password, successfully)

            if not successfully:
                text = (f"🛰️ <b>Ошибка - в терминале помехи</b>\n"
                        f"Банковская защита владельца счета остановила вашу хакерскую "
                        f"атаку. Попробуйте еще раз.\n"
                        f"Списано с баланса: <b>{config.PRICE_HACK_CRYSTALS} 💎</b>")

                await event.message.edit_text(text, parse_mode=HTML)
                return

            h = utils.check_password_user(bank_password, mb_password)

            result: bool = h['result']
            description: str = h['description']

            result_string = "✅ Пароли совпадают" if result else "❌ Пароли не совпадают"

            text = ("📡 <b>Отчет сравнения паролей</b>\n\n"
                    "Буквы: <b>A B C D E F G H I J K L M N O P Q R S T U V W X Y Z</b>\n"
                    "Цифры: <b>0 1 2 3 4 5 6 7 8 9</b>\n\n"
                    f"Введенный пароль: <b>{mb_password.upper()}</b>\n"
                    f"Результат: <b>{result_string}</b>\n\n"
                    f"<u>Анализ совпадений</u>\n{description}\n\n"
                    f"<u>Учитывайте, что пароль у счета может быть от 1 до 6-ти символов.</u> "
                    f"Символы: ❌ - не совпадает тип (буква вместо цифры или наоборот), "
                    f"♻️ - нет символа (пароль короче), ⬆️ - буква должна быть ближе к "
                    f"началу алфавита (цифра должна быть больше), ⬇️ - наоборот, ☑️ - символ "
                    f"совпадает.")
            await event.message.edit_text(text, parse_mode=HTML)

    except Exception as e:
        text = f"❌ {e}"
        if isinstance(event, types.Message):
            await event.answer(text, parse_mode=HTML)
        else:
            await event.answer(text, show_alert=True)


async def show_group_members(call: types.CallbackQuery, user: entities.User):
    # memberslist_{leader_id}_{group_id}
    leader_id = int(call.data.split("_")[1])
    call_group_id = int(call.data.split("_")[2])

    if user.user_id != leader_id:
        await call.answer("❌ Сообщение адресовано не вам", show_alert=True)
        return

    group = user.get_group()
    if group.group_id != call_group_id:
        await call.answer("❌ Вы не состоите в этой группе", show_alert=True)
        return

    await group.update()
    if not (await group.is_leader(user.user_id)):
        await call.answer("❌ Вы не являетесь лидером этой группы", show_alert=True)
        return

    await call.message.edit_text("⏳ Отправляю список участников...")

    members = await group.get_members()
    if members:
        file_caption = (f"Участники группы '{group.get_name()}'\n"
                        "ID | Username | Имя | Фамилия | Баланс | Кристаллы\n")
        file_data = "\n".join([
            f"{u['user_id']} | {u['username']} | {u['first_name']} | {u['last_name']} | {u['balance']} | {u['crystals']}"
            for u in members
        ])
        file_text = file_caption + file_data

        async with aiofiles.open("members.txt", mode="w", loop=asyncio.get_event_loop()) as f:
            await f.write(file_text)

        await call.bot.send_document(user.user_id, types.InputFile("members.txt"),
                                     caption=f"Список {len(members)} участников")

    else:
        await call.answer("❌ Не удалось загрузить список участников", show_alert=True)


async def show_all_users(message: types.Message, user: entities.User):
    await message.answer("⏳ Отправляю список пользователей...")
    users = await user.get_storage().get_users()

    if users:
        file_caption = "ID | Username | Имя | Фамилия\n"
        file_data = "\n".join([
            f"{u['user_id']} | {u['username']} | {u['first_name']} | {u['last_name']}"
            for u in users if not (u['user_id'] in config.ADMINS)
        ])
        file_text = file_caption + file_data

        async with aiofiles.open("users.txt", mode="w", loop=asyncio.get_event_loop()) as f:
            await f.write(file_text)

        await message.answer_document(types.InputFile("users.txt"), caption=f"Список {len(users)} пользователей")
    else:
        text = "❌ Не удалось загрузить пользователей"
        await message.answer(text)


async def show_agreement(message: types.Message, user: entities.User, reply: bool = False):
    shown_first_name = user.first_name.replace("<", "").replace(">", "")
    if user.last_name:
        shown_last_name = " " + user.last_name.replace("<", "").replace(">", "")
    else:
        shown_last_name = ""

    text = (
        f"<b>Дорогой новоприбывший <a href='tg://user?id={user.user_id}'>{shown_first_name}{shown_last_name}</a>, добро пожаловать в наш чатик</b>\n\n"
        f"🆔 Вам присвоен номер: <tg-spoiler>{user.user_id}</tg-spoiler>\n\n"
        "✋ <b>Здесь отсутствует администрация.</b> Участники в праве сами определять, "
        "что есть хорошо, а что есть плохо.\n\n"
        "⚠️ <b>Пожалуйста прочитайте правила чата:</b> https://t.me/c/1896008686/17 "
        "(там несколько сообщений). Если вы не согласны с ними, то пожалуйста покиньте группу.\n\n"
        f"☢️ <b>У вас есть {utils.format_time(config.TIME_TO_AGREED)}, чтобы принять правила чата.</b>")

    inter = message.reply if reply else message.answer
    await inter(text, parse_mode=HTML, reply_markup=keyboards.agreement_menu(user.user_id),
                disable_web_page_preview=True)


async def search_user(storage: db.Storage, event: types.Message | types.CallbackQuery, search_text: str | int,
                      check_mute: bool, bot_profile: types.User) -> entities.User | None:
    """check_mute = True -> исключает из поиска пользователей в муте"""
    search_text = str(search_text).replace("@", "")
    if not utils.is_text_cleared(search_text, extra="_"):
        text = "❌ Некорректный формат имени пользователя или его ID"

        if isinstance(event, types.Message):
            await event.answer(text)
        else:
            await event.answer(text, show_alert=True)

        return

    if search_text.replace("@", "") in (bot_profile.id, bot_profile.username):
        text = "❌ Нельзя выполнить действие с Аюми"

        if isinstance(event, types.Message):
            await event.answer(text)
        else:
            await event.answer(text, show_alert=True)

        return

    person = await entities.search_user(storage, search_text)

    if person:
        # Проверяем есть ли у пользователя мут.
        if person.is_muted() and check_mute:
            text = "❌ Действие недоступно пока искомый пользователь находится в муте"
            if isinstance(event, types.Message):
                await event.answer(text)
            else:
                await event.answer(text, show_alert=True)

        else:
            return person

    else:
        text = "❌ Пользователь не существует или заблокирован"
        if isinstance(event, types.Message):
            await event.answer(text)
        else:
            await event.answer(text, show_alert=True)


async def check_availability(bot: Bot, action: types.Message, user: entities.User,
                             call: types.CallbackQuery | None = None,
                             ignore_agree: bool = False) -> entities.AvailabilityReport:
    # Проверяем ID на игнорируемые.
    if user.user_id in config.IGNORED_IDS:
        return entities.AvailabilityReport(result=False)

    # Проверяем лс это или чат.
    now_chat_id = action.chat.id
    if not (now_chat_id == config.CHAT_ID or now_chat_id == user.user_id):
        return entities.AvailabilityReport(result=False)
    in_chat = (now_chat_id == config.CHAT_ID)

    # Если пользователя нет в БД и он написал в лс.
    if not await user.exists():
        if in_chat:
            # Создаем пользователя в БД.
            await user.update()
            await show_agreement(action, user)
        else:
            text = ("❌ Я не нашла твоего аккаунта у себя в записях.\n"
                    "К сожалению, я пока не могу скинуть тебе ссылку для входа в чат.")
            await action.answer(text)
        return entities.AvailabilityReport(result=False, delete=in_chat)

    # Проверям на админ статус.
    if user.admin():
        return entities.AvailabilityReport(result=True)

    # Проверяем бан статус пользователя.
    if user.banned:
        if in_chat:
            # Если это чат, то баним пользователя в чате.
            await bot.ban_chat_member(config.CHAT_ID, user.user_id)
            text = f"⛔ Пользователь <code>{user.user_id}</code> исключен"
            await action.answer(text, parse_mode=HTML)
        else:
            # Если это личные сообщения.
            text = "⛔ Вы заблокированы в чате"
            if call:
                await call.answer(text, show_alert=True)
            else:
                await action.answer(text, parse_mode=HTML)

        return entities.AvailabilityReport(False, in_chat and not call)

    # Проверяем AGREED статус пользователя (кроме кнопки нажатия принятия соглашения).
    if not ignore_agree:
        if not user.agreed and call:
            text = ("❌ Подтвердите, что принимаете правила группы.\n"
                    "Для этого напишите любое сообщение в лс Аюми (боту).")
            await call.answer(text, show_alert=True)

            return entities.AvailabilityReport(result=False, delete=False)

        elif user.agreed is None:
            # Пользователю еще не отправлялось соглашение.
            await show_agreement(action, user)
            # Устанавливаем agreed = 0, чтобы больше не отправлять соглашение.
            await user.set_agreed(new_value=False)

            return entities.AvailabilityReport(result=False, delete=in_chat)

        elif not user.agreed and isinstance(action, types.Message):
            # Пользователю отправлили соглашение, но он еще не принял его.
            # Проверяем сколько времени прошло.
            now_time = datetime.datetime.now()

            # Если прошло больше заданного времени, то блокируем пользователя.
            if now_time.timestamp() - user.created.timestamp() > config.TIME_TO_AGREED:
                await user.ban()
                await bot.ban_chat_member(config.CHAT_ID, user.user_id)

                if in_chat:
                    text = (f"⛔️ <b>Пользователь исключен</b>\n{user}\nБаланс: <b>{utils.format_balance(user.balance)} 🪙</b>\n\n"
                            f"Причина: не подтвердил согласие с правилами группы в течение {utils.format_time(config.TIME_TO_AGREED)}.")
                    await action.answer(text, parse_mode=HTML)

                else:
                    text = ("⛔️ Вы были заблокированы, так как не подтвердили согласие "
                            f"с правилами группы в течение {utils.format_time(config.TIME_TO_AGREED)}")
                    await action.answer(text)

            return entities.AvailabilityReport(result=False, delete=in_chat)

    # Проверяем мут статус пользователя.
    now_time = datetime.datetime.now()
    if user.is_muted():
        # Если мут уже прошел, то снимаем его.
        if now_time >= user.muted:
            pass

        else:
            # Вычисляем сколько осталось времени в часах.
            time_left = utils.format_time(int(user.muted.timestamp() - now_time.timestamp()))

            text = f"🔇 Вы в муте еще на {time_left}"
            if call:
                await call.answer(text, show_alert=True)
                return entities.AvailabilityReport(result=False, delete=False)

            if in_chat:
                return entities.AvailabilityReport(result=False, delete=True)
            else:
                await action.answer(text)
                return entities.AvailabilityReport(result=False, delete=False)

    # Проверяем состоит ли пользователь в чате, если пишет в лс.
    if not in_chat and not await user.subscribed(bot):
        text = "❌ Я могу общаться только с пользователями чата"
        if call:
            await call.answer(text, show_alert=True)
        else:
            await action.answer(text)

        return entities.AvailabilityReport(result=False)

    return entities.AvailabilityReport(True)
