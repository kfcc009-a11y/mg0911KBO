"""2026 KBO Supabase Streamlit 대시보드.

필수 Streamlit Secrets:
SUPABASE_URL = "https://<project-ref>.supabase.co"
SUPABASE_KEY = "sb_publishable_..."

관리자 CRUD를 사용할 때만 추가:
SUPABASE_ADMIN_KEY = "sb_secret_..."
ADMIN_PASSWORD = "충분히 긴 관리자 비밀번호"
"""

from __future__ import annotations

import hmac
import html as html_lib
from datetime import date, datetime, time
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client, create_client


st.set_page_config(page_title="2026 KBO 대시보드", page_icon="⚾", layout="wide")

STATUS_LABEL = {
    "scheduled": "예정",
    "live": "진행 중",
    "finished": "종료",
    "cancelled": "취소",
    "postponed": "연기",
}

TEAM_STYLE = {
    "KT": {"color": "#E60012", "code": "KT"},
    "삼성": {"color": "#074CA1", "code": "SS"},
    "LG": {"color": "#C30452", "code": "LG"},
    "KIA": {"color": "#EA0029", "code": "HT"},
    "두산": {"color": "#131230", "code": "OB"},
    "NC": {"color": "#315288", "code": "NC"},
    "한화": {"color": "#FC4E00", "code": "HH"},
    "SSG": {"color": "#CE0E2D", "code": "SK"},
    "롯데": {"color": "#041E42", "code": "LT"},
    "키움": {"color": "#570514", "code": "WO"},
}


def logo_url(short_name: str, stored_url: str | None = None) -> str:
    if stored_url:
        return stored_url
    code = TEAM_STYLE.get(short_name, {}).get("code", "")
    return (
        "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/"
        f"emblem/regular/2026/initial_{code}.png"
    )


def team_color(short_name: str) -> str:
    return TEAM_STYLE.get(short_name, {}).get("color", "#2563EB")

TABLE_CONFIG = {
    "seasons": {
        "label": "시즌",
        "pk": ["season_id"],
        "fields": {
            "season_id": ("시즌 ID", "int", False),
            "year": ("연도", "int", False),
            "season_name": ("시즌명", "text", False),
            "start_date": ("시작일", "date", True),
            "end_date": ("종료일", "date", True),
        },
    },
    "teams": {
        "label": "구단",
        "pk": ["team_id"],
        "fields": {
            "team_id": ("구단 ID", "int", False),
            "team_name": ("구단명", "text", False),
            "short_name": ("구단 약칭", "text", False),
            "city": ("연고지", "text", False),
            "home_stadium": ("홈구장", "text", False),
            "logo_url": ("로고 URL", "text", True),
        },
    },
    "games": {
        "label": "경기",
        "pk": ["game_id"],
        "fields": {
            "game_id": ("경기 ID", "int", False),
            "season_id": ("시즌", "season", False),
            "game_datetime": ("경기 일시", "datetime", False),
            "home_team_id": ("홈팀", "team", False),
            "away_team_id": ("원정팀", "team", False),
            "stadium_name": ("경기장", "text", False),
            "home_score": ("홈 점수", "int", True),
            "away_score": ("원정 점수", "int", True),
            "game_status": ("경기 상태", "status", False),
            "winning_team_id": ("승리팀", "team_nullable", True),
            "notes": ("비고", "textarea", True),
        },
    },
    "team_standings": {
        "label": "구단 순위",
        "pk": ["standing_id"],
        "fields": {
            "standing_id": ("순위 ID", "int", False),
            "season_id": ("시즌", "season", False),
            "team_id": ("구단", "team", False),
            "rank": ("순위", "int", False),
            "games_played": ("경기", "int", False),
            "wins": ("승", "int", False),
            "losses": ("패", "int", False),
            "draws": ("무", "int", False),
            "winning_percentage": ("승률", "float", False),
            "games_behind": ("게임차", "float", False),
            "source_updated_at": ("기준 시각", "datetime", False),
        },
    },
}


def get_secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


@st.cache_resource(show_spinner=False)
def client(url: str, key: str) -> Client:
    return create_client(url, key)


@st.cache_data(ttl=60, show_spinner=False)
def read_table(_client: Client, table: str, order: str, desc: bool = False) -> list[dict]:
    return _client.table(table).select("*").order(order, desc=desc).limit(1000).execute().data


