from telethon import TelegramClient, errors
import asyncio
import random
from datetime import datetime, timedelta
import os
import csv
import logging
import sys

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Konfiguratsiya
API_ID = 16072756
API_HASH = '5fc7839a0d020c256e5c901cebd21bb7'
SESSION_FOLDER = "sessions"
PHONE_CSV = "phone.csv"
INTERVAL_HOURS = 1

# Yangi xabar
MESSAGES = [
    "⭐️ YANGI OCHILGAN GURUHLAR, KAMPANIYALAR UCHUN ⭐️\n\n"
    "🚀 Faollik sustmi?\n"
    "📉 A’zolar kam yoki guruh sustlashib qoldimi?\n"
    "📢 Reklamangiz yetarli natija bermayaptimi?\n\n"
    "💡 Barcha turdagi guruh va kampaniyalar aktivligini oshiramiz!\n\n"
    "🔹 Yurmay qolgan loyihalarni jonlantiramiz\n"
    "🔹 Klent oqimini ko‘paytiramiz\n"
    "🔹 Kuchli rekrutlar bilan samaradorlikni oshiramiz\n"
    "🔹 Shlovchilar uchun maxsus faollik kuchaytirish tizimi\n\n"
    "📊 To‘g‘ri tizim – yaxshi natija!\n"
    "💰 Kuchli nastavnik – baquvvat jamoa!\n"
    "📈 Yaxshi sotuvchi har qanday tavarni o‘tkaza oladi!"
]

# Telefon raqamlari va mijozlarni yuklash
async def load_clients():
    if not os.path.exists(SESSION_FOLDER):
        os.makedirs(SESSION_FOLDER)

    phone_numbers = []
    try:
        with open(PHONE_CSV, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0].startswith('+'):
                    phone_numbers.append(row[0].strip())
                else:
                    logger.warning(f"Noto'g'ri formatdagi raqam o'tkazib yuborildi: {row}")
    except FileNotFoundError:
        logger.error(f"{PHONE_CSV} fayli topilmadi!")
        sys.exit(1)

    if not phone_numbers:
        logger.error("Faylda hech qanday telefon raqami topilmadi!")
        sys.exit(1)

    clients = []
    for phone in phone_numbers:
        session_file = os.path.join(SESSION_FOLDER, f"{phone}.session")
        client = TelegramClient(session_file, API_ID, API_HASH)

        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.info(f"{phone} uchun autentifikatsiya kerak")
                await client.send_code_request(phone)
                code = input(f"{phone} uchun kodni kiriting: ")
                try:
                    await client.sign_in(phone, code)
                except errors.SessionPasswordNeededError:
                    password = input(f"{phone} uchun 2FA parolni kiriting: ")
                    await client.sign_in(password=password)
                logger.info(f"{phone} muvaffaqiyatli ulandi va sessiya saqlandi")
            else:
                logger.info(f"{phone} allaqachon ulangan")
            clients.append((phone, client))
        except Exception as e:
            logger.error(f"{phone} ulanishda xato: {str(e)}")
            await client.disconnect()
            continue

    return clients

# Faqat guruhlarni olish (superguruhlar bilan)
async def get_all_groups(client):
    groups = []
    try:
        async for dialog in client.iter_dialogs():
            # Faqat guruhlar (oddiy guruhlar yoki superguruhlar)
            if dialog.is_group:
                try:
                    chat = await client.get_entity(dialog.id)
                    # Faqat kanal (broadcast) bo‘lsa o‘tkazib yuboramiz
                    if not dialog.is_group and dialog.is_channel:
                        continue
                    # Yozish imkoniyati borligini tekshirish
                    if hasattr(chat, 'restricted') and chat.restricted:
                        continue
                    groups.append({
                        'id': dialog.id,
                        'name': dialog.name,
                        'entity': chat
                    })
                except Exception as e:
                    logger.error(f"Guruh {dialog.name} olishda xato: {str(e)}")
                    continue  # Xato bo‘lsa tez o‘tib ketadi
    except Exception as e:
        logger.info(f"Dialoglarni olishda xato (e’tiborsiz): {str(e)}")
        # "Got difference for channel" kabi xatolar uchun tez o‘tib ketadi

    if not groups:
        logger.warning("Hech qanday guruh topilmadi")
    return groups

# Chalg‘ituvchi harakatlar (loglarsiz)
async def distract(client, group):
    try:
        # Guruhdagi oxirgi 5-10 ta xabarni ko‘rish
        limit = random.randint(5, 10)
        async for _ in client.iter_messages(group['entity'], limit=limit):
            await asyncio.sleep(random.uniform(0.5, 1.5))  # Tasodifiy kichik pauzalar
    except Exception:
        pass  # Xatolarni e’tiborsiz qoldiramiz, logga yozmaymiz

# Xabar yuborish
async def send_message(client, group, phone):
    try:
        message = random.choice(MESSAGES)
        await client.send_message(group['entity'], message)
        logger.info(f"{phone} dan {group['name']} ga xabar yuborildi")
        # Muvaffaqiyatli bo‘lsa chalg‘ituvchi harakatlar
        await distract(client, group)
        return True
    except errors.ChatWriteForbiddenError:
        logger.warning(f"{phone} dan {group['name']} ga yozish taqiqlangan")
        return False
    except errors.FloodWaitError as e:
        logger.warning(f"{phone} uchun Flood kutish: {e.seconds} soniya")
        return False
    except errors.RPCError as e:
        logger.error(f"{phone} dan {group['name']} ga xabar yuborishda xato: {str(e)}")
        return False

# Har bir mijoz uchun tarqatish
async def distribute_messages(phone, client):
    processed_groups = set()
    while True:
        try:
            logger.info(f"\n{phone} uchun yangi aylanish boshlandi ({datetime.now().strftime('%H:%M')})")
            groups = await get_all_groups(client)
            if not groups:
                logger.warning(f"{phone} uchun guruh topilmadi")
                await asyncio.sleep(60)  # 1 daqiqa kutish
                continue

            random.shuffle(groups)
            for group in groups:
                if group['id'] not in processed_groups:
                    if await send_message(client, group, phone):
                        processed_groups.add(group['id'])
                        await asyncio.sleep(random.randint(5, 10))  # 5-10 soniya kutish
                    # Muvaffaqiyatsiz bo‘lsa kutishsiz keyingi guruhga o‘tadi

            logger.info(f"{phone} keyingi tarqatish: {(datetime.now() + timedelta(hours=INTERVAL_HOURS)).strftime('%H:%M')}")
            await asyncio.sleep(INTERVAL_HOURS * 3600)
        except Exception as e:
            logger.error(f"{phone} tarqatishda xato: {str(e)}")
            await asyncio.sleep(60)  # Umumiy xato bo‘lsa 1 daqiqa kutish

# Asosiy funksiya
async def main():
    clients = await load_clients()
    if not clients:
        logger.error("Hech qanday mijoz ulanmadi!")
        sys.exit(1)

    logger.info(f"{len(clients)} ta raqam muvaffaqiyatli ulandi")
    
    tasks = [distribute_messages(phone, client) for phone, client in clients]
    await asyncio.gather(*tasks)

    for _, client in clients:
        await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nDastur foydalanuvchi tomonidan to'xtatildi!")
        sys.exit(0)