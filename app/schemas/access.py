from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StudentAccessRole, StudentAccessSource, StudentAccessStatus


class StudentResolveRequest(BaseModel):
    tenant_slug: str = Field(min_length=2, max_length=80)
    contact_id: str = Field(min_length=1, max_length=120)
    max_user_id: int | None = Field(default=None, gt=0)


class StudentAccessTarget(BaseModel):
    student_id: UUID
    display_name: str
    group_name: str | None = None
    venue_name: str | None = None
    teacher_name: str | None = None


class ContactResolveResponse(BaseModel):
    tenant_id: UUID
    contact_id: str
    contact_display_name: str | None = None
    students: list[StudentAccessTarget]


class AccessLinkCreate(BaseModel):
    tenant_slug: str = Field(min_length=2, max_length=80)
    contact_id: str = Field(min_length=1, max_length=120)
    max_user_id: int = Field(gt=0)
    role: StudentAccessRole
    username: str | None = Field(default=None, max_length=120)
    display_name: str | None = Field(default=None, max_length=160)


class AccessLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    account_id: UUID
    student_id: UUID
    role: StudentAccessRole
    status: StudentAccessStatus
    source: StudentAccessSource
    sponsor_access_link_id: UUID | None = None
    revoked_reason: str | None = None
    created_at: datetime


class AccessLinkBatchRead(BaseModel):
    tenant_id: UUID
    contact_id: str
    links: list[AccessLinkRead]


class StudentInvitationLinkCreate(BaseModel):
    tenant_slug: str = Field(min_length=2, max_length=80)
    token: str = Field(min_length=20, max_length=120)
    max_user_id: int = Field(gt=0)
    username: str | None = Field(default=None, max_length=120)
    display_name: str | None = Field(default=None, max_length=160)


class StudentInvitationLinkRead(BaseModel):
    tenant_slug: str
    student_id: UUID
    student_name: str
    group_name: str | None = None
    link: AccessLinkRead


class BotStoppedAccessRevoke(BaseModel):
    tenant_slug: str = Field(min_length=2, max_length=80)
    max_user_id: int = Field(gt=0)
    reason: str = Field(default="bot_stopped", min_length=2, max_length=80)


class BotStoppedAccessRevokeRead(BaseModel):
    max_user_id: int
    revoked_account_links: int
    revoked_child_links: int
    affected_tenants: int
