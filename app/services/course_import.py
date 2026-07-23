from __future__ import annotations

import json
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.teaching import Course, CourseLesson
from app.models.tenant import Tenant


class CourseImportError(RuntimeError):
    pass


def load_course_catalog(path: str | Path) -> dict[str, dict[str, dict[str, str]]]:
    source = Path(path)
    if not source.exists():
        raise CourseImportError(f"Файл курсов не найден: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CourseImportError(f"Не удалось прочитать файл курсов: {exc}") from exc
    if not isinstance(payload, dict):
        raise CourseImportError("Корень файла курсов должен быть JSON-объектом")
    return payload


def lesson_number_from_name(name: str, fallback: int) -> int:
    match = re.search(r"(\d+)(?!.*\d)", name)
    return int(match.group(1)) if match else fallback


async def import_courses_for_tenant(
    db: AsyncSession,
    *,
    tenant: Tenant,
    source_path: str | Path,
    commit: bool = True,
) -> dict[str, int | str]:
    catalog = load_course_catalog(source_path)
    existing_courses = (
        await db.scalars(
            select(Course)
            .where(Course.tenant_id == tenant.id)
            .options(selectinload(Course.lessons))
        )
    ).unique().all()
    courses_by_name = {course.name: course for course in existing_courses}

    created_courses = 0
    updated_courses = 0
    created_lessons = 0
    updated_lessons = 0
    skipped_lessons = 0

    for raw_course_name, raw_lessons in catalog.items():
        course_name = str(raw_course_name).strip()
        if not course_name or not isinstance(raw_lessons, dict):
            continue
        course = courses_by_name.get(course_name)
        if course is None:
            course = Course(tenant_id=tenant.id, name=course_name, is_active=True)
            db.add(course)
            await db.flush()
            courses_by_name[course_name] = course
            created_courses += 1
            lessons_by_number: dict[int, CourseLesson] = {}
        else:
            course.is_active = True
            updated_courses += 1
            lessons_by_number = {lesson.lesson_number: lesson for lesson in course.lessons}

        for position, (raw_lesson_name, raw_lesson) in enumerate(raw_lessons.items(), start=1):
            if not isinstance(raw_lesson, dict):
                skipped_lessons += 1
                continue
            title = str(raw_lesson_name).strip() or f"Урок {position}"
            educational_results = str(raw_lesson.get("educational_results") or "").strip()
            if not educational_results:
                skipped_lessons += 1
                continue
            lesson_number = lesson_number_from_name(title, position)
            lesson = lessons_by_number.get(lesson_number)
            if lesson is None:
                lesson = CourseLesson(
                    tenant_id=tenant.id,
                    course_id=course.id,
                    lesson_number=lesson_number,
                    title=title,
                    educational_results=educational_results,
                    image_path=str(raw_lesson.get("image") or "").strip() or None,
                )
                db.add(lesson)
                lessons_by_number[lesson_number] = lesson
                created_lessons += 1
            else:
                lesson.title = title
                lesson.educational_results = educational_results
                lesson.image_path = str(raw_lesson.get("image") or "").strip() or None
                updated_lessons += 1

    if commit:
        await db.commit()
    else:
        await db.flush()

    return {
        "tenant_slug": tenant.slug,
        "created_courses": created_courses,
        "updated_courses": updated_courses,
        "created_lessons": created_lessons,
        "updated_lessons": updated_lessons,
        "skipped_lessons": skipped_lessons,
    }
