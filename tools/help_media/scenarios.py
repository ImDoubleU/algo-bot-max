# ruff: noqa: E501
"""Editorial shot lists: one actual control per FAQ step, in FAQ order.

Never infer a target from arbitrary answer text. A changed question or step count
must be reviewed here, and a missing selector fails the build.
"""

DATA = """
Как открыть приложение? | bot@#chat;bot@#open;home@#openWalletButton | Кабинет загружен; имя и баланс относятся к выбранному ребёнку.
Что проверить после первого входа? | home@.profile-card;city@.tenant-option;home@[data-child-id];admin@[data-view="admin"] | Выбраны нужные ребёнок, город и рабочий профиль.
Как открыть нужный раздел на компьютере? | home@[data-view="store"];store@[data-view="store"];store@#railCollapseButton | Открыт магазин; левое меню можно свернуть.
Как открыть нужный раздел на телефоне? | mobile@[data-view="store"];mobile@#mobileMoreButton;more@[data-view="bank"] | Нужный раздел доступен через нижнюю панель или «Ещё».
Как закрыть окно и вернуться к разделу? | product@#productName;product@#productSaveButton;product@#productCancelEditButton | Сохранение и отмена являются разными действиями: перед закрытием выберите нужное.
Когда нажимать «Обновить»? | home@#refreshDataButton;familyorders@#orderSearch;support@[name="message"] | Сверьте список и баланс после обновления, прежде чем повторять операцию.
Как переключить город? | city@#tenantDialogTitle;city@.tenant-option;city@.tenant-option | После выбора проверьте название города и загрузившиеся данные.
Как быстро найти ответ в справке? | home@[data-view="help"];help@#helpSearchInput;helpsearch@.help-category-button;helpsearch@.help-faq-question | Найденный вопрос раскрывается нажатием на его заголовок.
Как родителю подключить ребёнка? | mail@#subject;mail@#invite;account@#parent;start@#start;connected@#message;connected@#open;home@[data-child-id] | После ответа об успешном подключении открывается семейный кабинет с нужным ребёнком.
Что делать, если письмо со ссылкой не пришло? | inbox@#spam;inbox@#email;inbox@#refresh;support@[name="message"] | Нашлось письмо школы: используйте только своё приглашение. Если нет, напишите куратору.
Почему ученик видит «Родителю нужно подтвердить связь»? | mail@#invite;start@#start;waiting@#check;qr@#studentQrPreviewDialog | После подключения родителя «Проверить доступ» открывает кабинет ученика.
Как проверить, кто уже подключён? | staffhome@[data-view="dashboard"];qrlist@[data-dashboard-mode];qrlist@#studentGroupFilter;qrlist@.student-card | У каждого ребёнка отдельно проверены подключения родителя и ученика.
Как родителю переключаться между детьми? | home@[data-child-id];home@[data-child-id];home@#openWalletButton | Перед покупкой, историей и банком проверьте имя активного ребёнка.
Где родителю найти QR-код ребёнка? | home@[data-view="dashboard"];home@QR-коды детей;home@[data-child-id];home@Скопировать ссылку | Код и ссылка относятся только к выбранному ученику; передавайте их лично.
Где сотруднику найти QR-код ученика? | staffhome@[data-view="dashboard"];qrlist@[data-dashboard-mode];qrlist@#studentGroupFilter;qrlist@Показать | Откройте код именно нужного ученика выбранной группы.
Можно ли отправить ссылку или снимок QR-кода? | home@[data-child-id];home@Скопировать ссылку;privatechat@#attachment;account@#student | Личное приглашение получает только нужный ученик и открывает его своим аккаунтом.
Что делать, если камера не распознаёт QR-код? | home@Увеличить;settings@#brightness;home@Скопировать ссылку;account@#student | Если сканирование не помогает, откройте личную ссылку в аккаунте ученика.
Почему статус подключения не изменился? | account@#student;connected@#message;home@#refreshDataButton | После завершения подключения и обновления проверьте новый статус в QR-кодах.
Что делать, если старая ссылка или QR-код не работают? | invalid@#message;mail@#invite;start@#start;waiting@#check | Актуальное приглашение и отдельный аккаунт дают успешное подключение; не меняйте символы ссылки.
Что делать, если подключили не того ученика? | support@[name="message"];admin@[data-view="admin"];contacts@.contact-student;contacts@[data-toggle-link];qr@#studentQrPreviewDialog | После сброса неверных привязок пользователь открывает правильное приглашение заново.
Что означает «Ребёнка пока не добавили в систему»? | support@[name="message"];connected@#open | Доступ появится после добавления ученика и правильного контакта школой.
Где посмотреть доступный баланс? | home@#openWalletButton;home@[data-view="wallet"];home@[data-child-id] | Доступный баланс и история относятся к выбранному ребёнку.
Где посмотреть, за что начислили или списали AC? | home@[data-view="wallet"];wallet@[data-child-id];wallet@.ledger-list | В истории найдены дата, название и сумма нужной операции.
Как начислить AC одному или нескольким ученикам? | accrual@[data-view="accrual"];accrualselected@#accrualGroupSelect;accrualselected@#groupAccrualReason;customaccrual@#groupAccrualAmount;accrualselected@[data-accrual-submit] | После начисления проверьте изменение баланса и запись в истории, не отправляйте повторно.
Можно ли удалить причину «С днем рождения»? | accrual@[data-view="accrual"];rules@#accrualRulesDialogTitle;rules@.accrual-rule-row;rules@#saveAccrualRulesButton | Системную причину не удаляют: сохраните нужную сумму.
Что делать, если баланс кажется неправильным? | home@#refreshDataButton;wallet@.ledger-list;bank@История вклада;familyorders@#orderSearch;support@[name="message"] | Сверены покупки, возвраты и вклад; расхождение передано школе с датой и ожидаемой суммой.
Как найти нужный товар? | store@[data-view="store"];store@#productSearch;filters@Фильтры;store@#productSort;store@В наличии | В списке остаются товары по выбранным условиям поиска.
Как сохранить товар в избранное? | store@[data-view="store"];store@[data-favorite-product];store@Избранное | Отмеченные сердечком товары доступны в избранном.
Почему товар не находится в магазине? | store@#productSearch;store@Все;store@В наличии;support@[name="message"] | После сброса условий найдите товар; если его нет, уточните доступность у сотрудника.
Как добавить товар в корзину? | store@#productSearch;store@[data-add-product];cart@#openCartButton;cart@[data-cart-increase] | В корзине видны правильные товар и количество.
Как оформить заказ? | cart@[data-view="cart"];cart@.cart-item;cart@#checkoutButton;checkout@#confirmCheckoutButton | После подтверждения заказ появляется в «Заказах»; проверьте номер и списание один раз.
Где найти код цифрового товара? | familyorders@[data-view="orders"];familyorders@[data-order-status="electronic"];code@#order;code@#copy | Выданный код доступен в заказе; не публикуйте его в общем чате.
Где посмотреть заказ и его статус? | familyorders@[data-view="orders"];familyorders@[data-order-status="all"];familyorders@#orderSearch;familyorders@[data-open-order] | В карточке можно сверить номер, товары и текущий этап заказа.
Как преподавателю выдать заказ ученику? | teacherorders@[data-open-order];teacherorders@Учитель получил;teacherorders@.order-card;teacherorders@Передать ученику | После фактической передачи заказ получает завершённый статус.
Как отменить заказ? | orders@[data-open-order];order@Отменить заказ;cancel@#reason;cancel@#confirm | Отмена подтверждается отдельно; проверьте статус и возврат AC.
После оформления появилась ошибка. Повторять заказ? | familyorders@[data-view="orders"];familyorders@#refreshDataButton;home@#openWalletButton;cart@#checkoutButton | Повторяйте оформление только если заказа нет и AC не списаны.
Почему заказ не виден в списке? | home@[data-child-id];city@.tenant-option;familyorders@[data-order-status="all"];familyorders@#refreshDataButton | После проверки ребёнка, города, поиска и статуса заказ найден либо требуется помощь школы.
Как открыть вклад? | banknew@[data-view="bank"];banknew@[name="amount"];banknew@Открыть вклад;bankconfirm@#confirm | После подтверждения вклад отображается в банке, а личный баланс уменьшается на внесённую сумму.
Как пополнить действующий вклад? | bank@[data-view="bank"];bank@[name="amount"];bank@Пополнить;bank@В банке | После пополнения проверьте новую сумму и запись в истории вклада.
Что будет при досрочном закрытии? | bank@[data-view="bank"];bank@Закрыть досрочно;bankclose@#calculation;bankclose@#confirm | После согласия вклад закрывается; сумма возврата и потеря процентов указаны до подтверждения.
Где посмотреть историю вклада? | bank@[data-view="bank"];bank@История вклада;bank@.bank-history-list | История показывает даты, направления операций и суммы по вкладу.
Как преподавателю найти свои группы при первом входе? | teacherprofile@#teacherProfileDialog;teacherprofile@#teacherProfileLastName;teacherprofile@#saveTeacherProfileButton | После сохранения точного ФИО проверьте список своих групп.
Почему преподаватель не видит свою группу? | teacherprofile@#teacherProfileDialog;profiledata@[name="teacher_name_choice"];staffhome@#refreshDataButton | ФИО преподавателя в профиле и данных ученика должны совпадать.
Как преподавателю изменить свои имя и фамилию? | staffhome@#teacherProfileButton;teacherprofile@#teacherProfileLastName;teacherprofile@#saveTeacherProfileButton | После сохранения обновлены имя профиля и связанные группы.
Как отменить ошибочное начисление? | wallet@.ledger-list;wallet@.ledger-list;support@[name="message"] | Проверьте возврат в истории; вне срока быстрой отмены обратитесь к администратору.
Как отправить новость ученикам и родителям? | broadcast@[data-view="broadcasts"];broadcast@[name="audience"];broadcast@#broadcastGroups;news@#broadcastMessage;newscheck@#previewBroadcastButton;newscheck@#broadcastAudiencePreview;newscheck@#sendBroadcastButton | После подтверждения проверьте отчёт отправки; не запускайте рассылку повторно без проверки.
Как добавить к новости фото или эмодзи? | news@[data-broadcast-step="2"];news@#broadcastEmojiButton;news@Добавить фото;news@#broadcastLivePreview | В предпросмотре проверьте текст, выбранный символ и фотографию до отправки.
Сохранится ли незаконченная рассылка? | news@#broadcastDraftStatus;news@[data-view="dashboard"];news@#broadcastMessage;newscheck@#previewBroadcastButton | На том же устройстве проверьте восстановленный текст, заново добавьте фото и пересчитайте аудиторию.
Как добавить площадку для рассылок? | broadcast@[data-broadcast-step="1"];broadcast@Добавить;venue@#broadcastVenueName;venue@#broadcastVenueEditorGroups;venue@#saveBroadcastVenueButton | Сохранённая площадка доступна в получателях с нужными группами.
Где посмотреть отчёт по начислениям? | report@[data-view="report"];report@#reportDateFrom;report@#reportTeacherFilter;report@Показать | В отчёте проверьте период, группу, преподавателя и итог AC.
Что находится в разделе «Управление»? | admin@[data-view="admin"];admin@[data-admin-tab="products"] | Нужная вкладка открывает соответствующую рабочую область выбранного города.
Как редактировать ученика? | registry@[data-view="wallet"];registry@[data-open-student];profile@[data-profile-tab="data"];profiledata@[name="last_name"];profiledata@[name="group_name_choice"];profiledata@[name="crm_deal_id"];profiledata@Сохранить данные;profilefinance@[name="balance"];profilehistory@История карточки | После сохранения проверьте исправленные данные и отдельное событие в истории карточки.
Где посмотреть вклады учеников и изменить ставку? | city@.tenant-option;bankadmin@[data-view="bank"];bankadmin@#bankReportSearch;bankadmin@[name="annual_rate"];rateconfirm@#confirm | Новая ставка применяется только после подтверждения; проверьте её в настройках города.
Как пригласить сотрудника по ссылке? | city@.tenant-option;staff@[data-admin-tab="staff"];staff@#staffInviteButton;invite@#staffInvitationRoleSelect;invitelink@Создать ссылку;privatechat@#attachment | Личное приглашение выдано нужной роли и только в выбранном городе.
Что делать, если приглашение открыл не тот человек? | staff@[data-admin-tab="staff"];staff@#adminEntitySearch;staffmenu@[data-toggle-staff];invite@#staffInvitationRoleSelect | Неверный доступ отозван; новое приглашение передают лично нужному человеку.
Как выдать роль по MAX ID? | city@.tenant-option;staff@[data-admin-tab="staff"];staff@#staffCreateButton;grant@#staffMaxUserId;grant@#staffMaxUserId;grant@#staffSaveButton | После выдачи проверьте MAX ID и активную роль в строке сотрудника.
Как добавить или отозвать роль сотрудника? | staff@[data-admin-tab="staff"];staffmenu@.admin-row-menu;staffrole@[data-staff-additional-role-select];staffmenu@[data-toggle-staff] | У сотрудника остаются только проверенные действующие роли.
Как директору настроить уведомления сотрудника? | staff@[data-admin-tab="staff"];staff@#adminEntitySearch;staff@[data-staff-notifications];notifications@[data-staff-notification-key];notifications@#saveStaffNotificationsButton | Сохранены только нужные события для выбранного сотрудника.
Как изменить ФИО сотрудника? | staff@[data-admin-tab="staff"];staffmenu@.admin-row-menu;staffmenu@[data-edit-staff-profile];staffname@[data-managed-staff-last-name];staffname@[data-save-managed-staff-profile] | После сохранения имя обновится у всех ролей сотрудника.
Как отвязать аккаунт родителя или ученика и подключить его заново? | contacts@[data-admin-tab="contacts"];contacts@#adminEntitySearch;contacts@[data-toggle-link];detach@#confirm;mail@#invite | Сброс касается всех привязок указанного MAX-аккаунта; затем подключите нужного человека заново.
"""

