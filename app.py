# 必要なライブラリを読み込む
import os
import json
from urllib.parse import parse_qs
from flask import Flask, request, abort
from datetime import datetime, timezone, timedelta
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
ADMIN_USER_IDS = [uid.strip() for uid in ADMIN_USER_IDS_str.split(',') if uid.strip()] # 空白を除去
# ★★★ 設定はここまで ★★★

configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# --- ▼▼▼ [修正点 1] Persistent Disk対応 ▼▼▼ ---
# データを永続ディスクの /data/ ディレクトリに保存
VOTES_FILE = '/data/votes.json' 
# --- ▲▲▲ [修正点 1] Persistent Disk対応 ▲▲▲ ---

# --- ▼▼▼ [修正点 2] 投票期間とタイムゾーンの定義 ▼▼▼ ---
# タイムゾーン (JST = 日本標準時)
JST = ZoneInfo("Asia/Tokyo")

# 投票期間の設定 (前回指定の日時)
VOTE_START = datetime(2025, 11, 8, 1, 36, 0, tzinfo=JST)
VOTE_END = datetime(2025, 11, 22, 23, 59, 59, tzinfo=JST)
# --- ▲▲▲ [修正点 2] 投票期間とタイムゾーンの定義 ▲▲▲ ---


CANDIDATES = {
    '1': {'group': 'A', 'name': '佐藤翼 No.1', 'image_url': 'https://i.postimg.cc/s2zVxgpw/317038.jpg', 'description': '【ど田舎からの刺客】'},
    '2': {'group': 'A', 'name': '高岡友輝 No.2', 'image_url': 'https://i.postimg.cc/tJsbwZj4/317039.jpg', 'description': '【制御不能なカリスマ】'},
    '3': {'group': 'A', 'name': '磯歩夢 No.3', 'image_url': 'https://i.postimg.cc/rwXTZwZg/317040.jpg', 'description': '【夢に向かって、歩む。】'},
    '4': {'group': 'B', 'name': '與田愛加 No.4', 'image_url': 'https://i.postimg.cc/vTJJK0h2/317041.jpg', 'description': '【控えめに見えて、透き通る強さ】'},
    '5': {'group': 'B', 'name': '早川晏麓 No.5', 'image_url': 'https://i.postimg.cc/rFWswbBL/317043.jpg', 'description': '【たまに見かけるシルカフェのお兄さん】'},
    '6': {'group': 'B', 'name': '岡村菜那 No.6', 'image_url': 'https://i.postimg.cc/BvZnNvXD/317044.jpg', 'description': '【笑顔でみなさんを元気にさせます🤍】'},
}

# --- ヘルパー関数 -----------------------------------------------------------------
# (VOTES_FILEのパスが修正された以外は、元のコードのまま)

