import json
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from deploy.fix_feedback_courses_20261005 import correct

CATALOG = json.loads(
    (Path(__file__).parents[1] / 'data/courses.json').read_text(encoding='utf-8')
)


def schedule(course='Python Start 1 год', count=36):
    return {'course': course, 'mode': 'group', 'rows': [
        {'id': str(uuid4()), 'number': i + 1, 'lesson': i + 1,
         'date': (date(2026, 9, 5) + timedelta(weeks=i)).isoformat(),
         'repeat': False, 'skipped': False} for i in range(count)
    ]}


def test_automatic_wrong_course_is_corrected_and_cropped():
    old = schedule()
    new = correct(old, ['Основы логики и программирования'], CATALOG, 1)
    assert new['course'] == 'Основы логики и программирования'
    assert len(new['rows']) == 32
    assert new['rows'][0] == old['rows'][0]
    assert old['course'] == 'Python Start 1 год'


def test_edited_course_choice_is_preserved():
    old = schedule('ОЛИП', 32)
    new = correct(old, ['Питон Старт 1-й год'], CATALOG, 2)
    assert new['course'] == 'Основы логики и программирования'
    assert new['rows'] == old['rows']


def test_observed_first_date_error_is_fixed_from_first_lesson():
    old = schedule('ОЛИП', 32)
    old['rows'][0]['date'] = '2026-10-03'
    new = correct(old, ['Основы логики и программирования'], CATALOG, 2)
    assert new['rows'][0]['date'] == '2026-10-03'
    assert new['rows'][1]['date'] == '2026-10-10'
    assert new['rows'][4]['date'] == '2026-10-31'
    assert [r['id'] for r in new['rows']] == [r['id'] for r in old['rows']]


def test_old_game_design_is_removed_without_losing_rows():
    old = schedule('Геймдизайн OLD')
    new = correct(old, ['Геймдизайн'], CATALOG, 2)
    assert 'Геймдизайн OLD' not in CATALOG
    assert new['course'] == 'Геймдизайн'
    assert new['rows'] == old['rows']


def test_ambiguous_graphic_design_keeps_existing_materials():
    old = schedule('Графический дизайн Middle', 32)
    new = correct(old, ['Графический дизайн 12-14'], CATALOG, 1)
    assert new == old