MORE = """
Как выгрузить подключения учеников и родителей в Excel? | contacts@[data-open-connection-export];export@[data-connection-export-key];export@Включить выбывших и архивных учеников;export@Скачать Excel;sheet@#pupils | Скачанный отчёт содержит листы «Ученики» и «Сводка» и фиксирует состояние на момент выгрузки.
Где взять ссылку для приглашения родителя? | parentlinks@[data-copy-shop-invitation];linkedit@#contact;privatechat@#attachment | Не меняйте остальную часть шаблона; отправьте приглашение только указанному родителю.
Как загрузить учеников из Excel? | crm@[data-admin-tab="crm"];crm@Скачать шаблон;crm@#crmStudentStatus;crm@.file-picker;crm@#crmPreviewButton;preview@Распределение по городам;preview@#crmImportButton | После импорта проверьте число новых и обновлённых учеников и их город; повторять импорт без проверки не нужно.
Какие листы можно импортировать? | preview@Распределение по городам;preview@.crm-import-result;spreadsheet@#city | Импортируйте лист «Шаблон» или «Сделки»; распределение должно соответствовать исходной таблице.
Появятся ли дубликаты при повторном импорте учеников? | crm@#crmPreviewButton;preview@.crm-import-result;spreadsheet@#ids | Неизменные исходные идентификаторы сопоставляют уже существующие карточки.
Как добавить физический товар? | products@[data-admin-tab="products"];products@#productCreateButton;product@#productName;product@#productFulfillmentType;product@.product-inventory-row;product@#productSaveButton | Проверьте физический товар в каталоге: цена, склады и фактический остаток сохранены.
Как добавить цифровой товар? | products@[data-admin-tab="products"];products@#productCreateButton;digital@#productFulfillmentType;digital@#productName;instant@#productNewCodes;instant@#productSaveButton | Без флажка код отправляет сотрудник; с мгновенной выдачей используются уникальные загруженные коды.
Как загрузить сразу несколько товаров? | products@[data-admin-tab="products"];productimport@Массовый импорт;productimport@Скачать шаблон XLSX;productimport@.file-picker;productimport@#productImportButton;products@.admin-entity-title | После импорта проверьте каждую карточку, артикул, фото и полный остаток.
Какие ссылки на фото подходят для импорта товаров? | privacy@#private;photopreview@#image;sharing@#public;spreadsheet@#photo;product@#productPhotoFile | Подходит публичный одиночный файл без авторизации; альтернативно загрузите фото в карточке.
Как изменить кадрирование фотографии товара? | products@[data-admin-tab="products"];products@[data-edit-product];product@[data-crop-product-photo];crop@#apply;product@#productSaveButton | Примените кадрирование и отдельно сохраните товар.
Когда товар скрывать, архивировать или удалять? | products@[data-admin-tab="products"];products@[data-toggle-product];product@#productStatus;products@[data-delete-product] | Скрытие обратимо; товары с заказами архивируют, а не удаляют.
Как показать товары только с одного склада? | products@[data-admin-tab="products"];products@#productWarehouseFilter;products@#productWarehouseFilter | Каталог отфильтрован по выбранному складу; это не меняет остатки.
Как добавить склад? | warehouses@[data-admin-tab="warehouses"];warehouses@#warehouseCreateButton;warehouse@#warehouseName;warehouse@#warehouseSaveButton | Новый склад появился в списке; проверьте точное название.
Как выбрать основной склад? | warehouses@[data-admin-tab="warehouses"];warehouses@#defaultWarehouseSelect;warehouses@#saveWarehousePreferenceButton | Сохранённый склад будет предварительно выбран в новых заказах.
Как подключить один склад к нескольким городам? | warehouses@.admin-entity-title;city@.tenant-option;warehouse@#warehouseName;warehouse@#warehouseSaveButton | Используйте точно то же название существующего склада, без новых вариантов написания.
Почему склад нельзя удалить? | products@#productWarehouseFilter;orders@[data-open-order];warehouses@.admin-entity-title | Склад с остатками, активными заказами или историей не удаляют; прекратите его использование.
Как назначить склад заказу? | orders@[data-order-status="assign"];orders@[data-open-order];assign@[data-order-item-warehouse];assign@Подтвердить склады | Каждая позиция получила склад, и заказ перешёл к сборке.
Как собрать и распределить заказы? | orders@[data-order-status="collect"];assemble@[data-fulfillment-confirm];orders@[data-order-status="route"];distribute@.fulfillment-venue;distribute@[data-fulfillment-confirm] | Отмечайте только фактически собранные и переданные позиции; статус соответствует физической передаче.
Где посмотреть, кто изменил товар, заказ или доступ? | audit@[data-admin-tab="history"];audit@[data-audit-filter];audit@[data-audit-search];audit@.audit-list;audit@[data-audit-more] | Найдены участники, время по Москве, раздел и результат нужного события.
Как отправить заявку из мини-приложения? | supportrole@[data-support-role="parent"];support@[name="message"];support@Прикрепить фото;support@[type="submit"] | Дождитесь номера заявки; при ошибке отправки текст формы можно уточнить и попробовать снова.
Как сообщить о проблеме через бота? | botsupport@#role;botsupport@#name;botsupport@#compose;botsupport@#attachment;botsupport@#send | Бот подтвердит отправку номером заявки; сохраните его для продолжения переписки.
Кто получает заявки и где их смотреть? | tickets@#inbox;tickets@#status;tickets@#ticket;tickets@#next | Владелец видит заявку и переписку; статус и страницы помогают найти остальные обращения.
Почему видны данные другого города? | city@#tenantDialogTitle;city@.tenant-option;admin@#refreshDataButton | Выбран правильный город, данные обновлены.
Почему список пустой, хотя данные должны быть? | orders@#orderSearch;orders@[data-order-status="all"];city@.tenant-option;admin@.profile-card;admin@#refreshDataButton | После сброса условий и проверки роли список должен соответствовать доступной области.
Что делать, если раздел долго загружается? | loading@#loading;home@#refreshDataButton;bot@#close;bot@#open | При восстановлении сети раздел загружается; не запускайте одну операцию повторно.
Почему в окне не видно кнопку сохранения? | keyboard@#hide;product@#productDescription;product@#productSaveButton;missing@#screenshot | После закрытия клавиатуры и прокрутки видна нижняя панель «Сохранить товар». Если панели нет, приложите полный скриншот и отправьте заявку.
Что делать, если операция завершилась сообщением о сбое? | failure@#error;home@#refreshDataButton;wallet@.ledger-list;support@[name="message"];support@[name="message"] | Если действие уже записано в истории, не повторяйте его. Неоднозначный результат передайте администратору.
Почему появились одинаковые категории товаров? | products@[data-admin-tab="products"];products@#productCategoryFilter;product@#productCategory;product@#productSaveButton;products@#refreshDataButton | Одинаковые названия во всех карточках объединяют категорию после обновления.
Почему появился второй склад с похожим названием? | warehouses@.admin-entity-title;products@#productWarehouseFilter;support@[name="message"] | Склад с остатками или историей не удаляйте; передайте администратору точные названия.
Почему после выхода новой версии приложение выглядит по-старому? | bot@#close;bot@#chat;bot@#open;settings@#restart | После повторного открытия MAX проверьте обновившийся интерфейс.
Почему не пришло уведомление? | settings@#blocked;city@.tenant-option;contacts@.contact-student;notifications@#saveStaffNotificationsButton | Бот разблокирован, связь активна, нужные события уведомлений включены.
Что приложить к сообщению об ошибке? | support@[name="message"];support@[name="message"];support@[name="message"];support@[name="message"];support@[name="message"];support@Прикрепить фото | В заявке указаны время МСК, город, роль, запись, последовательность и полный скриншот без личных ссылок.
Что делать, если данные не принимаются? | product@#productName;profiledata@[name="lms_student_id"];product@#productPrice;product@#productSaveButton | Исправьте отмеченные значения и отправьте форму один раз, затем проверьте результат.
Что делать, если вход не подтверждён или нет доступа? | bot@#open;city@.tenant-option;profiledata@[name="venue_name"];staffmenu@[data-add-staff-role] | Рабочий профиль и доступная площадка подтверждены директором.
Что означает сообщение «Не найдено»? | city@.tenant-option;registry@#refreshDataButton;registry@#studentRegistrySearch;support@[name="message"];profileaccess@ID родителя из CRM | Запись найдена через актуальный список либо контакт и город переданы куратору на проверку.
Почему действие конфликтует с текущими данными? | failure@#error;admin@#refreshDataButton;profiledata@[name="lms_student_id"];orders@[data-open-order] | Продолжайте с актуального состояния после проверки дубликатов и статуса заказа.
Что означают «Ссылка отозвана», «уже использована» или «срок истёк»? | support@[name="message"];invite@#staffInvitationRoleSelect;privatechat@#attachment | Директор создал новое персональное приглашение с правильными ролью и городом.
Что делать, если файл слишком большой? | spreadsheet@#cleanup;crop@#size;crm@.file-picker | После уменьшения исходника повторите выбор файла и его проверку.
Что делать, если сервис временно недоступен? | failure@#error;home@#refreshDataButton;wallet@.ledger-list;support@[name="message"] | Сначала проверьте результат в истории, затем сообщите повторяющийся сбой администратору.
Почему файл учеников не проходит проверку? | crm@Скачать шаблон;spreadsheet@#sheet;spreadsheet@#format;spreadsheet@#city;crm@#crmPreviewButton | Свежий XLSX проходит проверку: ID сохранены как текст, города и обязательные колонки верны.
Почему не сохраняется карточка ученика? | profiledata@[name="last_name"];profiledata@[name="lms_student_id"];profiledata@[name="venue_name"];registry@#studentRegistrySearch | После исправления исходных данных сохраните карточку и проверьте её историю, не создавая дубликат.
Почему не сохраняется товар или его остаток? | product@#productName;product@.product-inventory-row;products@.admin-entity-meta;instant@#productNewCodes | Цена, способ выдачи, фактические остатки и уникальность кодов проверены перед сохранением.
Почему ссылка на фотографию товара не загружается? | privacy@#private;sharing@#public;sharing@#file;product@#productPhotoFile | Если облако требует авторизацию или ссылка истекает, используйте прямую загрузку фото.
Почему заказ не удаётся оформить или обработать? | home@#openWalletButton;store@#refreshDataButton;assign@[data-order-item-warehouse];orders@[data-open-order] | Доступ, баланс, количество и склад проверены; продолжайте с текущего статуса заказа.
Почему не выполняется операция по вкладу? | child@.profile-card;bank@[name="amount"];bank@#refreshDataButton;profiledata@[name="status"] | Операции выполняет активный ученик с достаточным личным балансом и допустимой датой.
Почему не начисляются или не отменяются астрокоины? | accrualselected@#accrualGroupSelect;customaccrual@#groupAccrualAmount;wallet@.ledger-list;support@[name="message"] | Не начисляйте повторно ради отмены; спорную операцию проверяет администратор.
MAX пишет «Техническая заминка». Что проверить? | bot@#open;settings@#network;support@[name="message"];botsupport@#attachment | Работа через другую сеть помогает локализовать сбой; при повторении отправьте заявку через бота.
Почему не пришло сообщение о появлении ребёнка? | pending@#message;support@[name="message"];mail@#invite;support@[type="submit"] | Школа проверяет загрузку ребёнка и контакт; после исправления повторно откройте своё приглашение.
Как ученику зарегистрироваться после родителя? | connected@#message;home@QR-коды детей;account@#student;start@#start;child@#openWalletButton | Ученик открыл свой кабинет отдельным MAX-аккаунтом после подтверждения родителя.
Нажал ссылку, но вижу только кнопку «Начать». Это нормально? | account@#parent;start@#start;connected@#open;support@[name="message"] | «Начать» запускает бота; после успешного ответа откройте кабинет. При молчании бота отправьте описание шага.
Что делать с ошибкой «Аккаунт MAX уже подключён как родитель / ученик»? | account@#student;account@#parent;supportrole@[data-support-role="parent"] | Для разных ролей нужны разные аккаунты; ошибочную связь проверяет и сбрасывает администратор.
Сотрудник отправил электронный код. Куда он придёт? | familyorders@[data-order-status="electronic"];code@#order;code@#copy | Код хранится в заказе, даже если уведомление MAX задержалось; повторная покупка не нужна.
Как отправить код по электронному заказу? | orders@[data-view="orders"];digitalorders@[data-order-status="electronic"];codesend@#codes;codesend@#send;code@#status | Статус «Код выдан» подтверждает выдачу; код сохранён в заказе.
Выбор группы или преподавателя в карточке меняет всех учеников? | profile@[data-profile-tab="data"];profiledata@[name="group_name_choice"];profiledata@Сохранить данные | Сохраняются только данные открытого ученика; исходную таблицу исправляют отдельно.
Какой формат нужен для ID при работе с Google Таблицами? | spreadsheet@#ids;spreadsheet@#format;spreadsheet@#ids;crm@#crmPreviewButton | Исходные ID заново вставлены как текст и проверены перед импортом XLSX.
Что означают цифры и флажки в экспорте подключений? | sheet@#pupils;sheet@#summary;export@Скачать Excel | Отчёт является снимком; изменение флажков в Excel не изменяет доступ в приложении.
Как подготовить обратную связь по своей группе? | feedback@#group;feedback@#course;feedback@#lesson;feedback@#absent;feedback@#prepare;feedback@#copy | Подготовленный текст проверен и скопирован; преподаватель сам отправляет его в родительский чат.
Как создать обратную связь вручную? | feedbackmanual@#manual;feedbackmanual@#course;feedbackmanual@#absent;feedbackmanual@#coins;feedbackmanual@#prepare;feedbackmanual@#copy | Флажок AC меняет только текст, а не начисляет валюту; отправка сообщения выполняется самостоятельно.
Как изменить расписание, добавить повтор или пропуск занятия? | schedule@#schedule;schedule@#date;schedule@#repeat;schedule@#add;schedule@#disabled;schedule@#save | После сохранения проверьте даты и активные занятия; выключенные строки не участвуют в календаре.
Как дополнить обращение после ответа поддержки? | ticketreply@#ticket;ticketreply@#reply;ticketreply@#number;ticketreply@#send | Подтверждение добавления содержит тот же номер обращения, а не номер новой заявки.
Почему не получается скачать Excel подключений? | export@[data-connection-export-select];export@Скачать Excel;contacts@[data-open-connection-export];downloads@#file | При ненулевом числе учеников скачайте файл и проверьте загрузки браузера или MAX.
Электронный заказ ждёт код, хотя AC уже списались. Это ошибка? | codewaiting@#status;codewaiting@#mode;support@[name="message"] | Для товара под заказ ожидание нормально; для мгновенной выдачи отсутствие кода требует поддержки, а не повторной покупки.
"""


