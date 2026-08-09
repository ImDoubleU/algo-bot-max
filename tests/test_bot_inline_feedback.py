from __future__ import annotations

from typing import Any

from app.bot.keyboards import role_menu_keyboard
from app.bot.max_client import SimulationMaxClient
from app.bot.max_long_polling import LongPollingBot

COURSE_ID = "11111111-1111-1111-1111-111111111111"
OUTPUT_ID = "22222222-2222-2222-2222-222222222222"
STUDENT_ID = "33333333-3333-3333-3333-333333333333"


class FeedbackBackend:
    def __init__(self) -> None:
        self.generated: list[dict[str, Any]] = []
        self.sent: list[dict[str, Any]] = []
        self.outputs: list[dict[str, Any]] = []

    def get_session(self, *, tenant_slug: str, max_user_id: int) -> dict[str, Any]:
        return {
            "staff_roles": ["teacher"],
            "student_roles": [],
            "students": [
                {
                    "student_id": STUDENT_ID,
                    "display_name": "Иван Петров",
                    "group_name": "Python Start",
                }
            ],
        }

    def get_teaching_workspace(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
    ) -> dict[str, Any]:
        return {
            "groups": [
                {
                    "name": "Python Start",
                    "course_name": "Python",
                    "student_count": 1,
                }
            ],
            "courses": [
                {
                    "id": COURSE_ID,
                    "name": "Python",
                    "lesson_count": 12,
                }
            ],
        }

    def get_course_lessons(self, **payload: Any) -> list[dict[str, Any]]:
        return [{"lesson_number": 4, "title": "Циклы"}]

    def get_manual_feedback_outputs(self, **payload: Any) -> list[dict[str, Any]]:
        return self.outputs

    def generate_manual_feedback(self, **payload: Any) -> dict[str, Any]:
        self.generated.append(payload)
        output = {
            "id": OUTPUT_ID,
            "group_name": "Python Start",
            "feedback_text": "Добрый день! На уроке изучили циклы.",
            "status": "generated",
        }
        self.outputs.append(output)
        return output

    def send_manual_feedback(self, **payload: Any) -> dict[str, Any]:
        self.sent.append(payload)
        return {
            "parent_recipients": 1,
            "sent_recipients": 1,
            "status": "sent",
        }


def callback(bot: LongPollingBot, payload: str, *, user_id: int = 7) -> dict[str, Any]:
    bot.handle_message_callback(
        {
            "callback": {
                "payload": payload,
                "callback_id": f"callback-{payload}",
                "user": {"user_id": user_id},
                "message": {"recipient": {"chat_id": user_id}},
            }
        }
    )
    return bot.client.sent_messages[-1]


def keyboard_payloads(attachments: list[dict[str, Any]]) -> list[str]:
    return [
        button.get("payload", "")
        for row in attachments[0]["payload"]["buttons"]
        for button in row
        if button["type"] == "callback"
    ]


def test_role_menu_only_links_cabinet_and_staff_feedback(monkeypatch) -> None:
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/miniapp")

    teacher = role_menu_keyboard(
        "teacher",
        user_id=7,
        tenant_slug="n-novgorod",
        compact=False,
    )
    student = role_menu_keyboard(
        "student",
        user_id=8,
        tenant_slug="n-novgorod",
        compact=False,
    )

    teacher_buttons = teacher[0]["payload"]["buttons"]
    assert [button["text"] for row in teacher_buttons for button in row] == [
        "Открыть рабочий кабинет",
        "Обратная связь",
        "База знаний",
        "Помощь",
    ]
    assert "feedback" not in keyboard_payloads(student)


def test_text_command_redirects_to_inline_menu() -> None:
    client = SimulationMaxClient()
    bot = LongPollingBot(client, backend_client=FeedbackBackend())

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 7},
                "recipient": {"chat_id": 7},
                "body": {"text": "/catalog"},
            }
        }
    )

    assert "команды больше не используются" in client.sent_messages[-1]["text"]


def test_teacher_can_open_knowledge_base() -> None:
    client = SimulationMaxClient()
    bot = LongPollingBot(client, backend_client=FeedbackBackend())

    menu = callback(bot, "knowledge")
    assert "Выберите раздел" in menu["text"]
    assert "knowledge:hub_tables_docs" in keyboard_payloads(menu["attachments"])

    contacts = callback(bot, "knowledge:hub_contacts")
    assert "Контакты" in contacts["text"]
    assert "knowledge:contact_admin" in keyboard_payloads(contacts["attachments"])


def test_feedback_inline_flow_generates_and_sends() -> None:
    backend = FeedbackBackend()
    client = SimulationMaxClient()
    bot = LongPollingBot(client, backend_client=backend)

    menu = callback(bot, "feedback")
    assert "feedback:manual" in keyboard_payloads(menu["attachments"])

    groups = callback(bot, "feedback:manual")
    assert "feedback:group:0" in keyboard_payloads(groups["attachments"])

    courses = callback(bot, "feedback:group:0")
    assert "feedback:course:0" in keyboard_payloads(courses["attachments"])

    lessons = callback(bot, "feedback:course:0")
    assert "feedback:lesson:0" in keyboard_payloads(lessons["attachments"])

    setup = callback(bot, "feedback:lesson:0")
    assert "Все были на уроке" in setup["text"]

    selected = callback(bot, f"feedback:absent:{STUDENT_ID}")
    assert "Отсутствуют: Иван Петров" in selected["text"]

    preview = callback(bot, "feedback:generate")
    assert "Черновик ОС" in preview["text"]
    assert backend.generated[0]["absent_students"] == ["Иван Петров"]
    assert backend.generated[0]["course_id"] == COURSE_ID
    assert backend.generated[0]["lesson_number"] == 4

    sent = callback(bot, f"feedback:manual_send:{OUTPUT_ID}")
    assert "отправлена всем родителям" in sent["text"]
    assert backend.sent[0]["output_id"] == OUTPUT_ID