def clear_and_rerun(message: str) -> None:
    st.session_state["flash"] = message
    st.cache_data.clear()
    st.rerun()


def korean_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce").dt.tz_convert("Asia/Seoul")


def game_frame(games: list[dict], team_names: dict[int, str]) -> pd.DataFrame:
    if not games:
        return pd.DataFrame()
    frame = pd.DataFrame(games)
    dt = korean_datetime(frame["game_datetime"])
    frame["경기일"] = dt.dt.strftime("%Y-%m-%d")
    frame["시간"] = dt.dt.strftime("%H:%M")
    frame["원정팀"] = frame["away_team_id"].map(team_names)
    frame["홈팀"] = frame["home_team_id"].map(team_names)
    frame["스코어"] = frame.apply(
        lambda row: "-" if pd.isna(row["away_score"]) else f'{int(row["away_score"])} : {int(row["home_score"])}',
        axis=1,
    )
    frame["상태"] = frame["game_status"].map(STATUS_LABEL).fillna(frame["game_status"])
    frame["경기장"] = frame["stadium_name"]
    frame["비고"] = frame["notes"].fillna("")
    return frame[["game_id", "경기일", "시간", "원정팀", "스코어", "홈팀", "경기장", "상태", "비고"]]


def render_game_cards(frame: pd.DataFrame, limit: int = 6) -> None:
    if frame.empty:
        st.info("표시할 경기가 없습니다.")
        return
    cards = []
    for _, row in frame.head(limit).iterrows():
        away, home = str(row["원정팀"]), str(row["홈팀"])
        status = str(row["상태"])
        badge_class = {
            "종료": "done", "예정": "ready", "취소": "cancel", "연기": "cancel", "진행 중": "live"
        }.get(status, "ready")
        cards.append(f"""
        <div class="game-card">
          <div class="game-meta"><span>{html_lib.escape(str(row['경기일']))} · {html_lib.escape(str(row['시간']))}</span><b class="status {badge_class}">{html_lib.escape(status)}</b></div>
          <div class="matchup">
            <div class="club"><img src="{logo_url(away)}" alt="{html_lib.escape(away)}"><strong>{html_lib.escape(away)}</strong><small>AWAY</small></div>
            <div class="score">{html_lib.escape(str(row['스코어']))}</div>
            <div class="club"><img src="{logo_url(home)}" alt="{html_lib.escape(home)}"><strong>{html_lib.escape(home)}</strong><small>HOME</small></div>
          </div>
          <div class="stadium">📍 {html_lib.escape(str(row['경기장']))}</div>
        </div>""")
    st.markdown('<div class="game-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def next_id(db: Client, table: str, pk: str) -> int:
    rows = db.table(table).select(pk).order(pk, desc=True).limit(1).execute().data
    return int(rows[0][pk]) + 1 if rows else 1


def normalize(value: Any, kind: str, nullable: bool) -> Any:
    if value in (None, ""):
        return None if nullable else value
    if kind in {"int", "team", "team_nullable", "season"}:
        return int(value)
    if kind == "float":
        return float(value)
    if kind == "date":
        return value.isoformat() if isinstance(value, date) else str(value)
    if kind == "datetime":
        return value.isoformat() if isinstance(value, datetime) else str(value)
    return str(value).strip()


def field_input(
    name: str,
    spec: tuple,
    value: Any,
    disabled: bool,
    teams: list[dict],
    seasons: list[dict],
    widget_key: str,
) -> Any:
    label, kind, nullable = spec
    if kind == "team" or kind == "team_nullable":
        options = ([None] if kind == "team_nullable" else []) + [row["team_id"] for row in teams]
        current = int(value) if value not in (None, "") else options[0]
        return st.selectbox(
            label, options, index=options.index(current) if current in options else 0,
            format_func=lambda x: "선택 안 함" if x is None else next(t["short_name"] for t in teams if t["team_id"] == x),
            disabled=disabled, key=widget_key,
        )
    if kind == "season":
        options = [row["season_id"] for row in seasons]
        current = int(value) if value not in (None, "") else options[0]
        return st.selectbox(label, options, index=options.index(current) if current in options else 0,
                            format_func=lambda x: next(s["season_name"] for s in seasons if s["season_id"] == x),
                            disabled=disabled, key=widget_key)
    if kind == "status":
        options = list(STATUS_LABEL)
        return st.selectbox(label, options, index=options.index(value) if value in options else 0,
                            format_func=lambda x: STATUS_LABEL[x], disabled=disabled, key=widget_key)
    if kind == "textarea":
        return st.text_area(label, value=str(value or ""), disabled=disabled, key=widget_key)
    if kind == "date":
        parsed = date.fromisoformat(str(value)[:10]) if value else date.today()
        result = st.date_input(label, value=parsed, disabled=disabled, key=widget_key)
        return None if nullable and not value and result == date.today() else result
    if kind == "datetime":
        parsed = pd.to_datetime(value).to_pydatetime().replace(tzinfo=None) if value else datetime.now().replace(second=0, microsecond=0)
        day = st.date_input(f"{label} 날짜", parsed.date(), disabled=disabled, key=widget_key + "_date")
        clock = st.time_input(f"{label} 시간", parsed.time(), disabled=disabled, key=widget_key + "_time")
        return datetime.combine(day, clock)
    if kind == "int":
        return st.number_input(label, value=int(value or 0), step=1, disabled=disabled, key=widget_key)
    if kind == "float":
        return st.number_input(label, value=float(value or 0), step=0.001, format="%.3f", disabled=disabled, key=widget_key)
    return st.text_input(label, value=str(value or ""), disabled=disabled, key=widget_key)


def admin_crud(db: Client, table: str, teams: list[dict], seasons: list[dict]) -> None:
    cfg = TABLE_CONFIG[table]
    rows = read_table(db, table, cfg["pk"][0])
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=310)
    choices = [None] + list(range(len(rows)))
    selected_index = st.selectbox(
        "수정·삭제 대상",
        choices,
        format_func=lambda i: "선택 안 함" if i is None else " / ".join(
            f"{pk}={rows[i][pk]}" for pk in cfg["pk"]
        ),
        key=f"target_{table}",
    )
    selected = rows[selected_index] if selected_index is not None else None
    create_tab, update_tab, delete_tab = st.tabs(["신규 등록", "수정", "삭제"])

    with create_tab:
        values = {}
        with st.form(f"create_{table}"):
            cols = st.columns(2)
            for idx, (name, spec) in enumerate(cfg["fields"].items()):
                initial = next_id(db, table, name) if name in cfg["pk"] and spec[1] == "int" else None
                with cols[idx % 2]:
                    values[name] = field_input(name, spec, initial, False, teams, seasons, f"create_{table}_{name}")
            submitted = st.form_submit_button("등록", type="primary")
        if submitted:
            try:
                payload = {n: normalize(values[n], s[1], s[2]) for n, s in cfg["fields"].items()}
                db.table(table).insert(payload).execute()
                clear_and_rerun("등록했습니다.")
            except Exception as exc:
                st.error(f"등록 실패: {exc}")

    with update_tab:
        if not selected:
            st.info("수정할 행을 선택하세요.")
        else:
            values = {}
            with st.form(f"update_{table}_{selected_index}"):
                cols = st.columns(2)
                for idx, (name, spec) in enumerate(cfg["fields"].items()):
                    with cols[idx % 2]:
                        values[name] = field_input(name, spec, selected.get(name), name in cfg["pk"], teams, seasons, f"update_{table}_{name}")
                submitted = st.form_submit_button("수정 저장", type="primary")
            if submitted:
                try:
                    payload = {n: normalize(values[n], s[1], s[2]) for n, s in cfg["fields"].items() if n not in cfg["pk"]}
                    query = db.table(table).update(payload)
                    for pk in cfg["pk"]:
                        query = query.eq(pk, selected[pk])
                    query.execute()
                    clear_and_rerun("수정했습니다.")
                except Exception as exc:
                    st.error(f"수정 실패: {exc}")

    with delete_tab:
        if not selected:
            st.info("삭제할 행을 선택하세요.")
        else:
            st.warning("연결된 데이터가 있으면 외래키 제약조건으로 삭제가 거부됩니다.")
            confirmed = st.checkbox("삭제 대상을 확인했습니다.", key=f"confirm_{table}_{selected_index}")
            if st.button("영구 삭제", disabled=not confirmed, key=f"delete_{table}_{selected_index}"):
                try:
                    query = db.table(table).delete()
                    for pk in cfg["pk"]:
                        query = query.eq(pk, selected[pk])
                    query.execute()
                    clear_and_rerun("삭제했습니다.")
                except Exception as exc:
                    st.error(f"삭제 실패: {exc}")


