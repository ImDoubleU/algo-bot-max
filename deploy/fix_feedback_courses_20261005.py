"""Preview/apply the imported-course correction; snapshot changed rows before commit."""

import argparse
import asyncio
import copy
import json
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv('/etc/algo-max/algo-max.env')

from sqlalchemy import select  # noqa: E402

import app.db.base  # noqa: E402, F401
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.enums import StudentStatus  # noqa: E402
from app.models.feedback_schedule import FeedbackSchedule  # noqa: E402
from app.models.student import Student  # noqa: E402
from app.schemas.feedback_schedule import FeedbackScheduleData  # noqa: E402

ALIASES = {
    'Python Start 1 год': 'Питон Старт 1-й год',
    'Python Start 2 год': 'Питон Старт 2-й год',
    'Питон Старт 2й год': 'Питон Старт 2-й год',
    'Python Pro 1 год': 'Питон Профессиональный 1-й год',
    'Python Pro 2 год': 'Питон Профессиональный 2-й год',
    'Геймдизайн OLD': 'Геймдизайн',
    'Геймдизайн NEW': 'Геймдизайн',
    'Создание сайтов': 'Создание веб-сайтов',
    'ОЛИП': 'Основы логики и программирования',
    'Визуальное программирование 1 год': 'Визуальное программирование',
}


def correct(schedule, imported_courses, catalog, revision):
    result = copy.deepcopy(schedule)
    original = result['course']
    result['course'] = ALIASES.get(original, original)
    expected = {ALIASES.get(course, course) for course in imported_courses if course}
    # Only untouched automatically generated schedules can override teacher choices.
    untouched = revision == 1 and all(
        r['number'] == i and r['lesson'] == i and not r['skipped'] and not r['repeat']
        and r['date'] == (date.fromisoformat(result['rows'][0]['date'])
                          + timedelta(weeks=i - 1)).isoformat()
        for i, r in enumerate(result['rows'], 1)
    )
    if untouched and len(expected) == 1 and next(iter(expected)) in catalog:
        result['course'] = next(iter(expected))
        result['rows'] = result['rows'][:len(catalog[result['course']])]
    # Repair the observed OLIP first-row-only date edit, preserving its chosen start.
    rows = result['rows']
    if (result['course'] == 'Основы логики и программирования' and len(rows) > 1
            and rows[0]['date'] > rows[1]['date'] and all(
                r['number'] == i and r['lesson'] == i and not r['repeat'] and not r['skipped']
                and (i == 1 or r['date'] == (date.fromisoformat(rows[1]['date'])
                    + timedelta(weeks=i - 2)).isoformat())
                for i, r in enumerate(rows, 1))):
        for i, row in enumerate(rows):
            row['date'] = (date.fromisoformat(rows[0]['date']) + timedelta(weeks=i)).isoformat()
    FeedbackScheduleData.model_validate(result)
    assert result['course'] in catalog
    assert all(row['lesson'] <= len(catalog[result['course']]) for row in rows)
    return result


def read_catalog(path=None):
    source = Path(path) if path else Path(__file__).resolve().parents[1] / 'data/courses.json'
    return json.loads(source.read_text(encoding='utf-8'))


def save_backup(backup, changes):
    with Path(backup).open('x', encoding='utf-8') as out:
        json.dump(changes, out, ensure_ascii=False, indent=2)


async def main(apply, backup, catalog_path=None):
    catalog = await asyncio.to_thread(read_catalog, catalog_path)
    async with AsyncSessionLocal() as db:
        records = (await db.scalars(select(FeedbackSchedule).with_for_update())).all()
        changes = []
        for record in records:
            imported = (await db.scalars(select(Student.course_name).where(
                Student.tenant_id == record.tenant_id, Student.group_name == record.group_name,
                Student.status == StudentStatus.ACTIVE))).all()
            corrected = correct(record.schedule, imported, catalog, record.revision)
            if corrected == record.schedule:
                continue
            changes.append({'id': str(record.id), 'group': record.group_name,
                            'revision': record.revision, 'before': record.schedule,
                            'after': corrected})
            print(record.group_name, record.schedule['course'], '->', corrected['course'],
                  len(corrected['rows']), 'lessons; first:', corrected['rows'][0]['date'])
            if apply:
                record.schedule = corrected
                record.revision += 1
        if apply:
            await asyncio.to_thread(save_backup, backup, changes)
            await db.commit()
        else:
            await db.rollback()
        print('Applied' if apply else 'Preview:', len(changes), 'schedule corrections')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup', default='/tmp/feedback-courses-before-20261005.json')
    parser.add_argument('--catalog', help='Use a staged catalog when previewing before deployment')
    args = parser.parse_args()
    asyncio.run(main(args.apply, args.backup, args.catalog))
