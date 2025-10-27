# 必要なライブラリを読み込む
import os
import json
from urllib.parse import parse_qs
from flask import Flask, request, abort
from datetime import datetime
from zoneinfo import ZoneInfo # タイムゾーンを扱うために追加

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    TemplateMessage,
    CarouselTemplate,
    CarouselColumn,
    PostbackAction,
    ImageMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent

# --- 準備 ---------------------------------------------------------------------

app = Flask(__name__)

# ★★★ Renderの環境変数から設定を読み込む ★★★
ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
ADMIN_USER_IDS_str = os.environ.get('ADMIN_USER_IDS', '') # カンマ区切りの文字列として読み込む

# カンマ区切りの文字列をリストに変換
ADMIN_USER_IDS = ADMIN_USER_IDS_str.split(',')
# ★★★ 設定はここまで ★★★

configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

VOTES_FILE = 'votes.json'

CANDIDATES = {
    '1': {'group': 'A', 'name': '佐藤翼 No.1', 'image_url': 'https://i.postimg.cc/s2zVxgpw/317038.jpg', 'description': '【ど田舎からの刺客】'},
    '2': {'group': 'A', 'name': '高岡友輝 No.2', 'image_url': 'https://i.postimg.cc/tJsbwZj4/317039.jpg', 'description': '【制御不能なカリスマ】'},
    '3': {'group': 'A', 'name': '磯歩夢 No.3', 'image_url': 'https://i.postimg.cc/rwXTZwZg/317040.jpg', 'description': '【夢に向かって、歩む。】'},
    '4': {'group': 'B', 'name': '與田愛加 No.4', 'image_url': 'https://i.postimg.cc/vTJJK0h2/317041.jpg', 'description': '【控えめに見えて、透き通る強さ】'},
    '5': {'group': 'B', 'name': '早川晏麓 No.5', 'image_url': 'https://i.postimg.cc/rFWswbBL/317043.jpg', 'description': '【たまに見かけるシルカフェのお兄さん】'},
    '6': {'group': 'B', 'name': '岡村菜那 No.6', 'image_url': 'https://i.postimg.cc/BvZnNvXD/317044.jpg', 'description': '【笑顔でみなさんを元気にさせます🤍】'},
}

# --- ヘルパー関数 -----------------------------------------------------------------

def load_votes():
    if not os.path.exists(VOTES_FILE):
        return {'votes': {id: 0 for id in CANDIDATES}, 'voters': {}}
    with open(VOTES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_votes(data):
    with open(VOTES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- LINE Botのメイン処理 -----------------------------------------------------

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

def create_carousel_message(group):
    columns = []
    for id, candidate in CANDIDATES.items():
        if candidate['group'] == group:
            column = CarouselColumn(
                thumbnail_image_url=candidate['image_url'],
                title=candidate['name'],
                text=candidate['description
