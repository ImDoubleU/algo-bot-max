from app.bot.backend_client import BackendApiError
from app.bot.keyboards import callback_button, inline_keyboard
from app.bot.models import BotResponse


def support_keyboard(stage):
    rows = []
    if stage == "role":
        rows = [[callback_button(label, f"support:role:{role}")] for role, label in (
            ("parent", "Я родитель"), ("student", "Я ученик"), ("staff", "Я сотрудник"),
        )]
    elif stage == "photos":
        rows.append([callback_button("Отправить заявку", "support:submit")])
    rows.append([callback_button("Отменить", "support:cancel")])
    return inline_keyboard(rows)


def cancel_support(bot, user_id):
    if user_id is not None and hasattr(bot.backend_client, "support_event"):
        try:
            bot.backend_client.support_event(max_user_id=user_id,
                tenant_slug=bot.current_tenant_slug(user_id), action="cancel")
        except BackendApiError:
            pass


def support_response(bot, user_id, action, **fields):
    if user_id is None or not hasattr(bot.backend_client, "support_event"):
        return BotResponse("Отправка заявки временно недоступна.",
                           bot.main_menu_attachments(user_id))
    try:
        result = bot.backend_client.support_event(max_user_id=user_id,
            tenant_slug=bot.current_tenant_slug(user_id), action=action, **fields)
    except BackendApiError as exc:
        if action == "message" and exc.status_code not in {400, 422, 429}:
            # Do not break ordinary bot commands if support is temporarily unavailable.
            return None
        text = "Не удалось отправить данные. Попробуйте ещё раз."
        if exc.status_code in {400, 429}:
            text = str(exc).split(": ", 1)[-1]
        return BotResponse(text, support_keyboard("photos" if action == "submit" else None))
    if not result.get("active"):
        if action == "message":
            return None
        return BotResponse(result.get("text", "Заявка отправлена."),
                           bot.main_menu_attachments(user_id))
    return BotResponse(result["text"], support_keyboard(result["stage"]))


def handle_support_message(bot, user_id, body):
    if not hasattr(bot.backend_client, "support_event") or user_id is None:
        return None
    text = str(body.get("text") or "").strip()
    if text.startswith("/"):
        cancel_support(bot, user_id)
        return None
    photos = [a.get("payload", {}).get("url") for a in body.get("attachments") or []
              if a.get("type") in {"image", "photo"}]
    photos = [url for url in photos if isinstance(url, str) and url]
    if len(photos) > 5:
        return BotResponse("К заявке можно прикрепить до 5 фотографий.",
                           support_keyboard("photos"))
    return support_response(bot, user_id, "message", text=text,
                            photo_urls=photos, event_id=str(body.get("mid") or ""))
