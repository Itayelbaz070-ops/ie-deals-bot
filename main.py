import os
import re
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = "8758744215:AAG2bLai_AgtQDYc5ASQD9Zf2hh4cgLYN_c"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6Iml0YXllbGJhemdpYm9yQGdtYWlsLmNvbSIsImxhbmciOiJlbiIsImlkIjozMTEyLCJ1c2VyX3R5cGUiOiJhZmZpbGlhdGUiLCJpYXQiOjE3OTA2MTI4OTIsIm9yaWdfaWF0IjoxNzkwNjEyODkyLCJleHAiOjE3OTE0NzY4OTJ9._QFaIGS35Icuu_VGtXaQ8anyFKIEUUrYbPktDhhevOg"

HEADERS = {
    "accept": "*/*",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "referer": "https://affiracle.com/affiliates/aliexpress"
}
COOKIES = {
    "access_token": ACCESS_TOKEN
}

STYLE_WORDS = {"leopard", "cheetah", "tiger", "flower", "floral", "flame", "fire", "checkerboard", "grid", "rainbow"}

# שרת ווב מזערי שפועל במקביל כדי לספק ל-Render את הפורט הדרוש לחשבון החינמי
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"IE Deals Bot is running 24/7!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

def clean_aliexpress_url(raw_url: str) -> str:
    item_match = re.search(r"item/(\d+)\.html", raw_url)
    if item_match:
        return f"https://www.aliexpress.com/item/{item_match.group(1)}.html"
    return raw_url.split("?")[0]

def get_product_details(url: str):
    api_url = "https://affiracle.com/aliexpress/generate-link"
    clean_url = clean_aliexpress_url(url)
    payload = {"url": clean_url}
    
    for attempt in range(2):
        try:
            res = requests.post(api_url, json=payload, headers=HEADERS, cookies=COOKIES, timeout=10)
            data = res.json()
            
            if "error" in data:
                time.sleep(3)
                continue
                
            tracked_url = data.get("tracked_url")
            product = data.get("product") or {}
            
            p_usd = float(product.get("sale_price_usd") or product.get("original_price_usd") or product.get("price_usd") or 0.0)
            p_ils = float(product.get("sale_price_ils") or product.get("original_price_ils") or product.get("price_ils") or 0.0)
            
            if p_ils == 0.0 and p_usd > 0.0:
                price_ils = round(p_usd * 3.7, 2)
            else:
                price_ils = p_ils
                
            title = product.get("title") or "מוצר מעליאקספרס"
            
            return {
                "tracked_url": tracked_url,
                "title": title,
                "price_ils": price_ils,
                "price_usd": p_usd
            }
        except Exception as e:
            print(f"Error fetching product: {e}")
            time.sleep(2)
            
    return None

def extract_essential_terms(title: str) -> list:
    cleaned = re.sub(r"[^\w\s]", " ", title)
    stop_words = {"new", "hot", "sale", "2024", "2025", "2026", "original", "best", "for", "with", "and", "the", "in", "high", "quality", "pro", "room", "space", "home", "decoration", "living", "bedroom"}
    words = [w.lower() for w in cleaned.split() if w.lower() not in stop_words and (len(w) > 2 or w.isdigit())]
    return words

