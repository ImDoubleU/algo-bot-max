from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINIAPP = ROOT / "app" / "web" / "static" / "miniapp"


def test_demo_students_are_active_for_role_previews() -> None:
    source = (MINIAPP / "app-core.js").read_text(encoding="utf-8")
    match = re.search(r"let students = \[(.*?)\];\s*\n\s*let accessLinks", source, re.DOTALL)

    assert match is not None
    student_block = match.group(1)
    assert student_block.count('status: "active"') == 3


def test_miniapp_static_assets_share_cache_version() -> None:
    source = (MINIAPP / "index.html").read_text(encoding="utf-8")
    versions = re.findall(r"(?:styles|app(?:-[a-z]+)?)\.js?\?v=([0-9.]+)", source)

    # CSS is captured separately because its extension is not JavaScript.
    versions.extend(re.findall(r"styles\.css\?v=([0-9.]+)", source))
    assert versions
    assert set(versions) == {"0.91.28"}


def test_help_contains_searchable_accordion_and_full_faq() -> None:
    index_source = (MINIAPP / "index.html").read_text(encoding="utf-8")
    help_source = (MINIAPP / "app-help.js").read_text(encoding="utf-8")
    styles_source = (MINIAPP / "styles.css").read_text(encoding="utf-8")

    assert "Скоро..." not in index_source
    assert 'id="helpSearchInput"' in index_source
    assert 'id="helpCategoryFilters"' in index_source
    assert 'app-help.js?v=0.91.28' in index_source
    assert help_source.count("\n  helpFaq(") >= 125
    assert "Родителю нужно подтвердить связь" in help_source
    assert "Может ли ученик войти до подключения родителя?" in help_source
    assert "его привязка сохранится" in help_source
    assert "Что произойдёт после отзыва родительской связи?" in help_source
    assert '{ id: "popular"' not in help_source
    assert "MAX-профил" not in help_source
    assert "images: options.images || []" in help_source
    assert "/miniapp/static/assets/help/" in help_source
    assert "helpVisibleCount" not in index_source
    assert "categoryItems.length}" not in help_source
    assert '<details class="help-faq-item">' in help_source
    assert "function renderHelpFaq()" in help_source
    assert ".help-faq-item[open]" in styles_source
    assert ".help-faq-figure" in styles_source
    assert "Как редактировать ученика?" in help_source
    assert "Что делать, если вход не подтверждён или нет доступа?" in help_source
    assert "Что делать, если данные не принимаются?" in help_source
    assert "Почему не сохраняется карточка ученика?" in help_source

    category_labels = [
        "1. С чего начать",
        "2. Вход и доступ",
        "3. Астрокоины",
        "4. Магазин и заказы",
        "5. Банк",
        "6. Работа преподавателя",
        "7. Рассылки и отчёты",
        "8. Управление",
        "9. Если что-то не работает",
    ]
    assert [help_source.index(label) for label in category_labels] == sorted(
        help_source.index(label) for label in category_labels
    )

    screenshot_paths = set(
        re.findall(r'src: "/miniapp/static/(assets/help/[^"]+)"', help_source)
    )
    assert len(screenshot_paths) == 9
    for screenshot_path in screenshot_paths:
        assert (MINIAPP / screenshot_path).is_file()


def test_teacher_qr_shows_parent_and_student_connections_independently() -> None:
    index_source = (MINIAPP / "index.html").read_text(encoding="utf-8")
    core_source = (MINIAPP / "app-core.js").read_text(encoding="utf-8")
    shell_source = (MINIAPP / "app-shell.js").read_text(encoding="utf-8")
    styles_source = (MINIAPP / "styles.css").read_text(encoding="utf-8")
    communications_source = (MINIAPP / "app-communications.js").read_text(
        encoding="utf-8"
    )

    assert "parentConnected: Boolean(student.parent_connected)" in core_source
    assert "Родителю нужно подтвердить связь" in shell_source
    assert "перейти по персональной ссылке" in shell_source
    assert 'data.parent_connected !== false' in communications_source
    assert 'data.student_connected === true' in communications_source
    assert "Родитель подключен" in communications_source
    assert "Родитель не подключен" in communications_source
    assert "Ученик подключен" in communications_source
    assert "Ученик не подключен" in communications_source
    assert "teacher-qr-statuses" in communications_source
    assert ".teacher-qr-statuses" in styles_source
    assert index_source.index('id="studentAccessNotice"') < index_source.index(
        'id="dashboardView"'
    )


