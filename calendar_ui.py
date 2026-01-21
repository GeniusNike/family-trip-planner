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
    v3.5 (모바일 개선)
    - 모바일 화면에서는 달력이 한 눈에 들어오도록 "콤팩트 모드" 자동 적용(미디어쿼리)
      * 날짜 칸 높이/글자 축소
      * 일정 텍스트는 숨기고 ● 점 + 개수만 표시
    - 데스크톱에서는 기존처럼 일정 텍스트(최대 max_events_per_day) 표시
    """
    st.subheader(title)

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
      .tp-cal .dots {{ display: none; font-size: 11px; line-height: 1.2; margin-top: 6px; opacity: 0.9; }}
      .tp-cal .dot {{ display: inline-block; margin-right: 2px; }}

      /* ✅ Mobile compact mode */
      @media (max-width: 640px) {{
        .tp-cal th {{ padding: 6px 4px; font-size: 12px; }}
        .tp-cal td {{ padding: 4px; height: 78px; }}
        .tp-cal .daynum {{ margin-bottom: 2px; font-size: 12px; }}
        .tp-cal .evt, .tp-cal .more {{ display: none; }}
        .tp-cal .dots {{ display: block; }}
      }}
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

            # Desktop list
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

            # Mobile dots summary
            if len(evts) == 0:
                html.append('<div class="dots"></div>')
            else:
                dots_n = min(5, len(evts))
                dots = "".join('<span class="dot">●</span>' for _ in range(dots_n))
                extra = f" +{len(evts)-dots_n}" if len(evts) > dots_n else ""
                html.append(f'<div class="dots">{dots}{extra}</div>')

            html.append("</td>")
        html.append("</tr>")
    html.append("</tbody></table>")

    st.components.v1.html("".join(html), height=820, scrolling=True)
