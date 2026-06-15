import os
import logging
import base64
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

# =============================================================================
# CONFIGURATION - UPDATE THIS PART
# =============================================================================
BOT_TOKEN = '8593822956:AAEqQUB91Q6aHpYx0_wQ0c530Q4u_PurCIk'

# HOW TO SET YOUR KEY:
# Option 1: If the key in 'ecrypt' is a simple string:
# DECRYPTION_KEY = b'your_string_here'

# Option 2: If the key is Hex (e.g., "a1b2c3d4..."):
# DECRYPTION_KEY = bytes.fromhex('a1b2c3d4...')

# Option 3: If the key is Base64 (e.g., "SGVsbG8..."):
# DECRYPTION_KEY = base64.b64decode('SGVsbG8...')

DECRYPTION_KEY = b'1e0db84fb3ed1c750c407529b32693dd'

# The IV (Initialization Vector).
# If you didn't find one in JADX, 16 zeros are a common default.
IV = b'\x00' * 16
# =============================================================================

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

def decrypt_logic(ciphertext):
    """
    The core decryption engine. This assumes AES-CBC.
    If the bot returns gibberish, the algorithm might be different (e.g. XOR).
    """
    try:
        # 1. Setup the AES Cipher
        cipher = Cipher(
            algorithms.AES(DECRYPTION_KEY),
            modes.CBC(IV),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()

        # 2. Decrypt the data
        decrypted_padded = decryptor.update(ciphertext) + decryptor.finalize()

        # 3. Remove PKCS7 Padding
        # AES requires data to be in blocks of 16. Padding adds extra bytes at the end.
        unpadder = padding.PKCS7(128).unpadder()
        decrypted_data = unpadder.update(decrypted_padded) + unpadder.finalize()

        return decrypted_data.decode('utf-8', errors='ignore')
    except Exception as e:
        logging.error(f"Decryption error: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛡️ **Config Decryptor Bot**\n\n"
        "Send me a `.ehi` or `.hc` file and I will attempt to extract the payload."
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    file_name = doc.file_name

    # Validate extension
    if not (file_name.endswith('.ehi') or file_name.endswith('.hc')):
        await update.message.reply_text("❌ Invalid file type. Please send .ehi or .hc files.")
        return

    status_msg = await update.message.reply_text("⏳ Processing file...")

    try:
        # Download file
        tg_file = await context.bot.get_file(doc.file_id)
        local_path = f"temp_{doc.file_id}.bin"
        await tg_file.download_to_drive(local_path)

        # Read binary content
        with open(local_path, 'rb') as f:
            encrypted_content = f.read()

        # Decrypt
        decrypted_text = decrypt_logic(encrypted_content)

        if decrypted_text:
            # If result is short, send as message. If long, send as file.
            if len(decrypted_text) < 4000:
                await update.message.reply_text(
                    f"✅ **Decrypted Content:**\n\n`{decrypted_text}`",
                    parse_mode='Markdown'
                )
            else:
                out_file = f"decrypted_{file_name}.txt"
                with open(out_file, "w", encoding="utf-8") as f:
                    f.write(decrypted_text)
                await update.message.reply_document(
                    document=open(out_file, "rb"),
                    caption="✅ Decrypted successfully (sent as file)."
                )
                os.remove(out_file)
        else:
            await update.message.reply_text(
                "❌ **Decryption Failed.**\n"
                "This usually means the key in the `ecrypt` file is wrong, "
                "the IV is incorrect, or the app uses a different algorithm."
            )

    except Exception as e:
        logging.error(f"General error: {e}")
        await update.message.reply_text("⚠️ An internal error occurred.")

    finally:
        if 'local_path' in locals() and os.path.exists(local_path):
            os.remove(local_path)
        await status_msg.delete()

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("Bot is online... Press Ctrl+C to stop.")
    app.run_polling()
