import os
from playwright.sync_api import sync_playwright

# ==== 環境変数 ====
BUFFER_EMAIL = os.getenv("BUFFER_EMAIL")
BUFFER_PASSWORD = os.getenv("BUFFER_PASSWORD")

if not BUFFER_EMAIL or not BUFFER_PASSWORD:
    raise ValueError("環境変数 BUFFER_EMAIL / BUFFER_PASSWORD を設定してください")

with sync_playwright() as p:
    # 初回は目視推奨
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    # 正しいログインURL
    page.goto("https://publish.buffer.com/login")

    # 入力 & ログイン
    page.fill("input#email", BUFFER_EMAIL)
    page.fill("input#password", BUFFER_PASSWORD)
    page.click("button#login-form-submit")

    page.wait_for_load_state("networkidle")

    # セッション保存（以後この状態でログイン不要）
    context.storage_state(path="buffer_session.json")
    print("✅ buffer_session.json にセッションを保存しました")

    browser.close()
