from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import (
    MaxAccount,
    StaffNotificationPreference,
    StaffRoleAssignment,
)
from app.models.enums import AssignmentStatus, StaffRole
from app.services.staff import configured_superadmin_max_user_id


@dataclass(frozen=True)
class StaffNotificationDefinition:
    key: str
    category: str
    label: str
    description: str
    admin_default: bool = False
    curator_default: bool = False


CATEGORY_LABELS = {
    "orders": "Заказы",
    "inventory": "Товары и склады",
    "students": "Импорт и ученики",
    "astrocoins": "Астрокоины",
    "broadcasts": "Рассылки",
    "staff": "Сотрудники",
}


def _item(
    key: str,
    category: str,
    label: str,
    description: str,
    *,
    admin: bool = False,
    curator: bool = False,
) -> StaffNotificationDefinition:
    return StaffNotificationDefinition(
        key=key,
        category=category,
        label=label,
        description=description,
        admin_default=admin,
        curator_default=curator,
    )


STAFF_NOTIFICATION_CATALOG = (
    _item(
        "orders.created", "orders", "Новый заказ", "Заказ ожидает назначения склада.", admin=True
    ),
    _item(
        "orders.warehouse_overdue",
        "orders",
        "Склад не назначен",
        "Заказ слишком долго остается в резерве.",
        admin=True,
    ),
    _item(
        "orders.insufficient_stock",
        "orders",
        "Не хватает товара",
        "Склад не может выполнить заказ.",
        admin=True,
    ),
    _item(
        "orders.problem",
        "orders",
        "Проблема с заказом",
        "Заказ требует ручной проверки.",
        admin=True,
    ),
    _item(
        "orders.cancelled",
        "orders",
        "Заказ отменен",
        "Причина отмены и ответственный сотрудник.",
        admin=True,
        curator=True,
    ),
    _item(
        "orders.stock_zeroed",
        "orders",
        "Товар закончился при отмене",
        "Остаток товара был обнулен.",
        admin=True,
    ),
    _item(
        "orders.delivered_to_venue",
        "orders",
        "Заказ доставлен на площадку",
        "Заказ готов к передаче преподавателю.",
        admin=True,
        curator=True,
    ),
    _item(
        "orders.transferred",
        "orders",
        "Учитель получил заказ",
        "Преподаватель подтвердил получение заказа.",
        admin=True,
        curator=True,
    ),
    _item(
        "orders.issue_overdue",
        "orders",
        "Заказ не выдан вовремя",
        "Срок выдачи заказа прошел.",
        admin=True,
        curator=True,
    ),
    _item("orders.issued", "orders", "Заказ выдан", "Заказ получен учеником.", admin=True),
    _item(
        "orders.daily_summary",
        "orders",
        "Сводка по заказам",
        "Новые, ожидающие и просроченные заказы.",
        admin=True,
    ),
    _item(
        "inventory.low_stock",
        "inventory",
        "Мало товара",
        "Остаток достиг установленного порога.",
        admin=True,
    ),
    _item(
        "inventory.digital_codes_low",
        "inventory",
        "Мало кодов для автовыдачи",
        "Количество неиспользованных кодов достигло порога.",
        admin=True,
    ),
    _item(
        "inventory.out_of_stock",
        "inventory",
        "Товар закончился",
        "На складе не осталось товара.",
        admin=True,
    ),
    _item(
        "inventory.mismatch",
        "inventory",
        "Ошибка в остатках",
        "Резерв превышает остаток или количество некорректно.",
        admin=True,
    ),
    _item(
        "inventory.adjusted",
        "inventory",
        "Остаток изменен вручную",
        "Количество товара изменено сотрудником.",
        admin=True,
    ),
    _item(
        "inventory.transferred",
        "inventory",
        "Перемещение товара",
        "Товар перемещен между складами.",
        admin=True,
    ),
    _item(
        "products.published",
        "inventory",
        "Новый товар",
        "Товар добавлен или опубликован в магазине.",
        admin=True,
        curator=True,
    ),
    _item(
        "products.changed",
        "inventory",
        "Товар изменен",
        "Изменены цена или статус товара.",
        admin=True,
    ),
    _item(
        "products.hidden",
        "inventory",
        "Товар скрыт",
        "Товар снят с продажи или архивирован.",
        admin=True,
    ),
    _item(
        "warehouses.default_missing",
        "inventory",
        "Не выбран главный склад",
        "У сотрудника не настроен главный склад.",
        admin=True,
    ),
    _item(
        "inventory.daily_summary",
        "inventory",
        "Сводка по остаткам",
        "Заканчивающиеся и отсутствующие товары.",
        admin=True,
    ),
    _item(
        "imports.completed",
        "students",
        "Импорт завершен",
        "Количество созданных и обновленных записей.",
        admin=True,
        curator=True,
    ),
    _item(
        "imports.partial",
        "students",
        "Импорт с ошибками",
        "Часть строк не удалось обработать.",
        admin=True,
    ),
    _item(
        "imports.failed",
        "students",
        "Импорт не выполнен",
        "Файл не распознан или операция прервана.",
        admin=True,
    ),
    _item(
        "students.added",
        "students",
        "Новые ученики",
        "После импорта появились новые ученики.",
        curator=True,
    ),
    _item(
        "students.departed",
        "students",
        "Ученики выбыли",
        "Ученики переведены в статус выбывших.",
        admin=True,
        curator=True,
    ),
    _item(
        "students.group_changed",
        "students",
        "Смена группы",
        "Ученик переведен в другую группу.",
        curator=True,
    ),
    _item(
        "access.linked",
        "students",
        "Родитель связан с детьми",
        "Создана новая связь доступа.",
        curator=True,
    ),
    _item(
        "access.revoked",
        "students",
        "Связь доступа нарушена",
        "Ребенок потерял доступ к приложению.",
        admin=True,
        curator=True,
    ),
    _item(
        "access.messages_blocked",
        "students",
        "Сообщения запрещены",
        "Родитель запретил сообщения бота.",
        curator=True,
    ),
    _item(
        "access.unlinked_summary",
        "students",
        "Ученики без связи",
        "Список учеников без связанного родителя.",
        curator=True,
    ),
    _item(
        "students.data_conflict",
        "students",
        "Конфликт данных",
        "Найдены дубликаты или противоречивые данные.",
        admin=True,
    ),
    _item(
        "imports.stale",
        "students",
        "Данные давно не обновлялись",
        "Импорт не выполнялся установленное время.",
        admin=True,
    ),
    _item(
        "astrocoins.large_accrual",
        "astrocoins",
        "Крупное начисление",
        "Начисление выше установленного порога.",
        curator=True,
    ),
    _item(
        "astrocoins.group_accrual",
        "astrocoins",
        "Начисление группе",
        "Преподаватель начислил астрокоины группе.",
        curator=True,
    ),
    _item(
        "astrocoins.anomaly",
        "astrocoins",
        "Необычное начисление",
        "Частые повторы или начисление вне занятия.",
        curator=True,
    ),
    _item(
        "astrocoins.failed",
        "astrocoins",
        "Начисление не выполнено",
        "При начислении произошла ошибка.",
        admin=True,
        curator=True,
    ),
    _item(
        "astrocoins.reversed",
        "astrocoins",
        "Возврат или списание",
        "Баланс ученика был скорректирован.",
        admin=True,
        curator=True,
    ),
    _item(
        "astrocoins.teacher_summary",
        "astrocoins",
        "Отчет по преподавателям",
        "Сводка начислений за выбранный период.",
        curator=True,
    ),
    _item(
        "astrocoins.no_activity",
        "astrocoins",
        "Давно не было начислений",
        "В группе нет начислений установленное время.",
        curator=True,
    ),
    _item(
        "broadcasts.completed",
        "broadcasts",
        "Рассылка завершена",
        "Количество доставленных сообщений.",
        admin=True,
        curator=True,
    ),
    _item(
        "broadcasts.partial",
        "broadcasts",
        "Рассылка выполнена частично",
        "Часть сообщений не доставлена.",
        admin=True,
        curator=True,
    ),
    _item(
        "broadcasts.failed",
        "broadcasts",
        "Рассылка не выполнена",
        "Не удалось отправить сообщения.",
        admin=True,
        curator=True,
    ),
    _item(
        "broadcasts.unreachable",
        "broadcasts",
        "Много недоступных получателей",
        "Получатели запретили сообщения или потеряли связь.",
        curator=True,
    ),
    _item(
        "staff.access_requested",
        "staff",
        "Запрос доступа сотрудника",
        "Новый сотрудник ожидает подтверждения.",
        admin=True,
    ),
    _item(
        "staff.role_changed",
        "staff",
        "Роль сотрудника изменена",
        "Роль назначена, восстановлена или отозвана.",
        admin=True,
    ),
    _item(
        "staff.unreachable",
        "staff",
        "Сотрудник недоступен",
        "Бот не может доставить сотруднику сообщения.",
        admin=True,
    ),
    _item(
        "staff.default_warehouse_changed",
        "staff",
        "Главный склад изменен",
        "Сотрудник выбрал другой главный склад.",
        admin=True,
    ),
)

