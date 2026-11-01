# ruff: noqa: E501
"""Named, reproducible demo UI states. All mutations are browser-memory fixtures."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Screen:
    role: str = "admin"
    view: str = "admin"
    js: str = ""
    mobile: bool = False
    reconstructed: bool = False


def admin(tab, js="", **kwargs):
    return Screen(js=f"state.adminTab='{tab}';{js};renderAdminPanel();", **kwargs)


PRODUCT = "state.productEditorOpen=true;state.editingProductId='demo-mug';state.productPhotoSourceUrl='/miniapp/static/assets/dashboard-learning.png';state.productPhotoPreviewUrl='/miniapp/static/assets/dashboard-learning.png';"
DIGITAL = PRODUCT + "products.find(p=>p.id==='demo-mug').fulfillmentType='digital_manual';"
SCREENS = {
    "parentmailoverview": Screen("parent", "external"),
    "parentmaillink": Screen("parent", "external"),
    "home": Screen("parent", "dashboard"),
    "child": Screen("student", "dashboard"),
    "staffhome": Screen("teacher", "dashboard"),
    "qrlist": Screen(
        "teacher",
        "dashboard",
        "state.dashboardMode='qr';renderAll();await loadTeacherInvitations(true);",
    ),
    "qr": Screen("parent", "dashboard", "openStudentQrPreview('demo-alisa');"),
    "mobile": Screen("parent", "dashboard", mobile=True),
    "more": Screen("parent", "dashboard", "qs('#mobileMoreButton').click();", mobile=True),
    "refresh": Screen("parent", "dashboard"),
    "help": Screen("parent", "help"),
    "helpsearch": Screen("parent", "help", "helpFaqState.query='QR';renderHelpFaq();"),
    "city": Screen(
        "parent",
        "dashboard",
        "state.canManageTenants=true;state.availableTenants=[{tenant_slug:'demo-one',city_name:'Нижний Новгород',partner_name:'Учебный партнёр',tenant_name:'Демо'},{tenant_slug:'demo-two',city_name:'Бор',partner_name:'Учебный партнёр',tenant_name:'Демо'}];qs('#tenantSwitcherButton').hidden=false;openTenantDialog();",
        reconstructed=True,
    ),
    "admin": admin("summary"),
    "products": admin("products"),
    "product": admin("products", PRODUCT),
    "digital": admin("products", DIGITAL),
    "instant": admin(
        "products", DIGITAL + "products.find(p=>p.id==='demo-mug').fulfillmentType='digital_code';"
    ),
    "productimport": admin("products", "state.productImportFileName='demo-products.xlsx';"),
    "warehouses": admin("warehouses"),
    "warehouse": admin("warehouses", "state.warehouseEditorOpen=true;"),
    "contacts": admin("contacts", "state.expandedContactStudents=new Set(students.map(s=>s.id));"),
    "export": admin("contacts", "", reconstructed=False),
    "crm": admin("crm"),
    "preview": admin(
        "crm",
        "state.crmImportFileName='demo-pupils.xlsx';state.crmImportPreview={parsed_rows:3,distinct_groups:3,distinct_courses:2,distinct_teachers:2,rows_with_contacts:3,distinct_cities:1,city_distribution:[{city_name:'Нижний Новгород',tenant_name:'Учебный город',rows:3,rows_count:3,student_count:3}]};",
        reconstructed=True,
    ),
    "staff": admin("staff", role="partner_director"),
    "staffmenu": admin("staff", role="partner_director"),
    "invite": admin("staff", "state.staffInvitationOpen=true;", role="partner_director"),
    "invitelink": admin(
        "staff",
        "state.staffInvitationOpen=true;state.staffInvitationLink='https://example.invalid/DEMO-INVITE';",
        role="partner_director",
        reconstructed=True,
    ),
    "grant": admin("staff", "state.staffEditorOpen=true;", role="partner_director"),
    "staffname": admin(
        "staff",
        "state.staffProfileEditorAccountId=staffAssignments[0].accountId;state.staffProfileEditorFirstName='Иван';state.staffProfileEditorLastName='Петров';",
        role="partner_director",
    ),
    "staffrole": admin(
        "staff",
        "state.staffRoleEditorAccountId=staffAssignments[1].accountId;state.staffRoleEditorRole='curator';",
        role="partner_director",
    ),
    "notifications": Screen(
        "partner_director",
        "admin",
        "state.staffNotificationSettings={display_name:'Учебный администратор',roles:['admin'],max_user_id:100000001,items:[{event_key:'demo-order',category:'orders',category_label:'Заказы',label:'Новые заказы',description:'События заказов выбранного города',enabled:true},{event_key:'demo-support',category:'orders',category_label:'Заказы',label:'Проблема с заказом',description:'Сообщения о затруднениях',enabled:true}]};qs('#staffNotificationDialog').hidden=false;renderStaffNotificationSettings();",
        reconstructed=True,
    ),
    "registry": Screen("admin", "wallet"),
    "profile": Screen(
        "admin",
        "wallet",
        "state.studentProfileId='demo-alisa';state.studentProfileTab='overview';renderStudentRegistry();",
    ),
    "profiledata": Screen(
        "admin",
        "wallet",
        "state.studentProfileId='demo-alisa';state.studentProfileTab='data';renderStudentRegistry();",
    ),
    "profilefinance": Screen(
        "admin",
        "wallet",
        "state.studentProfileId='demo-alisa';state.studentProfileTab='finance';renderStudentRegistry();await loadStudentLedger('demo-alisa');await loadStudentBank('demo-alisa');",
    ),
    "teacherprofilefinance": Screen(
        "teacher",
        "wallet",
        "applyAdminStudentRegistry(demoAdminStudentRegistry());state.studentProfileId='demo-alisa';state.studentProfileTab='finance';renderStudentRegistry();await loadStudentLedger('demo-alisa');await loadStudentBank('demo-alisa');",
    ),
    "profilehistory": Screen(
        "admin",
        "wallet",
        "state.studentProfileId='demo-alisa';state.studentProfileTab='history';renderStudentRegistry();",
    ),
    "profileaccess": Screen(
        "admin",
        "wallet",
        "state.studentProfileId='demo-alisa';state.studentProfileTab='access';renderStudentRegistry();",
    ),
    "audit": admin("history"),
    "wallet": Screen("parent", "wallet"),
    "store": Screen("parent", "store"),
    "filters": Screen("parent", "store", "state.storeFiltersOpen=true;renderAll();", mobile=True),
    "cart": Screen("student", "cart", "addToCart('demo-pen');renderCart();"),
    "checkout": Screen(
        "student", "cart", "addToCart('demo-pen');renderCart();openCheckoutDialog();"
    ),
    "orders": Screen("admin", "orders", "state.staffRoles=['admin','teacher'];renderAll();"),
    "familyorders": Screen("parent", "orders"),
    "teacherorders": Screen("teacher", "orders"),
    "order": Screen("admin", "orders", "openOrderDetails('1357');"),
    "assign": Screen("admin", "orders", "openOrderDetails('1357');"),
    "assemble": Screen(
        "admin", "orders", "state.orderStatusFilter='fulfillment_collect';renderOrders();"
    ),
    "distribute": Screen(
        "admin", "orders", "state.orderStatusFilter='fulfillment_route';renderOrders();"
    ),
    "digitalorders": Screen(
        "admin",
        "orders",
        "orders[0].items[0].fulfillmentType='digital_manual';orders[0].rawStatus='created';state.orderStatusFilter='electronic';renderOrders();",
        reconstructed=True,
    ),
    "bank": Screen("student", "bank"),
    "banknew": Screen(
        "student",
        "bank",
        "state.activeStudentId='demo-mark';state.bankSummary=demoBankSummary('demo-mark');renderBankView();",
    ),
    "bankadmin": Screen("admin", "bank"),
    "accrual": Screen("teacher", "accrual"),
    "accrualselected": Screen(
        "teacher",
        "accrual",
        "state.accrualGroup=students[0].group;state.selectedAccrualStudents=new Set(['demo-alisa']);renderAccrual();qs('#groupAccrualReason').value='Проект';qs('#groupAccrualReason').dispatchEvent(new Event('change',{bubbles:true}));",
    ),
    "rules": Screen("admin", "accrual", "openAccrualRulesDialog();"),
    "report": Screen("admin", "report"),
    "broadcast": Screen("admin", "broadcasts"),
    "news": Screen(
        "admin",
        "broadcasts",
        "state.broadcastStep=2;renderBroadcasts();qs('#broadcastMessage').value='Учебная новость: встречаемся на занятии';renderBroadcastLivePreview();",
    ),
    "newscheck": Screen(
        "admin",
        "broadcasts",
        "qs('#broadcastTitle').value='Учебная новость';qs('#broadcastMessage').value='Приглашаем на занятие';state.broadcastStep=3;renderBroadcasts();await previewBroadcastAudience();",
        reconstructed=True,
    ),
    "venue": Screen("admin", "broadcasts", "openBroadcastVenueEditor();"),
    "teacherprofile": Screen(
        "teacher",
        "dashboard",
        "qs('#teacherProfileDialog').hidden=false;qs('#teacherProfileLastName').value='Петров';qs('#teacherProfileFirstName').value='Иван';qs('#saveTeacherProfileButton span').textContent='Сохранить и найти группы';",
        reconstructed=True,
    ),
    "supportrole": Screen("parent", "help", "supportOpenForm();"),
    "support": Screen(
        "parent",
        "help",
        "supportOpenForm();supportSetRole('parent');qs('#supportForm').elements.first_name.value='Иван';qs('#supportForm').elements.last_name.value='Петров';qs('#supportForm').elements.message.value='Учебный пример. Город: Нижний Новгород. Роль: родитель. Время: 12:30 МСК. Раздел: карточка. После прокрутки не видна кнопка. Ожидал сохранения, получил ошибку. Скриншот всего окна приложен.';",
    ),
    "supportsent": Screen(
        "parent",
        "help",
        "supportOpenForm();supportSetRole('parent');qs('#supportFormStatus').textContent='Учебный пример: заявка №123 отправлена.';",
        reconstructed=True,
    ),
}

DIGITAL_ORDER = "orders[0].items[0].fulfillmentType='digital_manual';orders[0].rawStatus='created';"
FEEDBACK = """feedbackState.contextKey=feedbackContextStorageKey();feedbackState.catalog={'Python Start':[{title:'Знакомство с Python',educational_results:'Создали первую программу и изучили команды'},{title:'Условия',educational_results:'Научились использовать условия'}]};feedbackState.loading=false;feedbackState.restored=true;feedbackState.course='Python Start';feedbackState.group=students[0].group;feedbackState.schedules[students[0].group]={course:'Python Start',mode:'group',rows:feedbackSeries('Python Start','2026-10-18',1,1,2,7,feedbackState.catalog)};feedbackSelectGroup(students[0].group);"""
TICKETS = """supportState.owner=true;supportState.loaded=true;supportState.total=35;supportState.items=[{id:123,first_name:'Иван',last_name:'Петров',role:'parent',message:'Учебный пример: не видна нижняя кнопка в окне',status:'new',private_note:'',created_at:'2026-10-24T09:30:00Z',replies:[],photo_ids:[],unread_count:0}];supportState.openTickets.add(123);qs('#supportInbox').hidden=false;qs('#helpFaqPanel').hidden=true;document.querySelectorAll('[data-support-tab]').forEach(e=>e.hidden=false);supportRenderInbox({new:1});"""
SCREENS.update(
    {
        "parentlinks": admin("contacts"),
        "customaccrual": Screen(
            "admin",
            "accrual",
            "state.accrualGroup=students[0].group;state.selectedAccrualStudents=new Set(['demo-alisa']);renderAccrual();qs('#groupAccrualReason').value='__custom__';qs('#groupAccrualReason').dispatchEvent(new Event('change',{bubbles:true}));qs('#customAccrualReason').value='Учебный проект';qs('#customAccrualAmount').value='30';",
        ),
        "codesend": Screen(
            "admin", "orders", DIGITAL_ORDER + "openOrderDetails('1357');", reconstructed=True
        ),
        "codewaiting": Screen(
            "parent", "orders", DIGITAL_ORDER + "openOrderDetails('1357');", reconstructed=True
        ),
        "code": Screen(
            "parent",
            "orders",
            DIGITAL_ORDER
            + "orders[0].rawStatus='issued_to_student';orders[0].items[0].issuedCodes=['DEMO-NOT-A-REAL-CODE'];openOrderDetails('1357');",
            reconstructed=True,
        ),
        "cancel": Screen(
            "admin", "orders", "openOrderDetails('1357');showCancelOrderForm('1357');"
        ),
        "detach": admin(
            "contacts",
            "void requestConfirmation({title:'Отвязать аккаунт MAX?',message:'Будут сброшены все привязки учебного MAX ID 100000001. Баланс, заказы и история сохранятся.',confirmLabel:'Отвязать аккаунт',destructive:true});",
            reconstructed=True,
        ),
        "bankconfirm": Screen(
            "student",
            "bank",
            "openBankConfirmation({title:'Открыть вклад?',content:'<p>Сумма: 100 AC</p><p>Проверьте конечную дату и расчёт перед подтверждением.</p>',confirmLabel:'Открыть вклад'});",
            reconstructed=True,
        ),
        "bankclose": Screen(
            "student",
            "bank",
            "openBankConfirmation({title:'Закрыть вклад досрочно?',content:'<p>Возврат: 600 AC</p><p>Причисленные проценты будут потеряны: 18 AC</p>',confirmLabel:'Закрыть вклад',tone:'danger'});",
            reconstructed=True,
        ),
        "rateconfirm": Screen(
            "admin",
            "bank",
            "openBankConfirmation({title:'Изменить процентную ставку?',content:'<p>Новая ставка: 36,50% годовых</p>',confirmLabel:'Изменить ставку'});",
            reconstructed=True,
        ),
        "tickets": Screen("superadmin", "help", TICKETS, reconstructed=True),
        "feedback": Screen(
            "teacher", "feedback", FEEDBACK + "renderFeedback();", reconstructed=True
        ),
        "feedbackmanual": Screen(
            "teacher",
            "feedback",
            FEEDBACK + "feedbackState.tab='manual';feedbackState.group='';renderFeedback();",
            reconstructed=True,
        ),
        "schedule": Screen(
            "teacher",
            "feedback",
            FEEDBACK + "renderFeedback();qs('.feedback-schedule-settings').open=true;",
            reconstructed=True,
        ),
        "loading": Screen(
            "parent",
            "orders",
            "showNotice('Загрузка данных. Подождите завершения.', 'info');",
            reconstructed=True,
        ),
        "failure": Screen(
            "parent",
            "orders",
            "showNotice('Операция не подтверждена. Обновите данные и проверьте результат до повторения.', 'danger');",
            reconstructed=True,
        ),
        "keyboard": Screen(
            "student",
            "bank",
            "openBankConfirmation({title:'Открыть вклад?',content:'<p>Сумма: 100 AC</p><p>Проверьте расчёт.</p>',confirmLabel:'Открыть вклад'});",
            mobile=True,
            reconstructed=True,
        ),
    }
)

SCREENS["staffcity"] = Screen(
    "partner_director", "dashboard", SCREENS["city"].js, reconstructed=True
)
SCREENS["staffhome"] = Screen(
    "teacher",
    "dashboard",
    "state.teacherProfile={first_name:'Иван',last_name:'Петров'};syncTeacherProfileControl();",
)
SCREENS["crop"] = admin(
    "products", PRODUCT + "renderAdminPanel();cropProductPhoto();", reconstructed=True
)
SCREENS["cancelconfirm"] = Screen(
    "admin",
    "orders",
    "openOrderDetails('1357');void requestConfirmation({title:'Отменить заказ №1357?',message:'Причина: по просьбе родителя. AC будут возвращены ученику.',confirmLabel:'Да, отменить заказ',cancelLabel:'Оставить заказ',destructive:true});",
    reconstructed=True,
)
SCREENS["warehousedelete"] = admin(
    "warehouses",
    "void requestConfirmation({title:'Удалить склад?',message:'Проверьте отсутствие остатков и истории. Удаление нельзя отменить.',confirmLabel:'Удалить',destructive:true});",
    reconstructed=True,
)
SCREENS["feedbackassign"] = Screen(
    "teacher",
    "feedback",
    FEEDBACK
    + "feedbackState.schedules[students[0].group]={course:'',rows:[]};await renderFeedback();",
    reconstructed=True,
)
SCREENS["schedulerepeat"] = Screen(
    "teacher",
    "feedback",
    SCREENS["schedule"].js + "qs('#feedbackRepeatDialog').showModal();",
    reconstructed=True,
)
SCREENS["audit"] = admin(
    "history",
    "const feed=auditFeed('actions');feed.rows=[normalizeAdminHistoryEntry({id:'demo-action',title:'Астрокоины начислены',category:'Астрокоины',status:'success',actor_name:'Учебный преподаватель',actor_max_user_id:100000001,created_at:'2026-10-24T09:30:00Z',payload:{amount:30,reason:'Проект',students:[{id:'demo-alisa',name:'Васильева Алиса',group:'Союзный 45',teacher:'Учебный преподаватель'}]}})];feed.total=101;feed.more=true;",
    reconstructed=True,
)
for key, role in [("supportstudent", "student"), ("supportstaff", "staff")]:
    actual_role = "admin" if role == "staff" else role
    SCREENS[key] = Screen(
        actual_role,
        "help",
        SCREENS["support"]
        .js.replace("supportSetRole('parent')", f"supportSetRole('{role}')")
        .replace("Роль: родитель", "Роль: " + ("сотрудник" if role == "staff" else "ученик")),
    )
for source, target in [
    ("support", "supportsent"),
    ("supportstudent", "supportstudentsent"),
    ("supportstaff", "supportstaffsent"),
]:
    base = SCREENS[source]
    SCREENS[target] = Screen(
        base.role,
        base.view,
        base.js + "qs('#supportFormStatus').textContent='Учебный пример: заявка №123 отправлена.';",
        reconstructed=True,
    )
SCREENS["supportcta"] = Screen(
    "parent", "help", "document.querySelector('.help-faq-item').open=true;"
)
SCREENS["feedbackgroup"] = Screen(
    "teacher",
    "feedback",
    FEEDBACK + "await renderFeedback();qs('#feedbackGroupDialog').showModal();",
    reconstructed=True,
)
SCREENS["ticketqueued"] = Screen(
    "superadmin",
    "help",
    TICKETS.replace(
        "replies:[]",
        "replies:[{id:'demo-reply',author:'staff',message:'Учебный ответ: проверьте нижнюю панель.',status:'queued',created_at:'2026-10-24T09:35:00Z',photo_ids:[]}]",
    ),
    reconstructed=True,
)
SCREENS["ticketsent"] = Screen(
    "superadmin",
    "help",
    SCREENS["ticketqueued"].js.replace(
        "status:'queued'", "status:'sent',sent_at:'2026-10-24T09:35:00Z'"
    ),
    reconstructed=True,
)
SCREENS["ticketdeleted"] = Screen(
    "superadmin",
    "help",
    TICKETS + "supportState.items=[];supportRenderInbox({});",
    reconstructed=True,
)

SCREENS.update(
    {
        "familyorder": Screen("parent", "orders", "openOrderDetails('1357');"),
        "storecart": Screen("student", "store", "addToCart('demo-pen');renderAll();"),
        "cityselected": Screen(
            "parent",
            "dashboard",
            "qs('#tenantSwitcherButton').hidden=false;qs('#tenantTitle').textContent='Бор · Учебный партнёр';qs('#statusTenantTitle').textContent='Бор';qs('#statusTenantTitle').hidden=false;",
            reconstructed=True,
        ),
        "accessgate": Screen(
            "parent",
            "dashboard",
            "qs('.app-shell').hidden=true;qs('#accessGate').hidden=false;qs('#accessGateTitle').textContent='Подключите профиль';",
            reconstructed=True,
        ),
        "bankopened": Screen(
            "student",
            "bank",
            "state.activeStudentId='demo-mark';state.bankSummary=demoBankSummary('demo-mark');state.bankSummary=applyDemoBankMutation('open',{amount:100,maturity_on:'2027-01-22'});renderBankView();",
            reconstructed=True,
        ),
        "banktopped": Screen(
            "student",
            "bank",
            "state.bankSummary=applyDemoBankMutation('topup',{amount:100});renderBankView();",
            reconstructed=True,
        ),
        "bankclosed": Screen(
            "student",
            "bank",
            "state.bankSummary=applyDemoBankMutation('close',{});renderBankView();",
            reconstructed=True,
        ),
        "supportphoto": Screen(
            "parent",
            "help",
            SCREENS["support"].js
            + "supportState.files=[{url:'/miniapp/static/assets/help/start-navigation.png',id:null}];supportRenderPhotos();",
            reconstructed=True,
        ),
    }
)

for name in ("banknew", "bankopened"):
    base = SCREENS[name]
    SCREENS[name] = Screen(
        base.role,
        base.view,
        base.js.replace(
            "renderBankView();",
            "state.bankLoadedStudentId=state.activeStudentId;renderStatus();renderBankView();",
        ),
        reconstructed=base.reconstructed,
    )

# These controls exist but are only displayed after a read-only UI interaction.
AFTER = {
    "export": "await openConnectionExportDialog()",
    "staffmenu": "document.querySelectorAll('.admin-row-menu').forEach(e=>e.open=true)",
    "contacts": "document.querySelectorAll('[data-access-child]').forEach(e=>e.open=true)",
    "assemble": "document.querySelector('[data-order-pick-group]').click();",
    "distribute": "document.querySelector('[data-fulfillment-select-all=route]').click();",
    "keyboard": "const keyboard=document.createElement('div');keyboard.id='demoKeyboard';keyboard.style='position:fixed;bottom:0;left:0;right:0;height:260px;background:#cbd2da;z-index:99999;padding:15px;font:20px Arial';keyboard.innerHTML='<button id=keyboardHide style=\"float:right;padding:10px\">Скрыть клавиатуру ↓</button><p>Учебная экранная клавиатура</p><p>Й Ц У К Е Н Г Ш Щ</p><p>Ф Ы В А П Р О Л Д</p><p>Я Ч С М И Т Ь Б Ю</p>';document.body.append(keyboard);",
}
