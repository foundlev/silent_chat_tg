import copy

import datetime

import db
import config
import utils


class AvailabilityReport:
    def __init__(self, result: bool, delete: bool = False):
        self.result: bool = result
        self.delete: bool = delete


class Group:
    def __init__(self, storage: db.Storage, group_id: int | None):
        self.storage = storage
        self.group_id = group_id

        self.leader_id: int | None = None
        self.level: int | None = None
        self.tax: int | None = None

        self.members: tuple = tuple()
        self.info: dict = {}

        self.name: str | None = None

        self.created: datetime.datetime | None = None

    def exists(self) -> bool:
        return bool(self.group_id)

    async def can_join(self) -> bool:
        if not self.updated():
            await self.update()

        return bool(self.leader_id) and bool(self.members) and (await self.can_invite())

    async def get_leader(self):
        if not self.updated():
            await self.update()

        return await search_user(self.storage, str(self.leader_id))

    def load_from_dict(self, info: dict):
        self.info = info

        self.leader_id = self.info.get('leader_id')
        self.name = self.info.get('caption')
        self.level = self.info.get('level')
        self.tax = self.info.get('tax')
        self.created = self.info.get('created')

    async def update(self):
        await self.update_info()
        await self.update_members()

    async def update_info(self):
        if self.exists():
            self.info = await self.storage.get_group(self.group_id)
            self.leader_id = self.info.get('leader_id')
            self.name = self.info.get('caption')
            self.level = self.info.get('level')
            self.tax = self.info.get('tax')

    async def get_level(self) -> int | None:
        if not self.updated():
            await self.update()
        return self.level

    async def get_tax(self) -> int | None:
        if not self.updated():
            await self.update()
        return self.tax

    async def get_max_members_count(self) -> int:
        return config.MAX_GROUP_MEMBERS[await self.get_level()]

    async def can_invite(self) -> bool:
        max_count = await self.get_max_members_count()
        members = await self.get_members()

        return len(members) < max_count

    async def update_members(self):
        if self.exists():
            self.members = await self.storage.get_group_members(self.group_id)

    async def get_info(self) -> dict:
        if not self.updated():
            await self.update()

        return self.info

    async def get_members(self) -> tuple:
        if not self.updated():
            await self.update()

        return self.members

    def updated(self) -> bool:
        return bool(self.leader_id) and bool(self.members)

    async def get_total_balance(self) -> int:
        # Загружаем участником, если они не загружены.
        if not self.updated():
            await self.update()

        return int(sum([member['balance'] for member in self.members]))

    async def is_leader(self, user_id: int) -> bool:
        if not self.updated():
            await self.update()

        return self.leader_id and self.leader_id == user_id

    async def is_member(self, user_id: int) -> bool:
        if not self.updated():
            await self.update()

        if not self.members:
            return False

        ids = [u['user_id'] for u in self.members]

        return user_id in ids

    def get_name(self) -> str:
        return self.name.capitalize() if self.name else "-"

    def get_user_post(self, member_id: int) -> str:
        if not self.leader_id:
            return "-"

        if self.leader_id == member_id:
            return "Лидер"

        return "Участник"

    async def upgrade(self) -> int:
        if not self.updated():
            await self.update()
        return await self.storage.upgrade_group_level(self)

    async def set_tax(self, new_tax: int):
        await self.storage.set_group_tax(self, new_tax)


