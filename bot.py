from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram import F
import asyncio
from datetime import datetime
import aiohttp
import uuid

API_TOKEN = "TG bot token"
RANDOM_ORG_API_KEY = "random.org API"

# запрос на random.org
async def fetch_random_numbers(api_key, n, min_value, max_value):
    url = "https://api.random.org/json-rpc/4/invoke"
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "method": "generateIntegers",
        "params": {
            "apiKey": api_key,
            "n": n,
            "min": min_value,
            "max": max_value,
            "replacement": False
        },
        "id": 1
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            data = await response.json()

            if 'result' in data and 'random' in data['result']:
                return data['result']['random']['data']
            else:
                error_message = data.get('error', {}).get('message', 'Неизвестная ошибка')
                raise Exception(f"Ошибка от random.org: {error_message}")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class ContestStates(StatesGroup):
    SET_DATE_TIME = State()
    SET_PRIZES = State()
    SET_GROUP = State()
    SET_POST_TEXT = State()
    SET_IMAGES = State()
    SET_SUBSCRIPTION = State()

contests = {}
participants = {}

@router.message(Command("start"))
async def start_command(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать новый розыгрыш", callback_data="create_new_contest")]
    ])
    await message.answer("Добро пожаловать в бота для проведения розыгрышей! Выберите действие:", reply_markup=keyboard)

# Создание нового розыгрыша
@router.callback_query(F.data == "create_new_contest")
async def create_new_contest(callback: CallbackQuery):
    temporary_data = {"created_by": callback.from_user.id, "completed": False}
    contests["temporary"] = temporary_data

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Указать дату и время окончания", callback_data="set_date_time_temporary")],
        [InlineKeyboardButton(text="🏆 Указать количество призовых мест", callback_data="set_prizes_temporary")],
        [InlineKeyboardButton(text="✉️ Выбрать группу", callback_data="set_group_temporary")],
        [InlineKeyboardButton(text="☑️ Проверка подписки на канал", callback_data="set_subscription_temporary")],
        [InlineKeyboardButton(text="📝 Указать текст поста", callback_data="set_post_text_temporary")],
        [InlineKeyboardButton(text="🎨 Добавить изображения", callback_data="set_images_temporary")],
        [InlineKeyboardButton(text="✅ Опубликовать конкурс", callback_data="publish_contest_temporary")]
    ])
    await callback.message.answer(
        "Конкурс создан, но пока не опубликован. Укажите параметры настройки:",
        reply_markup=keyboard
    )
    await callback.answer()

# Указание даты и времени окончания розыгрыша
@router.callback_query(F.data.startswith("set_date_time_"))
async def set_date_time(callback: CallbackQuery, state: FSMContext):
    contest_id = callback.data.split("_")[-1]
    await state.set_state(ContestStates.SET_DATE_TIME)
    await state.update_data(contest_id=contest_id)
    await callback.message.answer("Введите дату и время окончания розыгрыша в формате ДД-ММ-ГГГГ ЧЧ:ММ")
    await callback.answer()

@router.message(ContestStates.SET_DATE_TIME)
async def handle_date_time_input(message: Message, state: FSMContext):
    data = await state.get_data()
    contest_id = data['contest_id']
    try:
        end_datetime = datetime.strptime(message.text, "%d-%m-%Y %H:%M")
        
        if end_datetime <= datetime.now():
            await message.reply("Дата и время не могут быть в прошлом. Попробуйте ещё раз.")
            return
        
        contests[contest_id]['end_datetime'] = end_datetime
        await message.reply(f"Дата и время окончания розыгрыша установлены: {message.text}")
        await state.clear()
    except ValueError:
        await message.reply("Неправильная дата или время. Попробуйте ещё раз в формате ДД-ММ-ГГГГ ЧЧ:ММ.")


# Проверка подписки на канал
@router.callback_query(F.data.startswith("set_subscription_"))
async def set_subscription(callback: CallbackQuery, state: FSMContext):
    contest_id = callback.data.split("_")[-1]
    await state.set_state(ContestStates.SET_SUBSCRIPTION)
    await state.update_data(contest_id=contest_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data=f"subscribe_yes_{contest_id}")],
        [InlineKeyboardButton(text="Нет", callback_data=f"subscribe_no_{contest_id}")]
    ])
    await callback.message.answer("Необходимо ли участникам быть подписанными на канал?", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("subscribe_yes_"))
async def subscribe_yes(callback: CallbackQuery, state: FSMContext):
    contest_id = callback.data.split("_")[-1]
    contests[contest_id]['require_subscription'] = True
    await callback.message.answer("Проверка подписки включена. Укажите ссылку на канал:")
    await state.set_state(ContestStates.SET_GROUP)

@router.callback_query(F.data.startswith("subscribe_no_"))
async def subscribe_no(callback: CallbackQuery, state: FSMContext):
    contest_id = callback.data.split("_")[-1]
    contests[contest_id]['require_subscription'] = False
    await callback.message.answer("Проверка подписки отключена.")
    await state.clear()

