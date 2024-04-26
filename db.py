import asyncio
import random
import typing
import copy

import aiomysql
import datetime

import config
import entities
import utils

HIGH_LIMIT = 9999


class Tables:
    users = "users"
    reports = "reports"
    polls = "polls"
    votes = "votes"
    temp_storage = "temp_storage"
    banks = "banks"
    transfers = "transfers"
    hugs = "hugs"
    tasks = "tasks"
    casino = "casino"
    market = "market"
    payments = "payments"
    credits = "credits"
    teams = "teams"
    hacks = "hacks"
    messages = "messages"
    ads = "ads"


class Currency:
    crystals = "crystals"
    coins = "coins"


class PaymentType:
    market = "market"
    reports_removing = "reports_removing"
    create_group = "create_group"
    join_group = "join_group"
    rename_group = "rename_group"
    updage_group = "upgrade_group"
    group_member_tax = "group_member_tax"
    group_leader_fine = "group_leader_fine"
    upgrade_bank = "upgrade_bank"
    protect_level = "protect_level"
    alcohol = "alcohol"
    cigarettes = "cigarettes"
    drugs = "drugs"
    hack = "hack"
    create_msg_code = "create_msg_code"
    send_message = "send_message"
    post_ad = "post_ad"
    unbank = "unbank"
    relink_bank = "relink_bank"


class MarketDirection:
    sell = "sell"
    buy = "buy"