def load_votes():
    """Persistent Diskから投票データを読み込む"""
    if not os.path.exists(VOTES_FILE):
        # 初回起動時、空のファイルを作成
        print(f"初回起動: {VOTES_FILE} が見つからないため、空のファイルを作成します。")
        initial_data = {'votes': {id: 0 for id in CANDIDATES}, 'voters': {}}
        save_votes(initial_data)
        return initial_data
    try:
        with open(VOTES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        # ファイルが破損していたらリセット
        print(f"エラー: {VOTES_FILE} の読み込みに失敗 ({e})。ファイルをリセットします。")
        initial_data = {'votes': {id: 0 for id in CANDIDATES}, 'voters': {}}
        save_votes(initial_data)
        return initial_data


def save_votes(data):
    """Persistent Diskに投票データを書き込む"""
    try:
        with open(VOTES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"エラー: {VOTES_FILE} への書き込みに失敗しました ({e})") # Renderのログに出力

# --- LINE Botのメイン処理 -----------------------------------------------------

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel secret.")
        abort(400)
    except Exception as e:
        print(f"Handler error: {e}")
        abort(500)
    return 'OK'

def create_carousel_message(group):
    """カルーセルメッセージを作成する (元のコードのまま)"""
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
    """テキストメッセージ受信時の処理 (大幅に修正)"""
    
    text = event.message.text.strip()
    user_id = event.source.user_id
    now_jst = datetime.now(JST) # 現在時刻をJSTで取得
    
    messages_to_send = []

    # --- ▼▼▼ [修正点 3] 管理者モードの処理を最優先 ▼▼▼ ---
    if user_id in ADMIN_USER_IDS:
        if text == '集計':
            data = load_votes()
            vote_counts = data['votes']
            sorted_votes = sorted(vote_counts.items(), key=lambda item: item[1], reverse=True)
            reply_text = "【現在の投票結果 (管理者モード)】\n\n"
            for candidate_id, count in sorted_votes:
                candidate_name = CANDIDATES.get(candidate_id, {}).get('name', '不明な候補者')
                reply_text += f"{candidate_name}: {count}票\n"
            total_voters = len(data['voters'])
            reply_text += f"\n総投票者数: {total_voters}人"
            messages_to_send.append(TextMessage(text=reply_text))

        elif text == 'リセット':
            data = load_votes()
            voter_info = data['voters'].get(user_id)
            if voter_info and 'last_vote_date' in voter_info:
                del data['voters'][user_id]['last_vote_date']
                save_votes(data) # リセット時のみ保存
                reply_text = "【管理者テスト】あなたの投票記録をリセットしました。再度「投票」と入力してテストを開始できます。"
            else:
                reply_text = "【管理者テスト】リセット対象の投票記録がありません。"
            messages_to_send.append(TextMessage(text=reply_text))
        
        elif text == '投票':
            # 管理者が「投票」した場合、テストモードであることを通知しつつ、カルーセルを出す
            messages_to_send.append(TextMessage(text=f"【管理者テストモード】\n（集計には加算されません）\n\nまずは、COOL部門の投票です！\n現在の時刻: {now_jst.strftime('%H:%M:%S')}"))
            messages_to_send.append(
                ImageMessage(
                    original_content_url='https://i.postimg.cc/Z5mVnGDg/cool3.jpg',
                    preview_image_url='https://i.postimg.cc/Z5mVnGDg/cool3.jpg'
                )
            )
            messages_to_send.append(create_carousel_message('A'))
        
        # (管理者のその他のテキストは無視)

    # --- ▼▼▼ 一般ユーザーの処理 ▼▼▼ ---
    else:
        if text == '投票':
            # --- [修正点 2] 投票期間チェック ---
            if now_jst < VOTE_START:
                messages_to_send.append(TextMessage(text=f"ただいまメンテナンス中です。\n投票は 11月8日(土) 午前4時 からです。\nもうしばらくお待ちください！"))
            elif now_jst > VOTE_END:
                messages_to_send.append(TextMessage(text="投票は 11月22日をもって終了しました。\nたくさんのご投票、ありがとうございました！"))
            # --- 期間内の処理 (元のロジック) ---
            else:
                today_jst_str = now_jst.strftime('%Y-%m-%d')
                data = load_votes()
                voter_info = data['voters'].get(user_id, {})
                last_vote_date = voter_info.get('last_vote_date')

                if last_vote_date == today_jst_str:
                    messages_to_send.append(TextMessage(text='本日の投票は既に完了しています。また明日、よろしくお願いします！'))
                
                elif voter_info.get('A') and not voter_info.get('B'):
                    # (グループAには投票済みだが、Bにはまだ)
                    messages_to_send.append(TextMessage(text='CUTE部門の投票がまだ完了していません。\nこちらから投票をお願いします。'))
                    messages_to_send.append(
                        ImageMessage(
                            original_content_url='https://i.postimg.cc/15qjfcRr/cute3.jpg',
                            preview_image_url='https://i.postimg.cc/15qjfcRr/cute3.jpg'
                        )
                    )
                    messages_to_send.append(create_carousel_message('B'))
                    
                else:
                    # (本日初めての投票 or 両方リセットされた)
                    data['voters'][user_id] = {} # ユーザー情報を初期化 (グループA, Bの投票記録を消す)
                    save_votes(data)
                    messages_to_send.append(TextMessage(text='まずは、COOL部門の投票です！'))
                    messages_to_send.append(
                        ImageMessage(
                            original_content_url='https://i.postimg.cc/Z5mVnGDg/cool3.jpg',
                            preview_image_url='https://i.postimg.cc/Z5mVnGDg/cool3.jpg'
                        )
                    )
                    messages_to_send.append(create_carousel_message('A'))
        
        # (一般ユーザーの '投票' 以外のテキストは無視)

    # --- ▼▼▼ [修正点 4] API呼び出しの共通化 ▼▼▼ ---
    if messages_to_send:
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(reply_token=event.reply_token, messages=messages_to_send)
                )
        except Exception as e:
            print(f"Error sending reply message: {e}")
    # --- ▲▲▲ [修正点 4] API呼び出しの共通化 ▲▲▲ ---


