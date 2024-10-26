import os
import re
import time
import redis
import requests
from pyrogram import Client, filters
from urllib.parse import urlparse
from requests.exceptions import RequestException

# Configuration
API_ID = 22419004
API_HASH = "34982b52c4a83c2af3ce8f4fe12fe4e1"
BOT_TOKEN = "YOUR_BOT_TOKEN"
ADMINS = [6742022802, 7442532306]
PRIVATE_CHAT_ID = -1002445495902
DOWNLOAD_FOLDER = "/tmp/"

# Redis Configuration
REDIS_CONFIG = {
    "csrfToken": "m_zbAV1arBvXCvTgmFvSluXY",
    "browserid": "EAaVwqpE6IPuBWAbOmlwEa-HARfMNQSSWLn9wiOXV1pWAEArqSzqtnmnkqM",
    "lang": "en",
    "TSID": "RgCB6tEItxCB33EMPKyzutFSBMmUxfjl",
    "__bid_n": "190fa81594548da7784207",
    "ndus": "YuaYNCMteHuiIaOZqGpTf8Z9-n1Si4erYpgWHcaX",
    "ab_sr": "1.0.1_ODA4NTRlNzE0MjVkYzczZjZjNmQ3NGI0MzZjNTIxNGI1MThmNjdmZTNlM2I1ZmU5N2E0NmY5Mjg2OTdjMDg5NzM2NDhiZWRlNGFjY2RiZTNhNzQ2YmEwNzAwNzJhZGQ3ZDNiOTY3ZjNjYjVhZGZiODA4ZWU5ZDUxZjZkMjk0NTYzOWYyYzVkZDFhZmRmM2RhNjUyNDA5YTBjZjk0MDVlZg==",
    "ndut_fmt": "426D9C20125DC8DFB9349A68EB0F767398283E07567B9C028271312D315A284E"
}

# Initialize Redis
redis_client = redis.StrictRedis(
    host=REDIS_CONFIG["HOST"],
    port=REDIS_CONFIG["PORT"],
    username=REDIS_CONFIG["USERNAME"],
    password=REDIS_CONFIG["PASSWORD"],
    decode_responses=True
)

# Authentication Cookie
COOKIE = {
    "csrfToken": "m_zbAV1arBvXCvTgmFvSluXY",
    "browserid": "EAaVwqpE6IPuBWAbOmlwEa-HARfMNQSSWLn9wiOXV1pWAEArqSzqtnmnkqM",
    "lang": "en",
    "TSID": "RgCB6tEItxCB33EMPKyzutFSBMmUxfjl"
}

class TeraBoxDownloader:
    def __init__(self):
        self.last_send_time = time.time() - 20
        self.session = requests.Session()
        self.headers = {
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
            "Cookie": "; ".join([f"{k}={v}" for k, v in COOKIE.items()])
        }

    def can_send(self):
        if time.time() - self.last_send_time >= 5:
            self.last_send_time = time.time()
            return True
        return False

    def get_data(self, url):
        surl = extract_surl(url)
        if not surl or not self.can_send():
            print("Cooldown or invalid URL.")
            return None

        cached_result = redis_client.get(surl)
        if cached_result:
            return eval(cached_result)

        response = self.session.get(url, headers=self.headers)
        if response.status_code != 200:
            return None

        jsToken = find_between(response.text, "fn%28%22", "%22%29")
        logid = find_between(response.text, "dp-logid=", "&")
        default_thumbnail = find_between(response.text, 'og:image" content="', '"')

        if not jsToken or not logid:
            return None

        api_url = (
            f"https://www.terabox.app/share/list?app_id=250528&jsToken={jsToken}"
            f"&dp-logid={logid}&shorturl={surl}&root=1"
        )
        response = self.session.get(api_url, headers=self.headers)

        if response.status_code != 200 or "list" not in response.json():
            return None

        file_info = response.json()["list"][0]
        file_name = file_info.get("server_filename")
        download_link = file_info.get("dlink")
        direct_link = self.session.head(download_link, headers=self.headers).headers.get("location")

        if not direct_link:
            return None

        result = {
            "file_name": file_name,
            "link": download_link,
            "direct_link": direct_link,
            "thumbnail": default_thumbnail or file_info.get("thumbs", {}).get("url3"),
            "size_bytes": file_info.get("size")
        }

        redis_client.setex(surl, 3600, str(result))
        return result

    def download_file(self, url, file_name):
        try:
            response = self.session.get(url, stream=True)
            file_path = os.path.join(DOWNLOAD_FOLDER, file_name)
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    file.write(chunk)
            return file_path
        except RequestException:
            return None

# Utility Functions
def find_between(data, start, end):
    try:
        return data.split(start)[1].split(end)[0]
    except IndexError:
        return None

def extract_surl(url):
    match = re.search(r"(surl=)([^&]+)", url)
    return match.group(2) if match else None

# Initialize Telegram Bot
app = Client("terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.text & filters.user(ADMINS))
async def handle_message(client, message):
    urls = re.findall(r"https?://[^\s]+", message.text)
    if not urls:
        await message.reply("⚠️ No valid TeraBox URL found.")
        return

    downloader = TeraBoxDownloader()
    for url in urls:
        await message.reply("🔄 Fetching file information...")

        result = downloader.get_data(url)
        if result:
            await message.reply(f"📥 Downloading file: **{result['file_name']}**")

            file_path = downloader.download_file(result["direct_link"], result["file_name"])
            if file_path:
                await message.reply("⏫ Uploading file to Telegram...")

                await client.send_document(
                    PRIVATE_CHAT_ID, file_path,
                    caption=f"**File:** {result['file_name']}\n**Size:** {result['size_bytes'] / (1024 * 1024):.2f} MB",
                )

                os.remove(file_path)
                await message.reply("✅ File uploaded successfully!")
            else:
                await message.reply("❌ Failed to download file.")
        else:
            await message.reply("❌ Could not retrieve file information.")

app.run()
