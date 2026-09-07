from enum import StrEnum


class TenantStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class StaffRole(StrEnum):
    SUPERADMIN = "superadmin"
    PARTNER_DIRECTOR = "partner_director"
    ADMIN = "admin"
    CURATOR = "curator"
    TEACHER = "teacher"


class AssignmentStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class StudentStatus(StrEnum):
    ACTIVE = "active"
    DEPARTED = "departed"
    ARCHIVED = "archived"


class StudentAccessRole(StrEnum):
    PARENT = "parent"
    STUDENT = "student"


class StudentAccessStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    DISPUTED = "disputed"


class StudentAccessSource(StrEnum):
    ID_ENTRY = "id_entry"
    ADMIN = "admin"
    IMPORT = "import"
    PARENT_QR = "parent_qr"


class LedgerDirection(StrEnum):
    CREDIT = "credit"
    DEBIT = "debit"
    REVERSAL = "reversal"


class LedgerCategory(StrEnum):
    ACCRUAL = "accrual"
    PURCHASE = "purchase"
    BANK = "bank"


class BankDepositStatus(StrEnum):
    ACTIVE = "active"
    MATURED = "matured"
    EARLY_CLOSED = "early_closed"
    STUDENT_INACTIVE_CLOSED = "student_inactive_closed"


class BankOperationType(StrEnum):
    OPENED = "opened"
    TOPPED_UP = "topped_up"
    INTEREST_CAPITALIZED = "interest_capitalized"
    RATE_CHANGED = "rate_changed"
    MATURED = "matured"
    EARLY_CLOSED = "early_closed"
    STUDENT_INACTIVE_CLOSED = "student_inactive_closed"


class ProductStatus(StrEnum):
    ACTIVE = "active"
    HIDDEN = "hidden"
    ARCHIVED = "archived"


class ProductFulfillmentType(StrEnum):
    WAREHOUSE = "warehouse"
    DIGITAL_CODE = "digital_code"


class ProductCodeStatus(StrEnum):
    AVAILABLE = "available"
    ISSUED = "issued"
    DISABLED = "disabled"


class WarehouseType(StrEnum):
    COMMON = "common"
    VENUE = "venue"
    PARTNER = "partner"
    EXTERNAL = "external"


class StockMovementType(StrEnum):
    INITIAL = "initial"
    ADJUSTMENT = "adjustment"
    TRANSFER = "transfer"
    RESERVE = "reserve"
    RELEASE_RESERVE = "release_reserve"
    ISSUE = "issue"
    RETURN = "return"


class OrderStatus(StrEnum):
    CREATED = "created"
    RESERVED = "reserved"
    AWAITING_DELIVERY = "awaiting_delivery"
    DELIVERED_TO_VENUE = "delivered_to_venue"
    TRANSFERRED_TO_TEACHER = "transferred_to_teacher"
    ISSUED_TO_STUDENT = "issued_to_student"
    CANCELLED = "cancelled"
    RETURNED = "returned"
    COINS_REFUNDED = "coins_refunded"
    PROBLEM = "problem"
