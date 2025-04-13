from flask import Flask, jsonify, render_template
from flask_cors import CORS
from flask_caching import Cache
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})

@app.route("/")
def home():
    return render_template("index.html")

@cache.cached(timeout=300)
@app.route("/api/news")
def news():
    headers = {"User-Agent": "Mozilla/5.0"}
    queries = ["BNB", "바이낸스"]
    base_url = "https://search.naver.com/search.naver?where=news&query={}&start={}"

    today = datetime.now().date()
    targets = [today - timedelta(days=i) for i in range(4)]
    date_map = {date: [] for date in targets}

def classify(date_str, article):
    d = date_str.strip()
    article_date = None
    try:
        if "초 전" in d or "분 전" in d or "시간 전" in d or "방금 전" in d:
            article_date = today
        elif "오늘" in d:
            article_date = today
        elif "어제" in d:
            article_date = today - timedelta(days=1)
        elif "그제" in d:
            article_date = today - timedelta(days=2)
        elif "일 전" in d:
            # 예: 2일 전
            days = int(d.replace("일 전", "").strip())
            article_date = today - timedelta(days=days)
        else:
            # 예: 2025.04.12. → 20250412
            try:
                clean_date = d.replace(".", "").replace(" ", "")
                article_date = datetime.strptime(clean_date, "%Y%m%d").date()
            except:
                return
    except:
        return

    if article_date in date_map and len(date_map[article_date]) < 30:
        date_map[article_date].append(article)

    count = 0
    for query in queries:
        for page in range(1, 11):
            start = (page - 1) * 10 + 1
            url = base_url.format(query, start)
            try:
                response = requests.get(url, headers=headers, timeout=5)
                soup = BeautifulSoup(response.text, "html.parser")
            except Exception as e:
                print(f"⛔ 요청 실패: {e}")
                continue

            for item in soup.select("div.news_area"):
                a = item.select_one("a.news_tit")
                p = item.select_one("a.info.press")
                d = item.select_one("span.info")
                if not a or not p or not d:
                    continue
                article = {
                    "title": a.get_text(strip=True),
                    "url": a["href"],
                    "press": p.get_text(strip=True).replace("언론사 선정", "").strip(),
                    "date": d.get_text(strip=True)
                }
                classify(article["date"], article)
                count += 1
                if count >= 100:
                    break
            if count >= 100:
                break

    result = {dt.strftime("%Y년 %m월 %d일"): date_map.get(dt, []) for dt in targets}
    return jsonify(result)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