def test_student_registry_opens_dedicated_editable_profile() -> None:
    admin_source = (MINIAPP / "app-admin.js").read_text(encoding="utf-8")
    app_source = (MINIAPP / "app.js").read_text(encoding="utf-8")

    assert 'data-open-student-profile="${escapeHtml(student.id)}"' in admin_source
    assert "function studentProfileMarkup(student)" in admin_source
    assert "data-student-profile-form" in admin_source
    assert "Системные идентификаторы" in admin_source
    assert "Связи и доступ" in admin_source
    assert '<details class="student-registry-card"' not in admin_source
    assert "openAdminStudentProfile" in app_source


def test_bank_opening_shows_projected_income_and_demo_history_survives_refresh() -> None:
    bank_source = (MINIAPP / "app-bank.js").read_text(encoding="utf-8")

    assert "/api/v1/miniapp/bank/deposits/preview" in bank_source
    assert "Расчетный доход" in bank_source
    assert "projection.projectedInterest" in bank_source
    assert "projection.projectedBalance" in bank_source
    assert "state.bankSummary && state.bankSummary.studentId === studentId" in bank_source


def test_shared_warehouse_controls_are_explicit() -> None:
    core_source = (MINIAPP / "app-core.js").read_text(encoding="utf-8")
    admin_source = (MINIAPP / "app-admin.js").read_text(encoding="utf-8")
    app_source = (MINIAPP / "app.js").read_text(encoding="utf-8")

    assert "product.can_manage !== false" in core_source
    assert "warehouse.is_owner !== false" in core_source
    assert "Товар другого города" not in admin_source
    assert "во всех подключенных городах" in app_source
    assert "Отключить склад от города" in admin_source
    assert "Сам склад, товары и общие остатки сохранятся" in app_source


def test_staff_action_menu_is_not_clipped_by_admin_panel() -> None:
    styles_source = (MINIAPP / "styles.css").read_text(encoding="utf-8")

    assert ".admin-row-menu[open] { z-index: 30; }" in styles_source
    assert ".admin-panel:has(.admin-row-menu[open]) { overflow: visible; }" in styles_source


def test_staff_cards_group_roles_and_expose_profile_management() -> None:
    core_source = (MINIAPP / "app-core.js").read_text(encoding="utf-8")
    admin_source = (MINIAPP / "app-admin.js").read_text(encoding="utf-8")
    app_source = (MINIAPP / "app.js").read_text(encoding="utf-8")

    assert "function groupedStaffAssignments" in core_source
    assert 'roleLabels.join(", ")' in admin_source
    assert "data-add-staff-role" in admin_source
    assert "data-edit-staff-profile" in admin_source
    assert "data-save-staff-profile" in admin_source
    assert "data-staff-status-filter" not in admin_source
    assert (
        'assignments: group.assignments.filter((assignment) => assignment.status === "active")'
        in admin_source
    )
    assert '.filter((group) => group.assignments.length > 0)' in admin_source
    assert 'state.staffStatusFilter' not in core_source
    assert 'dataset.staffStatusFilter' not in app_source
    assert '>Отозвать: ${escapeHtml(staffRoleLabel(assignment.role))}</button>' in admin_source
    assert "async function saveAdditionalStaffRole" in app_source
    assert "async function saveManagedStaffProfile" in app_source
    assert "/profile`" in app_source


