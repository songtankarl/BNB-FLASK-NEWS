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
    base_url = "https://search.naver.com/search.naver?where=news&query=비트코인&start="

    today = datetime.now().date()
    targets = [today - timedelta(days=i) for i in range(3)]
    date_map = {date: [] for date in targets}

    def classify(date_str, article):
        d = date_str.strip()
        article_date = None
        try:
            if "일 전" in d:
                days = int(d.replace("일 전", "").strip())
                article_date = today - timedelta(days=days)
            elif "시간 전" in d or "분 전" in d:
                article_date = today
            else:
                try:
                    article_date = datetime.strptime(d, "%Y.%m.%d.").date()
                except:
                    return
        except:
            return
        if article_date in date_map and len(date_map[article_date]) < 30:
            date_map[article_date].append(article)

    count = 0
    for page in range(1, 11):
        url = base_url + str((page - 1) * 10 + 1)
        soup = BeautifulSoup(requests.get(url, headers=headers).text, "html.parser")
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
