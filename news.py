import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

CONFIG_FILE = "config.json"
OUTPUT_FILE = "data.json"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def download(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "2034-Watch/1.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def clean(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)

    return (
        text.replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .strip()
    )


def parse_date(value):
    if not value:
        return None

    try:
        return parsedate_to_datetime(value)
    except Exception:
        return None


def parse_rss(data, source_name):
    root = ET.fromstring(data)
    articles = []

    for item in root.findall(".//item"):
        title = clean(item.findtext("title", ""))
        link = clean(item.findtext("link", ""))
        description = clean(item.findtext("description", ""))
        date = parse_date(item.findtext("pubDate", ""))

        if not title or not link:
            continue

        articles.append({
            "title": title,
            "url": link,
            "summary": description[:1000],
            "date": date.isoformat() if date else "",
            "source": source_name
        })

    return articles


def keyword_relevance(article, categories):
    text = (
        article["title"] + " " + article["summary"]
    ).lower()

    matches = []

    for category, keywords in categories.items():
        score = 0

        for keyword in keywords:
            if keyword.lower() in text:
                score += 1

        if score:
            matches.append((category, score))

    if not matches:
        return None, 0

    matches.sort(key=lambda x: x[1], reverse=True)

    return matches[0]


def ai_analyse(article, categories):
    """
    Gemini analysis.

    If GEMINI_API_KEY is not available, the program falls back
    to the keyword system instead of crashing.
    """

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(
            "gemini-2.0-flash"
        )

        category_names = ", ".join(categories.keys())

        prompt = f"""
You are the analysis engine of a personal news tracker called 2034 Watch.

The user is tracking long-term progress in Hungary and the EU.

Categories:
{category_names}

Article title:
{article["title"]}

Article summary:
{article["summary"]}

Return ONLY valid JSON in this exact structure:

{{
  "category": "one category from the list",
  "impact": "positive OR negative OR neutral",
  "importance": 1,
  "progress": 0,
  "explanation": "one short sentence in Hungarian"
}}

Rules:

- importance: 1-5
- progress: -2, -1, 0, +1 or +2
- +2 means major progress toward the user's goals
- +1 means smaller progress
- 0 means unclear or unrelated
- -1 means setback
- -2 means major setback
- Do not treat ordinary political statements as completed reforms.
- Distinguish announcements from actual laws or implementation.
- Be factual and cautious.
"""

        response = model.generate_content(prompt)

        text = response.text.strip()

        text = re.sub(
            r"^```json\s*|\s*```$",
            "",
            text,
            flags=re.IGNORECASE
        )

        return json.loads(text)

    except Exception as error:
        print("Gemini hiba:", error)
        return None


def main():

    config = load_config()

    categories = config["categories"]

    cutoff = datetime.now(timezone.utc) - timedelta(
        days=config["news"]["lookback_days"]
    )

    candidates = []

    for source in config["news"]["sources"]:

        try:
            print("Forrás:", source["name"])

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

                category, score = keyword_relevance(
                    article,
                    categories
                )

                if not category:
                    continue

                article["_keyword_score"] = score

                candidates.append(article)

        except Exception as error:

            print(
                "Forrás hiba:",
                source["name"],
                error
            )

    # Duplicate removal
    unique = {}

    for article in candidates:

        key = article["url"] or article["title"]

        if key not in unique:
            unique[key] = article

    candidates = list(unique.values())

    # Highest keyword relevance first
    candidates.sort(
        key=lambda x: x["_keyword_score"],
        reverse=True
    )

    # Don't send hundreds of articles to Gemini
    candidates = candidates[
        :config["news"]["ai_articles"]
    ]

    results = []

    for article in candidates:

        analysis = ai_analyse(
            article,
            categories
        )

        if analysis:

            article["category"] = analysis.get(
                "category",
                ""
            )

            article["impact"] = analysis.get(
                "impact",
                "neutral"
            )

            article["importance"] = analysis.get(
                "importance",
                1
            )

            article["progress"] = analysis.get(
                "progress",
                0
            )

            article["explanation"] = analysis.get(
                "explanation",
                ""
            )

        else:

            article["category"] = keyword_relevance(
                article,
                categories
            )[0]

            article["impact"] = "neutral"
            article["importance"] = 1
            article["progress"] = 0
            article["explanation"] = (
                "AI-értékelés nem érhető el."
            )

        article.pop("_keyword_score", None)

        results.append(article)

    results.sort(
        key=lambda x: (
            x.get("importance", 1),
            x.get("progress", 0)
        ),
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
            {
                "updated": datetime.now(
                    timezone.utc
                ).isoformat(),

                "articles": results
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"{len(results)} AI-val értékelt hírt mentettem."
    )


if __name__ == "__main__":
    main()