class User:
    def __init__(self, storage: db.Storage, user_id: int, username: str | None = None,
                 first_name: str | None = None, last_name: str | None = None):
        self.storage = storage

        self.user_id = user_id
        self.username: str | None = username
        self.first_name: str | None = first_name
        self.last_name: str | None = last_name

        self.balance: int | None = None
        self.crystals: int | None = None

        self.team_id: int | None = None
        self.policy: int | None = None
        self.msg_code: str | None = None
        self.extra_percent: int | None = None
        self.protect_level: int | None = None

        self.banned: bool | None = None
        self.agreed: bool | None = None
        self.muted: datetime.datetime | None = None

        self.first: bool | None = None

        self.reward_updated: datetime.datetime | None = None
        self.updated: datetime.datetime | None = None
        self.created: datetime.datetime | None = None

        self.team_level: int | None = None

    def __str__(self) -> str:
        shown_username = f"@{self.username}" if self.username else "-"
        shown_name = str(self.first_name) + " " + (self.last_name or " ")

        printed_text = f"ID: <code>{self.user_id}</code>\nИмя: <code>{shown_name}</code>\n" \
                       f"Username: {shown_username}"

        return printed_text

    def get_days(self) -> int:
        now = datetime.datetime.now()
        return int((now - self.created).days)

    def get_username(self) -> str:
        shown_username = f"@{self.username}" if self.username else "-"
        return shown_username

    def admin(self) -> bool:
        return int(self.user_id) in config.ADMINS

    async def can_send(self) -> bool:
        last_poll_date = await self.storage.get_last_finished_poll_time(self)
        if last_poll_date is None:
            return True
        else:
            now = datetime.datetime.now()
            last_poll_expired = last_poll_date + datetime.timedelta(seconds=config.TIME_TO_POLL)
            return now >= last_poll_expired

    def get_storage(self) -> db.Storage:
        if self.storage is None:
            raise
        return self.storage

    async def exists(self) -> bool:
        return await self.storage.user_exists(self.user_id)

    async def subscribed(self, bot) -> bool:
        try:
            status = (await bot.get_chat_member(config.CHAT_ID, self.user_id))['status']
            return status in ("creator", "administrator", "member")
        except:
            return False

    def is_muted(self) -> bool:
        now_time = datetime.datetime.now()
        return self.muted and self.muted.timestamp() > now_time.timestamp() + 60

    async def update(self):
        await self.storage.update_user(self)

    async def load_from_db(self):
        try:
            await self.storage.load_user_from_db(self)
        except:
            pass

    async def load_balance_from_db(self):
        await self.storage.load_user_balance_from_db(self)

    def load_from_dict(self, data: dict):
        self.username = data["username"]
        self.first_name = data["first_name"]
        self.last_name = data["last_name"]

        self.balance = data.get("balance")
        self.crystals = data.get("crystals")
        self.team_id = data.get("team_id")
        self.msg_code = data.get("msg_code")
        self.policy = data.get("policy")
        self.extra_percent = data.get("extra_percent")
        self.protect_level = data.get("protect_level")
        self.banned = data.get("banned")
        self.muted = data.get("muted")
        self.agreed = data.get("agreed")

        self.reward_updated = data.get("reward_updated")
        self.updated = data.get("updated")
        self.created = data.get("created")

    @staticmethod
    def _set_date_format(date: datetime.datetime, mask: str = "%H:%M:%S %d.%m.%Y"):
        return date.strftime(mask)

    def get_updated(self) -> str:
        return User._set_date_format(self.updated)

    def get_created(self) -> str:
        return User._set_date_format(self.created)

    async def get_banks(self) -> list:
        return await self.storage.get_user_banks(self)

    async def get_banks_profile_info(self, banks: list | None = None) -> dict:
        return await self.storage.get_banks_profile_info(self, banks)

    async def unlink(self, password: str):
        ...

    async def unbank(self, password: str, fee: int) -> dict | None:
        return await self.storage.unbank_by_password(self, password, fee)

    async def relink_bank(self, password: str) -> dict:
        return await self.storage.relink_bank(self.user_id, password)

    async def get_bank_by_password(self, password: str, fee: int) -> dict | None:
        return await self.storage.get_bank_by_password(self, password, fee)

    async def change_bank_password(self, old_password: str, new_password: str, fee: int) -> dict | None:
        return await self.storage.change_bank_password(self.user_id, old_password, new_password, fee)

    async def get_group_extra_percent(self) -> int:
        if self.team_id:
            if self.team_level is None:
                group_level = await self.storage.get_group_level(self.team_id)
                self.team_level = int(group_level)
            return self.team_level
        else:
            return 0

    async def get_bank_percent(self, including_group: bool = True) -> int:
        assert not (self.extra_percent is None), "Ошибка банковского дополнительного процента"

        if self.team_id and including_group:
            if self.team_level is None:
                if config.DEBUG_MODE:
                    print(f'getting group level | UID: {self.user_id} | GID: {self.team_id}')

                group_level = await self.storage.get_group_level(self.team_id)
                self.team_level = int(group_level)

            extra_group_percent = self.team_level
        else:
            extra_group_percent = 0

        return int(config.BET_BANK_DAILY_DEFAULT + self.extra_percent + extra_group_percent)

    async def set_agreed(self, new_value: bool):
        await self.storage.set_user_agreed(self, new_value)

    async def ban(self):
        await self.storage.ban_user(self)
        self.banned = True

    async def mute(self, till: datetime.datetime):
        await self.storage.mute_user(self, till)
        self.muted = till

    async def unmute(self):
        await self.storage.unmute_user(self)
        self.muted = None

    async def send(self, to, amount: int, fee_sum: int, comment: str | None) -> int:
        return await self.storage.send(self, to, amount, fee_sum, comment)

    async def send_crystals(self, to, amount: int, comment: str | None):
        await self.storage.send_crystals(self, to, amount, comment)

    async def pay(self, amount: int):
        if self.balance < amount:
            raise
        await self.storage.decrease_user_balance(self.user_id, amount)

    async def earn(self, amount: int):
        await self.storage.increase_user_balance(self.user_id, amount)

    async def report(self, to, comment: str | None):
        await self.storage.report_user(self, to, comment)

    async def get_reports_sum(self) -> dict:
        return await self.storage.get_reports_sum(self)

    async def register_poll(self) -> int:
        return await self.storage.register_poll(self)

    async def get_last_poll_time(self) -> datetime.datetime | None:
        return await self.storage.get_last_poll_time(self)

    async def get_last_report_time(self) -> datetime.datetime | None:
        return await self.storage.get_last_report_time(self)

    async def get_vote(self, poll_id: int, stage: int) -> dict:
        return await self.storage.get_vote(self, poll_id, stage)

    async def vote(self, poll_id: int, stage: int, decision: str):
        await self.storage.vote(self, poll_id, stage, decision)

    async def fine(self, amount: int):
        """Оштрафовать на {amount} монеток."""
        await self.storage.decrease_user_balance(self.user_id, amount)

    async def get_top_place_info(self) -> dict:
        return await self.storage.get_top_place_info(self)

    def value(self, key: str, new_value=None, default_value=None):
        return self.storage.local_value(self.user_id, key, new_value, default_value)

    def reset_value(self, key: str):
        self.storage.reset_local_value(self.user_id, key)

    def cooldown(self, key: str, required_cooldown: int) -> bool:
        """True - время кд прошло, иначе False."""
        return self.storage.cooldown(self.user_id, key, required_cooldown)

    def get_cooldown_last_time(self, key: str) -> int:
        """0 - время не было записано"""
        return self.storage.get_cooldown_last_time(self.user_id, key)

    async def play_game(self, bet_amount: int, profit: int):
        await self.storage.play_game(self.user_id, bet_amount, profit)

    async def sell_crystals(self, crystals: int, price: int):
        await self.storage.make_sell_offer(self.user_id, crystals, price)

    async def buy_crystals(self, crystals: int, price: int):
        await self.storage.make_buy_offer(self.user_id, crystals, price)

    async def return_crystals(self) -> int:
        return await self.storage.return_market_crystals(self.user_id)

    async def return_coins(self) -> int:
        return await self.storage.return_market_coins(self.user_id)

    async def get_market_crystals_count(self) -> dict[str: int]:
        return await self.storage.get_market_crystals_count(self.user_id)

    async def add_hack_attempt(self, bank_id: int, mb_password: str, bank_password: str, successfully: bool):
        await self.storage.add_hack_attempt(self.user_id, bank_id, mb_password, bank_password, successfully)

    async def delete_reports(self) -> int:
        return await self.storage.delete_user_reports(self.user_id)

    async def add_payment(self, seller_id: int | None, caption: str, price: int, currency: str):
        await self.storage.add_payment(self.user_id, seller_id, caption, price, currency)

    async def create_group(self, caption: str):
        await self.storage.create_group(self.user_id, caption)

    async def rename_group(self, new_caption: str):
        await self.storage.rename_group(self.user_id, new_caption)

    async def join_group(self, group_id: int):
        await self.storage.join_group(self.user_id, group_id)

    def in_group(self) -> bool:
        return bool(self.team_id)

    def get_group(self) -> Group:
        return Group(self.storage, self.team_id)

    async def exit_group(self, group_id: int):
        await self.storage.exit_group(self.user_id, group_id)

    async def upgrade_bank(self, price: int):
        await self.storage.upgrade_user_bank(self.user_id, price)

    async def deupgrade_bank(self, price: int):
        await self.storage.deupgrade_user_bank(self.user_id, price)

    async def upgrage_protection(self, price: int):
        await self.storage.upgrade_user_protection(self.user_id, price)

    async def create_msg_code(self):
        assert self.balance >= config.PRICE_MSG_CODE, "Недостаточно средств на балансе"
        await self.pay(config.PRICE_MSG_CODE)
        await self.storage.add_payment(self.user_id, None, db.PaymentType.create_msg_code,
                                       config.PRICE_MSG_CODE, db.Currency.coins)
        # Получаем список используемых кодов.
        used_codes = await self.storage.get_msg_codes()
        # Создаем новый.
        new_code = utils.create_msg_code(used_codes)
        # Устанавливаем его.
        await self.storage.set_user_msg_code(self.user_id, new_code)
        self.msg_code = new_code

    def get_msg_code(self) -> str:
        return self.msg_code.upper() if self.msg_code else "-"

    async def send_message(self, to, text: str,  dialog_id: str | None = None):
        if isinstance(to, int):
            to_id = to
        else:
            to_id = to.user_id
        await self.storage.send_message(self.user_id, to_id, dialog_id, text)

    async def remove_group(self, group_id: int):
        await self.storage.remove_group(self.user_id, group_id)

    async def change_policy(self):
        await self.storage.change_user_policy(self)

    async def post_ad(self, text: str):
        await self.storage.post_ad(self.user_id, text)


