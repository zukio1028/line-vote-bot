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

# ★★★ あなたの設定に合わせて、以下の3つを書き換えてください ★★★

# 1. LINE Developersコンソールで取得したチャネルアクセストークン
ACCESS_TOKEN = 'CRGRXv3lv4npWSbG3EWlkjLfbO2BlC76kiDRSwb99Tzx9IIrnkZYALJzS4NQ92acWNVGZG1apefFqXOsnlL4Q73c6KDM2wcw14ibmD34rpH5BY+R29TiHRfHSSPZENgQGlAr3ikb0ydq21ZOwXQ9mgdB04t89/1O/w1cDnyilFU='
# 2. LINE Developersコンソールで取得したチャネルシークレット
CHANNEL_SECRET = '963605e7b2c57bf9262699e1bc4be12a'
# 3. 管理者として登録したい人のLINEユーザーID (カンマ区切りで複数人設定可能)
ADMIN_USER_IDS = [
    'Uf1611271742fa4f05fa7cc43fba1069d',
    'Ud261a022a8834f5febb028928488477d',
    'U591f718b10f9f62d09be717c34261e3f',
    'U6752c92e842f5e1401e2b1ec479856d0',
]
# ★★★ 設定はここまで ★★★

configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

VOTES_FILE = 'votes.json'

CANDIDATES = {
    '1': {'group': 'A', 'name': '佐藤翼 No.1', 'image_url': 'https://i.postimg.cc/s2zVxgpw/317038.jpg', 'description': '【ど田舎からの刺客】'},
    '2': {'group': 'A', 'name': '高岡友輝 No.2', 'image_url': 'https://i.postimg.cc/tJsbwZj4/317039.jpg', 'description': '【制御不能なカリスマ】'},
    '3': {'group': 'A', 'name': '磯歩夢 No.3', 'image_url': 'https://i.postimg.cc/rwXTZwZg/317040.jpg', 'description': '【夢に向かって、歩む。】'},
    '4': {'group': 'B', 'name': '興田愛加 No.4', 'image_url': 'https://i.postimg.cc/vTJJK0h2/317041.jpg', 'description': '【控えめに見えて、透き通る強さ】'},
    '5': {'group': 'B', 'name': '早川 No.5', 'image_url': 'https://i.postimg.cc/rFWswbBL/317043.jpg', 'description': '【たまに見かけるシルカフェのお兄さん】'},
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
                text=candidate['description'],
                actions=[PostbackAction(label='この人に投票する', display_text=f'{candidate["name"]}に投票します', data=f'action=vote&candidate_id={id}')]
            )
            columns.append(column)
    return TemplateMessage(alt_text=f'グループ{group}の候補者リスト', template=CarouselTemplate(columns=columns))

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text
    user_id = event.source.user_id
    messages_to_send = []

    if text == '投票':
        now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))
        # ★★★ 投票開始日をここで設定 ★★★
        start_date = datetime(2025, 10, 24, 0, 0, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

        if now_jst < start_date:
            messages_to_send.append(TextMessage(text='投票は10月24日の午前0時から開始します。もうしばらくお待ちください！'))
        else:
            today_jst_str = now_jst.strftime('%Y-%m-%d')
            data = load_votes()
            voter_info = data['voters'].get(user_id, {})
            last_vote_date = voter_info.get('last_vote_date')

            if last_vote_date == today_jst_str:
                messages_to_send.append(TextMessage(text='本日の投票は既に完了しています。また明日、よろしくお願いします！'))
            else:
                data['voters'][user_id] = {}
                save_votes(data)
                messages_to_send.append(TextMessage(text='まずは、COOL部門の投票です！'))
                messages_to_send.append(
                    ImageMessage(
                        original_content_url='https://i.postimg.cc/Z5mVnGDg/cool3.jpg',
                        preview_image_url='https://i.postimg.cc/Z5mVnGDg/cool3.jpg'
                    )
                )
                messages_to_send.append(create_carousel_message('A'))
            
    elif text == '集計':
        if user_id in ADMIN_USER_IDS:
            data = load_votes()
            vote_counts = data['votes']
            sorted_votes = sorted(vote_counts.items(), key=lambda item: item[1], reverse=True)
            reply_text = "【現在の投票結果】\n\n"
            for candidate_id, count in sorted_votes:
                candidate_name = CANDIDATES.get(candidate_id, {}).get('name', '不明な候補者')
                reply_text += f"{candidate_name}: {count}票\n"
            total_voters = len(data['voters'])
            reply_text += f"\n総投票者数: {total_voters}人"
            messages_to_send.append(TextMessage(text=reply_text))
        else:
            pass

    elif text == 'リセット':
        if user_id in ADMIN_USER_IDS:
            data = load_votes()
            voter_info = data['voters'].get(user_id)

            if voter_info and 'last_vote_date' in voter_info:
                del data['voters'][user_id]['last_vote_date']
                save_votes(data)
                reply_text = "あなたの投票記録をリセットしました。再度「投票」と入力してテストを開始できます。"
            else:
                reply_text = "リセット対象の投票記録がありません。"
            
            messages_to_send.append(TextMessage(text=reply_text))
        else:
            pass

    if messages_to_send:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply

