from flask import Flask, jsonify, render_template
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os

app = Flask(__name__)
CORS(app)

cache = {"timestamp": None, "data": None}

def fetch_naver_news():
    headers = {"User-Agent": "Mozilla/5.0"}
    queries = ["BNB", "바이낸스"]
    all_articles = []

    for query in queries:
        base_url = f"https://search.naver.com/search.naver?where=news&query={query}&start="
        today = datetime.now().date()
        for page in range(1, 11):
            start = (page - 1) * 10 + 1
            url = base_url + str(start)
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")
            for item in soup.select("div.news_area"):
                a_tag = item.select_one("a.news_tit")
                press_tag = item.select_one("a.info.press")
                date_tag = item.select_one("span.info")

                if not a_tag or not press_tag or not date_tag:
                    continue

                title = a_tag.get_text(strip=True)
                link = a_tag["href"]
                press = press_tag.get_text(strip=True).replace("언론사 선정", "").strip()
                date_str = date_tag.get_text(strip=True)

                article = {
                    "title": title,
                    "url": link,
                    "press": press,
                    "date": date_str
                }

                all_articles.append(article)

    # 날짜별 분류
    targets = [today - timedelta(days=i) for i in range(4)]
    date_map = {date: [] for date in targets}

def classify_article(date_str, article):
    try:
        if "일 전" in date_str:
            days_ago = int(date_str.replace("일 전", "").strip())
            article_date = today - timedelta(days=days_ago)
        elif "시간 전" in date_str or "분 전" in date_str or "초 전" in date_str:
            article_date = today
        elif "어제" in date_str:
            article_date = today - timedelta(days=1)
        elif "오늘" in date_str:
            article_date = today
        else:
            # 예: 2025.04.12. → 20250412 → 날짜 객체로 변환
            clean_date = date_str.strip().replace(".", "")
            article_date = datetime.strptime(clean_date, "%Y%m%d").date()

        # 날짜가 원하는 범위 안에 있는 경우에만 저장
        if article_date in date_map and len(date_map[article_date]) < 30:
            date_map[article_date].append(article)

    except Exception as e:
        print(f"⛔ 날짜 파싱 실패: {date_str} → {e}")
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
