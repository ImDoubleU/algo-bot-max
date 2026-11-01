# ruff: noqa: E501
"""Supplied email screenshot and safe reconstructions of other external UI."""

import base64
from pathlib import Path

PARENT_MAIL_SOURCE = Path(__file__).parent / "assets/parent-invitation.png"


def parent_mail_html(name):
    image = "data:image/png;base64," + base64.b64encode(PARENT_MAIL_SOURCE.read_bytes()).decode()
    if name == "parentmailoverview":
        content = (
            f'<img src="{image}" style="position:absolute;left:0;top:0;width:1060px;height:1088px">'
            '<span id="subject" style="left:247px;top:44px;width:260px;height:22px"></span>'
        )
    else:
        content = (
            '<div style="position:absolute;left:0;top:120px;width:1060px;height:250px;overflow:hidden">'
            f'<img src="{image}" style="position:absolute;left:-570px;top:-1220px;width:2494px;height:2560px">'
            '<span id="invite" aria-label="ссылке" style="left:172px;top:154px;width:72px;height:26px"></span>'
            "</div>"
        )
    return (
        '<!doctype html><html lang="ru"><meta charset="utf-8"><style>'
        "body{margin:0;background:#181b1b;width:1060px;height:740px;overflow:hidden}"
        "span{position:absolute;display:block}img{display:block}</style>"
        f'<body data-source-screenshot="parent-invitation.png">{content}</body></html>'
    )


MAIL = """<section><h2 id="subject">Школа Алгоритмика! Важно!</h2><p class="muted">От: куратор школы · Кому: parent@example.invalid</p><hr><p>Зарегистрируйте себя и нашего студента в программе начисления астрокоинов.</p><p>Регистрация по <span id="invite" style="color:#2356b3;text-decoration:underline">ссылке</span></p><p class="muted">Учебная ссылка отключена. Настоящее приглашение получает только родитель.</p></section>"""
BOT_HEAD = '<div class="toolbar"><strong id="chat">Algo MAX · школьный бот</strong><button id="close">Закрыть приложение</button></div>'


def bot(message, extra="", start=False):
    return (
        BOT_HEAD
        + f'<section class="chat"><div class="bubble" id="message">{message}</div>{extra}</section><div class="bottom"><button id="{"start" if start else "open"}" class="primary">{"Начать" if start else "Открыть"}</button><span class="muted">Сообщение</span></div>'
    )


