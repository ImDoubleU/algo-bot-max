"""Build the bundled word-game dictionary; no online dictionary is needed during play.

Developer dependency: pymorphy3==2.0.6. Source noun list is pinned and hash-checked.
Run: python -m app.cli.build_arcade_words
"""

import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
REVISION = "6f0ae9f0619cf0401c6935b7cbba1165bf4c7f19"
SOURCE = f"https://raw.githubusercontent.com/Harrix/Russian-Nouns/{REVISION}/dist/russian_nouns.txt"
SHA256 = "661949699919aa968dd0033f7bdd8abbe4db09d161b565f3f0181283fd0d0da7"
ROOTS = [
    "КОСМОНАВТИКА",
    "ЭЛЕКТРОСТАНЦИЯ",
    "ПРОГРАММИРОВАНИЕ",
    "ПУТЕШЕСТВЕННИК",
    "МАТЕМАТИКА",
    "КОНСТРУКТОР",
    "ПРОСТОКВАШИНО",
    "ВЕЛОСИПЕДИСТ",
    "АВТОМОБИЛИСТ",
    "АВИАМОДЕЛИРОВАНИЕ",
    "АЭРОДИНАМИКА",
    "АРХЕОЛОГИЯ",
    "АСТРОНОМИЯ",
    "АСТРОНАВТИКА",
    "БИОЛОГИЯ",
    "БИБЛИОТЕКА",
    "БИБЛИОТЕКАРЬ",
    "ВЕЛОСИПЕДИСТКА",
    "ВЕРТОЛЕТОСТРОЕНИЕ",
    "ВОДОПРОВОДЧИК",
    "ВОЗДУХОПЛАВАНИЕ",
    "ВОСПИТАТЕЛЬ",
    "ГЕОМЕТРИЯ",
    "ГРАВИТАЦИЯ",
    "ГРАМОТНОСТЬ",
    "ГИДРОЭЛЕКТРОСТАНЦИЯ",
    "ДОСТОПРИМЕЧАТЕЛЬНОСТЬ",
    "ЕСТЕСТВОЗНАНИЕ",
    "ЖЕЛЕЗНОДОРОЖНИК",
    "ЖУРНАЛИСТИКА",
    "ЗАКОНОМЕРНОСТЬ",
    "ЗЕМЛЕПОЛЬЗОВАНИЕ",
    "ЗЕМЛЯНИКА",
    "ЗНАКОМСТВО",
    "ЗООГЕОГРАФИЯ",
    "ИЗОБРЕТАТЕЛЬ",
    "ИЛЛЮСТРАЦИЯ",
    "ИНФОРМАТИКА",
    "ИНФРАСТРУКТУРА",
    "ИССЛЕДОВАТЕЛЬ",
    "КАЛЕЙДОСКОП",
    "КАРТОФЕЛИНА",
    "КИНЕМАТОГРАФИЯ",
    "КЛАВИАТУРА",
    "КЛАССИФИКАЦИЯ",
    "КОЛЛЕКЦИОНЕР",
    "КОМБИНАТОРИКА",
    "КОММУНИКАЦИЯ",
    "КОМПЛЕКТАЦИЯ",
    "КОМПЬЮТЕРИЗАЦИЯ",
    "КОНДИТЕРСКАЯ",
    "КОНСТРУИРОВАНИЕ",
    "КООРДИНАТА",
    "КОРАБЛЕСТРОЕНИЕ",
    "КОРРЕСПОНДЕНЦИЯ",
    "КОСМОДРОМ",
    "КРИСТАЛЛИЗАЦИЯ",
    "КУЛИНАРИЯ",
    "ЛАБОРАТОРИЯ",
    "ЛАНДШАФТОВЕДЕНИЕ",
    "ЛЕГОКОНСТРУИРОВАНИЕ",
    "ЛЕСОЗАГОТОВКА",
    "ЛИТЕРАТУРА",
    "МАГНИТОФОН",
    "МАСТЕРСКАЯ",
    "МЕЖПЛАНЕТНОСТЬ",
    "МЕТАЛЛООБРАБОТКА",
    "МЕТЕОРОЛОГИЯ",
    "МИКРОБИОЛОГИЯ",
    "МИКРОПРОЦЕССОР",
    "МИРОВОЗЗРЕНИЕ",
    "МОДЕЛИРОВАНИЕ",
    "МУЛЬТИПЛИКАЦИЯ",
    "НАБЛЮДАТЕЛЬНОСТЬ",
    "НАТУРАЛИСТ",
    "НЕБОСКРЕБ",
    "НЕВЕСОМОСТЬ",
    "НЕФТЕПЕРЕРАБОТКА",
    "ОБОРУДОВАНИЕ",
    "ОБРАЗОВАНИЕ",
    "ОБСЕРВАТОРИЯ",
    "ОКЕАНОГРАФИЯ",
    "ОЛИМПИАДА",
    "ОРГАНИЗАЦИЯ",
    "ОРНИТОЛОГИЯ",
    "ПАЛЕОНТОЛОГИЯ",
    "ПАРАШЮТИСТ",
    "ПАРИКМАХЕРСКАЯ",
    "ПАССАЖИРОПЕРЕВОЗКА",
    "ПЕРВОКЛАССНИК",
    "ПЕРЕПРОГРАММИРОВАНИЕ",
    "ПЛАНЕТАРИЙ",
    "ПОДВОДНИК",
    "ПОЗНАВАТЕЛЬНОСТЬ",
    "ПОЛИКЛИНИКА",
    "ПОЛИМЕРИЗАЦИЯ",
    "ПОСЛЕДОВАТЕЛЬНОСТЬ",
    "ПРИКЛЮЧЕНИЕ",
    "ПРИРОДОВЕДЕНИЕ",
    "ПРОИЗВОДИТЕЛЬНОСТЬ",
    "ПРОФЕССИОНАЛИЗМ",
    "ПУТЕВОДИТЕЛЬ",
    "РАДИОКОНСТРУКТОР",
    "РАДИОПЕРЕДАТЧИК",
    "РАДИОСТАНЦИЯ",
    "РАЗНООБРАЗИЕ",
    "РАСПРЕДЕЛЕНИЕ",
    "РАСТЕНИЕВОДСТВО",
    "РЕГИСТРАЦИЯ",
    "РЕКОНСТРУКЦИЯ",
    "РЕПРОДУКЦИЯ",
    "РЕСТАВРАЦИЯ",
    "РОБОТОТЕХНИКА",
    "САМОЛЕТОСТРОЕНИЕ",
    "САНАТОРИЙ",
    "СВЕРХПРОВОДИМОСТЬ",
    "СВЕТОПРЕДСТАВЛЕНИЕ",
    "СЕБЕСТОИМОСТЬ",
    "СЕЛЕКЦИОНИРОВАНИЕ",
    "СЕРТИФИКАЦИЯ",
    "СИНХРОНИЗАЦИЯ",
    "СИСТЕМАТИЗАЦИЯ",
    "СКАЗОЧНИК",
    "СКВОЗНЯК",
    "СНОУБОРДИСТ",
    "СОВЕРШЕНСТВОВАНИЕ",
    "СОПРОТИВЛЕНИЕ",
    "СОРЕВНОВАНИЕ",
    "СПЕЛЕОЛОГИЯ",
    "СТИХОТВОРЕНИЕ",
    "СТРОИТЕЛЬСТВО",
    "СУДОСТРОЕНИЕ",
    "ТЕЛЕВИДЕНИЕ",
    "ТЕЛЕКОММУНИКАЦИЯ",
    "ТЕЛЕПЕРЕДАЧА",
    "ТЕРРАФОРМИРОВАНИЕ",
    "ТЕРМОДИНАМИКА",
    "ТЕХНОЛОГИЯ",
    "ТРАНСПОРТИРОВКА",
    "ТРАНСФОРМАТОР",
    "ТРЕУГОЛЬНИК",
    "УДОСТОВЕРЕНИЕ",
    "УНИВЕРСИТЕТ",
    "УПОРЯДОЧЕННОСТЬ",
    "УСОВЕРШЕНСТВОВАНИЕ",
    "ФАНТАСТИКА",
    "ФАРМАКОЛОГИЯ",
    "ФИЗКУЛЬТУРА",
    "ФИЛАТЕЛИСТ",
    "ФОТОГРАФИЯ",
    "ФОТОКОРРЕСПОНДЕНТ",
    "ФОТОЛАБОРАТОРИЯ",
    "ХОЛОДИЛЬНИК",
    "ХОРЕОГРАФИЯ",
    "ХРОНОМЕТРАЖ",
    "ЦЕНТРИФУГА",
    "ЦИВИЛИЗАЦИЯ",
    "ПЕРЕКРЕСТОК",
    "ШАХМАТИСТ",
    "ЭКСКАВАТОР",
    "ЭКСПЕРИМЕНТ",
    "ЭЛЕКТРОДВИГАТЕЛЬ",
    "ЭНЦИКЛОПЕДИЯ",
    "ЭНЕРГОСБЕРЕЖЕНИЕ",
    "ЭНТУЗИАЗМ",
]