def search_cheapest_alternative(orig_title: str, orig_price_ils: float):
    terms = extract_essential_terms(orig_title)
    query = " ".join(terms[:4])
    
    search_url = "https://affiracle.com/aliexpress/search"
    params = {
        "q": query,
        "page": 1,
        "page_size": 50,
        "sort": "price_asc"
    }
    
    orig_lower = orig_title.lower()
    orig_numbers = set(re.findall(r"\b\d+\b", orig_title))
    orig_has_black = "black" in orig_lower
    orig_styles = {w for w in STYLE_WORDS if w in orig_lower}
    is_original_accessory = any(acc in orig_lower for acc in ["controller only", "adapter only"])
    
    try:
        res = requests.get(search_url, params=params, headers=HEADERS, cookies=COOKIES, timeout=10)
        data = res.json()
        products = data.get("products", [])
        
        valid_alternatives = []
        min_price = orig_price_ils * 0.25 if orig_price_ils > 0 else 5.0
        core_keywords = set(terms[:3])

        for item in products:
            item_title = item.get("title", "")
            item_lower = item_title.lower()
            
            p_usd = float(item.get("sale_price_usd") or item.get("original_price_usd") or 0.0)
            price = float(item.get("sale_price_ils") or 0.0)
            if price == 0.0 and p_usd > 0.0:
                price = round(p_usd * 3.7, 2)
            
            if orig_price_ils > 0:
                if not (min_price <= price < orig_price_ils):
                    continue
            else:
                if price <= 0:
                    continue

            item_numbers = set(re.findall(r"\b\d+\b", item_title))
            if orig_numbers and not (orig_numbers & item_numbers):
                continue

            item_styles = {w for w in STYLE_WORDS if w in item_lower}
            if item_styles != orig_styles:
                continue

            if orig_has_black and "black" not in item_lower:
                continue

            matching_core = sum(1 for w in core_keywords if w in item_lower)
            if matching_core < min(2, len(core_keywords)):
                continue

            if not is_original_accessory:
                if any(bad in item_lower for bad in ["controller only", "remote only", "adapter only", "u-groove", "roller tool", "diffuser"]):
                    continue

            valid_alternatives.append({
                "title": item_title,
                "price_ils": price,
                "url": item.get("product_url")
            })

        if valid_alternatives:
            valid_alternatives.sort(key=lambda x: x["price_ils"])
            cheapest = valid_alternatives[0]
            
            time.sleep(2)
            
            aff_details = get_product_details(cheapest["url"])
            if aff_details and aff_details.get("tracked_url"):
                cheapest["url"] = aff_details["tracked_url"]
                
            return cheapest

    except Exception as e:
        print(f"Error in search: {e}")
        
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ברוך הבא ל-IE Deals!\n\n"
        "שלח לי קישור של מוצר מעליאקספרס ואאתר עבורך את הגרסה הזולה ביותר של אותו פריט עם קישורי שותפים וקופונים!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    url_match = re.search(r"(https?://[^\s]+)", text)
    
    if url_match and ("aliexpress.com" in text or "ali.ski" in text):
        raw_url = url_match.group(0)
        await update.message.reply_text("🔎 סורק את עליאקספרס ומחפש התאמה מדויקת של אותו דגם...")
        
        orig = get_product_details(raw_url)
        
        if orig and orig.get("tracked_url"):
            orig_price = orig["price_ils"]
            orig_title = orig["title"]
            
            cheapest = search_cheapest_alternative(orig_title, orig_price)
            
            price_display = f"₪{orig_price:.2f}" if orig_price > 0 else "לפי בחירת דגם בעמוד"
            
            msg = (
                f"📦 {orig_title[:65]}...\n"
                f"💰 מחיר בקישור ששלחת: {price_display}\n"
                f"🔗 קישור ישיר:\n{orig['tracked_url']}\n\n"
            )
            
            if cheapest and cheapest.get("url"):
                diff = orig_price - cheapest["price_ils"] if orig_price > 0 else 0
                savings_text = f" (חיסכון של ₪{diff:.2f}!)" if diff > 0 else "!"
                msg += (
                    f"🎉 מצאנו את אותו מוצר בדיוק במחיר נמוך יותר!\n"
                    f"📉 מחיר מוזל: ₪{cheapest['price_ils']:.2f}{savings_text}\n"
                    f"🛒 קישור לרכישה במחיר הזול:\n{cheapest['url']}\n\n"
                )
            else:
                msg += "✅ המוצר בקישור ששלחת הוא כרגע במחיר המשתלם ביותר שנמצא לפריט זה!\n\n"
                
            msg += (
                "🏷️ קופונים זמינים בקופה:\n"
                "• ILAFFSEP1 (מעל $29)\n"
                "• ILAFFSEP2 (מעל $59)\n"
                "• ILAFFSEP3 (מעל $89)"
            )
            
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("⚠️ המערכת עמוסה רגעית. אנא נסה שוב בעוד מספר שניות.")
    else:
        await update.message.reply_text("⚠️ אנא שלח קישור תקין של מוצר מעליאקספרס.")

if __name__ == "__main__":
    # הפעלת שרת הדמה ברקע
    server_thread = threading.Thread(target=run_dummy_server, daemon=True)
    server_thread.start()
    
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot IE Deals running with web listener on Render Free...")
    app.run_polling(poll_interval=0.5, timeout=10)