def definitions():
    result = {}
    for line in (DATA + MORE).strip().splitlines():
        if not line.strip():
            continue
        question, shots, outcome = [part.strip() for part in line.split(" | ")]
        if question in result:
            raise ValueError("Duplicate scenario: " + question)
        result[question] = {"shots": shots.split(";"), "outcome": outcome}
    for new, old in ALIASES.items():
        result[new] = dict(result[old])
    for question, shot in APPEND.items():
        result[question]["shots"] = result[question]["shots"] + [shot]
    for line in REVISIONS.strip().splitlines():
        question, shots, outcome = [part.strip() for part in line.split(" | ")]
        result[question] = {"shots": shots.split(";"), "outcome": outcome}
    result["Что проверить после первого входа?"]["text"] = {
        3: "В семейном кабинете проверьте доступные разделы: магазин, заказы, история AC и банк. Рабочие разделы сотрудников в семейном профиле не показываются."
    }
    result["Как закрыть окно и вернуться к разделу?"]["text"] = {
        0: "Сначала проверьте, нужно ли подтвердить введённые данные. Пример: окно операции по вкладу ученика.",
        1: "Если хотите выполнить действие, нажмите нижнюю кнопку подтверждения один раз. В разных формах она называется «Сохранить», «Открыть вклад» или «Подтвердить заказ».",
        2: "Крестик или «Отмена» закрывают окно без подтверждения операции. Не путайте закрытие с сохранением.",
    }
    for definition in result.values():
        definition["shots"] = [FIXED_TARGETS.get(shot, shot) for shot in definition["shots"]]
    return result


