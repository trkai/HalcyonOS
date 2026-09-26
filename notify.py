import os
import sys
import requests
import random
import string

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

def read_file_if_exists(path, default=""):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                val = f.read().strip()
                return val if val else default
        except Exception:
            return default
    return default

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

def get_progress_bar(status):
    stages = ['start', 'download', 'unpack', 'build', 'pack', 'upload', 'success']
    status = status.lower()
    if status == 'fail':
        return "[❌ Build thất bại]"
    
    current_index = -1
    if status in stages:
        current_index = stages.index(status)
        
    total = len(stages)
    filled = current_index + 1 if current_index >= 0 else 0
    bar = "▰" * filled + "▱" * (total - filled)
    percent = int((filled / total) * 100)
    return f"[{bar}] {percent}%"

def get_progress_percent(status):
    """Tính % tiến độ dựa trên status"""
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

def is_available(val):
    return val and val.strip() and val.lower() != 'không tìm thấy key' and 'not found' not in val.lower()

def send_notification(status, repo_name, rom_link, channel_id, bot_token, msg_id, build_id, builder_name, builder_id):
    from datetime import datetime
    
    icon, status_title, status_desc = get_status_info(status)
    action_url = f"https://github.com/{repo_name}/actions"
    
    device_name = read_file_if_exists("bin/ddevice/device_name.txt", "Thiết bị")
    codename = read_file_if_exists("bin/ddevice/device_code.txt")
    if not codename: codename = read_file_if_exists("bin/ddevice/device_f.txt", "unknown")
    version_rom = read_file_if_exists("bin/ddevice/base_rom_code.txt")
    if not version_rom: version_rom = read_file_if_exists("bin/ddevice/base_build_id.txt", "Unknown")
    output_zip = read_file_if_exists("bin/ddevice/output_zip.txt")

    builder_text = builder_name if builder_name else "HalcyonOS System"
    progress_percent = get_progress_percent(status)
    
    # Status badge colors
    status_color = "✅" if status.lower() == 'success' else "⏳" if status.lower() in ['start', 'download', 'unpack', 'build', 'pack', 'upload'] else "❌"
    status_label = "Hoàn tất" if status.lower() == 'success' else "Đang tiến hành" if status.lower() != 'fail' else "Thất bại"
    
    # Progress bar with filled blocks
    progress_blocks = int(progress_percent / 10)
    progress_bar_visual = "▰" * progress_blocks + "▱" * (10 - progress_blocks)
    
    # Time
    now = datetime.now()
    time_str = now.strftime("%H:%M · %d/%m")
    
    # Message content - format theo hình
    lines = [
        f"<b>HalcyonOS - ROM Builder</b>",
        f"│{codename} · {device_name}",
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
    
    # Delete old progress message if build is complete (success or fail)
    if status.lower() in ['success', 'fail'] and msg_id:
        try:
            delete_url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
            delete_payload = {"chat_id": channel_id, "message_id": msg_id}
            requests.post(delete_url, json=delete_payload)
            print(f"✅ Xóa message tiến trình cũ (ID: {msg_id})")
        except Exception as e:
            print(f"⚠️  Lỗi xóa message cũ: {e}")
    
    # Inline buttons for success status
    reply_markup = None
    if status.lower() == 'success':
        reply_markup = {
            "inline_keyboard": [
                [
                    # Thay link thư mục Google Drive mới của bạn vào thuộc tính "url" bên dưới:
                    {"text": "📥 Tải ROM", "url": "https://drive.google.com/drive/folders/1AeAHmwsEFmBLqFJuLC6K0KEpTM4KoQR8?usp=sharing"},
                    {"text": "🔍 Duyệt", "callback_data": "duyetrom"}
                ]
            ]
        }

    # Send new message (always send new when build complete, don't edit)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": channel_id, 
        "text": message, 
        "parse_mode": "HTML", 
        "disable_web_page_preview": True
    }
    
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        res_data = response.json()
        new_msg_id = res_data.get('result', {}).get('message_id')
        
        if new_msg_id and "GITHUB_ENV" in os.environ:
            with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as f:
                f.write(f"TELEGRAM_MSG_ID={new_msg_id}\n")
        
        print(f"✅ Gửi notification thành công")
            
        if status.lower() in ['success', 'fail'] and builder_id:
            pm_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            if status.lower() == 'success':
                pm_text = f"<b>✅ BUILD THÀNH CÔNG!</b>\n\n{message}"
            else:
                pm_text = f"<b>❌ BUILD THẤT BẠI!</b>\n\n{message}\n\nKiểm tra GitHub logs để biết chi tiết."
            pm_payload = {"chat_id": builder_id, "text": pm_text, "parse_mode": "HTML", "disable_web_page_preview": True}
            try: 
                requests.post(pm_url, json=pm_payload)
                print(f"✅ Gửi PM cho builder thành công")
            except Exception: 
                pass

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
    msg_id = os.environ.get("TELEGRAM_MSG_ID") 
    build_id = os.environ.get("TELEGRAM_BUILD_ID")

    if not build_id:
        build_id = f"{prefix}_{''.join(random.choices(string.digits, k=8))}"
        if "GITHUB_ENV" in os.environ:
            with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as f:
                f.write(f"TELEGRAM_BUILD_ID={build_id}\n")

    if bot_token and channel_id:
        send_notification(status, repo_name, rom_link, channel_id, bot_token, msg_id, build_id, builder_name, builder_id)