CONFIGURABLE_STAFF_NOTIFICATION_KEYS = frozenset(
    {
        "orders.created",
        "orders.insufficient_stock",
        "orders.problem",
        "orders.cancelled",
        "orders.stock_zeroed",
        "orders.delivered_to_venue",
        "orders.transferred",
        "orders.issued",
        "inventory.low_stock",
        "inventory.digital_codes_low",
        "broadcasts.completed",
        "broadcasts.partial",
        "broadcasts.failed",
    }
)
STAFF_NOTIFICATION_BY_KEY = {item.key: item for item in STAFF_NOTIFICATION_CATALOG}
MANAGEABLE_NOTIFICATION_ROLES = {StaffRole.ADMIN, StaffRole.CURATOR}


def default_notification_enabled(
    definition: StaffNotificationDefinition,
    roles: set[StaffRole],
) -> bool:
    admin_enabled = bool(
        definition.admin_default
        and roles.intersection({StaffRole.SUPERADMIN, StaffRole.PARTNER_DIRECTOR, StaffRole.ADMIN})
    )
    curator_enabled = definition.curator_default and StaffRole.CURATOR in roles
    return admin_enabled or curator_enabled


async def staff_notification_user_ids(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    event_key: str,
) -> set[int]:
    definition = STAFF_NOTIFICATION_BY_KEY.get(event_key)
    if definition is None:
        return set()

    rows = (
        await db.execute(
            select(StaffRoleAssignment, MaxAccount)
            .join(MaxAccount, MaxAccount.id == StaffRoleAssignment.account_id)
            .where(
                StaffRoleAssignment.tenant_id == tenant_id,
                StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
            )
        )
    ).all()
    accounts: dict[UUID, tuple[MaxAccount, set[StaffRole]]] = {}
    configured_superadmin_id = configured_superadmin_max_user_id()
    for assignment, account in rows:
        if (
            assignment.role == StaffRole.SUPERADMIN
            and configured_superadmin_id is not None
            and account.max_user_id != configured_superadmin_id
        ):
            continue
        account_id = UUID(str(account.id))
        if account_id not in accounts:
            accounts[account_id] = (account, set())
        accounts[account_id][1].add(assignment.role)

    if configured_superadmin_id is not None:
        superadmin = await db.scalar(
            select(MaxAccount)
            .join(StaffRoleAssignment, StaffRoleAssignment.account_id == MaxAccount.id)
            .where(
                MaxAccount.max_user_id == configured_superadmin_id,
                StaffRoleAssignment.role == StaffRole.SUPERADMIN,
                StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
            )
            .limit(1)
        )
        if superadmin is not None:
            account_id = UUID(str(superadmin.id))
            if account_id not in accounts:
                accounts[account_id] = (superadmin, set())
            accounts[account_id][1].add(StaffRole.SUPERADMIN)

    if not accounts:
        return set()

    preferences = {
        UUID(str(preference.account_id)): preference.enabled
        for preference in (
            await db.scalars(
                select(StaffNotificationPreference).where(
                    StaffNotificationPreference.tenant_id == tenant_id,
                    StaffNotificationPreference.event_key == event_key,
                    StaffNotificationPreference.account_id.in_(accounts),
                )
            )
        ).all()
    }

    recipients: set[int] = set()
    for account_id, (account, roles) in accounts.items():
        if not roles.intersection(
            {
                StaffRole.SUPERADMIN,
                StaffRole.PARTNER_DIRECTOR,
                StaffRole.ADMIN,
                StaffRole.CURATOR,
            }
        ):
            continue
        enabled = default_notification_enabled(definition, roles)
        if (
            not roles.intersection({StaffRole.SUPERADMIN, StaffRole.PARTNER_DIRECTOR})
            and account_id in preferences
        ):
            enabled = preferences[account_id]
        if enabled:
            recipients.add(account.max_user_id)
    return recipients