ALIASES = {
    "Почему группы преподавателя не нашлись?": "Почему преподаватель не видит свою группу?",
    "Как создать и отправить новость?": "Как отправить новость ученикам и родителям?",
}

APPEND = {
    "Где родителю найти QR-код ребёнка?": "privatechat@#attachment",
    "Что делать, если старая ссылка или QR-код не работают?": "child@#openWalletButton",
    "Как начислить AC одному или нескольким ученикам?": 'profilefinance@[name="balance"]',
    "Как оформить заказ?": "familyorders@[data-open-order]",
    "Как преподавателю выдать заказ ученику?": 'teacherorders@[data-order-status="issued_to_student"]',
    "Как отменить заказ?": 'orders@[data-order-status="cancelled"]',
    "Как открыть вклад?": "bank@.bank-history-list",
    "Что будет при досрочном закрытии?": "bank@.bank-history-list",
    "Где посмотреть вклады учеников и изменить ставку?": 'bankadmin@[name="annual_rate"]',
    "Что делать, если приглашение открыл не тот человек?": "staff@#adminEntitySearch",
    "Как выдать роль по MAX ID?": "staff@#adminEntitySearch",
    "Как отвязать аккаунт родителя или ученика и подключить его заново?": "contacts@.access-child-statuses",
    "Где взять ссылку для приглашения родителя?": "connected@#open",
    "Как загрузить учеников из Excel?": "registry@[data-open-student-profile]",
    "Как добавить физический товар?": "products@.admin-entity-title",
    "Какие ссылки на фото подходят для импорта товаров?": "product@#productSaveButton",
    "Как подключить один склад к нескольким городам?": "warehouses@.admin-entity-title",
    "Почему склад нельзя удалить?": 'support@[type="submit"]',
    "Как назначить склад заказу?": 'orders@[data-order-status="fulfillment_collect"]',
    "Как собрать и распределить заказы?": 'orders@[data-order-status="awaiting_delivery"]',
    "Что приложить к сообщению об ошибке?": 'support@[type="submit"]',
    "Почему не сохраняется карточка ученика?": "profiledata@Сохранить данные",
    "Почему ссылка на фотографию товара не загружается?": "product@#productSaveButton",
    "Что делать с ошибкой «Аккаунт MAX уже подключён как родитель / ученик»?": "child@#openWalletButton",
    "Как подготовить обратную связь по своей группе?": "privatechat@#compose",
    "Как изменить расписание, добавить повтор или пропуск занятия?": "schedule@#feedbackActiveLesson",
    "Как создать и отправить новость?": "newscheck@#broadcastAudiencePreview",
}