def test_staff_qr_capabilities_cover_teachers_and_administrators() -> None:
    core_source = (MINIAPP / "app-core.js").read_text(encoding="utf-8")
    communications_source = (MINIAPP / "app-communications.js").read_text(encoding="utf-8")
    app_source = (MINIAPP / "app.js").read_text(encoding="utf-8")

    assert "function hasTeacherCapabilities" in core_source
    assert "function hasStudentQrCapabilities" in core_source
    assert "return hasTeacherCapabilities() || canManageStudentRecords();" in core_source
    assert "function studentsForStudentQrCapabilities" in core_source
    assert "const available = hasStudentQrCapabilities();" in communications_source
    assert "hasStudentQrCapabilities()" in app_source


def test_dashboard_switches_between_students_orders_and_qr_codes() -> None:
    source = (MINIAPP / "index.html").read_text(encoding="utf-8")
    core_source = (MINIAPP / "app-core.js").read_text(encoding="utf-8")
    communications_source = (MINIAPP / "app-communications.js").read_text(
        encoding="utf-8"
    )
    app_source = (MINIAPP / "app.js").read_text(encoding="utf-8")

    assert 'data-dashboard-mode="overview"' in source
    assert 'data-dashboard-mode="qr"' in source
    assert "Ученики и заказы" in source
    assert 'dashboardMode: "overview"' in core_source
    assert "overview.hidden = qrSelected;" in communications_source
    assert "state.dashboardMode = dashboardMode;" in app_source


def test_tenant_switcher_is_available_for_any_multi_tenant_account() -> None:
    shell_source = (MINIAPP / "app-shell.js").read_text(encoding="utf-8")

    assert "state.canManageTenants" in shell_source
    assert "!state.canCreateTenants || !apiContext.maxUserId" in shell_source


def test_connections_show_per_city_shop_invitation_templates() -> None:
    core_source = (MINIAPP / "app-core.js").read_text(encoding="utf-8")
    admin_source = (MINIAPP / "app-admin.js").read_text(encoding="utf-8")
    app_source = (MINIAPP / "app.js").read_text(encoding="utf-8")

    assert "session.shop_invitation_templates" in core_source
    assert "Ссылки приглашения для родителей" in admin_source
    assert "ID родителя из CRM" in admin_source
    assert "<ID_родителя>" in core_source
    assert "data-copy-shop-invitation" in admin_source
    assert "target.dataset.copyShopInvitation" in app_source


def test_admin_products_and_warehouses_have_delete_actions() -> None:
    admin_source = (MINIAPP / "app-admin.js").read_text(encoding="utf-8")
    app_source = (MINIAPP / "app.js").read_text(encoding="utf-8")

    assert 'data-delete-product="${escapeHtml(product.id)}"' in admin_source
    assert 'data-delete-warehouse="${escapeHtml(warehouse.id)}"' in admin_source
    assert "async function deleteProduct(productId)" in app_source
    assert "async function deleteWarehouse(warehouseId)" in app_source
    assert '{ method: "DELETE" }' in app_source
    assert "Товар и все его остатки будут удалены" in app_source
    assert "Сначала обнулите остатки" not in app_source


def test_product_visibility_icon_reflects_current_state() -> None:
    admin_source = (MINIAPP / "app-admin.js").read_text(encoding="utf-8")

    assert '=== "active" ? "eye" : "eye-off"' in admin_source
    assert "Товар доступен. Нажмите, чтобы скрыть" in admin_source
    assert "Товар скрыт. Нажмите, чтобы опубликовать" in admin_source


def test_accrual_rules_dialog_keeps_actions_outside_scroll_area() -> None:
    index_source = (MINIAPP / "index.html").read_text(encoding="utf-8")
    styles_source = (MINIAPP / "styles.css").read_text(encoding="utf-8")

    content_start = index_source.index('<div class="accrual-rules-content">')
    content_end = index_source.index('<div class="dialog-actions">', content_start)
    scroll_content = index_source[content_start:content_end]

    assert 'id="accrualRulesEditor"' in scroll_content
    assert 'id="addAccrualRuleButton"' in scroll_content
    assert 'id="saveAccrualRulesButton"' not in scroll_content
    assert ".accrual-rules-content" in styles_source
    assert "overflow-y: auto" in styles_source


