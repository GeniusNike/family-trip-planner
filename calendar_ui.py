import calendar as _cal
from collections import defaultdict
from html import escape

import streamlit as st


def render_month_calendar(
    events_by_date: dict,
    year: int,
    month: int,
    title: str = "📅 달력",
    max_events_per_day: int = 6,
    cell_height_px: int = 170,
):
    """
    events_by_date: {"YYYY-MM-DD": [ {"time":..., "title":...}, ... ] }

    변경점(v3.4)
    - 일요일 시작 달력(일-토)
    - 칸 높이 증가 + 일정 표시 줄 수 확대(기본 6개)
    - 주말(토/일) 빨간색
    """
    st.subheader(title)

    # Sunday first
    cal = _cal.Calendar(firstweekday=6)  # Sunday first
    month_days = cal.monthdatescalendar(year, month)

    by_day = defaultdict(list)
    for k, v in (events_by_date or {}).items():
        by_day[k].extend(v)

    dow = ["일", "월", "화", "수", "목", "금", "토"]

    html = []
    html.append(f"""
    <style>
      .tp-cal {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
      .tp-cal th {{ padding: 8px 6px; border-bottom: 1px solid rgba(0,0,0,0.12); font-weight: 700; }}
      .tp-cal td {{ vertical-align: top; padding: 6px; height: {int(cell_height_px)}px; border: 1px solid rgba(0,0,0,0.08); overflow: hidden; }}
      .tp-cal .muted {{ opacity: 0.45; }}
      .tp-cal .daynum {{ font-weight: 800; margin-bottom: 6px; }}
      .tp-cal .evt {{ font-size: 12px; line-height: 1.25; margin: 3px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
      .tp-cal .weekend, .tp-cal th.weekend {{ color: #d11a2a; }}
      .tp-cal .more {{ font-size: 12px; opacity: 0.75; margin-top: 3px; }}
    </style>
    """)

    html.append('<table class="tp-cal">')
    html.append("<thead><tr>")
    for i, d in enumerate(dow):
        cls = "weekend" if i in (0, 6) else ""  # Sunday + Saturday
        html.append(f'<th class="{cls}">{d}</th>')
    html.append("</tr></thead><tbody>")

    for week in month_days:
        html.append("<tr>")
        for d in week:
            in_month = (d.month == month)
            key = d.strftime("%Y-%m-%d")
            evts = by_day.get(key, [])

            # Python weekday: Mon=0..Sun=6
            weekday = d.weekday()
            weekend = weekday in (5, 6)  # Sat or Sun

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
                if shown >= max_events_per_day:
                    break
                t = (e.get("time") or "").strip()
                ttl = (e.get("title") or "").strip()
                label = f"{t} {ttl}".strip()
                html.append(f'<div class="evt">{escape(label)}</div>')
                shown += 1

            if len(evts) > max_events_per_day:
                html.append(f'<div class="more">+{len(evts)-max_events_per_day} 더보기</div>')

            html.append("</td>")
        html.append("</tr>")
    html.append("</tbody></table>")

    st.components.v1.html("".join(html), height=820, scrolling=True)
