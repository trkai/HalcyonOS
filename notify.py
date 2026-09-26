import os
import sys
import requests
import random
import string
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

MSG_ID_FILE = "/tmp/telegram_msg_id.txt"
BUILD_ID_FILE = "/tmp/telegram_build_id.txt"

def read_file_if_exists(path, default=""):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                val = f.read().strip()
                return val if val else default
        except Exception:
            return default
    return default

def save_to_env_and_file(env_key, file_path, value):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(str(value).strip())
    except Exception:
        pass
    if "GITHUB_ENV" in os.environ:
        try:
            with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as f:
                f.write(f"{env_key}={value}\n")
        except Exception:
            pass

def get_status_info(status):
    status = status.lower()
    if status == 'start': return "🚀", "START", "Đang thiết lập môi trường build..."
    if status == 'download': return "⬇️", "DOWNLOAD", "Đang tải ROM cơ sở..."
    if status == 'unpack': return "📦", "UNPACK", "Đang giải nén images..."
    if status == 'build': return "⚙️", "BUILD", "Đang vá lỗi và mod hệ thống..."
    if status == 'pack': return "🗜️", "PACK", "Đang nén thành flashable zip..."
    if status == 'upload': return "☁️", "UPLOAD", "Đang upload lên Cloud..."
    if status == 'success': return "✅", "SUCCESS", "Build hoàn tất thành công!"
    if status == 'fail':
        err_msg = read_file_if_exists("bin/ddevice/error_msg.txt")
        desc = err_msg if err_msg else "Build bị dừng lại. Kiểm tra GitHub logs để biết chi tiết."
        return "❌", "FAILED", desc
    return "ℹ️", "UPDATE", status.upper()

def get_progress_percent(status):
    stages = {
        'start': 15,
        'download': 30,
        'unpack': 45,
        'build': 60,
        'pack': 75,
        'upload': 90,
        'success': 100
    }
    return stages.get(status.lower(), 0)

def send_notification(status, repo_name, rom_link, target_chat_id, bot_token, msg_id, build_id, builder_name):
    icon, status_title, status_desc = get_status_info(status)

    device_name = read_file_if_exists("bin/ddevice/device_name.txt", "Thiết bị")
    codename = read_file_if_exists("bin/ddevice/device_code.txt")
    if not codename:
        codename = read_file_if_exists("bin/ddevice/device_f.txt", "unknown")
    version_rom = read_file_if_exists("bin/ddevice/base_rom_code.txt")
    if not version_rom:
        version_rom = read_file_if_exists("bin/ddevice/base_build_id.txt", "Unknown")

    progress_percent = get_progress_percent(status)

    status_color = "✅" if status.lower() == 'success' else "⏳" if status.lower() in ['start', 'download', 'unpack', 'build', 'pack', 'upload'] else "❌"
    status_label = "Hoàn tất" if status.lower() == 'success' else "Đang tiến hành" if status.lower() != 'fail' else "Thất bại"

    progress_blocks = int(progress_percent / 10)
    progress_bar_visual = "▰" * progress_blocks + "▱" * (10 - progress_blocks)

    now = datetime.now()
    time_str = now.strftime("%H:%M · %d/%m")

    lines = [
        f"<b>HalcyonOS - ROM Builder</b>",
        f"│{codename}",
        f"│{version_rom}",
        "",
        f"{status_color} <b>{status_label}</b>",
        f"{progress_bar_visual} {progress_percent}%",
        f"{status_desc}",
        "",
        f"<code>ID: {build_id}</code>",
        f"{time_str}",
        f"<a href='{rom_link}'>🔗 Nguồn ROM</a>",
    ]

    message = "\n".join(lines)

    # Nút bấm khi hoàn tất (callback_data khớp với approve_rom_ trên Cloudflare Worker)
    reply_markup = None
    if status.lower() == 'success':
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "📥 Tải ROM", "url": "https://drive.google.com/drive/folders/1AeAHmwsEFmBLqFJuLC6K0KEpTM4KoQR8?usp=sharing"},
                    {"text": "🔍 Duyệt", "callback_data": f"approve_rom_{build_id}"}
                ]
            ]
        }

    # 1. Nếu đã có msg_id -> Sửa thẳng vào tin nhắn cũ (editMessageText)
    if msg_id:
        edit_url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
        edit_payload = {
            "chat_id": target_chat_id,
            "message_id": int(msg_id),
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if reply_markup:
            edit_payload["reply_markup"] = reply_markup

        try:
            res = requests.post(edit_url, json=edit_payload)
            res_json = res.json()
            if res.status_code == 200 and res_json.get("ok"):
                print(f"✅ Đã cập nhật tiến trình vào tin nhắn (ID: {msg_id})")
                return
            elif "message is not modified" in res_json.get("description", "").lower():
                print("ℹ️ Nội dung tin nhắn không thay đổi, bỏ qua.")
                return
            else:
                print(f"⚠️ Không sửa được tin nhắn cũ ({res_json.get('description')}), sẽ gửi tin nhắn mới...")
        except Exception as e:
            print(f"⚠️ Lỗi khi sửa tin nhắn cũ: {e}")

    # 2. Nếu chưa có msg_id (bước start) hoặc sửa lỗi -> Gửi tin nhắn mới
    send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    send_payload = {
        "chat_id": target_chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        send_payload["reply_markup"] = reply_markup

    try:
        response = requests.post(send_url, json=send_payload)
        response.raise_for_status()
        res_data = response.json()
        new_msg_id = res_data.get('result', {}).get('message_id')

        if new_msg_id:
            save_to_env_and_file("TELEGRAM_MSG_ID", MSG_ID_FILE, new_msg_id)
        print(f"✅ Gửi notification mới thành công (ID: {new_msg_id})")
    except Exception as e:
        print(f"❌ Lỗi gửi notification: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(1)

    status = sys.argv[1]
    repo_name = sys.argv[2]
    rom_link = sys.argv[3]
    prefix = sys.argv[4] if len(sys.argv) > 4 else "build"
    builder_name = sys.argv[5] if len(sys.argv) > 5 else ""
    builder_id = sys.argv[6] if len(sys.argv) > 6 else ""

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID")

    # Ưu tiên gửi về builder_id (nếu có), nếu không thì gửi về TELEGRAM_CHANNEL_ID (đặt là ID cá nhân của bạn trên GitHub)
    target_chat_id = builder_id.strip() if builder_id and builder_id.strip() else channel_id

    # Đọc msg_id và build_id từ file tạm hoặc biến môi trường
    msg_id = read_file_if_exists(MSG_ID_FILE) or os.environ.get("TELEGRAM_MSG_ID")
    build_id = read_file_if_exists(BUILD_ID_FILE) or os.environ.get("TELEGRAM_BUILD_ID")

    if not build_id:
        build_id = f"{prefix}_{''.join(random.choices(string.digits, k=8))}"
        save_to_env_and_file("TELEGRAM_BUILD_ID", BUILD_ID_FILE, build_id)

    if bot_token and target_chat_id:
        send_notification(status, repo_name, rom_link, target_chat_id, bot_token, msg_id, build_id, builder_name)