st.markdown("""
<style>
  .stApp {background:radial-gradient(circle at 85% 5%,#dbeafe 0,transparent 24%),linear-gradient(180deg,#f8fbff 0%,#fff 48%)}
  .block-container {padding-top:1.2rem;padding-bottom:3rem;max-width:1380px}
  [data-testid="stSidebar"] {background:linear-gradient(180deg,#0f172a,#172554)}
  [data-testid="stSidebar"] * {color:#f8fafc}
  [data-testid="stSidebar"] > div {padding-top:1.1rem}
  .side-brand {padding:18px 17px;margin:0 0 16px;border:1px solid rgba(255,255,255,.14);border-radius:18px;background:linear-gradient(135deg,rgba(37,99,235,.42),rgba(239,68,68,.25));box-shadow:0 12px 30px rgba(0,0,0,.18)}
  .side-brand .ball {display:inline-grid;place-items:center;width:42px;height:42px;border-radius:13px;background:white;font-size:24px;box-shadow:0 7px 18px rgba(0,0,0,.18)}
  .side-brand h2 {margin:11px 0 2px!important;font-size:1.25rem!important;color:#fff!important}.side-brand p{margin:0;color:#bfdbfe!important;font-size:.75rem;letter-spacing:1.5px;font-weight:700}
  [data-testid="stSidebar"] [role="radiogroup"] {gap:7px}
  [data-testid="stSidebar"] [role="radiogroup"] label {padding:10px 12px!important;border:1px solid transparent;border-radius:12px;background:rgba(255,255,255,.045);transition:.18s}
  [data-testid="stSidebar"] [role="radiogroup"] label:hover {background:rgba(255,255,255,.1);border-color:rgba(255,255,255,.14);transform:translateX(2px)}
  [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {background:linear-gradient(90deg,#2563eb,#7c3aed);border-color:rgba(255,255,255,.28);box-shadow:0 7px 18px rgba(37,99,235,.3)}
  [data-testid="stSidebar"] [data-testid="stExpander"] {border:1px solid rgba(255,255,255,.14);border-radius:14px;background:rgba(255,255,255,.05)}
  [data-testid="stSidebar"] .stButton button {width:100%;border-radius:11px;border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.1)}
  [data-testid="stMetric"] {background:rgba(255,255,255,.92);border:1px solid #dbe5f2;border-top:4px solid #2563eb;border-radius:16px;padding:17px;box-shadow:0 8px 24px rgba(30,64,175,.08)}
  [data-testid="stMetric"]:nth-child(2n) {border-top-color:#f97316}
  .hero {position:relative;overflow:hidden;padding:30px 34px;border-radius:24px;background:linear-gradient(120deg,#0f172a 0%,#1d4ed8 52%,#ef4444 120%);color:white;margin-bottom:22px;box-shadow:0 18px 45px rgba(30,64,175,.2)}
  .hero:after {content:'⚾';position:absolute;right:34px;top:4px;font-size:100px;opacity:.15;transform:rotate(-14deg)}
  .hero h1 {margin:0;font-size:2.25rem;letter-spacing:-1px}.hero p {margin:.55rem 0 0;color:#dbeafe;font-size:1.05rem}
  .game-grid {display:grid;grid-template-columns:1fr;gap:14px;margin:8px 0 20px}
  .game-card {background:#fff;border:1px solid #e2e8f0;border-radius:18px;padding:15px 17px;box-shadow:0 7px 22px rgba(15,23,42,.07)}
  .game-card:hover {transform:translateY(-2px);box-shadow:0 12px 28px rgba(30,64,175,.13);transition:.2s}
  .game-meta {display:flex;justify-content:space-between;align-items:center;color:#64748b;font-size:.82rem}
  .status {padding:4px 9px;border-radius:999px;font-size:.72rem}.status.done{background:#dcfce7;color:#166534}.status.ready{background:#dbeafe;color:#1d4ed8}.status.cancel{background:#fee2e2;color:#b91c1c}.status.live{background:#ffedd5;color:#c2410c}
  .matchup {display:grid;grid-template-columns:1fr 64px 1fr;align-items:center;margin:13px 0 9px}
  .club {display:flex;flex-direction:column;align-items:center;gap:4px}.club img{width:58px;height:58px;object-fit:contain}.club strong{font-size:1rem}.club small{color:#94a3b8;font-size:.62rem;letter-spacing:1px}
  .score {font-size:1.28rem;font-weight:900;text-align:center;color:#0f172a}.stadium{text-align:center;color:#64748b;font-size:.78rem;border-top:1px dashed #e2e8f0;padding-top:8px}
  .team-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:17px}
  .team-card {position:relative;overflow:hidden;background:#fff;border-radius:20px;padding:22px;border:1px solid #e2e8f0;box-shadow:0 8px 24px rgba(15,23,42,.08)}
  .team-card:before {content:'';position:absolute;left:0;top:0;bottom:0;width:7px;background:var(--team)}
  .team-head {display:flex;align-items:center;gap:20px}.team-head img{width:78px;height:78px;object-fit:contain}.team-head h3{margin:0;color:#0f172a;font-size:1.25rem}.team-head p{margin:7px 0 0;color:#64748b}.team-chip{display:inline-block;margin-top:9px;padding:4px 10px;border-radius:999px;background:color-mix(in srgb,var(--team) 12%,white);color:var(--team);font-weight:800;font-size:.75rem}
  div[data-baseweb="tab-list"] {gap:8px}button[data-baseweb="tab"] {background:#fff;border-radius:12px;padding:8px 18px;border:1px solid #e2e8f0}
  @media(max-width:800px){.game-grid,.team-grid{grid-template-columns:1fr}.hero:after{display:none}}
</style>
<div class="hero"><h1>2026 KBO LEAGUE</h1><p>10개 구단의 뜨거운 승부 · 경기 일정 · 결과 · 팀 순위</p></div>
""", unsafe_allow_html=True)

