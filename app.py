from flask import Flask, jsonify, render_template
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
from pytz import timezone

app = Flask(__name__)
CORS(app)

cache = {"timestamp": None, "data": None}

def fetch_naver_news():
    headers = {"User-Agent": "Mozilla/5.0"}
    queries = ["BNB", "바이낸스"]
    all_articles = []

    now = datetime.now()
    today = now.date()
    targets = [today - timedelta(days=i) for i in range(4)]
    date_map = {date: [] for date in targets}

    def classify_article(date_str, article):
        d = date_str.strip()
        article_date = None
        try:
            if any(x in d for x in ["초 전", "분 전", "시간 전", "방금 전", "오늘"]):
                article_date = today
            elif "어제" in d:
                article_date = today - timedelta(days=1)
            elif "그제" in d:
                article_date = today - timedelta(days=2)
            elif "일 전" in d:
                days_ago = int(d.replace("일 전", "").strip())
                article_date = today - timedelta(days=days_ago)
            else:
                if d.endswith("."):
                    d = d[:-1]
                article_date = datetime.strptime(d, "%Y.%m.%d").date()

            if article_date in date_map and len(date_map[article_date]) < 30:
                date_map[article_date].append(article)

        except Exception as e:
            print(f"[❌ 날짜 파싱 실패] {d} → {e}")
            return

    for query in queries:
        base_url = f"https://search.naver.com/search.naver?where=news&query={query}&start="
        for page in range(1, 11):
            start = (page - 1) * 10 + 1
            url = base_url + str(start)
            try:
                response = requests.get(url, headers=headers, timeout=5)
                soup = BeautifulSoup(response.text, "html.parser")
            except Exception as e:
                print(f"⛔ 요청 실패: {url} → {e}")
                continue

            for item in soup.select("div.news_area"):
                a_tag = item.select_one("a.news_tit")
                press_tag = item.select_one("a.info.press")
                date_tag = item.select_one("span.info")

                if not a_tag or not press_tag or not date_tag:
                    continue

                article = {
                    "title": a_tag.get_text(strip=True),
                    "url": a_tag["href"],
                    "press": press_tag.get_text(strip=True).replace("언론사 선정", "").strip(),
                    "date": date_tag.get_text(strip=True)
                }

                classify_article(article["date"], article)

    result = {}
    for dt in targets:
        key = dt.strftime("%Y년 %m월 %d일")
        result[key] = date_map.get(dt, [])

    return result

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/news")
def get_news():
    now = datetime.now()
    if cache["timestamp"] and (now - cache["timestamp"]).total_seconds() < 300:
        return jsonify(cache["data"])
    data = fetch_naver_news()
    cache["timestamp"] = now
    cache["data"] = data
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
