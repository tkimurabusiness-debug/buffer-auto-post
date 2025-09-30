# buffer_scheduler.py

import os
import sys
import re
import argparse
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

# ====== 設定 ======
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1tId6_EGwNPbvSnVRynozNE8uo6qwOnT0a1MgWcF6wk4")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "看護師自動投稿1")
GOOGLE_CREDENTIALS = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS",
    "/Users/kimuratakezou/Documents/threads自動投稿/threads-outomation-17e522c47052.json"
)
BUFFER_SESSION_PATH = os.getenv("BUFFER_SESSION_PATH", "buffer_session.json")
HASHTAG_WORD = os.getenv("HASHTAG_WORD", "看護師")  # 固定タグ

# ====== Google Sheets ======
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS, scopes=SCOPES)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)

def get_next_post():
    """B列:親, C列:子, E列:未投稿のみ対象"""
    rows = sheet.get_all_values()
    if not rows:
        return None, None, None
    for idx, row in enumerate(rows[1:], start=2):
        content = (row[1].strip() if len(row) > 1 else "")
        cta     = (row[2].strip() if len(row) > 2 else "")
        status  = (row[4].strip() if len(row) > 4 else "")
        if status == "未投稿" and content:
            return idx, content, cta
    return None, None, None

def mark_status(row_idx, text):
    sheet.update_cell(row_idx, 5, text)

# ====== Buffer 投稿処理 ======
def post_to_buffer(content, cta, headed=False, slowmo=0, mode="schedule"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed, slow_mo=slowmo)
        context = browser.new_context(storage_state=BUFFER_SESSION_PATH)
        page = context.new_page()

        try:
            # ダッシュボード
            page.goto("https://publish.buffer.com/all-channels", wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")

            # New Post
            page.get_by_role("button", name=re.compile(r"New Post", re.I)).first.click(timeout=6000)

            # 親投稿
            parent = page.get_by_role("textbox").first
            parent.fill(content)

            if cta:
                # Tab 7回 → Enter で Start Thread を開く
                for _ in range(7):
                    page.keyboard.press("Tab")
                page.keyboard.press("Enter")
                page.wait_for_timeout(800)

                # 子投稿入力
                child_box = page.locator('div[role="textbox"][data-draftid="threads"]')
                if child_box.count() == 0:
                    child_box = page.get_by_role("textbox").last
                child_box.fill(cta)

                # タグ入力
                tag_input = page.locator("#threads-topic")
                tag_input.wait_for(state="visible", timeout=5000)
                tag_input.fill(HASHTAG_WORD)
                tag_input.press("Enter")
                page.wait_for_timeout(500)

                # Tab 4回 → Enter でスケジュール
                for _ in range(4):
                    page.keyboard.press("Tab")
                page.keyboard.press("Enter")

            page.wait_for_timeout(3000)
            print("✅ Buffer予約投稿が完了しました")

        finally:
            browser.close()

# ====== メイン ======
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["schedule", "now"], default="schedule")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--slowmo", type=int, default=0)
    args = parser.parse_args()

    row_idx, content, cta = get_next_post()
    if not content:
        print("⚠️ 未投稿の行が見つかりませんでした")
        sys.exit(0)

    print(f"投稿開始 → 親: {content[:20]}... / 子: {(cta or '')[:20]}...")
    try:
        post_to_buffer(content, cta, headed=args.headed, slowmo=args.slowmo, mode=args.mode)
        mark_status(row_idx, "予約済み" if args.mode == "schedule" else "即投稿済み")
        print("✅ 完了: Buffer 投稿 & シート更新")
    except Exception as e:
        mark_status(row_idx, f"エラー: {e}")
        print("❌ 失敗:", e)
        sys.exit(1)