url, public_key = get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY")
if not url or not public_key:
    st.error("Streamlit Secrets에 SUPABASE_URL과 SUPABASE_KEY를 설정하세요.")
    st.stop()

public_db = client(url, public_key)
try:
    seasons = read_table(public_db, "seasons", "year", True)
    teams = read_table(public_db, "teams", "team_id")
    games = read_table(public_db, "games", "game_datetime")
    standings = read_table(public_db, "team_standings", "rank")
except Exception as exc:
    st.error(f"Supabase 데이터 조회 실패: {exc}")
    st.stop()

team_names = {row["team_id"]: row["short_name"] for row in teams}
games_df = game_frame(games, team_names)
standings_df = pd.DataFrame(standings)
if not standings_df.empty:
    standings_df["구단"] = standings_df["team_id"].map(team_names)

with st.sidebar:
    st.markdown("""
    <div class="side-brand">
      <div class="ball">⚾</div>
      <h2>KBO DATA CENTER</h2>
      <p>2026 SEASON</p>
    </div>
    """, unsafe_allow_html=True)
    menu_labels = {
        "📊 종합 현황": "종합 현황",
        "🗓️ 경기 일정·결과": "경기 일정·결과",
        "🏆 팀 순위": "팀 순위",
        "🛡️ 구단 정보": "구단 정보",
        "⚙️ 관리자 CRUD": "관리자 CRUD",
    }
    selected_menu = st.radio("NAVIGATION", list(menu_labels), label_visibility="collapsed")
    page = menu_labels[selected_menu]
    st.divider()
    if st.session_state.get("admin"):
        st.success("관리자 로그인됨")
        if st.button("로그아웃"):
            st.session_state["admin"] = False
            st.rerun()
    else:
        with st.expander("관리자 로그인"):
            password = st.text_input("관리자 비밀번호", type="password")
            if st.button("로그인"):
                expected = get_secret("ADMIN_PASSWORD")
                if expected and hmac.compare_digest(password, expected):
                    st.session_state["admin"] = True
                    st.rerun()
                else:
                    st.error("비밀번호가 올바르지 않습니다.")

