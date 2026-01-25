import calendar as _cal
from collections import defaultdict
from html import escape
from urllib.parse import urlencode

import streamlit as st


def render_month_calendar(
    events_by_date: dict,
    year: int,
    month: int,
    title: str = "📅 달력",
    max_events_per_day: int = 6,
    cell_height_px: int = 170,
    link_param: str = "jump",
    link_base_params: dict | None = None,
):
    """
    v3.7
    - 날짜(숫자)를 누르면 같은 페이지를 query param으로 다시 열도록 링크 제공
      예) ?trip=...&jump=2026-02-15
    - 페이지에서 query param(jump)을 읽어서 해당 날짜 섹션으로 스크롤/이동 처리 가능

    v3.6 유지
    - 모바일 콤팩트(● 점 + 개수), 다크모드 가독성, viewport meta
    """
    st.subheader(title)

    cal = _cal.Calendar(firstweekday=6)  # Sunday first
    month_days = cal.monthdatescalendar(year, month)

    by_day = defaultdict(list)
    for k, v in (events_by_date or {}).items():
        by_day[k].extend(v)

    dow = ["일", "월", "화", "수", "목", "금", "토"]

    def _href_for(date_str: str) -> str:
        params = dict(link_base_params or {})
        params[link_param] = date_str
        return "?" + urlencode(params)

    html = []
    html.append(f"""
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      :root {{
        --tp-border: rgba(0,0,0,0.10);
        --tp-border-strong: rgba(0,0,0,0.14);
        --tp-text: rgba(0,0,0,0.88);
        --tp-muted: rgba(0,0,0,0.45);
        --tp-bg: rgba(255,255,255,1);
        --tp-cell-bg: rgba(255,255,255,1);
        --tp-weekend: #d11a2a;
        --tp-link: rgba(0,0,0,0.88);
      }}

      @media (prefers-color-scheme: dark) {{
        :root {{
          --tp-border: rgba(255,255,255,0.14);
          --tp-border-strong: rgba(255,255,255,0.18);
          --tp-text: rgba(255,255,255,0.92);
          --tp-muted: rgba(255,255,255,0.45);
          --tp-bg: rgba(15,18,25,1);
          --tp-cell-bg: rgba(20,24,33,1);
          --tp-weekend: #ff5a66;
          --tp-link: rgba(255,255,255,0.92);
        }}
      }}

      .tp-wrap {{
        background: var(--tp-bg);
        color: var(--tp-text);
        border-radius: 12px;
        padding: 6px;
        box-sizing: border-box;
      }}
      .tp-cal {{
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        background: transparent;
      }}
      .tp-cal th {{
        padding: 8px 6px;
        border-bottom: 1px solid var(--tp-border-strong);
        font-weight: 800;
        font-size: 14px;
        color: var(--tp-text);
      }}
      .tp-cal td {{
        vertical-align: top;
        padding: 6px;
        height: {int(cell_height_px)}px;
        border: 1px solid var(--tp-border);
        overflow: hidden;
        background: var(--tp-cell-bg);
      }}
      .tp-cal .muted {{
        opacity: 0.55;
        background: transparent;
      }}
      .tp-cal .daynum {{
        font-weight: 900;
        margin-bottom: 6px;
        color: var(--tp-text);
      }}
      .tp-cal a.daylink {{
        color: var(--tp-link);
        text-decoration: none;
        display: inline-block;
        padding: 2px 6px;
        border-radius: 8px;
      }}
      .tp-cal a.daylink:hover {{
        background: rgba(120, 160, 255, 0.18);
      }}
      .tp-cal .evt {{
        font-size: 12px;
        line-height: 1.25;
        margin: 3px 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        color: var(--tp-text);
      }}
      .tp-cal .weekend, .tp-cal th.weekend {{
        color: var(--tp-weekend);
      }}
      .tp-cal .more {{
        font-size: 12px;
        opacity: 0.78;
        margin-top: 3px;
        color: var(--tp-muted);
      }}

      .tp-cal .dots {{
        display: none;
        font-size: 11px;
        line-height: 1.2;
        margin-top: 6px;
        opacity: 0.9;
        color: var(--tp-text);
      }}
      .tp-cal .dot {{
        display: inline-block;
        margin-right: 2px;
      }}

      @media (max-width: 640px) {{
        .tp-cal th {{ padding: 6px 4px; font-size: 12px; }}
        .tp-cal td {{ padding: 4px; height: 74px; }}
        .tp-cal .daynum {{ margin-bottom: 2px; font-size: 12px; }}
        .tp-cal .evt, .tp-cal .more {{ display: none; }}
        .tp-cal .dots {{ display: block; }}
      }}
    </style>
    """)

    html.append('<div class="tp-wrap">')
    html.append('<table class="tp-cal">')
    html.append("<thead><tr>")
    for i, d in enumerate(dow):
        cls = "weekend" if i in (0, 6) else ""
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

            href = _href_for(key)

            html.append(f'<td class="{cls_str}">')
            html.append(f'<div class="daynum"><a class="daylink" href="{href}">{d.day}</a></div>')

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

            if len(evts) == 0:
                html.append('<div class="dots"></div>')
            else:
                dots_n = min(5, len(evts))
                dots = "".join('<span class="dot">●</span>' for _ in range(dots_n))
                extra = f" +{len(evts)-dots_n}" if len(evts) > dots_n else ""
                html.append(f'<div class="dots">{dots}{extra}</div>')

            html.append("</td>")
        html.append("</tr>")
    html.append("</tbody></table></div>")

    st.components.v1.html("".join(html), height=820, scrolling=True)