class Storage:
    def __init__(self, loop):
        self.loop = loop
        self.pool = None
        self.local = {}

    def local_value(self, user_id: int, key: str, new_value=None, default_value=None):
        uid = str(user_id)
        if new_value is None:
            return self.local.get(uid, {}).get(key, default_value)
        else:
            if isinstance(new_value, (list, tuple, dict)):
                new_value = copy.deepcopy(new_value)

            if not self.local.get(uid):
                self.local[uid] = {}

            self.local[uid][key] = new_value

    def reset_local_value(self, user_id: int, key: str):
        uid = str(user_id)
        if self.local.get(uid, {}).get(key):
            self.local[uid].pop(key)

    def get_cooldown_last_time(self, user_id: int, key: str) -> int:
        last_time = self.local_value(user_id, key)
        if not isinstance(last_time, (int, float)):
            last_time = 0

        return int(last_time)

    def cooldown(self, user_id: int, key: str, required_cooldown: int) -> bool:
        last_time = self.local_value(user_id, key)
        if not isinstance(last_time, (int, float)):
            last_time = 0

        last_time: int | float
        now = datetime.datetime.now()

        if not last_time:
            self.local_value(user_id, key, now.timestamp())
            print(f"local_value: {self.local_value(user_id, key)}")
            return True

        if now.timestamp() - last_time >= required_cooldown:
            self.local_value(user_id, key, now.timestamp())
            return True
        else:
            return False

    def common_cooldown(self, key: str, required_cooldown: int) -> bool:
        return self.cooldown(0, key, required_cooldown)

    async def _update_pool(self):
        if self.pool is None:
            self.pool = await aiomysql.create_pool(
                host='127.0.0.1',
                port=3306,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                db=config.DB_DATABASE,
                loop=self.loop,
                cursorclass=aiomysql.DictCursor,
                autocommit=True
            )

    async def _execute(self, query):
        # Создаем пул, если он не создан.
        await self._update_pool()

        async with self.pool.acquire() as connection:
            connection: aiomysql.Connection

            async with connection.cursor() as cursor:
                cursor: aiomysql.cursors.DictCursor

                if config.DEBUG_MODE:
                    print(query.replace("    ", ""))

                await cursor.execute(query)
                return await cursor.fetchall()

    @staticmethod
    def cnv(value) -> str:
        if value is None:
            return "NULL"
        elif isinstance(value, datetime.datetime):
            return f"'{value}'"
        elif isinstance(value, bool):
            return str(int(value))
        return f"'{aiomysql.escape_string(str(value))}'"

    @staticmethod
    def convert_update_string(d: dict) -> str:
        return ", ".join([f"{k} = {Storage.cnv(v)}" for k, v in d.items()])

    @staticmethod
    def convert_insert_string(values: typing.Iterable, escaping: bool) -> str:
        return ", ".join([(Storage.cnv(x) if escaping else x) for x in values])

    async def _exists(self, table: str, where: str) -> bool:
        q = f"""
            SELECT 1 FROM {table}
            WHERE {where};
        """
        return bool(await self._execute(q))

    async def _update(self, table: str, payload: dict, where: str):
        q = f"""
            UPDATE {table}
            SET {Storage.convert_update_string(payload)}
            WHERE {where};
        """
        await self._execute(q)

    async def _insert(self, table: str, payload: dict):
        q = f"""
            INSERT INTO {table}
                ({Storage.convert_insert_string(payload.keys(), escaping=False)})
            VALUES
                ({Storage.convert_insert_string(payload.values(), escaping=True)});
        """
        await self._execute(q)

    async def _select(self, table: str, keys: list | None = None, where: str | None = None, limit: int | None = None) -> tuple[dict]:
        keys_query = ", ".join(keys) if keys else "*"
        where_query = f"WHERE {where}" if where else ""
        limit_queary = f"LIMIT {limit}" if limit else ""

        q = f"""
            SELECT {keys_query}
            FROM {table} {where_query} {limit_queary};
        """
        return await self._execute(q)

    async def _select_one(self, table: str, keys: list | None = None, where: str | None = None) -> dict:
        return (await self._select(table, keys, where, 1))[0]

    async def _delete(self, table: str, where: str, limit: int = 1):
        q = f"""
            DELETE FROM {table}
            WHERE {where}
            LIMIT {limit};
        """
        await self._execute(q)

    async def _insert_or_update(self, table: str, insert_payload: dict,
                                update_payload: dict, where: str) -> bool:
        """
        :return: True - Inserted, False - Updated
        """
        # Проверяем на наличие записи в таблице.
        if await self._exists(table, where):
            if update_payload:
                # Запись существует, обновляем.
                await self._update(table, update_payload, where)
            return False
        else:
            if insert_payload:
                # Запись отсутствует, создаем.
                await self._insert(table, insert_payload)
            return True

    async def increase_user_balance(self, user_id: int, increase_by: int):
        q = f"""
            UPDATE users
            SET balance = balance + {increase_by}
            WHERE user_id = {user_id};
        """
        await self._execute(q)

    async def load_user_balance_from_db(self, user):
        condition = f"user_id = {user.user_id}"
        info = await self._select_one(Tables.users, where=condition)

        user.balance = info["balance"]
        user.crystals = info["crystals"]

    async def decrease_user_balance(self, user_id: int, decrease_by: int):
        """Уменьшение баланса"""
        q = f"""
            UPDATE users
            SET balance = balance - {decrease_by}
            WHERE user_id = {user_id};
        """
        await self._execute(q)

    async def add_user_crystals(self, user_id: int, crystals: int):
        """Увеличение баланса"""
        q = f"""
            UPDATE users
            SET crystals = crystals + {crystals}
            WHERE user_id = {user_id};
        """
        await self._execute(q)

    async def remove_user_crystals(self, user_id: int, crystals: int):
        q = f"""
            UPDATE users
            SET crystals = crystals - {crystals}
            WHERE user_id = {user_id};
        """
        await self._execute(q)

    async def user_exists(self, user_id: int) -> bool:
        return await self._exists(Tables.users, f"user_id = {user_id}")

    async def load_user_from_db(self, user):
        where = f"user_id = {user.user_id}"
        user_info = await self._select_one(Tables.users, where=where)

        if not (user.username or user.first_name or user.last_name):
            user.username = user_info["username"]
            user.first_name = user_info["first_name"]
            user.last_name = user_info["last_name"]

        user.balance = user_info["balance"]
        user.crystals = user_info["crystals"]
        user.team_id = user_info["team_id"]
        user.policy = user_info["policy"]
        user.msg_code = user_info["msg_code"]
        user.extra_percent = user_info["extra_percent"]
        user.protect_level = user_info["protect_level"]
        user.banned = user_info["banned"]
        user.muted = user_info["muted"]
        user.agreed = user_info["agreed"]

        user.reward_updated = user_info["reward_updated"]
        user.updated = user_info["updated"]
        user.created = user_info["created"]

    async def update_user(self, user):
        condition = f"user_id = {user.user_id}"
        # Проверяем на существование учетную запись пользователя.
        if await self._exists(Tables.users, condition):
            user.first = False
            # Загружаем информацию из БД.
            user_info = await self._select_one(Tables.users, where=condition)

            user.balance = user_info["balance"]
            user.crystals = user_info["crystals"]

            user.team_id = user_info["team_id"]
            user.msg_code = user_info["msg_code"]
            user.policy = user_info["policy"]
            user.extra_percent = user_info["extra_percent"]
            user.protect_level = user_info["protect_level"]

            user.banned = user_info["banned"]
            user.muted = user_info["muted"]
            user.agreed = user_info["agreed"]

            user.reward_updated = user_info["reward_updated"]
            user.updated = user_info["updated"]
            user.created = user_info["created"]

            # Обновляем значения пользователя, которые могут измениться.
            payload = {
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name
            }

            # Проверяем вознаграждение за общение.
            now_time = datetime.datetime.now()
            if user.reward_updated and now_time.timestamp() - user.reward_updated.timestamp() >= config.COOLDOWN_CHAT_REWARD:
                if not config.DEBUG_MODE:
                    # Получаем уровень группы.
                    group_level = await self.get_group_level(user.team_id)
                    # Вычисляем вознаграждение.
                    reward = utils.calc_reward(group_level)
                    # Обновляем значение баланса в БД.
                    await self.increase_user_balance(user.user_id, reward)
                # Прописываем новое время последнего вознаграждения.
                payload["reward_updated"] = now_time

            # Обновляем только если пользователь не в муте.
            if not user.is_muted():
                payload["updated"] = now_time

            await self._update(Tables.users, payload, condition)

        else:
            # Первый вход в бота.
            user.first = True
            # Записываем информацию.
            payload = {
                "user_id": user.user_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name
            }
            await self._insert(Tables.users, payload)

    async def update_temp_storage(self, key_name: str, string_value: str | int | None):
        if not (string_value is None):
            string_value = str(string_value)

        payload = {
            "key_name": key_name,
            "string_value": string_value
        }

        await self._insert_or_update(Tables.temp_storage, payload, payload, f"key_name = {self.cnv(key_name)}")

    async def get_temp_storage(self, key_name: str) -> str | None:
        try:
            return (await self._select_one(Tables.temp_storage, ["string_value"], f"key_name = {self.cnv(key_name)}"))["string_value"]
        except:
            return

    async def get_user_by_id(self, user_id: int) -> dict:
        cond = f"user_id = {user_id}"
        return await self._select_one(Tables.users, where=cond)

    async def search_user(self, search_text: str) -> dict:
        mandatory_condition = " AND banned = 0 AND agreed = 1"
        if search_text.isdigit():
            # Проверяем как ID пользователя.
            wh = f"user_id = {int(search_text)}" + mandatory_condition
        else:
            # Проверяем как юзернейм пользователя.
            ready_search_text = search_text.lower().replace('@', '')
            wh = (f"(username = {self.cnv(ready_search_text)} OR msg_code = {self.cnv(ready_search_text)})"
                  + mandatory_condition)
        return await self._select_one(Tables.users, where=wh)

    async def last_hug_user(self, from_id: int, to_id: int) -> datetime.datetime | None:
        try:
            q = f"""
                SELECT created FROM hugs
                WHERE from_id = {from_id} AND to_id = {to_id}
                ORDER BY created DESC LIMIT 1;
            """
            return (await self._execute(q))[0]["created"]
        except:
            return

    async def last_hug(self, from_id: int) -> datetime.datetime | None:
        try:
            q = f"""
                SELECT created FROM hugs
                WHERE from_id = {from_id}
                ORDER BY created DESC LIMIT 1;
            """
            return (await self._execute(q))[0]["created"]
        except:
            return

    async def hug_exists(self, from_id: int, to_id: int) -> bool:
        return await self._exists(Tables.hugs, f"from_id = {from_id} AND to_id = {to_id}")

    async def add_hug(self, from_id: int, from_balance: int, to_id: int):
        payload = {
            "from_id": from_id,
            "to_id": to_id
        }
        await self._insert(Tables.hugs, payload)
        await self.increase_user_balance(to_id, utils.calc_hug_reward(from_balance))

    async def get_users_percent_dict(self) -> dict:
        users_task = asyncio.create_task(self._select(Tables.users))
        group_task = asyncio.create_task(self._select(Tables.teams))

        users = await users_task
        groups_list: tuple[dict] = await group_task

        groups = {}
        for group in groups_list:
            group: dict
            groups[group['team_id']] = group['level']

        percentage = {}
        for user in users:
            extra_group_percent = groups.get(user['team_id'], 0)
            percentage[user['user_id']] = int(user['extra_percent'] + config.BET_BANK_DAILY_DEFAULT + extra_group_percent)

        return percentage

    async def get_top_groups(self) -> list:
        cond = f"team_id AND banned = 0 AND agreed = 1"

        group_members_task = asyncio.create_task(self._select(Tables.users, where=cond))
        banks_task = asyncio.create_task(self.get_top_banks())
        groups_db_task = asyncio.create_task(self.get_groups())

        group_members = list(await group_members_task)
        banks = await banks_task
        groups_db = await groups_db_task

        # keys: members: list[int], balance: int
        groups = {}

        for member in group_members:
            user_id: int = member['user_id']
            group_id: int = member['team_id']
            balance: int = member['balance']
            crystals: int = member['crystals']

            if groups.get(group_id) is None:
                groups[group_id] = {
                    "members": [],
                    "balance": 0,
                    "crystals": 0
                }

            groups[group_id]["members"].append(user_id)
            groups[group_id]["balance"] += balance
            groups[group_id]["crystals"] += crystals

        for bank in banks:
            owner_id: int = bank["user_id"]
            now_balance: int = bank['unbankSum']

            for group_id in groups.keys():
                if owner_id in groups[group_id]['members']:
                    groups[group_id]['balance'] += now_balance
                    break

        for group_info in groups_db:
            if groups.get(group_info['team_id']):
                groups[group_info['team_id']]['caption'] = group_info['caption']

        groups = [
            {
                "group_id": gid,
                "caption": groups[gid]['caption'],
                "members": len(groups[gid]['members']),
                "balance": int(groups[gid]['balance']),
                "crystals": int(groups[gid]['crystals'])
            }
            for gid in groups.keys()
        ]
        groups.sort(key=lambda x: x["balance"], reverse=True)

        return groups

    async def get_top_banks(self) -> list:
        cond = "status = 1"
        banks = list(await self._select(Tables.banks, where=cond))
        users_percent_dict = await self.get_users_percent_dict()

        for bank in banks:
            owner_id = bank["user_id"]
            user_percent = users_percent_dict[owner_id]
            bank["unbankSum"] = utils.calc_bank_balance(bank["balance"], user_percent, bank["created"])
            bank["ownerPercent"] = user_percent

        banks.sort(key=lambda x: x["unbankSum"], reverse=True)

        return banks

    async def get_user_banks(self, user, banks: list | None = None) -> list:
        if banks:
            user_banks = [bank for bank in banks if bank["user_id"] == user.user_id]
        else:
            cond = f"user_id = {user.user_id} AND status = 1"

            user_banks = list(await self._select(Tables.banks, where=cond))

            for bank in user_banks:
                bank["unbankSum"] = utils.calc_bank_balance(bank["balance"], await user.get_bank_percent(), bank["created"])

            user_banks.sort(key=lambda x: x["unbankSum"], reverse=True)
        return user_banks

    async def get_bank_by_id(self, bank_id: int) -> dict:
        try:
            cond = f"account_id = {bank_id} AND status = 1"
            return await self._select_one(Tables.banks, where=cond)
        except:
            return {}

    async def get_banks_profile_info(self, user, banks: list | None = None) -> dict:
        user_banks = await self.get_user_banks(user, banks)
        total_balance = int(sum([bank["unbankSum"] for bank in user_banks]))
        return {
            "balance": total_balance,
            "count": len(user_banks)
        }

    async def create_bank(self, user, amount: int, amount_with_fee: int, password: str):
        # Создаем счет.
        payload = {
            "user_id": user.user_id,
            "a_password": password,
            "balance": amount
        }
        await self._insert(Tables.banks, payload)
        # Уменьшаем баланс.
        await self.decrease_user_balance(user.user_id, amount_with_fee)

    async def set_user_agreed(self, user, new_value: bool):
        payload = {
            "agreed": new_value
        }
        await self._update(Tables.users, payload, f"user_id = {user.user_id}")

    async def change_bank_password(self, user_id: int, old_password: str, new_password: str, fee: int) -> dict | None:
        old_password = old_password.lower()
        new_password = new_password.lower()

        bank_condition = f"a_password = {self.cnv(old_password)} AND status = 1"
        if await self._exists(Tables.banks, bank_condition):
            bank = await self._select_one(Tables.banks, where=bank_condition)
            if bank:
                # Снимаем кристаллы.
                await self.remove_user_crystals(user_id, config.PRICE_CHANGE_BANK_CRYSTALS)
                # Обновляем пароль.
                payload = {
                    "a_password": new_password
                }
                await self._update(Tables.banks, payload, bank_condition)

                return bank
            else:
                raise

        else:
            # Снимаем комиссию с пользователя.
            await self.decrease_user_balance(user_id, fee)

    async def relink_bank(self, user_id: int, password: str) -> dict:
        password = password.lower()
        bank_condition = f"a_password = {self.cnv(password)} AND status = 1"
        if await self._exists(Tables.banks, bank_condition):
            await self.remove_user_crystals(user_id, config.PRICE_LINK_CRYSTALS)
            await self.add_payment(user_id, None, PaymentType.relink_bank, config.PRICE_LINK_CRYSTALS, Currency.crystals)

            bank = await self._select_one(Tables.banks, where=bank_condition)

            payload = {
                "user_id": user_id
            }
            await self._update(Tables.banks, payload, bank_condition)
            return bank
        return {}

    async def get_bank_by_password(self, user, password: str, fee: int) -> dict | None:
        password = password.lower()
        bank_condition = f"a_password = {self.cnv(password)} AND status = 1"
        if await self._exists(Tables.banks, bank_condition):
            bank = await self._select_one(Tables.banks, where=bank_condition)

            bank_owner = entities.User(user.get_storage(), bank['user_id'])
            await bank_owner.load_from_db()

            # Вычисляем сумму для начисления.
            unbank_sum = utils.calc_bank_balance(int(bank["balance"]), await bank_owner.get_bank_percent(), bank["created"])
            bank["unbankSum"] = unbank_sum

            return bank
        else:
            # Снимаем комиссию с пользователя.
            await self.decrease_user_balance(user.user_id, fee)
            return None

    async def unbank_by_password(self, user, password: str, fee: int) -> dict | None:
        password = password.lower()
        bank_condition = f"a_password = {self.cnv(password)} AND status = 1"
        if await self._exists(Tables.banks, bank_condition):
            bank = await self._select_one(Tables.banks, where=bank_condition)

            if bank:
                # Снимаем кристаллы.
                await self.remove_user_crystals(user.user_id, config.PRICE_UNBANK_CRYSTALS)
                # Регистрируем платеж.
                await self.add_payment(user.user_id, None, PaymentType.unbank, config.PRICE_UNBANK_CRYSTALS, Currency.crystals)

                bank_owner = entities.User(user.get_storage(), bank['user_id'])
                await bank_owner.load_from_db()

                # Вычисляем сумму для начисления.
                unbank_sum = utils.calc_bank_balance(int(bank["balance"]), await bank_owner.get_bank_percent(), bank["created"])
                bank["unbankSum"] = unbank_sum

                # Деактивируем запись о счете.
                payload = {
                    "status": False
                }
                await self._update(Tables.banks, payload, bank_condition)

                # Увеличиваем баланс пользователя.
                await self.increase_user_balance(user.user_id, unbank_sum)

                return bank
            else:
                raise
        else:
            # Снимаем комиссию с пользователя.
            await self.decrease_user_balance(user.user_id, fee)

    async def ban_user(self, user):
        payload = {
            "banned": True,
            "team_id": None
        }
        cond = f"user_id = {user.user_id}"
        await self._update(Tables.users, payload, cond)

    async def mute_user(self, user, muted_till: int | datetime.datetime):
        if isinstance(muted_till, int):
            muted_till = datetime.datetime.fromtimestamp(muted_till)

        payload = {
            "muted": muted_till
        }
        cond = f"user_id = {user.user_id}"
        await self._update(Tables.users, payload, cond)

    async def unmute_user(self, user):
        q = f"""
            UPDATE users
            SET muted = '2000-01-01 01:00:00'
            WHERE user_id = {user.user_id};
        """
        await self._execute(q)

    async def get_users(self) -> tuple:
        keys = ["user_id", "username", "first_name", "last_name", "balance", "team_id", "extra_percent", "protect_level", "crystals"]
        cond = f"banned = 0 AND agreed = 1"
        return await self._select(Tables.users, keys, cond)

    async def get_random_users(self, number: int) -> tuple:
        users = list(await self.get_users())
        random.shuffle(users)
        return tuple(users[:number])

    async def send_crystals(self, from_user, to_user, amount: int, comment: str | None):
        # Уменьшаем баланс кристаллов пользователя.
        await self.remove_user_crystals(from_user.user_id, amount)
        # Увеличиваем баланс кристаллов пользователя.
        await self.add_user_crystals(to_user.user_id, amount)

        # Записываем перевод в БД.
        if not comment:
            comment = None
        payload = {
            "to_id": to_user.user_id,
            "from_id": from_user.user_id,
            "amount": amount,
            "fee_sum": 0,
            "currency": Currency.crystals,
            "t_comment": comment
        }
        await self._insert(Tables.transfers, payload)

    async def send(self, from_user, to_user, amount: int, fee_sum: int, comment: str | None) -> int:
        # Уменьшаем баланс пользователя.
        await self.decrease_user_balance(from_user.user_id, int(amount + fee_sum))

        # Увеличиваем баланс пользователя.
        await self.increase_user_balance(to_user.user_id, amount)
        # Записываем перевод в БД.
        if not comment:
            comment = None
        payload = {
            "to_id": to_user.user_id,
            "from_id": from_user.user_id,
            "amount": int(amount),
            "fee_sum": int(fee_sum),
            "currency": Currency.coins,
            "t_comment": comment
        }
        await self._insert(Tables.transfers, payload)
        # Получаем ID транзакции.
        q = f"""
            SELECT transfer_id FROM transfers
            WHERE to_id = {to_user.user_id} AND from_id = {from_user.user_id} AND
                amount = {int(amount)} AND fee_sum = {int(fee_sum)}
            ORDER BY transfer_id DESC LIMIT 1;
        """
        return int((await self._execute(q))[0]["transfer_id"])

    async def get_total_balance(self) -> int:
        now = datetime.datetime.now()
        q = f"""
            SELECT SUM(balance) as total_balance FROM users
            WHERE agreed = 1 AND banned = 0 AND muted <= '{now}';
        """
        return int((await self._execute(q))[0]["total_balance"])

    async def report_user(self, from_user, to_user, comment: str | None):
        # Начисляем вознаграждение.
        await self.increase_user_balance(from_user.user_id, config.REWARD_REPORT)

        from_balance = 0 if to_user.user_id == config.ADMIN_ID else from_user.balance
        if not comment:
            comment = None

        # Записываем жалобу.
        payload = {
            "to_id": to_user.user_id,
            "from_id": from_user.user_id,
            "from_balance": from_balance,
            "r_comment": comment
        }
        await self._insert(Tables.reports, payload)

    async def remove_user_reports(self, user):
        cond = f"to_id = {user.user_id}"
        await self._delete(Tables.reports, cond, HIGH_LIMIT)

    async def get_reports_sum(self, user) -> dict:
        try:
            keys = ["from_balance"]
            reports = await self._select(Tables.reports, keys, f"to_id = {user.user_id}")

            total_sum = 0
            for report in reports:
                total_sum += report["from_balance"]

            return {
                "count": len(reports),
                "sum": int(total_sum)
            }
        except:
            return {
                "count": 0,
                "sum": 0
            }

    async def get_users_count(self, include_muted: bool = False) -> int:
        now = datetime.datetime.now()
        extra_string = "" if include_muted else f"AND muted <= '{now}'"
        q = f"""
            SELECT COUNT(*) as users_count FROM users
            WHERE agreed = 1 AND banned = 0 {extra_string};
        """
        return int((await self._execute(q))[0]["users_count"])

    async def get_last_poll_time(self, user) -> datetime.datetime | None:
        try:
            q = f"""
                SELECT created, poll_id FROM polls
                WHERE to_id = {user.user_id}
                ORDER BY poll_id DESC LIMIT 1;
            """
            return (await self._execute(q))[0]["created"]
        except:
            return None

    async def get_last_report_time(self, user) -> datetime.datetime | None:
        try:
            q = f"""
                SELECT report_id, created FROM reports
                WHERE from_id = {user.user_id}
                ORDER BY report_id DESC LIMIT 1;
            """
            return (await self._execute(q))[0]["created"]
        except:
            return None

    async def get_poll(self, poll_id: int, stage: int) -> dict:
        return await self._select_one(Tables.polls, where=f"poll_id = {poll_id} AND stage = {stage}")

    async def get_vote(self, user, poll_id: int, stage: int) -> dict:
        try:
            cond = f"poll_id = {poll_id} AND user_id = {user.user_id} AND stage = {stage}"
            return await self._select_one(Tables.votes, where=cond)
        except:
            return {}

    async def vote(self, user, poll_id: int, stage: int, decision: str):
        payload = {
            "user_id": user.user_id,
            "poll_id": poll_id,
            "stage": stage,
            "decision": decision,
            "from_balance": user.balance
        }
        await self._insert(Tables.votes, payload)

    async def finish_poll(self, poll_id: int, win_decision_1: str, win_decision_2: str | None):
        payload = {
            "stage": 3,
            "win_decision_1": win_decision_1,
            "win_decision_2": win_decision_2
        }
        await self._update(Tables.polls, payload, f"poll_id = {poll_id}")

    async def register_poll(self, user) -> int:
        # Регистриуем новый опрос.
        table = Tables.polls
        payload = {
            "to_id": user.user_id
        }
        await self._insert(table, payload)

        # Получаем ID опроса.
        q = f"""
            SELECT poll_id FROM polls
            WHERE to_id = {user.user_id} AND stage = 1
            ORDER BY poll_id DESC LIMIT 1;
        """
        poll_id = int((await self._execute(q))[0]["poll_id"])

        # Удаляем все жалобы.
        await self._delete(Tables.reports, f"to_id = {user.user_id}", HIGH_LIMIT)

        return poll_id

    async def get_last_finished_poll_time(self, user) -> datetime.datetime | None:
        try:
            q = f"""
                SELECT * FROM polls
                WHERE to_id = {user.user_id} AND stage = 1
                ORDER BY created DESC LIMIT 1;
            """
            return (await self._execute(q))[0]["created"]
        except:
            return None

    async def get_poll_votes(self, poll_id: int, stage: int) -> dict:
        """
        :param poll_id:
        :param stage:
        :return: {"balances": {decision: total_balance}, "count": {decision: total_count}}
        """
        cond = f"poll_id = {poll_id} AND stage = {stage}"
        votes = await self._select(Tables.votes, where=cond)

        print(f"votes: {votes}")

        variants = {}
        numbers = {}
        for vote in votes:
            decision = vote["decision"]
            from_balance = vote["from_balance"]

            if variants.get(decision):
                variants[decision] += from_balance
                numbers[decision] += 1
            else:
                variants[decision] = from_balance
                numbers[decision] = 1

        return {
            "balances": variants,
            "count": numbers
        }

    async def transfer_to_users_percent(self, user_percent: int, amount: int) -> dict:
        """
        :param user_percent:
        :param amount:
        :return: {"amount_per_user": int, "users": list[dict]}
        """
        # Получаем пользователей.
        users = list(await self.get_users())
        # Количество пользователей, соответствующее проценту.
        users_count_to_transfer = int(len(users) * user_percent / 100)
        random.shuffle(users)

        # Пользователи, которые получат перевод.
        users_to_transfer = users[:users_count_to_transfer]
        # Монетки для каждого пользователя.
        amount_per_user = int(amount / len(users_to_transfer))

        if amount_per_user:
            #  Переводим каждому пользователю.
            for one_user in users_to_transfer:
                to_user_id = one_user["user_id"]
                await self.increase_user_balance(to_user_id, amount_per_user)

            return {
                "amount_per_user": amount_per_user,
                "users": users_to_transfer
            }

        else:
            return {}

    async def get_worst_balances(self) -> list:
        q = """
            SELECT balance FROM users
            WHERE banned = 0 AND agreed = 1
            ORDER BY balance
            LIMIT 10;
        """
        r = await self._execute(q)
        balances = [row['balance'] for row in r]
        return balances

    async def get_top_balances(self) -> list:
        users = await self.get_top_users()
        balances = [row['balance'] for row in users]
        return balances

    async def get_top_crystal_balances(self) -> list:
        q = """
            SELECT crystals FROM users
            WHERE banned = 0 AND agreed = 1
            ORDER BY crystals DESC;
        """
        r = await self._execute(q)
        balances = [row['crystals'] for row in r]
        return balances

    async def get_disagreed_users(self) -> list:
        now = datetime.datetime.now()
        then = now - datetime.timedelta(seconds=config.TIME_TO_AGREED)
        cond = f"banned = 0 AND agreed = 0 AND created <= '{then}'"

        rows = await self._select(Tables.users, ["user_id"], where=cond)
        users = [x["user_id"] for x in rows]

        return users

    async def get_inactive_users(self) -> list:
        now = datetime.datetime.now()
        then = now - datetime.timedelta(seconds=config.TIME_USER_MAX_INACTIVE)
        cond = f"banned = 0 AND updated < '{then}'"

        rows = await self._select(Tables.users, ["user_id"], where=cond)
        users = [x["user_id"] for x in rows]

        return users

    async def get_top_users(self, banks: list | None = None) -> list:
        q = """
            SELECT user_id, balance FROM users
            WHERE banned = 0 AND agreed = 1
            ORDER BY balance DESC;
        """
        users = list(await self._execute(q))

        if not banks:
            banks = await self.get_top_banks()

        for user_note in users:
            for bank in banks:
                if bank["user_id"] == user_note["user_id"]:
                    unbank_sum = bank["unbankSum"]
                    user_note["balance"] = int(user_note["balance"] + unbank_sum)

        users.sort(key=lambda x: x["balance"], reverse=True)

        return users

    async def get_top_place_info(self, user) -> dict:
        try:
            banks = await self.get_top_banks()
            users = await self.get_top_users(banks)

            uids = [row['user_id'] for row in users]

            return {
                "place": uids.index(user.user_id) + 1,
                "total": len(uids),
                "users": users,
                "banks": banks
            }
        except:
            return {}

    async def play_game(self, user_id: int, bet_amount: int, profit: int):
        payload = {
            "user_id": user_id,
            "bet_amount": bet_amount,
            "profit": profit
        }
        await self._insert(Tables.casino, payload)

    async def get_market_crystals_count(self, user_id: int) -> dict[str: int]:
        """
        :param user_id:
        :return: {"buy": int, "sell": int}
        """
        cond = f"crystals > 0 AND direction IN ('sell', 'buy') AND user_id = {user_id}"
        offers = await self._select(Tables.market, where=cond)

        buy = 0
        sell = 0
        for offer in offers:
            if offer["direction"] == "sell":
                sell += offer['crystals']

            elif offer["direction"] == "buy":
                buy += offer['crystals']

        return {
            "sell": int(sell),
            "buy": int(buy)
        }

    async def get_market_offer(self, offer_id: int) -> dict:
        try:
            cond = f"crystals > 0 AND offer_id = {offer_id}"
            return await self._select_one(Tables.market, where=cond)
        except:
            return {}

    async def get_market_offers(self) -> dict:
        cond = f"crystals > 0 AND direction IN ('sell', 'buy')"
        offers = await self._select(Tables.market, where=cond)

        sell_offers = []
        buy_offers = []

        for offer in offers:
            if offer["direction"] == "sell":
                sell_offers.append(offer)

            elif offer["direction"] == "buy":
                buy_offers.append(offer)

        # Сортируем.
        if sell_offers:
            sell_offers.sort(key=lambda x: x['price'])
        if buy_offers:
            buy_offers.sort(key=lambda x: x['price'], reverse=True)

        return {
            "sell": sell_offers,
            "buy": buy_offers
        }

    async def update_offer(self, offer: dict):
        payload = {
            "crystals": offer['crystals']
        }
        cond = f"user_id = {offer['user_id']} AND offer_id = {offer['offer_id']}"
        await self._update(Tables.market, payload, cond)

    async def make_sell_offer(self, user_id: int, crystals: int, price: int):
        # Отбираем кристаллы.
        await self.remove_user_crystals(user_id, crystals)
        # Выставляем их на маркет.
        payload = {
            "user_id": user_id,
            "crystals": crystals,
            "price": price,
            "direction": MarketDirection.sell
        }
        await self._insert(Tables.market, payload)

    async def make_buy_offer(self, user_id: int, crystals: int, price: int):
        # Отбираем монетки.
        await self.decrease_user_balance(user_id, int(crystals * price))
        # Выставляем заявку на покупку.
        payload = {
            "user_id": user_id,
            "crystals": crystals,
            "price": price,
            "direction": MarketDirection.buy
        }
        await self._insert(Tables.market, payload)

    async def return_market_crystals(self, user_id: int) -> int:
        offers_cond = f"crystals > 0 AND user_id = {user_id} AND direction = 'sell'"
        offers = await self._select(Tables.market, where=offers_cond)
        if offers:
            payload = {
                "crystals": 0
            }
            await self._update(Tables.market, payload, offers_cond)

            crystals = int(sum([o["crystals"] for o in offers]))
            await self.add_user_crystals(user_id, crystals)

            return crystals

        return 0

    async def return_market_coins(self, user_id: int) -> int:
        offers_cond = f"crystals > 0 AND user_id = {user_id} AND direction = 'buy'"
        offers = await self._select(Tables.market, where=offers_cond)
        if offers:
            payload = {
                "crystals": 0
            }
            await self._update(Tables.market, payload, offers_cond)

            coins = int(sum([int(o["crystals"] * o["price"]) for o in offers]))
            await self.increase_user_balance(user_id, coins)

            return coins

        return 0

    async def get_market_total_crystals(self) -> int:
        try:
            q = """
                SELECT SUM(crystals) as total_crystals FROM market
                WHERE crystals > 0 AND direction = 'sell';    
            """
            return int((await self._execute(q))[0]["total_crystals"])
        except:
            return 0

    async def add_payment(self, user_id: int, seller_id: int | None, caption: str, price: int, currency: str):
        if not (price > 0):
            raise

        payload = {
            "user_id": user_id,
            "seller_id": seller_id,
            "caption": caption,
            "price": price,
            "currency": currency
        }
        await self._insert(Tables.payments, payload)

    async def delete_user_reports(self, user_id: int) -> int:
        await self.remove_user_crystals(user_id, config.PRICE_DELETE_REPORTS_CRYSTALS)

        cond = f"to_id = {user_id}"
        reports = await self._select(Tables.reports, where=cond)

        # Регистрируем платеж.
        await self.add_payment(user_id, None, PaymentType.reports_removing, 1, Currency.crystals)

        if reports:
            await self._delete(Tables.reports, where=cond, limit=300)
            return len(reports)
        return 0

    async def join_group(self, user_id: int, group_id: int):
        # Списываем плату.
        await self.decrease_user_balance(user_id, config.PRICE_JOIN_GROUP)
        # Регистрируем оплату.
        await self.add_payment(user_id, None, PaymentType.join_group, config.PRICE_JOIN_GROUP,
                               Currency.coins)

        # Прописываем пользователя в группу.
        payload = {
            "team_id": group_id
        }
        cond = f"user_id = {user_id} AND team_id IS NULL"
        await self._update(Tables.users, payload, cond)

    async def group_exists_by_name(self, group_name: str) -> bool:
        cond = f"caption = {self.cnv(group_name)}"
        return await self._exists(Tables.teams, cond)

    async def group_exists_by_id(self, group_id: int) -> bool:
        cond = f"team_id = {group_id} AND leader_id IS NOT NULL"
        return await self._exists(Tables.teams, cond)

    async def create_group(self, leader_id: int, caption: str):
        # Списываем плату.
        await self.decrease_user_balance(leader_id, config.PRICE_CREATE_GROUP)
        await self.remove_user_crystals(leader_id, config.PRICE_CREATE_GROUP_CRYSTALS)

        # Регистрируем оплату.
        await self.add_payment(leader_id, None, PaymentType.create_group, config.PRICE_CREATE_GROUP,
                               Currency.coins)
        await self.add_payment(leader_id, None, PaymentType.create_group, config.PRICE_CREATE_GROUP_CRYSTALS,
                               Currency.crystals)

        # Создаем организацию.
        payload = {
            "caption": caption,
            "leader_id": leader_id
        }
        await self._insert(Tables.teams, payload)

        # Получаем ID созданной группы.
        team_id = int((await self._select_one(Tables.teams, ["team_id"], f"leader_id = {leader_id}"))["team_id"])

        # Помещаем пользователя в нее.
        update_payload = {
            "team_id": team_id
        }
        await self._update(Tables.users, update_payload, f"user_id = {leader_id}")

    async def rename_group(self, leader_id: int, new_caption: str):
        # Списываем плату.
        await self.remove_user_crystals(leader_id, config.PRICE_RENAME_GROUP_CRUYSTALS)

        # Регистрируем оплату.
        await self.add_payment(leader_id, None, PaymentType.rename_group, config.PRICE_RENAME_GROUP_CRUYSTALS,
                               Currency.coins)
        payload = {
            "caption": new_caption
        }
        await self._update(Tables.teams, payload, f"leader_id = {leader_id}")

    async def exit_group(self, user_id: int, group_id: int):
        cond = f"user_id = {user_id} AND team_id = {group_id}"
        payload = {
            "team_id": None
        }
        await self._update(Tables.users, payload, cond)

    async def delete_group(self, group_id: int):
        if not group_id:
            raise

        cond = f"team_id = {group_id}"

        # Выгоняем всех участников из группы.
        payload = {
            "team_id": None
        }
        await self._update(Tables.users, payload, cond)

        # Удаляем лидера из группы.
        payload = {
            "leader_id": None
        }
        await self._update(Tables.teams, payload, cond)

    async def get_group(self, group_id: int) -> dict:
        try:
            cond = f"team_id = {group_id} AND leader_id IS NOT NULL"
            return await self._select_one(Tables.teams, where=cond)
        except:
            return {}

    async def get_group_level(self, group_id: int | None) -> int:
        try:
            assert group_id, "Не указан ID группы"
            info = await self.get_group(group_id)
            return int(info['level'])
        except:
            return 0

    async def get_groups(self) -> tuple:
        cond = "level >= 1 AND leader_id IS NOT NULL"
        return await self._select(Tables.teams, where=cond)

    async def get_group_members(self, group_id: int) -> tuple:
        return await self._select(Tables.users, where=f"team_id = {group_id}")

    async def upgrade_group_level(self, group) -> int:
        new_level = int(group.level + 1)
        price = config.PRICE_GROUP_UPGRADE[new_level]
        price_coins = price["coins"]
        price_crystals = price["crystals"]

        # Списываем и регистрируем оплату.
        await self.decrease_user_balance(group.leader_id, price_coins)
        await self.remove_user_crystals(group.leader_id, price_crystals)
        await self.add_payment(group.leader_id, None, PaymentType.updage_group, price_coins, Currency.coins)
        await self.add_payment(group.leader_id, None, PaymentType.updage_group, price_crystals, Currency.crystals)

        # Поднимаем уровень группе.
        payload = {
            "level": new_level
        }
        cond = f"leader_id = {group.leader_id} AND team_id = {group.group_id}"
        await self._update(Tables.teams, payload, cond)

        return new_level

    async def set_group_tax(self, group, new_tax_value: int):
        payload = {
            "tax": new_tax_value
        }
        cond = f"leader_id = {group.leader_id} AND team_id = {group.group_id}"
        await self._update(Tables.teams, payload, cond)

    async def upgrade_user_protection(self, user_id: int, price: int):
        # Списываем кристаллы.
        await self.remove_user_crystals(user_id, price)
        # Регистрируем платеж.
        await self.add_payment(user_id, None, PaymentType.protect_level,
                               price, Currency.crystals)

        # Увеличиваем процент в банке.
        q = f"""
            UPDATE users
            SET protect_level = protect_level + 1
            WHERE user_id = {user_id};
        """
        await self._execute(q)

    async def deupgrade_user_bank(self, user_id: int, price: int):
        # Списываем кристаллы.
        await self.add_user_crystals(user_id, price)

        # Увеличиваем процент в банке.
        q = f"""
            UPDATE users
            SET extra_percent = extra_percent - 1
            WHERE user_id = {user_id};
        """
        await self._execute(q)

    async def upgrade_user_bank(self, user_id: int, price: int):
        # Списываем кристаллы.
        await self.remove_user_crystals(user_id, price)
        # Регистрируем платеж.
        await self.add_payment(user_id, None, PaymentType.upgrade_bank,
                               price, Currency.crystals)

        # Увеличиваем процент в банке.
        q = f"""
            UPDATE users
            SET extra_percent = extra_percent + 1
            WHERE user_id = {user_id};
        """
        await self._execute(q)

    async def add_hack_attempt(self, user_id: int, bank_id: int, mb_password: str, bank_password: str,
                               successfully: bool):
        payload = {
            "bank_id": bank_id,
            "user_id": user_id,
            "mb_password": mb_password,
            "a_password": bank_password,
            "successfully": successfully
        }
        await self._insert(Tables.hacks, payload)

    async def get_msg_codes(self) -> list:
        keys = ['msg_code']
        raw_codes = await self._select(Tables.users, keys)
        codes = [r['msg_code'] for r in raw_codes if r['msg_code']]
        return codes

    async def set_user_msg_code(self, user_id: int, new_msg_code: str):
        assert len(new_msg_code) == 4, "Неправильная длиная анонимного кода"

        payload = {
            "msg_code": new_msg_code.lower()
        }
        cond = f"user_id = {user_id}"
        await self._update(Tables.users, payload, cond)

    async def send_message(self, from_id: int, to_id: int, dialog_id: str | None, text: str):
        # Списываем монетки.
        await self.decrease_user_balance(to_id, config.PRICE_MSG_SEND)

        # Регистрируем платеж.
        await self.add_payment(from_id, to_id, PaymentType.send_message, config.PRICE_MSG_SEND, Currency.coins)

        payload = {
            "to_id": to_id,
            "from_id": from_id,
            "dialog_id": dialog_id,
            "msg_text": text
        }
        await self._insert(Tables.messages, payload)

    async def remove_group(self, leader_id: int, group_id: int):
        cond = f"leader_id = {leader_id} AND team_id = {group_id}"
        payload = {
            "leader_id": None
        }
        await self._update(Tables.teams, payload, cond)

        cond = f"team_id = {group_id}"
        payload = {
            "team_id": None
        }
        await self._update(Tables.users, payload, cond)

    async def change_user_policy(self, user):
        if user.policy == 1:
            new_policy = 2
        else:
            new_policy = 1

        payload = {
            "policy": new_policy
        }
        cond = f"user_id = {user.user_id}"
        await self._update(Tables.users, payload, cond)

    async def post_ad(self, user_id: int, text: str):
        # Списываем монетки.
        await self.decrease_user_balance(user_id, config.PRICE_POST_AD)

        # Регистрируем платеж.
        await self.add_payment(user_id, None, PaymentType.post_ad, config.PRICE_POST_AD, Currency.coins)

        payload = {
            "user_id": user_id,
            "ad_text": text
        }
        await self._insert(Tables.ads, payload)
