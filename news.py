import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime


CONFIG_FILE = "config.json"
OUTPUT_FILE = "news.json"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def download(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "2034-Watch/1.0"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def clean(text):
    if not text:
        return ""

    text = re.sub("<[^>]+>", "", text)
    text = text.replace("&amp;", "&")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")

    return " ".join(text.split())


def parse_date(value):
    if not value:
        return None

    try:
        return parsedate_to_datetime(value)
    except Exception:
        return None


def find_category(text, categories):

    text = text.lower()

    best_category = None
    best_score = 0

    for category, keywords in categories.items():

        score = 0

        for keyword in keywords:

            if keyword.lower() in text:
                score += 1

        if score > best_score:
            best_score = score
            best_category = category

    return best_category, best_score


def impact(text):

    text = text.lower()

    positive = [
        "csökkent",
        "csökkenti",
        "elfogad",
        "elfogadták",
        "bevezeti",
        "bevezet",
        "javul",
        "erősíti",
        "megszünteti",
        "ratifikál",
        "engedélyezi"
    ]

    negative = [
        "szigorít",
        "emelés",
        "emeli",
        "betilt",
        "megszünteti a támogatást",
        "visszalépés",
        "korlátozza",
        "korlátozás"
    ]

    p = sum(word in text for word in positive)
    n = sum(word in text for word in negative)

    if p > n and p > 0:
        return "🟢 valószínű pozitív irány"

    if n > p and n > 0:
        return "🔴 valószínű negatív irány"

    return "⚪ semleges / további ellenőrzés szükséges"


def parse_rss(data, source_name):

    root = ET.fromstring(data)

    articles = []

    for item in root.findall(".//item"):

        title = clean(
            item.findtext("title", "")
        )

        link = clean(
            item.findtext("link", "")
        )

        description = clean(
            item.findtext("description", "")
        )

        date = parse_date(
            item.findtext("pubDate", "")
        )

        articles.append({
            "title": title,
            "url": link,
            "summary": description[:500],
            "date": date.isoformat() if date else "",
            "source": source_name
        })

    return articles


def main():

    config = load_config()

    categories = config["categories"]

    cutoff = datetime.now(timezone.utc) - timedelta(
        days=config["news"]["lookback_days"]
    )

    results = []

    for source in config["news"]["sources"]:

        try:

            data = download(source["url"])

            articles = parse_rss(
                data,
                source["name"]
            )

            for article in articles:

                if article["date"]:

                    try:
                        article_date = datetime.fromisoformat(
                            article["date"]
                        )

                        if article_date < cutoff:
                            continue

                    except Exception:
                        pass

                combined = (
                    article["title"]
                    + " "
                    + article["summary"]
                )

                category, score = find_category(
                    combined,
                    categories
                )

                if not category:
                    continue

                article["category"] = category

                article["relevance"] = score

                article["impact"] = impact(
                    combined
                )

                results.append(article)

        except Exception as error:

            print(
                "Forrás hiba:",
                source["name"],
                error
            )

    unique = {}

    for article in results:

        key = article["url"] or article["title"]

        unique[key] = article

    results = list(unique.values())

    results.sort(
        key=lambda x: x.get("relevance", 0),
        reverse=True
    )

    results = results[
        :config["news"]["max_articles"]
    ]

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"{len(results)} releváns hírt mentettem."
    )


if __name__ == "__main__":
    main()