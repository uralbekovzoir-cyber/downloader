import asyncio
import logging
import os
import yt_dlp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

BOT_TOKEN = "8290403667:AAH-gsZiw4PI17fTdv3OV-2wIFk9zD6Bf_E"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# Vaqtinchalik havolalarni saqlash uchun lug'at
user_urls = {}

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "Assalomu alaykum! YouTube, Instagram yoki Pinterest havolasini yuboring."
    )

@dp.message(F.text)
async def handle_url(message: types.Message):
    url = message.text.strip()
    
    if not url.startswith(("http://", "https://")):
        await message.answer("Iltimos, to'g'ri URL havola yuboring.")
        return

    msg = await message.answer("⏳ Media ma'lumotlari olinmoqda, kuting...")

    try:
        # yt-dlp yordamida media ma'lumotlari va rasmini olish
        ydl_opts = {'quiet': True}
        def get_info():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        info = await asyncio.to_thread(get_info)
        thumbnail = info.get('thumbnail')
        
        # Foydalanuvchi havolasini saqlaymiz
        user_urls[message.from_user.id] = url

        # Video, Audio va Rasm tanlash uchun inline tugmalar
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🎥 Video", callback_data="type_video"),
                InlineKeyboardButton(text="🎵 Audio", callback_data="type_audio"),
                InlineKeyboardButton(text="🖼 Rasm", callback_data="type_photo")
            ]
        ])
        
        await msg.delete()

        # Agar rasm/thumbnail mavjud bo'lsa, rasm bilan birga yuboramiz
        if thumbnail:
            await message.answer_photo(
                photo=thumbnail,
                caption="Qaysi formatda yuklab olmoqchisiz?",
                reply_markup=keyboard
            )
        else:
            await message.answer(
                "Qaysi formatda yuklab olmoqchisiz?",
                reply_markup=keyboard
            )

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await msg.edit_text("❌ Havolani o'qishda xatolik yuz berdi. Boshqa havola yuborib ko'ring.")

@dp.callback_query(F.data == "type_video")
async def choose_video_format(callback: CallbackQuery):
    url = user_urls.get(callback.from_user.id)
    if not url:
        await callback.message.answer("Havola topilmadi. Qaytadan yuboring.")
        return

    await callback.message.edit_caption(caption="⏳ Video sifatlari aniqlanmoqda...")

    try:
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])

        inline_keyboard = []
        row = []
        resolutions = sorted(list(set([f.get('height') for f in formats if f.get('height') and f.get('ext') == 'mp4'])), reverse=True)
        
        for res in resolutions[:6]:
            row.append(InlineKeyboardButton(text=f"{res}p", callback_data=f"dl_vid_{res}"))
            if len(row) == 3:
                inline_keyboard.append(row)
                row = []
        if row:
            inline_keyboard.append(row)

        inline_keyboard.append([InlineKeyboardButton(text="📥 Original Format", callback_data="dl_vid_best")])

        markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
        await callback.message.edit_caption(caption="Kerakli video sifatini (pixel) tanlang:", reply_markup=markup)

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await callback.message.edit_caption(caption="❌ Formatlarni aniqlashda xatolik yuz berdi.")

@dp.callback_query(F.data == "type_audio")
async def choose_audio_format(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎵 Original Audio (MP3)", callback_data="dl_aud_best")],
        [InlineKeyboardButton(text="🎧 Remix / Maxsus format", callback_data="dl_aud_remix")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")]
    ])
    await callback.message.edit_caption(caption="Audio formatini tanlang:", reply_markup=keyboard)

@dp.callback_query(F.data == "type_photo")
async def download_photo_action(callback: CallbackQuery):
    url = user_urls.get(callback.from_user.id)
    await callback.message.edit_caption(caption="🖼 Rasm yuklab olinmoqda...")

    try:
        output_dir = "downloads"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        ydl_opts = {
            'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
            'writethumbnail': True,
            'skip_download': True,
            'quiet': True,
        }

        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # Thumbnail yoki rasm faylini topish
                filename = ydl.prepare_filename(info)
                base, _ = os.path.splitext(filename)
                for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    if os.path.exists(base + ext):
                        return base + ext
                return filename

        file_path = await asyncio.to_thread(download)
        
        if file_path and os.path.exists(file_path):
            media_file = FSInputFile(file_path)
            await callback.message.answer_photo(photo=media_file)
            await callback.message.delete()
            os.remove(file_path)
        else:
            await callback.message.answer("Rasmni topib bo'lmadi.")

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await callback.message.answer("❌ Rasmni yuklab bo'lmadi.")

@dp.callback_query(F.data.startswith("dl_vid_"))
async def download_video_action(callback: CallbackQuery):
    quality = callback.data.split("_")[2]
    url = user_urls.get(callback.from_user.id)
    
    await callback.message.edit_caption(caption="📥 Video yuklab olinmoqda va tayyorlanmoqda, kuting...")

    try:
        output_dir = "downloads"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if quality == "best":
            format_str = 'bestvideo+bestaudio/best'
        else:
            format_str = f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best'

        ydl_opts = {
            'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
            'format': format_str,
            'merge_output_format': 'mp4',
            'quiet': True,
        }

        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        file_path = await asyncio.to_thread(download)
        
        if os.path.exists(file_path):
            media_file = FSInputFile(file_path)
            await callback.message.answer_video(video=media_file)
            await callback.message.delete()
            os.remove(file_path)
        else:
            await callback.message.answer("Faylni yuborishda xatolik yuz berdi.")

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await callback.message.answer("❌ Videoni yuklab bo'lmadi. FFmpeg o'rnatilganligini tekshiring.")

@dp.callback_query(F.data.startswith("dl_aud_"))
async def download_audio_action(callback: CallbackQuery):
    action = callback.data.split("_")[2]
    url = user_urls.get(callback.from_user.id)
    
    await callback.message.edit_caption(caption="🎵 Audio yuklab olinmoqda...")

    try:
        output_dir = "downloads"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        ydl_opts = {
            'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }

        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                base, _ = os.path.splitext(filename)
                return f"{base}.mp3"

        file_path = await asyncio.to_thread(download)
        
        if os.path.exists(file_path):
            media_file = FSInputFile(file_path)
            await callback.message.answer_audio(audio=media_file)
            await callback.message.delete()
            os.remove(file_path)
        else:
            await callback.message.answer("Audioni yuborishda xatolik yuz berdi.")

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await callback.message.answer("❌ Audioni yuklab bo'lmadi.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())