def test_product_catalog_can_filter_by_warehouse() -> None:
    core_source = (MINIAPP / "app-core.js").read_text(encoding="utf-8")
    admin_source = (MINIAPP / "app-admin.js").read_text(encoding="utf-8")
    app_source = (MINIAPP / "app.js").read_text(encoding="utf-8")

    assert 'productWarehouseFilter: "all"' in core_source
    assert 'id="productWarehouseFilter"' in admin_source
    assert "productWarehouses(product).some" in admin_source
    assert 'target.id === "productWarehouseFilter"' in app_source


def test_product_editor_does_not_resubmit_immutable_imported_sku() -> None:
    app_source = (MINIAPP / "app.js").read_text(encoding="utf-8")

    assert 'sku: editing?.sku' not in app_source
    assert 'formData.set("sku"' not in app_source


def test_birthday_accrual_rule_is_system_managed_in_ui() -> None:
    index_source = (MINIAPP / "index.html").read_text(encoding="utf-8")
    core_source = (MINIAPP / "app-core.js").read_text(encoding="utf-8")
    store_source = (MINIAPP / "app-store.js").read_text(encoding="utf-8")
    app_source = (MINIAPP / "app.js").read_text(encoding="utf-8")

    assert 'systemKey: "birthday"' in core_source
    assert "function isBirthdayAccrualRule" in store_source
    assert "function normalizeAccrualRulesDraft" in store_source
    assert "state.accrualRulesDraft = normalizeAccrualRulesDraft" in store_source
    assert 'id="birthdayAccrualRuleEditor"' in index_source
    assert 'const systemEditor = qs("#birthdayAccrualRuleEditor")' in store_source
    assert "systemEditor.innerHTML = accrualRuleRowTemplate(birthdayRule, 0, true)" in store_source
    assert "rule.isActive && !isBirthdayAccrualRule(rule)" in store_source
    assert 'system_key: rule.systemKey || null' in store_source
    assert "if (isBirthdayAccrualRule(selectedRule))" in app_source
    assert "Можно изменить только сумму" in app_source


def test_store_uses_custom_sort_menu_and_normalized_category_keys() -> None:
    index_source = (MINIAPP / "index.html").read_text(encoding="utf-8")
    core_source = (MINIAPP / "app-core.js").read_text(encoding="utf-8")
    store_source = (MINIAPP / "app-store.js").read_text(encoding="utf-8")
    admin_source = (MINIAPP / "app-admin.js").read_text(encoding="utf-8")
    app_source = (MINIAPP / "app.js").read_text(encoding="utf-8")

    assert 'id="productSortMenu"' in index_source
    assert '<select id="productSort"' not in index_source
    assert 'data-product-sort="recommended"' in index_source
    assert "function normalizeProductCategoryName" in core_source
    assert "function productCategoryKey" in core_source
    assert "const categoryMap = new Map()" in store_source
    assert "productCategoryKey(product.category) === category" in store_source
    assert "const productCategoryMap = new Map()" in admin_source
    assert "productCategoryKey(product.category) === state.productCategoryFilter" in admin_source
    assert "const productSort = target.dataset.productSort" in app_source


def test_student_registry_shows_linked_max_teacher() -> None:
    shell_source = (MINIAPP / "app-shell.js").read_text(encoding="utf-8")
    admin_source = (MINIAPP / "app-admin.js").read_text(encoding="utf-8")

    assert "linkedTeachers: Array.isArray(item.linked_teacher_names)" in shell_source
    assert "Преподаватель в LMS" in admin_source
    assert "Преподаватели, связанные через MAX" in admin_source
    assert '(student.linkedTeachers || []).join(", ") || "Не привязаны"' in admin_source
