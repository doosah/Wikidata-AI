# app.py  (ссылки и кнопка «Показать ещё» работают)
import json
from flask import Flask, render_template, request, jsonify, session
import spacy
from utils.wikidata_helpers import find_and_describe

app = Flask(__name__)
app.secret_key = "super_secret_key_123"

LANGUAGES = {"ru": "Русский", "en": "English", "zh": "中文"}
nlp_ru = spacy.load("ru_core_news_sm")
nlp_en = spacy.load("en_core_web_sm")

@app.route("/")
def index():
    lang = session.get("lang") or request.accept_languages.best_match(LANGUAGES.keys()) or "ru"
    session["lang"] = lang
    return render_template("index.html", lang=lang, languages=LANGUAGES)

@app.route("/set_lang/<lang>")
def set_lang(lang):
    if lang in LANGUAGES:
        session["lang"] = lang
    return jsonify({"status": "ok"})

@app.route("/ask", methods=["POST"])
def ask():
    data     = request.get_json() or {}
    question = data.get("question", "").strip()
    lang     = session.get("lang", "ru")

    if not question:
        return jsonify({"answer": "Пожалуйста, введите вопрос."})

    nlp   = nlp_ru if lang == "ru" else nlp_en
    doc   = nlp(question)
    query = next((ent.text for ent in doc.ents if ent.label_ in {"PER", "ORG", "LOC"}), question)
    found = find_and_describe(query, lang)

    if not found:
        return jsonify({"answer": "Ничего не найдено. Попробуй переформулировать."})

    if len(found) == 1:
        text = found[0]["text"]
        more = False
    else:
        show = found[:3]
        rest = found[3:]
        lines = ["Я нашёл несколько объектов:\n"]
        for f in show:
            lines.append(f"• **{f['label']}** — {f['descr']}\n[🔗 Источник]({f['url']})")
        if rest:
            lines.append(f"\n... и ещё {len(rest)}. Нажми «Показать ещё».")
        text = "\n".join(lines)
        more = bool(rest)

    return jsonify({"answer": text, "more": more, "question": question})

@app.route("/more", methods=["POST"])
def more():
    data     = request.get_json() or {}
    question = data.get("question", "").strip()
    lang     = session.get("lang", "ru")
    found    = find_and_describe(question, lang)
    lines    = []
    for f in found:
        lines.append(f"• **{f['label']}** — {f['descr']}\n{f['text']}")
    full_text = "\n\n".join(lines)
    return jsonify({"answer": full_text, "more": False})

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
# для хостинга
if __name__ != "__main__":
    import spacy
    nlp_ru = spacy.load("ru_core_news_sm")
    nlp_en = spacy.load("en_core_web_sm")