from flask import Flask, jsonify, render_template
from flask_cors import CORS
from flask_caching import Cache
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, date
from pytz import timezone
import re
import urllib.parse  # URL 인코딩용 모듈 추가

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})

@app.route("/")
def home():
    return render_template("index.html")

@cache.cached(timeout=300)
@app.route("/api/news")
def news():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
        )
    }

    # 검색어 설정: "BNB OR 바이낸스" 를 URL 인코딩하여 사용
    keyword = "BNB OR 바이낸스"  # 또는 "BNB|바이낸스" / "BNB 바이낸스" 등 필요에 따라 수정
    encoded_keyword = urllib.parse.quote(keyword)
    base_url = f"https://m.search.naver.com/search.naver?where=m_news&query={encoded_keyword}&start="

    now = datetime.now(timezone('Asia/Seoul'))
    today = now.date()

    # 최근 4일 치를 저장할 딕셔너리
    date_map = {}
    for i in range(4):
        date_key = today - timedelta(days=i)
        date_map[date_key] = []

    def classify_relative_date(date_str: str):
        """
        'n시간 전', 'n분 전', 'n일 전', 'YYYY.MM.DD.', 'YYYY.MM.DD' 등을
        제대로 파싱하여 date 객체(년-월-일)로 반환. 파싱 실패 시 None.
        """
        date_str = date_str.strip()

        # 예: "2025.04.15." → "2025.04.15"
        if re.match(r"\d{4}\.\d{1,2}\.\d{1,2}\.$", date_str):
            date_str = date_str.rstrip(".")

        # 'n시간 전' / 'n분 전' / 'n일 전'
        m_relative = re.match(r'(\d+)(분|시간|일)\s*전', date_str)
        if m_relative:
            amount = int(m_relative.group(1))
            unit = m_relative.group(2)
            if unit == '분':
                return (now - timedelta(minutes=amount)).date()
            elif unit == '시간':
                return (now - timedelta(hours=amount)).date()
            elif unit == '일':
                return (now - timedelta(days=amount)).date()

        # 'YYYY.MM.DD' 형태
        m_date = re.match(r'^(\d{4})\.(\d{1,2})\.(\d{1,2})$', date_str)
        if m_date:
            y = int(m_date.group(1))
            m = int(m_date.group(2))
            d = int(m_date.group(3))
            try:
                return date(y, m, d)
            except ValueError:
                return None

        # 추가 예시: "어제", "이틀 전", "방금 전" 등
        if "어제" in date_str:
            return (now - timedelta(days=1)).date()
        if "이틀 전" in date_str:
            return (now - timedelta(days=2)).date()
        if "방금 전" in date_str:
            return now.date()

        return None

    def get_news_items(soup):
        """
        다양한 셀렉터 후보 중 하나라도 맞으면 해당 결과를 반환.
        """
        news_items_selectors = [
            "div.news_wrap.api_ani_send",
            "ul.list_news > li.bx",
            "li.bx"
        ]
        for sel in news_items_selectors:
            items = soup.select(sel)
            if items:
                return items
        return []

    count = 0
    for page in range(1, 6):
        url = base_url + str((page - 1) * 10 + 1)

        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
        except Exception as e:
            print(f"⛔ 요청 실패: {e}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        news_items = get_news_items(soup)
        if not news_items:
            print("⚠️ news_items가 비어 있음. HTML 구조 변경 가능성 있음.")
            continue

        for item in news_items:
            # 제목/URL 추출 시도
            a = item.select_one("a.news_tit") \
                or item.select_one("a.api_txt_lines") \
                or item.select_one("a.link_tit") \
                or item.select_one("a")  # 최후 수단

            if not a:
                continue

            # 언론사 / 날짜 정보 찾기
            info_group = (
                item.select_one("div.news_info > div.info_group")
                or item.select_one("div.info_group")
            )
            if not info_group:
                continue

            info_spans = info_group.select("span.info")
            press_str = ""
            raw_date = ""

            if len(info_spans) >= 2:
                press_str = info_spans[0].get_text(strip=True)
                raw_date = info_spans[1].get_text(strip=True)
            elif len(info_spans) == 1:
                text_candidate = info_spans[0].get_text(strip=True)
                if "전" in text_candidate or re.match(r'^\d{4}\.\d{1,2}\.', text_candidate):
                    raw_date = text_candidate
                else:
                    press_str = text_candidate

            # 날짜 파싱
            article_date = classify_relative_date(raw_date)
            if article_date and article_date in date_map:
                article = {
                    "title": a.get_text(strip=True),
                    "url": a["href"],
                    "press": press_str,
                    "date": raw_date
                }
                date_map[article_date].append(article)
                count += 1

            if count >= 100:
                break

        if count >= 100:
            break

    result = {
        dt.strftime("%Y년 %m월 %d일"): date_map.get(dt, [])
        for dt in sorted(date_map.keys(), reverse=True)
    }

    return jsonify(result)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