async def get_user_by_id(storage: db.Storage, user_id: int) -> User | None:
    try:
        info_dict = await storage.get_user_by_id(user_id)

        if info_dict:
            user_id = info_dict["user_id"]
            user = User(storage, user_id)
            user.load_from_dict(data=info_dict)
            return user
        raise
    except:
        ...


async def search_user(storage: db.Storage, search_text: str) -> User | None:
    try:
        info_dict = await storage.search_user(search_text)
        if info_dict:
            user_id = info_dict["user_id"]
            user = User(storage, user_id)
            user.load_from_dict(data=info_dict)
            return user
        raise
    except:
        return None


class TempStorage:
    def __init__(self):
        self.box = {}

    def value(self, user: int | str | User, key: str, value=None, default_value=None):
        if isinstance(user, User):
            user = user.user_id
        user = str(user)
        if value is None:
            return self.box.get(user, {}).get(key, default_value)
        else:
            if self.box.get(user) is None:
                self.box[user] = {}

            if isinstance(value, (list, tuple, dict)):
                value = copy.deepcopy(value)

            self.box[user][key] = value

    def common_value(self, key: str, value: str | None = None, default_value=None):
        return self.value("global", key, value, default_value)

    def status(self, user: int | str | User, value: str | None = None):
        if isinstance(user, User):
            user = user.user_id
        return self.value(user, "status", value)

    def reset(self, user: int | str | User):
        if isinstance(user, User):
            user = user.user_id
        self.box[str(user)] = {}