if st.session_state.pop("flash", None):
    st.success("처리가 완료되었습니다.")

if page == "종합 현황":
    finished = sum(g["game_status"] == "finished" for g in games)
    scheduled = sum(g["game_status"] == "scheduled" for g in games)
    cancelled = sum(g["game_status"] == "cancelled" for g in games)
    first_team = team_names.get(standings[0]["team_id"], "-") if standings else "-"
    cols = st.columns(5)
    for col, title, value in zip(cols, ["등록 구단", "전체 경기", "종료", "예정", "현재 1위"],
                                 [len(teams), len(games), finished, scheduled, first_team]):
        col.metric(title, value)
    st.subheader("팀별 승률")
    if not standings_df.empty:
        chart = standings_df.set_index("구단")[["winning_percentage"]].rename(columns={"winning_percentage": "승률"})
        st.bar_chart(chart)
    left, right = st.columns(2)
    with left:
        st.subheader("최근 종료 경기")
        recent = games_df[games_df["상태"] == "종료"].sort_values(["경기일", "시간"], ascending=False).head(8)
        render_game_cards(recent, 6)
    with right:
        st.subheader("다가오는 경기")
        upcoming = games_df[games_df["상태"] == "예정"].sort_values(["경기일", "시간"]).head(8)
        render_game_cards(upcoming, 6)