MOCKS = {
    "parentmailoverview": "",
    "parentmaillink": "",
    "mail": MAIL,
    "inbox": '<div class="toolbar"><button id="refresh">Обновить почту</button></div><div class="split"><nav class="side"><strong>Входящие</strong><button id="spam">Спам</button><button>Рассылки</button></nav><section><h2>Почта родителя</h2><label><span>Адрес, указанный школе</span><input id="email" value="parent@example.invalid"></label><hr><strong>Школа Алгоритмика! Важно!</strong><p>Приглашение в семейный кабинет</p></section></div>',
    "bot": bot("Здравствуйте! Кабинет подключён. Используйте кнопку «Открыть» внизу чата."),
    "start": bot(
        "Вы открыли приглашение школы. Нажмите «Начать», если бот ещё не запускался.", start=True
    ),
    "connected": bot(
        '<strong class="ok">Подключение успешно</strong><p>Найдено учеников: 3. Семейный кабинет готов.</p>'
    ),
    "pending": bot(
        "Мы сохранили вашу попытку. Ребёнка пока не добавили в систему. После загрузки данных школой мы сообщим об открытии доступа."
    ),
    "invalid": bot(
        '<strong class="error">Ссылка недействительна</strong><p>Не исправляйте символы приглашения. Передайте текст ответа куратору.</p>'
    ),
    "waiting": bot(
        "Родителю нужно подтвердить связь. Личный кабинет откроется после его подключения.",
        '<button id="check" class="primary">Проверить доступ</button>',
    ),
    "account": '<section><h2>Проверьте аккаунт до открытия приглашения</h2><p class="muted">Памятка, не экран MAX. Выбирать роль в школьном боте не требуется: приглашение определяет её автоматически.</p><article id="parent"><h2>Родитель</h2><p>Открывает персональную ссылку из письма школы в своём MAX-аккаунте.</p></article><hr><article id="student"><h2>Ученик</h2><p>Открывает личный QR-код или ссылку ученика в отдельном MAX-аккаунте ребёнка.</p></article></section>',
    "privatechat": '<div class="toolbar"><strong>Личный чат · нужный получатель</strong></div><section><div class="bubble" id="attachment"><strong>Учебное приглашение</strong><p>https://example.invalid/DEMO</p><p class="muted">В примере нет рабочего адреса и QR-кода.</p></div><textarea id="compose">Откройте ваше личное приглашение со своего MAX-аккаунта.</textarea><p><button class="primary">Отправить лично</button></p></section>',
    "settings": '<section><h2>Настройки телефона и MAX</h2><label id="brightness">Яркость экрана<input type="range" value="85"></label><label id="network">Мобильные данные<input type="checkbox" checked style="width:auto"> Включены · Wi-Fi и VPN выключены</label><label id="blocked">Школьный бот<input type="checkbox" style="width:auto"> Блокировка выключена</label><p><button id="restart">Закрыть и заново открыть MAX</button></p></section>',
    "spreadsheet": '<div class="toolbar"><strong>Учебная таблица · Шаблон.xlsx</strong><button id="format">Формат → Числа → Обычный текст</button></div><section><table><tr><th id="ids">ID ученика / сделки / контакта</th><th>ФИО</th><th id="city">Город</th><th id="photo">photo_url</th></tr><tr><td class="selected">001841 / 0081 / 00681</td><td>Васильева Алиса</td><td>Нижний Новгород</td><td>example.invalid/photo.png</td></tr><tr><td class="selected">002417 / 0082 / 00681</td><td>Петров Иван</td><td>Нижний Новгород</td><td>example.invalid/photo.png</td></tr></table><p class="muted">ID сохраняются как текст, без .0 и округления.</p><button id="cleanup">Удалить лишние листы, фото и пустые строки</button></section><div class="tabs"><button id="sheet">Шаблон</button><button>Сделки</button><button>Скачать XLSX</button></div>',
    "sheet": '<div class="toolbar"><strong>Подключения.xlsx · снимок на момент экспорта</strong></div><section><table id="pupils"><tr><th>LMS ID</th><th>Ученик</th><th>Родитель подключён ▾</th><th>Ученик подключён ▾</th></tr><tr><td>1841</td><td>Васильева Алиса</td><td>☑ ИСТИНА</td><td>☑ ИСТИНА</td></tr><tr><td>2417</td><td>Петров Иван</td><td>☑ ИСТИНА</td><td>☐ ЛОЖЬ</td></tr></table><h2 style="margin-top:22px" id="summary">Сводка · По группам</h2><table><tr><th>Группа</th><th>Всего</th><th>Подключено учеников</th></tr><tr><td>Учебная группа</td><td>2</td><td>1</td></tr></table></section><div class="tabs"><button>Ученики</button><button>Сводка</button></div>',
    "linkedit": '<section><h2>Шаблон приглашения родителя</h2><p>Не меняйте город и остальные символы шаблона.</p><label><span>ID контакта родителя из CRM, не MAX ID</span><input id="contact" value="00681"></label><textarea>https://example.invalid/DEMO~&lt;ID_родителя&gt;</textarea><p class="muted">Адрес отключён; используйте личное приглашение вашей школы.</p></section>',
    "privacy": '<div class="toolbar" id="private">Приватное окно браузера</div><section><h2>Проверка доступа к фото</h2><p>Файл должен открываться без авторизации и запроса доступа.</p><input value="https://example.invalid/photo.png"><p><button>Открыть без входа</button></p></section>',
    "photopreview": '<section><h2>Фото товара · просмотр без входа</h2><div class="photo" id="image">▱</div><p class="ok">Изображение открылось без авторизации</p></section>',
    "sharing": '<section><h2 id="file">Один файл: photo.png</h2><p>Не ссылка на папку</p><label id="public">Доступ по ссылке<select><option>Все, у кого есть ссылка · Просмотр</option></select></label><button>Скопировать публичную ссылку</button></section>',
    "downloads": '<section><h2>Загрузки браузера / MAX</h2><div class="bubble" id="file"><strong>Подключения.xlsx</strong><p class="ok">Загрузка завершена</p><button>Открыть файл</button></div></section>',
    "botsupport": bot(
        "Кто сообщает о проблеме?",
        '<div id="role" class="toolbar"><button>Я родитель</button><button>Я ученик</button><button>Я сотрудник</button></div><div class="bubble" id="name">Иван Петров</div><textarea id="compose">Время: 12:30 МСК. Город: учебный. Не вижу кнопку после закрытия клавиатуры и прокрутки.</textarea><p><button id="attachment">Прикрепить полный скриншот</button></p><button id="send" class="primary">Отправить заявку</button>',
    ),
    "ticketreply": bot(
        '<strong id="ticket">Поддержка · обращение №123</strong><p>Пожалуйста, уточните, на каком шаге возникла ошибка.</p>',
        '<button id="reply">Ответить по обращению №123</button><p id="number">Ждём ваше сообщение по обращению №123</p><textarea id="compose">Уточнение: после прокрутки панель отсутствует.</textarea><p><button id="send" class="primary">Отправить уточнение и фото</button></p>',
    ),
}
MOCKS["ticketchoice"] = bot(
    "К какому обращению относится ваше сообщение?",
    '<button id="number">Обращение №123 · Не видна кнопка</button><p class="muted">Сообщение сохранено: не отправляйте его повторно.</p>',
)
MOCKS.update(
    {
        "botsupportcity": bot(
            "Напишите ваш город. Например: Нижний Новгород.",
            '<div class="bubble" id="city">Нижний Новгород</div>',
        ),
        "botsupportchild": bot(
            "Напишите имя и фамилию ребёнка одним сообщением. Например: Иван Петров.",
            '<div class="bubble" id="child">Васильева Алиса</div><p class="muted">Этот шаг нужен родителю; ученик и сотрудник переходят к описанию проблемы.</p>',
        ),
        "studentconnected": bot(
            '<strong class="ok">Профиль ученика привязан</strong><p>Васильева Алиса. Родитель подключён. Можно открыть личный кабинет.</p>'
        ),
        "botsupportsent": bot(
            '<strong class="ok">Заявка №123 отправлена</strong><p>Учебное подтверждение. Ответ придёт в этот же чат.</p>'
        ),
        "schoolchat": '<div class="toolbar"><strong>Личный чат с куратором школы</strong></div><section><textarea id="compose">Здравствуйте! Город: Нижний Новгород. Ребёнок: Васильева Алиса. Подскажите, загружены ли данные и верно ли записан контакт родителя? Время попытки: 12:30 МСК.</textarea><p><button class="primary">Отправить лично куратору</button></p><p class="muted">Не прикладывайте персональную ссылку, QR-код или код товара.</p></section>',
        "schoolreply": bot(
            '<strong class="ok">Данные проверены школой</strong><p>Откройте своё актуальное приглашение. Дождитесь успешного ответа, затем откройте кабинет.</p>'
        ),
        "photoedit": '<section><h2>Уменьшенная копия снимка ошибки</h2><div class="photo">JPEG</div><label id="resize">Размер изображения<select><option>1280 px · сохранить читаемость</option></select></label><p>Личные ссылки и QR-коды закрыты.</p><button class="primary">Сохранить копию</button></section>',
        "ticketadded": bot(
            '<strong class="ok">Сообщение добавлено к обращению №123</strong><p>Номер обращения сохранён. Повторно отправлять то же уточнение не нужно.</p>'
        ),
    }
)


def html(name):
    if name in {"parentmailoverview", "parentmaillink"}:
        return parent_mail_html(name)
    template = (Path(__file__).parent / "templates/external.html").read_text(encoding="utf-8")
    return template.replace(
        '<main id="content"></main>', '<main id="content">' + MOCKS[name] + "</main>"
    )
