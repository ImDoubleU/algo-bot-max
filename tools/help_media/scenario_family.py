"""Explicit family-safe shots for the frozen FAQ steps.

Each tuple is editorially ordered, not padded from a generic screen. Repeated
form controls occur only when consecutive steps edit or check that same form.
Missing scenes and selectors must fail capture, never fall back to a whole page.
"""

FAMILY_SHOTS = {
    "Как открыть приложение?": (
        "bot@#chat",
        "bot@#open",
        "home@#profileTitle",
    ),
    "Что проверить после первого входа?": (
        "home@#profileTitle",
        'city@[data-tenant-switch="demo-one"]',
        'home@[data-active-student="demo-alisa"]',
        "home@#openWalletButton",
    ),
    "Как открыть нужный раздел на компьютере?": (
        'home@[data-view="dashboard"]',
        'store@[data-view="store"]',
        "store@#railCollapseButton",
    ),
    "Как открыть нужный раздел на телефоне?": (
        'mobile@[data-view="store"]',
        "mobile@#mobileMoreButton",
        'more@[data-view="bank"]',
    ),
    "Как закрыть окно и вернуться к разделу?": (
        "bankconfirm@#confirmBankActionButton",
        "bankconfirm@#closeBankConfirmationButton",
        "bankopened@.bank-history-entry",
    ),
    "Когда нажимать «Обновить»?": (
        "home@#refreshDataButton",
        'familyorders@[data-open-order="demo-order-1357"]',
        'support@[name="message"]',
    ),
    "Как переключить город?": (
        "city@#tenantSwitcherButton",
        'city@[data-tenant-switch="demo-two"]',
        "cityselected@#statusTenantTitle",
    ),
    "Как быстро найти ответ в справке?": (
        'home@[data-view="help"]',
        "help@#helpSearchInput",
        'helpsearch@[data-help-category="access"]',
        "helpsearch@.help-faq-question",
    ),
    "Как родителю подключить ребёнка?": (
        "parentmailoverview@#subject",
        "parentmaillink@#invite",
        "account@#parent",
        "start@#start",
        "connected@#message",
        "connected@#open",
        'home@[data-active-student="demo-alisa"]',
    ),
    "Что делать, если письмо со ссылкой не пришло?": (
        "inbox@#spam",
        "inbox@#email",
        "inbox@#refresh",
        'support@[name="message"]',
    ),
    "Почему ученик видит «Родителю нужно подтвердить связь»?": (
        "mail@#invite",
        "start@#start",
        "waiting@#check",
        "studentconnected@#open",
    ),
    "Как родителю переключаться между детьми?": (
        'home@[data-active-student="demo-ivan"]',
        'home@[data-active-student="demo-alisa"]',
        "home@#dashboardSpotlightTitle",
    ),
    "Почему в семейном кабинете виден только один ребёнок?": (
        "account@#parent",
        "mail@#invite",
        'home@[data-active-student="demo-alisa"]',
    ),
    "Где родителю найти QR-код ребёнка?": (
        'home@[data-view="dashboard"]',
        "home@QR-коды детей",
        'home@[data-open-student-qr="demo-alisa"]',
        "qr@[data-copy-student-link]",
        "privatechat@#attachment",
    ),
    "Может ли ученик войти до подключения родителя?": (
        "connected@#message",
        "waiting@#check",
    ),
    "Родитель вошёл в бот, но ребёнка в кабинете нет. Почему?": (
        "mail@#invite",
        "connected@#open",
        "pending@#message",
    ),
    "Родитель подключился после первой попытки ученика. Что делать ученику?": (
        "connected@#message",
        "waiting@#check",
        "pending@#message",
        "child@#profileTitle",
    ),
    "Можно ли отправить ссылку или снимок QR-кода?": (
        'home@[data-open-student-qr="demo-alisa"]',
        "qr@[data-copy-student-link]",
        "privatechat@#attachment",
        "studentconnected@#open",
    ),
    "Что делать, если камера не распознаёт QR-код?": (
        'home@[data-open-student-qr="demo-alisa"]',
        "settings@#brightness",
        'home@[data-copy-student-link="demo-alisa"]',
        "studentconnected@#open",
    ),
    "Почему статус подключения не изменился?": (
        "account@#parent",
        "connected@#message",
        "home@#refreshDataButton",
    ),
    "Что делать, если старая ссылка или QR-код не работают?": (
        "invalid@#message",
        "mail@#invite",
        "account@#student",
        "waiting@#check",
        "child@#profileTitle",
    ),
    "Что делать, если подключили не того ученика?": (
        'supportrole@[data-support-role="parent"]',
        'support@[name="message"]',
        "schoolreply@#message",
        "account@#parent",
        "connected@#open",
    ),
    "Что произойдёт после отзыва родительской связи?": (
        "schoolchat@#compose",
        "mail@#invite",
        "studentconnected@#message",
        "waiting@#check",
    ),
    "Что означает «Ребёнка пока не добавили в систему»?": (
        "pending@#message",
        "schoolchat@#compose",
        "connected@#open",
    ),
    "Что делать, если по ссылке подключился чужой ребёнок?": (
        "home@#dashboardSpotlightTitle",
        'support@[name="message"]',
        "account@#parent",
        "connected@#open",
    ),
    "Что делать, если MAX-аккаунт уже подключён?": (
        "bot@#open",
        "home@#dashboardSpotlightTitle",
        'support@[name="message"]',
    ),
    "Что произойдёт, если остановить бота в MAX?": (
        "start@#start",
        "mail@#invite",
        "studentconnected@#message",
        "waiting@#check",
    ),
    "Где посмотреть доступный баланс?": (
        "home@#openWalletButton",
        'home@[data-view="wallet"]',
        'home@[data-active-student="demo-alisa"]',
    ),
    "Где посмотреть, за что начислили или списали AC?": (
        'home@[data-view="wallet"]',
        'wallet@[data-active-student="demo-alisa"]',
        "wallet@.ledger-entry",
    ),
    "Что делать, если баланс кажется неправильным?": (
        "home@#refreshDataButton",
        "wallet@.ledger-entry",
        "bank@.bank-history-entry",
        "familyorders@#orderSearch",
        'support@[name="message"]',
    ),
    "Как найти нужный товар?": (
        'store@[data-view="store"]',
        "store@#productSearch",
        "filters@#mobileStoreFiltersButton",
        "store@#productSortMenu > summary",
        "store@#inStockOnly",
    ),
    "Как сохранить товар в избранное?": (
        'store@[data-view="store"]',
        'store@[data-favorite="demo-game"]',
        "store@#favoritesFilter",
    ),
    "Почему товар не находится в магазине?": (
        "store@#productSearch",
        'filters@[data-product-category="all"]',
        "store@#inStockOnly",
        'support@[name="message"]',
    ),
    "Как добавить товар в корзину?": (
        'store@[data-product-details="demo-pen"]',
        'store@[data-add="demo-pen"]',
        "storecart@#storeCartBar",
        "cart@[data-cart-quantity]",
    ),
    "Что делать, если не хватает AC?": (
        "cart@#cartTotal",
        'cart@[data-cart-step="-1"]',
        "child@#openWalletButton",
    ),
    "Как оформить заказ?": (
        'cart@[data-view="cart"]',
        "cart@[data-cart-quantity]",
        "cart@#placeOrderButton",
        "checkout@#confirmOrderButton",
        "familyorder@.order-dialog-summary",
    ),
    "Где найти код цифрового товара?": (
        'familyorders@[data-view="orders"]',
        'familyorders@[data-order-status="electronic"]',
        "code@#orderDialogTitle",
        "code@[data-copy-code]",
    ),
    "Где посмотреть заказ и его статус?": (
        'familyorders@[data-view="orders"]',
        'familyorders@[data-order-status="all"]',
        "familyorders@#orderSearch",
        "familyorder@.order-dialog-summary",
    ),
    "После оформления появилась ошибка. Повторять заказ?": (
        'familyorders@[data-view="orders"]',
        "familyorders@#refreshDataButton",
        'familyorders@[data-open-order="demo-order-1357"]',
        "cart@#placeOrderButton",
    ),
    "Почему заказ не виден в списке?": (
        'home@[data-active-student="demo-alisa"]',
        'familyorders@[data-order-status="all"]',
        "familyorders@#orderSearch",
        "wallet@.ledger-entry",
    ),
    "Почему не загружается фотография товара?": (
        "store@#refreshDataButton",
        'store@[data-product-details="demo-pen"]',
        "supportsent@#supportFormStatus",
    ),
    "Как открыть вклад?": (
        'banknew@[data-view="bank"]',
        'banknew@#bankOpenForm [name="amount"]',
        'banknew@#bankOpenForm [type="submit"]',
        "bankconfirm@#confirmBankActionButton",
        "bankopened@.bank-history-entry",
    ),
    "Как пополнить действующий вклад?": (
        "bank@.bank-deposit-details",
        'bank@#bankTopUpForm [name="amount"]',
        'bank@#bankTopUpForm [type="submit"]',
        "banktopped@.bank-history-entry",
    ),
    "Что будет при досрочном закрытии?": (
        'bank@[data-view="bank"]',
        "bank@[data-bank-early-close]",
        "bankclose@#bankConfirmationDescription",
        "bankclose@#confirmBankActionButton",
        "bankclosed@.bank-history-entry",
    ),
    "Где посмотреть историю вклада?": (
        'home@[data-active-student="demo-alisa"]',
        "bank@История вклада",
        "bank@.bank-history-entry",
    ),
    "Как отправить заявку из мини-приложения?": (
        'supportrole@[data-support-role="parent"]',
        'support@[name="message"]',
        "support@.support-file-label",
        "supportsent@#supportFormStatus",
    ),
    "Как сообщить о проблеме через бота?": (
        "botsupport@#role",
        "botsupport@#name",
        "botsupportcity@#city",
        "botsupportchild@#child",
        "botsupport@#compose",
        "botsupport@#attachment",
        "botsupportsent@#message",
    ),
    "Можно ли написать в поддержку без привязанного ученика?": (
        "accessgate@[data-support-open]",
        'support@[name="message"]',
        "supportphoto@.support-photo",
        "supportsent@#supportFormStatus",
    ),
    "Почему видны данные другого города?": (
        'city@[data-tenant-switch="demo-one"]',
        'home@[data-active-student="demo-alisa"]',
        "cityselected@#statusTenantTitle",
    ),
    "Почему список пустой, хотя данные должны быть?": (
        "familyorders@#orderSearch",
        'familyorders@[data-order-status="all"]',
        'city@[data-tenant-switch="demo-one"]',
        'home@[data-active-student="demo-alisa"]',
        "familyorders@#refreshDataButton",
    ),
    "Что делать, если раздел долго загружается?": (
        "loading@#noticeMessage",
        "loading@#refreshDataButton",
        "bot@#close",
        "bot@#open",
    ),
    "Почему в окне не видно кнопку сохранения?": (
        "keyboard@#keyboardHide",
        "bankconfirm@#confirmBankActionButton",
        "bankopened@.bank-history-entry",
        "bankconfirm@.bank-confirmation-dialog",
        'supportphoto@[name="message"]',
        "supportsent@#supportFormStatus",
    ),
    "Что делать, если операция завершилась сообщением о сбое?": (
        "failure@#noticeMessage",
        "familyorders@#refreshDataButton",
        "wallet@.ledger-entry",
        'support@[name="message"]',
    ),
    "Почему после выхода новой версии приложение выглядит по-старому?": (
        "bot@#close",
        "bot@#chat",
        "bot@#open",
        "settings@#restart",
    ),
    "Почему не пришло уведомление?": (
        "bot@#chat",
        "settings@#blocked",
        "home@#profileTitle",
        'support@[name="message"]',
    ),
    "Что приложить к сообщению об ошибке?": (
        'support@[name="message"]',
        'supportrole@[data-support-role="parent"]',
        "familyorder@#orderDialogTitle",
        'support@[name="message"]',
        "failure@#noticeMessage",
        "supportphoto@.support-photo",
        "supportsent@#supportFormStatus",
    ),
    "Что делать, если данные не принимаются?": (
        'support@[name="first_name"]',
        'banknew@#bankOpenForm [name="maturity_on"]',
        "support@.support-file-label",
        'support@[type="submit"]',
    ),
    "Что делать, если вход не подтверждён или нет доступа?": (
        "bot@#open",
        "account@#parent",
        "pending@#message",
        "waiting@#check",
    ),
    "Что означает сообщение «Не найдено»?": (
        'city@[data-tenant-switch="demo-one"]',
        "familyorders@#refreshDataButton",
        "familyorders@#orderSearch",
        "schoolchat@#compose",
    ),
    "Почему действие конфликтует с текущими данными?": (
        "failure@#noticeMessage",
        "familyorders@#refreshDataButton",
        "wallet@.ledger-entry",
        'support@[name="message"]',
    ),
    "Что делать, если файл слишком большой?": (
        "supportphoto@#supportPhotoCount",
        "photoedit@#resize",
        "supportphoto@[data-support-remove-photo]",
        "supportsent@#supportFormStatus",
    ),
    "Что делать, если сервис временно недоступен?": (
        "failure@#noticeMessage",
        "home@#refreshDataButton",
        "wallet@.ledger-entry",
        "botsupport@#send",
    ),
    "Почему заказ не удаётся оформить или обработать?": (
        "home@#profileTitle",
        "cart@#cartBalance",
        "familyorders@#orderSearch",
        "cart@[data-cart-quantity]",
    ),
    "Почему не выполняется операция по вкладу?": (
        "child@#profileTitle",
        'banknew@#bankOpenForm [name="amount"]',
        "bank@#refreshDataButton",
        'supportstudent@[name="message"]',
    ),
    "MAX пишет «Техническая заминка». Что проверить?": (
        "bot@#open",
        "settings@#network",
        'support@[name="message"]',
        "botsupport@#attachment",
    ),
    "Почему не пришло сообщение о появлении ребёнка?": (
        "pending@#message",
        "schoolchat@#compose",
        "connected@#open",
        'support@[type="submit"]',
    ),
    "Как ученику зарегистрироваться после родителя?": (
        "connected@#message",
        'home@[data-open-student-qr="demo-alisa"]',
        "account@#student",
        "studentconnected@#message",
        "child@#profileTitle",
    ),
    "Нажал ссылку, но вижу только кнопку «Начать». Это нормально?": (
        "account@#parent",
        "start@#start",
        "connected@#open",
        'support@[name="message"]',
    ),
    "Кнопка «Начать» не появилась. Что делать?": (
        "mail@#invite",
        "bot@#message",
        "connected@#open",
        "settings@#network",
    ),
    "Что делать с ошибкой «Аккаунт MAX уже подключён как родитель / ученик»?": (
        "account@#student",
        "account@#parent",
        'supportrole@[data-support-role="parent"]',
        "studentconnected@#open",
    ),
    "Сотрудник отправил электронный код. Куда он придёт?": (
        'familyorders@[data-order-status="electronic"]',
        "code@#orderDialogTitle",
        "code@[data-copy-code]",
    ),
    "Как дополнить обращение после ответа поддержки?": (
        "ticketreply@#ticket",
        "ticketreply@#reply",
        "ticketreply@#number",
        "ticketadded@#message",
    ),
    "Можно ли продолжить решённое обращение?": (
        "ticketreply@#reply",
        "ticketreply@#compose",
        "ticketreply@#send",
        "ticketadded@#message",
    ),
    "Почему бот спрашивает, к какому обращению относится сообщение?": (
        "ticketchoice@#message",
        "ticketchoice@#number",
        "ticketadded@#message",
    ),
    "Электронный заказ ждёт код, хотя AC уже списались. Это ошибка?": (
        "codewaiting@.order-dialog-summary",
        "schoolchat@#compose",
        'support@[name="message"]',
    ),
}


def family_definitions(items):
    """Return reviewed shots only for video FAQs explicitly allowed to families."""
    result = {}
    for item in items:
        if not item.get("video") or not {"parent", "student"}.intersection(
            item.get("audiences", ())
        ):
            continue
        question = item["question"]
        if question in result:
            raise ValueError("Duplicate family FAQ: " + question)
        if question not in FAMILY_SHOTS:
            raise ValueError("Missing editorial family scenario: " + question)
        shots = FAMILY_SHOTS[question]
        steps = item.get("steps", ())
        if len(shots) != len(steps):
            raise ValueError(
                f"{question}: {len(steps)} FAQ steps / {len(shots)} family shots; "
                "editorial review required"
            )
        if not item.get("outcome"):
            raise ValueError("Missing family outcome: " + question)
        result[question] = {"shots": list(shots), "outcome": item["outcome"]}
    return result
