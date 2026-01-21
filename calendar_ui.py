import calendar as _cal
from collections import defaultdict
from html import escape

import streamlit as st


def render_month_calendar(events_by_date: dict, year: int, month: int, title: str = "📅 달력"):
    """
    events_by_date: {"YYYY-MM-DD": [ {"time":..., "title":...}, ... ] }
    - 주말(토/일) 빨간색
    - 날짜 칸에 일정 최대 3개 표시
    """
    st.subheader(title)

    cal = _cal.Calendar(firstweekday=0)  # Monday first
    month_days = cal.monthdatescalendar(year, month)

    by_day = defaultdict(list)
    for k, v in (events_by_date or {}).items():
        by_day[k].extend(v)

    dow = ["월", "화", "수", "목", "금", "토", "일"]

    html = []
    html.append("""
    <style>
      .tp-cal { width: 100%; border-collapse: collapse; table-layout: fixed; }
      .tp-cal th { padding: 8px 6px; border-bottom: 1px solid rgba(0,0,0,0.12); font-weight: 700; }
      .tp-cal td { vertical-align: top; padding: 6px; height: 110px; border: 1px solid rgba(0,0,0,0.08); overflow: hidden; }
      .tp-cal .muted { opacity: 0.45; }
      .tp-cal .daynum { font-weight: 700; margin-bottom: 4px; }
      .tp-cal .evt { font-size: 12px; line-height: 1.25; margin: 2px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .tp-cal .weekend, .tp-cal th.weekend { color: #d11a2a; }
      .tp-cal .more { font-size: 12px; opacity: 0.7; margin-top: 2px; }
    </style>
    """)

    html.append('<table class="tp-cal">')
    html.append("<thead><tr>")
    for i, d in enumerate(dow):
        cls = "weekend" if i in (5, 6) else ""
        html.append(f'<th class="{cls}">{d}</th>')
    html.append("</tr></thead><tbody>")

    for week in month_days:
        html.append("<tr>")
        for d in week:
            in_month = (d.month == month)
            key = d.strftime("%Y-%m-%d")
            evts = by_day.get(key, [])
            weekday = d.weekday()  # Mon=0..Sun=6
            weekend = weekday in (5, 6)
            cls = []
            if not in_month:
                cls.append("muted")
            if weekend:
                cls.append("weekend")
            cls_str = " ".join(cls)

            html.append(f'<td class="{cls_str}">')
            html.append(f'<div class="daynum">{d.day}</div>')
            shown = 0
            for e in evts:
                if shown >= 3:
                    break
                t = (e.get("time") or "").strip()
                ttl = (e.get("title") or "").strip()
                label = f"{t} {ttl}".strip()
                html.append(f'<div class="evt">{escape(label)}</div>')
                shown += 1
            if len(evts) > 3:
                html.append(f'<div class="more">+{len(evts)-3} 더보기</div>')
            html.append("</td>")
        html.append("</tr>")
    html.append("</tbody></table>")

    st.components.v1.html("".join(html), height=720, scrolling=True)