REVISIONS = """
Что проверить после первого входа? | home@.profile-summary;city@.tenant-option;home@[data-child-id];home@[data-view="store"] | Выбраны правильный ребёнок и доступные разделы семейного кабинета.
Как закрыть окно и вернуться к разделу? | bankconfirm@#bankConfirmationDescription;bankconfirm@#confirmBankActionButton;bankconfirm@#closeBankConfirmationButton | Подтверждение операции и закрытие без изменений являются разными действиями.
Что делать, если подключили не того ученика? | support@[name="message"];supportrole@[data-support-role="parent"];support@[name="message"];support@[type="submit"];account@#student | Не используйте чужой профиль. Школа проверит связь, затем откройте правильное приглашение со своего аккаунта.
Почему в семейном кабинете виден только один ребёнок? | account@#parent;mail@#invite;home@[data-child-id] | После успешного подключения недостающего ребёнка обновите семейный кабинет.
Может ли ученик войти до подключения родителя? | connected@#message;waiting@#check | Привязка ученика сохраняется, но кабинет ждёт подключения родителя.
Родитель вошёл в бот, но ребёнка в кабинете нет. Почему? | mail@#invite;home@[data-child-id];pending@#message | При сохранённой попытке школа должна загрузить данные; ожидание действует 30 дней.
Родитель подключился после первой попытки ученика. Что делать ученику? | connected@#message;waiting@#check;pending@#message;child@#openWalletButton | После готовности родителя и профиля ученика проверка доступа открывает личный кабинет.
Что произойдёт после отзыва родительской связи? | support@[name="message"];mail@#invite;account@#student;waiting@#check | Повторное подключение выполняют только после проверки и разрешения школы.
Что означает «Ребёнка пока не добавили в систему»? | pending@#message;support@[name="message"];connected@#open | Сохранённая попытка действует 30 дней; после автоматического подключения проверьте имя в кабинете.
Что делать, если по ссылке подключился чужой ребёнок? | home@[data-child-id];support@[name="message"];account@#parent;connected@#open | Чужой профиль не используют; правильное подключение выполняют после исправления данных школой.
Что делать, если MAX-аккаунт уже подключён? | bot@#open;home@[data-child-id];support@[name="message"] | Если имя и роль верны, повторная регистрация не нужна. Ошибочную связь проверяет школа.
Что произойдёт, если остановить бота в MAX? | start@#start;mail@#invite;account@#student;waiting@#check | Запуск бота не восстанавливает связь сам по себе; дождитесь успешного подключения.
Как проверить, кому и кто начислил астрокоины? | audit@[data-admin-tab="history"];audit@[data-audit-search];audit@.audit-event | Найдены автор, ученик, сумма и время конкретного начисления.
Что делать, если не хватает AC? | cart@#cartTotal;cart@[data-cart-step="-1"];home@#openWalletButton | Итог должен укладываться в личный баланс. Реальные платёжные данные для получения AC не вводят.
Как смотреть заказы, если у меня несколько ролей? | orders@[data-view="orders"];orders@#orderViewSwitcher;orders@#orderSearch | Переключите рабочий вид заказов и продолжайте действие только в доступной роли.
Почему не загружается фотография товара? | store@#refreshDataButton;store@[data-open-product];support@[type="submit"] | Если фото не появилось после проверки сети, отправьте название и снимок карточки в поддержку.
Как преподавателю найти свои группы при первом входе? | staffcity@.tenant-option;teacherprofile@#teacherProfileLastName;teacherprofile@#saveTeacherProfileButton;staffhome@#studentGroupFilter | После точного ФИО и сохранения проверьте найденные группы.
Почему группы преподавателя не нашлись? | staffcity@.tenant-option;teacherprofile@#teacherProfileLastName;teacherprofile@#saveTeacherProfileButton;crm@#crmPreviewButton | Город и ФИО должны совпадать с последним импортом; иначе требуется проверка администратора.
Где сотруднику посмотреть историю ученика? | registry@[data-view="wallet"];registry@#studentRegistrySearch;registry@.student-registry-row;registry@[data-open-student-profile];profilefinance@.student-ledger-history | Карточка и финансовая история относятся к выбранному ученику.
Как работают несколько ролей у одного сотрудника? | staffcity@.tenant-option;admin@[data-view="admin"];staff@#adminEntitySearch | Роли проверяются отдельно для выбранного города; доступ сверяет администратор.
Как пригласить сотрудника по ссылке? | staffcity@.tenant-option;staff@[data-admin-tab="staff"];staff@#staffInviteButton;invite@#staffInvitationRoleSelect;invitelink@Создать ссылку;privatechat@#attachment;start@#start;staff@#adminEntitySearch | После входа сотрудника проверьте MAX ID, роль и город в обновлённом списке.
Как посмотреть историю подключений и открыть карточку ученика? | audit@[data-admin-tab="history"];audit@[data-audit-search];audit@.audit-event;registry@[data-open-student-profile] | История и карточка позволяют проверить вход, отказ и нужного ученика.
Можно ли написать в поддержку без привязанного ученика? | supportrole@[data-support-role="parent"];support@[name="message"];support@Прикрепить фото;support@[type="submit"] | Для заявки не требуется привязанный ученик; дождитесь её номера в своём MAX-аккаунте.
Как изменить статус тикета и оставить заметку? | tickets@.support-ticket-number;tickets@[name="status"];tickets@[data-support-update] [type="submit"];tickets@[name="private_note"] | После сохранения повторно откройте тикет и проверьте статус и внутреннюю заметку.
Как ответить автору и завершить тикет? | tickets@.support-ticket-message;tickets@[data-support-reply] [type="submit"];ticketqueued@[data-message-state];ticketsent@[data-message-state];tickets@[data-support-resolve] | Только «Отправлен в MAX» подтверждает передачу ответа, не прочтение; завершайте действительно решённый вопрос.
Как удалить тикет полностью? | tickets@[data-support-resolve];tickets@.support-ticket-number;tickets@[data-support-delete];ticketdeleted@#supportTicketList | Безвозвратное удаление отличается от завершения; сообщения, уже доставленные в MAX, остаются в чате.
Почему видны данные другого города? | city@#tenantDialogTitle;city@.tenant-option;home@#refreshDataButton | Проверьте выбранный город и заново загруженные данные.
Почему список пустой, хотя данные должны быть? | familyorders@#orderSearch;familyorders@[data-order-status="all"];city@.tenant-option;home@.profile-summary;home@#refreshDataButton | После проверки профиля и сброса условий список соответствует доступным семейным данным.
Почему в окне не видно кнопку сохранения? | keyboard@#keyboardHide;bankconfirm@#bankConfirmationDescription;bankconfirm@#confirmBankActionButton;support@Прикрепить фото;support@[name="message"];support@[type="submit"] | После закрытия клавиатуры и прокрутки проверьте нижнюю кнопку. При отсутствии отправьте полный скриншот в поддержку и дождитесь номера заявки.
Что делать, если операция завершилась сообщением о сбое? | failure@#notice;home@#refreshDataButton;wallet@.ledger-list;support@[type="submit"] | Если операция уже записана, не повторяйте её; неоднозначный результат сначала передайте поддержке.
Почему не пришло уведомление? | settings@#blocked;city@.tenant-option;home@[data-child-id];support@[name="message"] | Для семьи проверяют бот, город и связь. Рабочие уведомления сотрудников настраивает директор отдельно.
Что делать, если данные не принимаются? | support@[name="first_name"];support@[name="message"];banknew@[name="amount"];support@[type="submit"] | Исправьте обязательные поля и значения, отправьте форму один раз и дождитесь результата.
Что делать, если вход не подтверждён или нет доступа? | bot@#open;city@.tenant-option;home@[data-child-id];support@[name="message"] | Для семьи проверьте личное приглашение и ребёнка; для рабочих ролей обратитесь к директору без обхода ограничений.
Что означает сообщение «Не найдено»? | home@[data-child-id];familyorders@#refreshDataButton;familyorders@#orderSearch;support@[name="message"] | Ищите актуальную запись через список. Ответ бота при ошибке приглашения передайте куратору, не меняя цифры.
Почему действие конфликтует с текущими данными? | failure@#notice;home@#refreshDataButton;familyorders@#orderSearch;familyorders@[data-open-order] | Продолжайте только с актуального состояния заказа; не повторяйте неподтверждённую операцию.
Что означают «Ссылка отозвана», «уже использована» или «срок истёк»? | staff@#adminEntitySearch;invite@#staffInvitationRoleSelect;privatechat@#attachment;staff@#refreshDataButton | После нового приглашения проверьте правильные MAX ID, роль и город сотрудника.
Что делать, если файл слишком большой? | support@Прикрепить фото;photopreview@#image;support@Прикрепить фото;support@[type="submit"] | Отправьте уменьшенное читаемое фото JPEG/PNG/WebP и дождитесь номера заявки.
Почему заказ не удаётся оформить или обработать? | home@#openWalletButton;store@#refreshDataButton;familyorders@[data-open-order];familyorders@[data-order-status="all"] | В семейном кабинете проверьте баланс, количество и состояние заказа. Рабочую обработку выполняет школа.
Почему не выполняется операция по вкладу? | child@.profile-summary;bank@[name="amount"];bank@#refreshDataButton;support@[name="message"] | Операции доступны активному ученику; при неясном статусе передайте вопрос школе.
Кнопка «Начать» не появилась. Что делать? | mail@#invite;connected@#message;connected@#open;settings@#network | Если бот уже запускался, «Начать» может не требоваться; ориентируйтесь на новый ответ о подключении.
Можно ли добавить свою онлайн-группу или индивидуальные занятия? | feedback@[data-feedback-add-group];feedbackgroup@[name="name"];feedbackgroup@[type="submit"];feedback@[data-feedback-group] | Созданная группа проверена по формату, ученикам и расписанию перед подготовкой сообщения.
Что делать, если после изменения настроек сообщение устарело? | feedback@#feedbackText;feedback@#feedbackLesson;feedback@.feedback-generate;feedback@[data-feedback-copy] | После повторной подготовки проверьте новый текст и отправьте его самостоятельно в правильный чат.
Можно ли продолжить решённое обращение? | ticketreply@#reply;ticketreply@#number;ticketreply@#send;ticketreply@#ticket | Дополнение привязано к прежнему номеру обращения; проверьте подтверждение бота.
Почему бот спрашивает, к какому обращению относится сообщение? | ticketreply@#ticket;ticketchoice@#number;ticketreply@#number | Выберите правильный номер и не отправляйте уже отложенное сообщение повторно.
Почему сотруднику не удаётся обработать заказ? | orders@#orderViewSwitcher;orders@#refreshDataButton;assign@[data-order-item-warehouse];orders@[data-open-order] | Сверьте роль, номер, склад и фактическое действие; при неясном результате остановитесь до проверки.
Что сотруднику проверить, если нет доступа к рабочему разделу? | bot@#open;staffcity@.tenant-option;staff@#adminEntitySearch;admin@[data-view="admin"] | После исправления ролей заново откройте кабинет и проверьте область доступных данных.
Почему сотруднику не пришло рабочее уведомление? | settings@#blocked;staffcity@.tenant-option;notifications@#saveStaffNotificationsButton;bot@#chat | Новая настройка действует для следующих подходящих событий, не пересылает старые уведомления.
Что сотруднику делать, если файл импорта слишком большой? | spreadsheet@#sheet;spreadsheet@#cleanup;preview@#crmImportButton;products@.admin-entity-title | Проверка файла ещё не импортирует данные; при неясном результате не повторяйте импорт остатков.
Как удалить склад или отключить его от города? | warehouses@.admin-entity-title;warehouses@[data-delete-warehouse];warehousedelete@#confirmActionButton;warehouses@.admin-entity-title | Удаление или отключение подтверждается отдельно; склад с историей и остатками не удаляют.
"""