# Указание количества призовых мест
@router.callback_query(F.data.startswith("set_prizes_"))
async def set_prizes(callback: CallbackQuery, state: FSMContext):
    contest_id = callback.data.split("_")[-1]
    await state.set_state(ContestStates.SET_PRIZES)
    await state.update_data(contest_id=contest_id)
    await callback.message.answer("Введите количество призовых мест")
    await callback.answer()

@router.message(ContestStates.SET_PRIZES)
async def handle_prizes_input(message: Message, state: FSMContext):
    data = await state.get_data()
    contest_id = data['contest_id']
    try:
        contests[contest_id]['prizes'] = int(message.text)
        await message.reply(f"Количество призовых мест установлено: {message.text}")
        await state.clear()
    except ValueError:
        await message.reply("Введите корректное число.")

# Указание группы
@router.callback_query(F.data.startswith("set_group_"))
async def set_group(callback: CallbackQuery, state: FSMContext):
    contest_id = callback.data.split("_")[-1]
    await state.set_state(ContestStates.SET_GROUP)
    await state.update_data(contest_id=contest_id)
    await callback.message.answer("Введите ссылку на группу:")
    await callback.answer()

@router.message(ContestStates.SET_GROUP)
async def handle_group_input(message: Message, state: FSMContext):
    data = await state.get_data()
    contest_id = data['contest_id']
    contests[contest_id]['group'] = message.text
    await message.reply(f"Ссылка на группу установлена: {message.text}")
    await state.clear()

# Указание текста поста
@router.callback_query(F.data.startswith("set_post_text_"))
async def set_post_text(callback: CallbackQuery, state: FSMContext):
    contest_id = callback.data.split("_")[-1]
    await state.set_state(ContestStates.SET_POST_TEXT)
    await state.update_data(contest_id=contest_id)
    await callback.message.answer("Введите текст для поста:")
    await callback.answer()

@router.message(ContestStates.SET_POST_TEXT)
async def handle_post_text_input(message: Message, state: FSMContext):
    data = await state.get_data()
    contest_id = data['contest_id']
    contests[contest_id]['post_text'] = message.text
    await message.reply("Текст для поста установлен.")
    await state.clear()

# Добавление изображений
@router.callback_query(F.data.startswith("set_images_"))
async def set_images(callback: CallbackQuery, state: FSMContext):
    contest_id = callback.data.split("_")[-1]
    await state.set_state(ContestStates.SET_IMAGES)
    await state.update_data(contest_id=contest_id)
    await callback.message.answer("Отправьте изображения для поста:")
    await callback.answer()

@router.message(ContestStates.SET_IMAGES)
async def handle_images_input(message: Message, state: FSMContext):
    data = await state.get_data()
    contest_id = data['contest_id']
    if 'images' not in contests[contest_id]:
        contests[contest_id]['images'] = []
    contests[contest_id]['images'].append(message.photo[-1].file_id)
    await message.reply("Изображение добавлено.")

# Публикация конкурса
@router.callback_query(F.data.startswith("publish_contest_"))
async def publish_contest(callback: CallbackQuery):
    contest_id = callback.data.split("_")[-1]
    if contest_id == "temporary":
        contest = contests.get("temporary")
    else:
        contest = contests.get(contest_id)

    if not contest or not all(key in contest for key in ('end_datetime', 'prizes', 'group', 'post_text')):
        await callback.message.answer("Сначала укажите все параметры конкурса!")
        return

    group_username = contest['group'].replace("https://t.me/", "")
    user_id = callback.from_user.id

    # Проверка прав пользователя в группе
    try:
        member = await bot.get_chat_member(chat_id=f"@{group_username}", user_id=user_id)
        if member.status not in ["administrator", "creator"]:
            if "temporary" in contests:
                del contests["temporary"]

            await callback.message.answer("Вы не являетесь администратором выбранной группы.")
            return
    except Exception as e:
        if "temporary" in contests:
            del contests["temporary"]

        await callback.message.answer(f"Ошибка при проверке прав в группе. Убедитесь, что бот добавлен в группу и имеет права администратора.\nОшибка: {e}")
        return

    # Генерация UUID для конкурса
    generated_uuid = str(uuid.uuid4())
    contests[generated_uuid] = contest
    del contests["temporary"]
    contest['id'] = generated_uuid

    # Основной текст публикации
    contest_message = (
        f"{contest['post_text']}\n\n"
        f"📅 Бот автоматически выберет победителей {contest['end_datetime'].strftime('%d.%m.%Y в %H:%M')}\n"
        f"🏆 Количество призов: {contest['prizes']}\n\n"
        f"Нажмите на кнопку ниже, чтобы участвовать!"
    )

    participate_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Участвовать (0)", callback_data=f"participate_{generated_uuid}")]
    ])

    # Отправка сообщения с медиа
    try:
        if 'images' in contest and contest['images']:
            if len(contest['images']) == 1:
                msg = await bot.send_photo(
                    chat_id=f"@{group_username}",
                    photo=contest['images'][0],
                    caption=contest_message,
                    reply_markup=participate_button
                )
            else:
                media_group = [
                    {"type": "photo", "media": file_id} for file_id in contest['images']
                ]
                await bot.send_media_group(chat_id=f"@{group_username}", media=media_group)
                
                msg = await bot.send_message(
                    chat_id=f"@{group_username}",
                    text=contest_message,
                    reply_markup=participate_button
                )
        else:
            msg = await bot.send_message(
                chat_id=f"@{group_username}",
                text=contest_message,
                reply_markup=participate_button
            )

        contest['message_id'] = msg.message_id
        await callback.message.answer(f"Конкурс успешно опубликован! Его ID: {generated_uuid}")

    except Exception as e:
        await callback.message.answer(f"Ошибка при публикации в группу. Ошибка: {e}")

