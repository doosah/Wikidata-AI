# utils/wikidata_helpers.py  (полностью новый код)
import requests, itertools, re
from datetime import datetime
from typing import List, Dict, Optional

HEADERS = {"User-Agent": "FreeTextWikidataBot/1.0 (https://example.com; admin@example.com)"}
API = "https://www.wikidata.org/w/api.php"
WIKIDATA_ITEM = "https://www.wikidata.org/entity/{qid}"

# ---------- базовые вспомогательные ----------
def wd_get(url: str, params: dict, timeout=8):
    return requests.get(url, params, headers=HEADERS, timeout=timeout).json()

def label_for(qid: str, lang: str = "ru") -> str:
    """Кешируем лейблы, чтобы не дублировать запросы."""
    if not hasattr(label_for, "_cache"):
        label_for._cache = {}
    if qid in label_for._cache:
        return label_for._cache[qid]
    data = wd_get(API, {"action": "wbgetentities", "ids": qid, "props": "labels",
                        "languages": f"{lang}|en", "format": "json"})
    lbl = (data["entities"].get(qid, {}).get("labels", {}).get(lang) or
           data["entities"].get(qid, {}).get("labels", {}).get("en") or
           {}).get("value", qid)
    label_for._cache[qid] = lbl
    return lbl

# ---------- поиск сущностей ----------
def search_entities(query: str, lang: str = "ru", limit: int = 5) -> List[Dict]:
    """Возвращает список словарей {'qid': '..', 'label': '..', 'descr': '..'}"""
    params = {"action": "wbsearchentities", "search": query, "language": lang,
              "uselang": lang, "format": "json", "limit": limit}
    data = wd_get(API, params)
    results = []
    for item in data.get("search", []):
        results.append({"qid": item["id"],
                        "label": item.get("label", ""),
                        "descr": item.get("description", "")})
    # если русский не дал результатов – пробуем английский
    if not results and lang != "en":
        return search_entities(query, "en", limit)
    return results

# ---------- универсальный «человекочитаемый» сбор утверждений ----------
def free_text_description(qid: str, lang: str = "ru") -> str:
    """Собирает из объекта максимально развернутое, но читаемое описание."""
    ent = wd_get(API, {"action": "wbgetentities", "ids": qid,
                       "languages": f"{lang}|en", "props": "labels|descriptions|claims",
                       "format": "json"})["entities"].get(qid, {})
    if not ent:
        return "Объект не найден."

    name = (ent.get("labels", {}).get(lang) or ent.get("labels", {}).get("en") or {}).get("value", qid)
    descr = (ent.get("descriptions", {}).get(lang) or ent.get("descriptions", {}).get("en") or {}).get("value", "")

    lines = [f"**{name}** — {descr}." if descr else f"**{name}**"]

    claims = ent.get("claims", {})
    # покажем максимум 6 «самых понятных» свойств
    wanted_props = ["P31", "P106", "P569", "P570", "P19", "P27", "P571", "P112",
                    "P159", "P856", "P800", "P166", "P131", "P2048", "P18"]
    for prop in wanted_props:
        if len(lines) > 8:  # не раздувать
            break
        vals = get_claim_values(claims, prop, lang)
        if vals:
            prop_name = label_for(prop, lang)
            lines.append(f"**{prop_name}:** {', '.join(vals[:3])}{' …' if len(vals)>3 else ''}")

    lines.append(f"\n[🔗 Источник]({WIKIDATA_ITEM.format(qid=qid)})")
    return "\n".join(lines)

def get_claim_values(claims: dict, prop: str, lang: str):
    """Возвращает список человекочитаемых значений свойства."""
    if prop not in claims:
        return []
    out = []
    for c in claims[prop]:
        try:
            mainsnak = c["mainsnak"]
            if mainsnak.get("snaktype") != "value":
                continue
            dt = mainsnak["datatype"]
            val = mainsnak["datavalue"]["value"]
            if dt == "wikibase-item":
                out.append(label_for(val["id"], lang))
            elif dt == "time":
                out.append(human_date(val["time"]))
            elif dt in {"string", "external-id", "url"}:
                out.append(val)
            elif dt == "quantity":
                amount = val["amount"].lstrip("+")
                if val.get("unit") and val["unit"] != "http://www.wikidata.org/entity/Q199":
                    unit_qid = val["unit"].split("/")[-1]
                    amount += " " + label_for(unit_qid, lang)
                out.append(amount)
            else:
                out.append(str(val))
        except Exception:
            continue
    # уникальные + без пустых
    return list(dict.fromkeys(filter(None, out)))

def human_date(ts: str) -> str:
    """+1835-12-31T00:00:00Z -> 31 декабря 1835 года"""
    if not ts.startswith("+"):
        return ts
    try:
        d = datetime.strptime(ts[1:11], "%Y-%m-%d")
        months = ["января", "февраля", "марта", "апреля", "мая", "июня",
                  "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        return f"{d.day} {months[d.month-1]} {d.year} года"
    except Exception:
        return ts[1:11]

# ---------- высокоуровневые вызовы из Flask ----------
def find_and_describe(query: str, lang: str = "ru"):
    """Главная точка входа: ищем, возвращаем список {'label','descr','text','url'}"""
    hits = search_entities(query, lang)
    if not hits:
        return []
    results = []
    for h in hits:
        results.append({"label": h["label"],
                        "descr": h["descr"],
                        "text": free_text_description(h["qid"], lang),
                        "url": WIKIDATA_ITEM.format(qid=h["qid"])})
    return results