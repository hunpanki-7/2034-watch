import feedparser
import json
import os
import google.generativeai as genai

# Gemini API beállítása a GitHub titkos kulcsból
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    # Az ingyenesen használható modell
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

# A jóváhagyott RSS hírforrások
RSS_FEEDS = [
    "https://telex.hu/rss",
    "https://hvg.hu/rss/rss.hvg/hirek",
    "https://24.hu/feed/",
    "https://hu.euronews.com/rss"
]

# Kategóriák és kulcsszavak a szűréshez
CATEGORIES = {
    "Adózás és megélhetési költségek": ["adó", "áfa", "infláció", "élelmiszer", "ár", "menstruációs", "rezsi"],
    "Női és reproduktív jogok": ["női", "reproduktív", "abortusz", "resztoratív", "családvédelem"],
    "Egyenlőség és LMBTQ+ jogok": ["lmbtq", "egyenlőség", "diszkrimináció", "pride", "jogvédelem", "pronatalizmus"],
    "Környezet és energia": ["környezet", "energia", "szélenergia", "gáz", "kőolaj", "klíma", "fenntartható", "vízvédelem"],
    "Gazdaság, mezőgazdaság és innováció": ["gazdaság", "ipar", "mezőgazdaság", "innováció", "agrár", "K+F"],
    "Jogállamiság és intézmények": ["jogállam", "korrupció", "bíróság", "intézmény", "átláthatóság"],
    "Külpolitika és nemzetközi kapcsolatok": ["külpolitika", "diplomácia", "béke", "európai unió", "uniós forrás"],
    "Szociális biztonság és fogyatékosságügy": ["szociális", "fogyatékos", "esélyegyenlőség", "nyugdíj", "segítség"],
    "AI és gazdasági átalakulás": ["mesterséges intelligencia", "ai", "automatizáció", "robotizáció", "alapjövedelem"]
}

def fetch_news():
    articles = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:20]: # Hírforrásonként a 20 legfrissebb
            title = entry.get('title', '')
            summary = entry.get('summary', '')
            link = entry.get('link', '')
            
            matched_category = None
            text_to_check = (title + " " + summary).lower()
            
            for cat, keywords in CATEGORIES.items():
                if any(kw in text_to_check for kw in keywords):
                    matched_category = cat
                    break
            
            if matched_category:
                articles.append({
                    "title": title,
                    "link": link,
                    "category": matched_category,
                    "summary": summary[:200]
                })
    return articles

def analyze_with_ai(articles):
    if not model:
        print("Nincs AI kulcs, az elemzés alapértelmezett marad.")
        for a in articles:
            a["ai_eval"] = "⚪ Nincs még értékelve"
        return articles

    for article in articles:
        prompt = f"Elemozd ki ezt a hírt a(z) '{article['category']}' cél szempontjából. Válaszd ki pontosan az egyiket: '🟡 Előrelépés', '🟢 Teljesült', '🟠 Visszalépés', '🔴 Jelentős visszalépés', vagy '⚪ Semleges'. Csak ezt az egy kifejezést add meg! Hír: {article['title']}"
        try:
            response = model.generate_content(prompt)
            eval_text = response.text.strip()
            if "Előrelépés" in eval_text: article["ai_eval"] = "🟡 Előrelépés"
            elif "Teljesült" in eval_text: article["ai_eval"] = "🟢 Teljesült"
            elif "Visszalépés" in eval_text and "Jelentős" not in eval_text: article["ai_eval"] = "🟠 Visszalépés"
            elif "Jelentős" in eval_text: article["ai_eval"] = "🔴 Jelentős visszalépés"
            else: article["ai_eval"] = "⚪ Semleges"
        except Exception as e:
            print(f"AI hiba: {e}")
            article["ai_eval"] = "⚪ Nincs még értékelve"
    return articles

if __name__ == "__main__":
    news = fetch_news()
    analyzed_news = analyze_with_ai(news)
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(analyzed_news, f, ensure_ensure=False if 'ensure_ensure' not in globals() else True, indent=4)
    print(f"Kész! {len(analyzed_news)} releváns hír mentve a data.json-be.")