@handler.add(PostbackEvent)
def handle_postback(event):
    """Postbackイベント（投票ボタン押下時）の処理"""
    
    user_id = event.source.user_id
    now_jst = datetime.now(JST) # 現在時刻をJSTで取得
    postback_data = parse_qs(event.postback.data)
    action = postback_data.get('action', [None])[0]
    
    messages_to_send = []

    if action == 'vote':
        candidate_id = postback_data.get('candidate_id', [None])[0]
        voted_candidate = CANDIDATES.get(candidate_id)
        if not voted_candidate: return # 不正なIDは無視

        voted_group = voted_candidate['group']
        voted_name = voted_candidate['name']

        # --- ▼▼▼ [修正点 3] 管理者テストモード ▼▼▼ ---
        if user_id in ADMIN_USER_IDS:
            if voted_group == 'A':
                reply_text = f"【管理者テスト】\n{voted_name}さんに投票しました。\n（集計には加算されません）\n\n次は、CUTE部門の投票です！"
                messages_to_send.append(TextMessage(text=reply_text))
                messages_to_send.append(
                    ImageMessage(
                        original_content_url='https://i.postimg.cc/15qjfcRr/cute3.jpg',
                        preview_image_url='https://i.postimg.cc/15qjfcRr/cute3.jpg'
                    )
                )
                messages_to_send.append(create_carousel_message('B'))
            else: # グループB
                reply_text = f"【管理者テスト】\n{voted_name}さんに投票しました。\n\nテスト投票完了です！\n（集計には加算されません）"
                messages_to_send.append(TextMessage(text=reply_text))
            
            # (save_votes() は絶対に呼び出さない)
        
        # --- ▼▼▼ 一般ユーザーの処理 ▼▼▼ ---
        else:
            # --- [修正点 2] 投票期間チェック ---
            if now_jst < VOTE_START:
                messages_to_send.append(TextMessage(text=f"投票は 11月8日(土) 午前4時 からです。"))
            elif now_jst > VOTE_END:
                messages_to_send.append(TextMessage(text="投票は 11月22日(土) 23:59 に終了しました。"))
            # --- 期間内の処理 (元のロジック) ---
            else:
                data = load_votes()
                # handle_messageで初期化されているはずだが、安全のため .get() を使う
                voter_info = data['voters'].get(user_id, {}) 

                if voter_info.get(voted_group):
                    messages_to_send.append(TextMessage(text=f'グループ{voted_group}には既に投票済みです。'))
                else:
                    # ★★★ ここで集計に加算 ★★★
                    data['votes'][candidate_id] += 1
                    data['voters'][user_id][voted_group] = candidate_id
                    
                    if voted_group == 'A':
                        save_votes(data) # グループA投票後に一度保存
                        messages_to_send.append(TextMessage(text=f'{voted_name}さんに投票しました。\n次は、CUTE部門の投票です！'))
                        messages_to_send.append(
                            ImageMessage(
                                original_content_url='https://i.postimg.cc/15qjfcRr/cute3.jpg',
                                preview_image_url='https://i.postimg.cc/15qjfcRr/cute3.jpg'
                            )
                        )
                        messages_to_send.append(create_carousel_message('B'))
                    
                    else: # グループB
                        today_jst_str = now_jst.strftime('%Y-%m-%d')
                        data['voters'][user_id]['last_vote_date'] = today_jst_str # 1日の投票完了フラグを立てる
                        save_votes(data) # 最終保存
                        
                        voted_a_id = data['voters'][user_id].get('A')
                        voted_a_name = CANDIDATES.get(voted_a_id, {}).get('name', '未選択')
                        voted_b_name = voted_name
                        reply_text = f'{voted_b_name}さんに投票しました。\n\n本日の投票完了です！ありがとうございました！\nあなたの投票:\n- {voted_a_name}\n- {voted_b_name}'
                        messages_to_send.append(TextMessage(text=reply_text))

    # --- ▼▼▼ [修正点 4] API呼び出しの共通化 ▼▼▼ ---
    if messages_to_send:
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(reply_token=event.reply_token, messages=messages_to_send)
                )
        except Exception as e:
            print(f"Error sending reply message: {e}")
    # --- ▲▲▲ [修正点 4] API呼び出しの共通化 ▲▲▲ ---

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