# Участие в розыгрыше
@router.callback_query(F.data.startswith("participate_"))
async def participate(callback: CallbackQuery):
    contest_id = callback.data.split("_")[-1]
    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.full_name

    contest = contests.get(contest_id)
    if not contest:
        await callback.answer("Этот розыгрыш уже завершён. Регистрация невозможна.", show_alert=True)
        return
    
    if contest.get('completed', False):
        await callback.answer("Этот розыгрыш уже завершён. Регистрация невозможна.", show_alert=True)
        return
        
    if contest.get('require_subscription'):
        group_username = contest['group'].replace("https://t.me/", "")
        try:
            member = await bot.get_chat_member(chat_id=f"@{group_username}", user_id=user_id)
            if member.status == "left":
                await callback.answer("Для участия в розыгрыше необходимо подписаться на канал!", show_alert=True)
                return
        except Exception as e:
            await callback.answer(f"Ошибка проверки подписки: {e}", show_alert=True)
            return

    if contest_id not in participants:
        participants[contest_id] = {}

    if user_id in participants[contest_id]:
        await callback.answer("Вы уже участвуете в данном розыгрыше!", show_alert=True)
    else:
        participant_number = len(participants[contest_id]) + 1
        participants[contest_id][user_id] = participant_number

        button_text = f"Участвовать ({len(participants[contest_id])})"
        participate_button = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=button_text, callback_data=f"participate_{contest_id}")]
        ])
        await callback.message.edit_reply_markup(reply_markup=participate_button)
        await callback.answer("Вы были добавлены в список на участие!", show_alert=True)

def reset_participants(contest_id):
    if contest_id in participants:
        participants[contest_id] = {}

# Объявление победителей
async def announce_winners(contest_id):
    contest = contests.get(contest_id)
    group_username = contest['group'].replace("https://t.me/", "")
    prize_count = contest.get('prizes', 1)
    
    participants_list = list(participants.get(contest_id, {}).items())
    total_participants = len(participants_list)

    if total_participants == 0:
        await bot.send_message(chat_id=f"@{group_username}", text="😞 розыгрыш завершён, но никто не принял участие.")
        reset_participants(contest_id)
        return

    winners = []
    tries = 0

    while len(winners) < prize_count and tries < total_participants * 2:
        try:
            winner_ids = await fetch_random_numbers(RANDOM_ORG_API_KEY, 1, 1, total_participants)
            winner_id = participants_list[winner_ids[0] - 1][0]

            if contest.get('require_subscription'):
                member = await bot.get_chat_member(chat_id=f"@{group_username}", user_id=winner_id)
                if member.status == "left":
                    tries += 1
                    continue

            if winner_id not in winners:
                winners.append(winner_id)
        except Exception as e:
            tries += 1

    if not winners:
        await bot.send_message(chat_id=f"@{group_username}", text="❌ Розыгрыш завершён. Победителей не найдено.")
        reset_participants(contest_id)
        return

    if len(winners) == 1:
        result_message = (
            f"🎉 Розыгрыш завершён!\n\n"
            f"🏆 Победитель: [{winners[0]}](tg://user?id={winners[0]})"
        )
    else:
        winners_text = "\n".join([f"{i + 1}) [{winner}](tg://user?id={winner})" for i, winner in enumerate(winners)])
        result_message = (
            f"🎉 Розыгрыш завершён!\n\n"
            f"🏆 Количество призов: {prize_count}\n\n"
            f"🎊 Победители:\n{winners_text}"
        )

    await bot.send_message(chat_id=f"@{group_username}", text=result_message, parse_mode="Markdown")
    reset_participants(contest_id)

async def check_contests():
    while True:
        now = datetime.now()
        for contest_id, contest in contests.items():
            end_datetime = contest.get('end_datetime')
            if end_datetime and now >= end_datetime and not contest.get('completed'):
                contests[contest_id]['completed'] = True
                await announce_winners(contest_id)
        await asyncio.sleep(60)

async def on_startup():
    asyncio.create_task(check_contests())

dp.startup.register(on_startup)

async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
