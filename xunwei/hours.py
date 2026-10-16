"""Daily business hours, evaluated in Beijing time (opening inclusive, closing exclusive)."""
import re
from datetime import datetime, timedelta, timezone


def current_time():
    return datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M')


def valid_hours(start, end):
    return (not start and not end) or all(
        re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', value or '')
        for value in (start, end))


def business_hours(restaurant, now=None):
    row = dict(restaurant)
    start, end = row.get('opening_time'), row.get('closing_time')
    if not start or not end:
        return dict(is_open=False, label='营业时间未设置', schedule='')
    now = now or current_time()
    opened = start == end or (start <= now < end if start < end else now >= start or now < end)
    schedule = '全天营业' if start == end else f'每日 {start}–{"次日 " if start > end else ""}{end}'
    return dict(is_open=opened, label='营业中' if opened else '休息中', schedule=schedule)


# Bound times keep SQLite and MySQL ordering identical, before pagination.
OPEN_SQL = """CASE WHEN r.opening_time IS NOT NULL AND r.closing_time IS NOT NULL
    AND r.opening_time <> '' AND r.closing_time <> '' AND (
    r.opening_time = r.closing_time OR
    (r.opening_time < r.closing_time AND r.opening_time <= ? AND ? < r.closing_time) OR
    (r.opening_time > r.closing_time AND (r.opening_time <= ? OR ? < r.closing_time)))
    THEN 1 ELSE 0 END"""