def build():
    tools = ROOT / ".deploy_tmp/word-dictionary-tools"
    if tools.is_dir():
        sys.path.insert(0, str(tools))
    import pymorphy3

    raw = urlopen(SOURCE, timeout=30).read()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError("The pinned dictionary checksum does not match")
    morph = pymorphy3.MorphAnalyzer()
    banks = {root: Counter(root.lower()) for root in ROOTS}
    result = {root: set() for root in ROOTS}
    excluded = {"Name", "Surn", "Patr", "Geox", "Orgn", "Trad", "Abbr", "Obsc", "Vulg", "Erro"}
    for source_word in raw.decode("utf-8-sig").splitlines():
        word = unicodedata.normalize("NFC", source_word.strip().lower()).replace("ё", "е")
        if not re.fullmatch("[а-я]{3,16}", word):
            continue
        matches = [
            root
            for root, bank in banks.items()
            if len(word) < len(root) and not Counter(word) - bank
        ]
        if not matches:
            continue
        parses = morph.parse(word)
        if not any(
            p.is_known
            and p.tag.POS == "NOUN"
            and "nomn" in p.tag
            and not p.tag.grammemes.intersection(excluded)
            and p.normal_form.replace("ё", "е") == word
            for p in parses
        ):
            continue
        for root in matches:
            result[root].add(word)
    license_text = (
        urlopen(
            f"https://raw.githubusercontent.com/Harrix/Russian-Nouns/{REVISION}/LICENSE.md",
            timeout=30,
        )
        .read()
        .decode("utf-8")
    )
    credit = (
        "Bundled noun subsets for Algo Arcade, version 2.\n"
        f"Source: {SOURCE}\nSHA256: {SHA256}\n"
        "Changes: NFC, е/ё normalization, noun and letter-bank filtering.\n"
        "Morphological validation: pymorphy3 / OpenCorpora dictionaries,\n"
        "https://opencorpora.org/ — CC BY-SA 3.0, https://creativecommons.org/licenses/by-sa/3.0/\n"
        "This derived dictionary data is distributed under CC BY-SA 3.0.\n\n" + license_text
    )
    result = {
        root: words
        for index, (root, words) in enumerate(result.items())
        if index < 8 or len(words) >= 40 and sum(len(w) >= 4 for w in words) >= 12
    }
    packed = {root: " ".join(sorted(words)) for root, words in result.items()}
    output = ROOT / "app/web/static/miniapp/games-words-data.js"
    output.write_text(
        "/* "
        + credit.replace("*/", "* /")
        + "\n*/\n"
        + "window.ArcadeWordDictionary=Object.freeze({version:2,byRoot:"
        + json.dumps(packed, ensure_ascii=False, separators=(",", ":"))
        + "});\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "roots": {k: len(v) for k, v in result.items()},
                "unique": len(set().union(*result.values())),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    build()