# Explicit DOM corrections, reviewed against the current control inventory.
# No fallback to a whole screen or a nearest text match is permitted.
FIXED_TARGETS = {
    "cancelconfirm@#confirmActionButton": "cancelconfirm@#confirmConfirmationButton",
    "cancel@#confirm": "cancelconfirm@#confirmConfirmationButton",
    "detach@#confirmActionButton": "detach@#confirmConfirmationButton",
    "detach@#confirm": "detach@#confirmConfirmationButton",
    "warehousedelete@#confirmActionButton": "warehousedelete@#confirmConfirmationButton",
    "order@Отменить заказ": 'orders@[data-order-action="cancel"]',
    "invitelink@Создать ссылку": "invitelink@#staffInvitationCopyButton",
    "assign@[data-order-item-warehouse]": "assign@[data-order-warehouse]",
    "accrualselected@[data-accrual-submit]": "accrualselected@[data-selected-accrual]",
    "customaccrual@#groupAccrualAmount": "customaccrual@#customAccrualAmount",
    "audit@[data-audit-filter]": 'audit@[data-audit-field="days"]',
    "audit@[data-audit-search]": 'audit@[data-audit-field="q"]',
    "audit@.audit-list": "audit@.audit-event",
    'broadcast@[name="audience"]': "broadcast@#broadcastRecipientCategory",
    "broadcast@#broadcastGroups": "broadcast@#broadcastGroupList",
    "cart@#checkoutButton": "cart@#placeOrderButton",
    "cart@.cart-item": "cart@.cart-row",
    "cart@[data-cart-increase]": 'cart@[data-cart-step="1"]',
    "checkout@#confirmCheckoutButton": "checkout@#confirmOrderButton",
    "code@#order": "code@#orderDialogTitle",
    "code@#copy": "code@[data-copy-code]",
    "code@#status": "code@.order-dialog-summary .status-badge",
    "codewaiting@#status": "codewaiting@.order-dialog-summary .status-badge",
    "codewaiting@#mode": "codewaiting@.order-dialog-summary .student-meta",
    "codesend@#codes": "codesend@[data-digital-issue-item]",
    "codesend@#send": "codesend@[data-issue-digital-order]",
    "cancel@#reason": "cancel@#orderCancelReason",
    "bankconfirm@#confirm": "bankconfirm@#confirmBankActionButton",
    "bankclose@#confirm": "bankclose@#confirmBankActionButton",
    "bankclose@#calculation": "bankclose@#bankConfirmationDescription",
    "rateconfirm@#confirm": "rateconfirm@#confirmBankActionButton",
    "home@.profile-card": "home@.status-profile",
    "home@.profile-summary": "home@.status-profile",
    "child@.profile-card": "child@.status-profile",
    "child@.profile-summary": "child@.status-profile",
    "home@[data-child-id]": "home@[data-active-student]",
    "wallet@[data-child-id]": "wallet@[data-active-student]",
    "contacts@.contact-student": "contacts@[data-access-child] summary",
    "contacts@[data-toggle-link]": "contacts@[data-toggle-contact]",
    'profiledata@[name="group_name_choice"]': 'profiledata@[data-student-profile-choice="group_name"]',
    'profiledata@[name="teacher_name_choice"]': 'profiledata@[data-student-profile-choice="teacher_name"]',
    "qr@#studentQrPreviewDialog": "qr@#studentQrDialogTitle",
    "qrlist@#studentGroupFilter": "qrlist@#teacherQrGroupFilter",
    "qrlist@.student-card": "qrlist@.teacher-qr-card",
    "registry@[data-open-student]": "registry@[data-open-student-profile]",
    "report@#reportDateFrom": "report@#acReportDateFrom",
    "report@#reportTeacherFilter": "report@#acReportTeacherFilter",
    "rules@.accrual-rule-row": "rules@[data-accrual-rule-row]",
    "staffname@[data-save-managed-staff-profile]": "staffname@[data-save-staff-profile]",
    "staffhome@#teacherProfileButton": "staffhome@#editTeacherProfileButton",
    "store@#productSort": "store@#productSortMenu summary",
    "store@[data-add-product]": "store@[data-add]",
    "store@[data-favorite-product]": "store@[data-favorite]",
    "store@Избранное": "store@#favoritesFilter",
    "products@[data-toggle-product]": "products@[data-toggle-product-status]",
    "news@#broadcastDraftStatus": "news@#broadcastDraftState",
    "news@Добавить фото": "news@#broadcastPhotoFile",
    "notifications@[data-staff-notification-key]": "notifications@.staff-notification-row",
    "venue@#broadcastVenueEditorGroups": "venue@#broadcastVenueGroupList",
    "support@Прикрепить фото": "support@.support-file-label",
    "tickets@#inbox": 'tickets@[data-support-tab="inbox"]',
    "tickets@#status": "tickets@[data-support-filter]",
    "tickets@#ticket": "tickets@.support-ticket-number",
    "tickets@#next": "tickets@#supportNext",
    "feedback@#group": "feedback@[data-feedback-group]",
    "feedback@#course": 'feedbackassign@[name="course"]',
    "feedback@#lesson": "feedback@[data-feedback-row]",
    "feedback@#feedbackActiveLesson": "feedback@[data-feedback-row]",
    "feedback@#absent": 'feedback@[name="extraAbsent"]',
    "feedback@#prepare": "feedback@.feedback-generate",
    "feedback@#copy": "feedback@[data-feedback-copy]",
    "feedbackmanual@#manual": "feedbackmanual@#feedbackTab-manual",
    "feedbackmanual@#course": "feedbackmanual@#feedbackCourse",
    "feedbackmanual@#absent": 'feedbackmanual@[name="extraAbsent"]',
    "feedbackmanual@#coins": 'feedbackmanual@[name="coins"]',
    "feedbackmanual@#prepare": "feedbackmanual@.feedback-generate",
    "feedbackmanual@#copy": "feedbackmanual@[data-feedback-copy]",
    "schedule@#schedule": "schedule@.feedback-schedule-settings summary",
    "schedule@#date": 'schedule@[data-feedback-schedule-row] [name="date"]',
    "schedule@#repeat": 'schedulerepeat@#feedbackRepeatForm [type="submit"]',
    "schedule@#add": "schedule@[data-feedback-add-custom]",
    "schedule@#disabled": 'schedule@[name="skipped"]',
    "schedule@#save": 'schedule@#feedbackScheduleForm [type="submit"]',
    "schedule@#feedbackActiveLesson": "schedule@[data-feedback-row]",
    "assemble@[data-fulfillment-confirm]": "assemble@[data-fulfillment-confirm-picks]",
    "distribute@[data-fulfillment-confirm]": "distribute@[data-fulfillment-deliver-selected]",
    'orders@[data-order-status="assign"]': 'orders@[data-order-status="fulfillment_assign"]',
    'orders@[data-order-status="collect"]': 'orders@[data-order-status="fulfillment_collect"]',
    'orders@[data-order-status="route"]': 'orders@[data-order-status="fulfillment_route"]',
    'orders@[data-order-status="awaiting_delivery"]': 'orders@[data-order-status="fulfillment_route"]',
    "teacherorders@Учитель получил": 'teacherorders@[data-order-action="transfer"]',
    "teacherorders@Передать ученику": 'teacherorders@[data-order-action="issue"]',
    "teacherorders@.order-card": "teacherorders@.order-card",
    "warehouses@#warehousePreferenceSaveButton": "warehouses@#saveWarehousePreferenceButton",
    "registry@.student-registry-row": "registry@.student-registry-card",
    "crop@#apply": "crop@[data-apply-product-crop]",
}