elif page == "경기 일정·결과":
    st.header("경기 일정·결과")
    c1, c2, c3 = st.columns(3)
    with c1:
        selected_teams = st.multiselect("구단", list(team_names.values()))
    with c2:
        selected_status = st.multiselect("상태", list(STATUS_LABEL.values()))
    with c3:
        months = sorted(games_df["경기일"].str[:7].unique()) if not games_df.empty else []
        selected_month = st.selectbox("월", ["전체"] + months)
    filtered = games_df.copy()
    if selected_teams:
        filtered = filtered[filtered["홈팀"].isin(selected_teams) | filtered["원정팀"].isin(selected_teams)]
    if selected_status:
        filtered = filtered[filtered["상태"].isin(selected_status)]
    if selected_month != "전체":
        filtered = filtered[filtered["경기일"].str.startswith(selected_month)]
    st.caption(f"{len(filtered):,}경기")
    st.dataframe(filtered.drop(columns=["game_id"]), use_container_width=True, hide_index=True, height=600)
    st.download_button("CSV 다운로드", filtered.to_csv(index=False).encode("utf-8-sig"), "kbo_games.csv", "text/csv")

elif page == "팀 순위":
    st.header("2026 팀 순위")
    if standings_df.empty:
        st.info("순위 데이터가 없습니다.")
    else:
        view = standings_df[["rank", "구단", "games_played", "wins", "losses", "draws", "winning_percentage", "games_behind"]]
        view.columns = ["순위", "구단", "경기", "승", "패", "무", "승률", "게임차"]
        view.insert(1, "로고", view["구단"].map(lambda name: logo_url(name)))
        st.dataframe(
            view, use_container_width=True, hide_index=True, row_height=64,
            column_config={"로고": st.column_config.ImageColumn("엠블럼", width="small"),
                           "승률": st.column_config.NumberColumn(format="%.3f")},
        )

elif page == "구단 정보":
    st.header("구단 정보")
    cards = []
    for row in teams:
        short = row["short_name"]
        cards.append(f"""
        <div class="team-card" style="--team:{team_color(short)}">
          <div class="team-head">
            <img src="{logo_url(short, row.get('logo_url'))}" alt="{html_lib.escape(short)} 로고">
            <div><h3>{html_lib.escape(row['team_name'])}</h3>
              <p>📍 {html_lib.escape(row['city'])}<br>🏟️ {html_lib.escape(row['home_stadium'])}</p>
              <span class="team-chip">{html_lib.escape(short)}</span>
            </div>
          </div>
        </div>""")
    st.markdown('<div class="team-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)

else:
    st.header("관리자 CRUD")
    if not st.session_state.get("admin"):
        st.warning("사이드바에서 관리자 로그인이 필요합니다.")
    else:
        admin_key = get_secret("SUPABASE_ADMIN_KEY")
        if not admin_key:
            st.error("Streamlit Secrets에 SUPABASE_ADMIN_KEY를 설정해야 CRUD를 사용할 수 있습니다.")
        else:
            st.warning("관리자 작업은 즉시 데이터베이스에 반영됩니다.")
            admin_db = client(url, admin_key)
            table = st.selectbox("관리 대상", list(TABLE_CONFIG), format_func=lambda x: TABLE_CONFIG[x]["label"])
            admin_crud(admin_db, table, teams, seasons)

st.caption("데이터 기준: Supabase 저장 데이터 · 시간 표시는 Asia/Seoul 기준")