TOP = [
    (
        "parent",
        "Регистрация родителя",
        "mail",
        ["parent", "staff"],
        "Как родителю подключить ребёнка?",
    ),
    (
        "student",
        "Регистрация ученика",
        "qr-code",
        ["parent", "student", "staff"],
        "Как ученику зарегистрироваться после родителя?",
    ),
    ("import", "Импорт учеников", "file-input", ["staff"], "Как загрузить учеников из Excel?"),
    ("physical", "Физический товар", "package-plus", ["staff"], "Как добавить физический товар?"),
    (
        "electronic",
        "Электронный: под заказ и мгновенно",
        "key-round",
        ["staff"],
        "Как добавить цифровой товар?",
    ),
    (
        "codes",
        "Выдача электронных кодов",
        "send",
        ["staff"],
        "Как отправить код по электронному заказу?",
    ),
    (
        "checkout",
        "Оформление заказа",
        "shopping-cart",
        ["parent", "student", "staff"],
        "Как оформить заказ?",
    ),
    ("assign", "Назначение склада заказу", "warehouse", ["staff"], "Как назначить склад заказу?"),
    ("assembly", "Сборка и доставка", "truck", ["staff"], "Как собрать и распределить заказы?"),
    (
        "issue",
        "Выдача ученику",
        "package-check",
        ["staff"],
        "Как преподавателю выдать заказ ученику?",
    ),
    (
        "history",
        "История AC",
        "wallet",
        ["parent", "student", "staff"],
        "Где посмотреть, за что начислили или списали AC?",
    ),
    (
        "audit",
        "История действий и аудит",
        "history",
        ["staff"],
        "Где посмотреть, кто изменил товар, заказ или доступ?",
    ),
    (
        "access",
        "Сброс связей и повторный вход",
        "unlink",
        ["staff"],
        "Как отвязать аккаунт родителя или ученика и подключить его заново?",
    ),
    (
        "invite",
        "Приглашение сотрудника",
        "user-plus",
        ["staff"],
        "Как пригласить сотрудника по ссылке?",
    ),
    ("edit", "Редактирование ученика", "user-pen", ["staff"], "Как редактировать ученика?"),
    (
        "grants",
        "Начисление AC",
        "coins",
        ["staff"],
        "Как начислить AC одному или нескольким ученикам?",
    ),
    (
        "report",
        "Отчёт начислений",
        "file-chart-column",
        ["staff"],
        "Где посмотреть отчёт по начислениям?",
    ),
    ("bank", "Вклад ученика", "landmark", ["student", "staff"], "Как открыть вклад?"),
    (
        "bankhistory",
        "История вклада",
        "calendar-clock",
        ["parent", "student", "staff"],
        "Где посмотреть историю вклада?",
    ),
    (
        "rate",
        "Ставка и вклады города",
        "percent",
        ["staff"],
        "Где посмотреть вклады учеников и изменить ставку?",
    ),
    (
        "broadcast",
        "Рассылка новости",
        "megaphone",
        ["staff"],
        "Как создать и отправить новость?",
    ),
    (
        "feedback",
        "Обратная связь по группе",
        "message-square-text",
        ["staff"],
        "Как подготовить обратную связь по своей группе?",
    ),
    (
        "support",
        "Заявка в поддержку",
        "life-buoy",
        ["parent", "student", "staff"],
        "Как отправить заявку из мини-приложения?",
    ),
    (
        "save",
        "Не видна кнопка сохранения",
        "save",
        ["parent", "student", "staff"],
        "Почему в окне не видно кнопку сохранения?",
    ),
    (
        "connections",
        "Экспорт подключений",
        "file-spreadsheet",
        ["staff"],
        "Как выгрузить подключения учеников и родителей в Excel?",
    ),
]
