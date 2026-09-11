"""2026 KBO 즐겨찾기 대시보드.

Streamlit Secrets:
SUPABASE_URL = "https://<project-ref>.supabase.co"
SUPABASE_KEY = "sb_publishable_..."
"""

from __future__ import annotations

import html as html_lib
from datetime import datetime

import pandas as pd
import streamlit as st
from supabase import Client, create_client


st.set_page_config(page_title="My KBO 2026", page_icon="⚾", layout="wide")

STATUS_LABEL = {
    "scheduled": "예정", "live": "진행 중", "finished": "종료",
    "cancelled": "취소", "postponed": "연기",
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


def secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


def new_client(url: str, key: str) -> Client:
    return create_client(url, key)


def logo_url(short_name: str, stored: str | None = None) -> str:
    if stored:
        return stored
    code = TEAM_STYLE.get(short_name, {}).get("code", "")
    return f"https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/emblem/regular/2026/initial_{code}.png"


def color(short_name: str) -> str:
    return TEAM_STYLE.get(short_name, {}).get("color", "#2563EB")


@st.cache_data(ttl=60, show_spinner=False)
def public_rows(_db: Client, table: str, order: str, desc: bool = False) -> list[dict]:
    return _db.table(table).select("*").order(order, desc=desc).limit(1000).execute().data


def favorite_rows(db: Client) -> list[dict]:
    return db.table("favorite_teams").select("*").order("is_primary", desc=True).order("created_at").execute().data


def flash(message: str) -> None:
    st.session_state["flash"] = message
    st.cache_data.clear()
    st.rerun()


def game_frame(games: list[dict], names: dict[int, str]) -> pd.DataFrame:
    if not games:
        return pd.DataFrame()
    frame = pd.DataFrame(games)
    dt = pd.to_datetime(frame["game_datetime"], utc=True, errors="coerce").dt.tz_convert("Asia/Seoul")
    frame["경기일"] = dt.dt.strftime("%Y-%m-%d")
    frame["시간"] = dt.dt.strftime("%H:%M")
    frame["원정팀"] = frame["away_team_id"].map(names)
    frame["홈팀"] = frame["home_team_id"].map(names)
    frame["스코어"] = frame.apply(
        lambda r: "-" if pd.isna(r["away_score"]) else f'{int(r["away_score"])} : {int(r["home_score"])}', axis=1
    )
    frame["상태"] = frame["game_status"].map(STATUS_LABEL).fillna(frame["game_status"])
    frame["경기장"] = frame["stadium_name"]
    return frame


def team_card(team: dict, standing: dict | None = None, memo: str = "", primary: bool = False) -> str:
    short = team["short_name"]
    rank = f"{standing['rank']}위" if standing else "순위 정보 없음"
    record = f"{standing['wins']}승 {standing['losses']}패 {standing['draws']}무" if standing else ""
    badge = '<span class="primary">MY NO.1</span>' if primary else ""
    memo_html = f'<div class="memo">💬 {html_lib.escape(memo)}</div>' if memo else ""
    return f"""
    <div class="team-card" style="--team:{color(short)}">
      {badge}<div class="team-head">
        <img src="{logo_url(short, team.get('logo_url'))}" alt="{html_lib.escape(short)}">
        <div><small>{html_lib.escape(team['city'])}</small><h3>{html_lib.escape(team['team_name'])}</h3>
        <p>🏟️ {html_lib.escape(team['home_stadium'])}</p></div>
      </div>
      <div class="record"><strong>{rank}</strong><span>{record}</span></div>{memo_html}
    </div>"""


def render_games(frame: pd.DataFrame, limit: int = 8) -> None:
    if frame.empty:
        st.info("조건에 맞는 경기가 없습니다.")
        return
    cards = []
    for _, row in frame.head(limit).iterrows():
        away, home, status = str(row["원정팀"]), str(row["홈팀"]), str(row["상태"])
        badge = {"종료": "done", "예정": "ready", "취소": "cancel", "연기": "cancel", "진행 중": "live"}.get(status, "ready")
        cards.append(f"""
        <div class="game-card"><div class="game-meta"><span>{row['경기일']} · {row['시간']}</span><b class="status {badge}">{status}</b></div>
          <div class="matchup"><div class="club"><img src="{logo_url(away)}"><strong>{away}</strong></div>
          <div class="score">{row['스코어']}</div><div class="club"><img src="{logo_url(home)}"><strong>{home}</strong></div></div>
          <div class="stadium">📍 {html_lib.escape(str(row['경기장']))}</div></div>""")
    st.markdown('<div class="game-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)


st.markdown("""
<style>
.stApp{background:radial-gradient(circle at 85% 3%,#dbeafe 0,transparent 24%),linear-gradient(180deg,#f8fbff,#fff 48%)}
.block-container{padding-top:1.2rem;padding-bottom:3rem;max-width:1380px}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0f172a,#172554)}[data-testid="stSidebar"] *{color:#f8fafc}
.side-brand{padding:18px;margin-bottom:16px;border:1px solid #ffffff24;border-radius:18px;background:linear-gradient(135deg,#2563eb66,#ef444444)}
.side-brand b{display:block;font-size:1.2rem;margin-top:10px}.side-brand small{color:#bfdbfe;letter-spacing:1.4px}
[data-testid="stSidebar"] [role="radiogroup"]{gap:7px}[data-testid="stSidebar"] [role="radiogroup"] label{padding:10px 12px!important;border-radius:12px;background:#ffffff0c}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:linear-gradient(90deg,#2563eb,#7c3aed);box-shadow:0 7px 18px #2563eb44}
.hero{position:relative;overflow:hidden;padding:30px 34px;border-radius:24px;background:linear-gradient(120deg,#0f172a,#1d4ed8 52%,#ef4444);color:#fff;margin-bottom:22px;box-shadow:0 18px 45px #1e40af33}
.hero:after{content:'⭐';position:absolute;right:35px;top:8px;font-size:90px;opacity:.16}.hero h1{margin:0;font-size:2.2rem}.hero p{margin:.55rem 0 0;color:#dbeafe}
[data-testid="stMetric"]{background:#fff;border:1px solid #dbe5f2;border-top:4px solid #7c3aed;border-radius:16px;padding:16px;box-shadow:0 8px 24px #1e40af14}
.team-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:17px}.team-card{position:relative;overflow:hidden;background:#fff;border-radius:20px;padding:22px;border:1px solid #e2e8f0;box-shadow:0 8px 24px #0f172a14}.team-card:before{content:'';position:absolute;left:0;top:0;bottom:0;width:7px;background:var(--team)}
.team-head{display:flex;align-items:center;gap:20px}.team-head img{width:82px;height:82px;object-fit:contain}.team-head h3{margin:2px 0;color:#0f172a}.team-head p,.team-head small{margin:0;color:#64748b}.record{display:flex;justify-content:space-between;margin-top:15px;padding:11px 13px;border-radius:12px;background:#f8fafc}.record strong{color:var(--team)}.memo{margin-top:10px;color:#475569;font-size:.85rem}.primary{position:absolute;right:14px;top:14px;padding:5px 9px;border-radius:999px;background:#fef3c7;color:#b45309;font-size:.65rem;font-weight:900}
.game-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.game-card{background:#fff;border:1px solid #e2e8f0;border-radius:18px;padding:15px 17px;box-shadow:0 7px 22px #0f172a12}.game-meta{display:flex;justify-content:space-between;color:#64748b;font-size:.82rem}.status{padding:4px 9px;border-radius:999px;font-size:.72rem}.done{background:#dcfce7;color:#166534}.ready{background:#dbeafe;color:#1d4ed8}.cancel{background:#fee2e2;color:#b91c1c}.live{background:#ffedd5;color:#c2410c}.matchup{display:grid;grid-template-columns:1fr 64px 1fr;align-items:center;margin:13px 0}.club{display:flex;flex-direction:column;align-items:center}.club img{width:58px;height:58px;object-fit:contain}.score{text-align:center;font-size:1.25rem;font-weight:900}.stadium{text-align:center;color:#64748b;font-size:.78rem;border-top:1px dashed #e2e8f0;padding-top:8px}
@media(max-width:800px){.team-grid,.game-grid{grid-template-columns:1fr}.hero:after{display:none}}
</style>
<div class="hero"><h1>MY KBO 2026</h1><p>좋아하는 팀만 모아보는 나만의 KBO 대시보드</p></div>
""", unsafe_allow_html=True)

url, key = secret("SUPABASE_URL"), secret("SUPABASE_KEY")
if not url or not key:
    st.error("Streamlit Secrets에 SUPABASE_URL과 SUPABASE_KEY를 설정하세요.")
    st.stop()

db = new_client(url, key)
try:
    teams = public_rows(db, "teams", "team_id")
    games = public_rows(db, "games", "game_datetime")
    standings = public_rows(db, "team_standings", "rank")
except Exception as exc:
    st.error(f"데이터 조회 실패: {exc}")
    st.stop()

team_by_id = {row["team_id"]: row for row in teams}
names = {row["team_id"]: row["short_name"] for row in teams}
standing_by_team = {row["team_id"]: row for row in standings}
games_df = game_frame(games, names)

with st.sidebar:
    st.markdown('<div class="side-brand"><span style="font-size:2rem">⚾</span><b>MY KBO</b><small>FAVORITE CLUB</small></div>', unsafe_allow_html=True)
    labels = {
        "🏠 홈": "홈",
        "🛡️ 구단 정보": "구단 정보",
        "📅 경기 일정/결과": "경기 일정/결과",
        "🏆 구단 순위": "구단 순위",
        "⭐ 내 즐겨찾기": "내 즐겨찾기",
        "➕ 즐겨찾기 등록": "팀 선택",
    }
    chosen = st.radio("메뉴", list(labels), label_visibility="collapsed")
    page = labels[chosen]
    st.divider()
    st.caption("🔒 개인용 싱글 사용자 모드")

message = st.session_state.pop("flash", None)
if message:
    st.success(message)

favorites = favorite_rows(db)
favorite_ids = {row["team_id"] for row in favorites}

if page == "홈":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("KBO 구단", f"{len(teams)}팀")
    c2.metric("전체 경기", f"{len(games):,}경기")
    c3.metric("내 즐겨찾기", f"{len(favorites)}팀")
    c4.metric("현재 1위", names.get(standings[0]["team_id"], "-") if standings else "-")
    if favorites:
        primary = next((f for f in favorites if f["is_primary"]), favorites[0])
        team_id = primary["team_id"]
        st.subheader(f"⭐ {names[team_id]} 주요 경기")
        mine = games_df[(games_df["home_team_id"] == team_id) | (games_df["away_team_id"] == team_id)]
        render_games(mine.sort_values("game_datetime", ascending=False), 6)
    else:
        st.info("'즐겨찾기 등록'에서 좋아하는 구단을 등록해 보세요.")

    st.subheader("🏆 현재 순위 TOP 5")
    top_rows = []
    for row in standings[:5]:
        top_rows.append({
            "순위": row["rank"], "구단": names.get(row["team_id"], "-"),
            "경기": row["games_played"], "승": row["wins"], "패": row["losses"],
            "무": row["draws"], "승률": float(row["winning_percentage"]),
        })
    st.dataframe(pd.DataFrame(top_rows), hide_index=True, use_container_width=True)

elif page == "구단 정보":
    st.header("🛡️ 2026 KBO 구단 정보")
    keyword = st.text_input("구단 검색", placeholder="구단명, 연고지 또는 홈구장을 입력하세요")
    filtered = [
        team for team in teams
        if not keyword or keyword.lower() in " ".join([
            str(team.get("team_name", "")), str(team.get("short_name", "")),
            str(team.get("city", "")), str(team.get("home_stadium", "")),
        ]).lower()
    ]
    if filtered:
        cards = [team_card(team, standing_by_team.get(team["team_id"])) for team in filtered]
        st.markdown('<div class="team-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)
    else:
        st.info("검색 조건에 맞는 구단이 없습니다.")

elif page == "경기 일정/결과":
    st.header("📅 경기 일정 및 결과")
    f1, f2, f3 = st.columns([1, 1, 1.3])
    status_options = ["전체"] + sorted(games_df["상태"].dropna().unique().tolist())
    selected_status = f1.selectbox("경기 상태", status_options)
    selected_team = f2.selectbox("구단", ["전체"] + [team["short_name"] for team in teams])
    date_range = f3.date_input("경기 기간", value=(), help="선택하지 않으면 전체 기간을 표시합니다.")

    filtered_games = games_df.copy()
    if selected_status != "전체":
        filtered_games = filtered_games[filtered_games["상태"] == selected_status]
    if selected_team != "전체":
        filtered_games = filtered_games[
            (filtered_games["원정팀"] == selected_team) | (filtered_games["홈팀"] == selected_team)
        ]
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        dates = pd.to_datetime(filtered_games["경기일"]).dt.date
        filtered_games = filtered_games[(dates >= date_range[0]) & (dates <= date_range[1])]

    st.caption(f"총 {len(filtered_games):,}경기")
    render_games(filtered_games.sort_values("game_datetime", ascending=False), max(len(filtered_games), 1))

elif page == "구단 순위":
    st.header("🏆 2026 KBO 구단 순위")
    ranking = []
    for row in standings:
        team = team_by_id.get(row["team_id"], {})
        ranking.append({
            "순위": row["rank"], "구단": team.get("team_name", "-"),
            "경기": row["games_played"], "승": row["wins"], "패": row["losses"],
            "무": row["draws"], "승률": float(row["winning_percentage"]),
            "게임차": float(row["games_behind"]),
        })
    ranking_df = pd.DataFrame(ranking)
    st.dataframe(
        ranking_df.style.background_gradient(subset=["승률"], cmap="Blues").format({"승률": "{:.3f}", "게임차": "{:.1f}"}),
        hide_index=True, use_container_width=True, height=425,
    )
    if not ranking_df.empty:
        chart = ranking_df.set_index("구단")[["승", "패"]]
        st.subheader("구단별 승·패 비교")
        st.bar_chart(chart, color=["#2563EB", "#EF4444"])

elif page == "내 즐겨찾기":
    st.header("내 즐겨찾기")
    if not favorites:
        st.info("등록된 즐겨찾기 팀이 없습니다.")
    else:
        cards = [team_card(team_by_id[f["team_id"]], standing_by_team.get(f["team_id"]), f.get("memo") or "", f["is_primary"]) for f in favorites]
        st.markdown('<div class="team-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)
        st.subheader("즐겨찾기 정보 수정·삭제")
        target = st.selectbox("팀", favorites, format_func=lambda f: names[f["team_id"]])
        with st.form("favorite_update"):
            memo = st.text_input("나만의 메모", value=target.get("memo") or "")
            primary = st.checkbox("대표 즐겨찾기 팀", value=target["is_primary"])
            update = st.form_submit_button("수정 저장", type="primary")
        if update:
            try:
                if primary:
                    db.table("favorite_teams").update({"is_primary": False, "updated_at": datetime.now().isoformat()}).neq("favorite_id", target["favorite_id"]).execute()
                db.table("favorite_teams").update({"memo": memo.strip() or None, "is_primary": primary, "updated_at": datetime.now().isoformat()}).eq("favorite_id", target["favorite_id"]).execute()
                flash("즐겨찾기 정보를 수정했습니다.")
            except Exception as exc:
                st.error(f"수정 실패: {exc}")
        confirm = st.checkbox("선택한 즐겨찾기를 삭제합니다.")
        if st.button("즐겨찾기 삭제", disabled=not confirm):
            try:
                db.table("favorite_teams").delete().eq("favorite_id", target["favorite_id"]).execute()
                flash("즐겨찾기를 삭제했습니다.")
            except Exception as exc:
                st.error(f"삭제 실패: {exc}")

elif page == "팀 선택":
    st.header("즐겨찾는 팀 등록")
    available = [team for team in teams if team["team_id"] not in favorite_ids]
    if not available:
        st.success("모든 구단을 즐겨찾기에 등록했습니다.")
    else:
        selected = st.selectbox("구단 선택", available, format_func=lambda t: t["team_name"])
        st.markdown('<div class="team-grid">' + team_card(selected, standing_by_team.get(selected["team_id"])) + "</div>", unsafe_allow_html=True)
        with st.form("favorite_create"):
            memo = st.text_input("나만의 메모", placeholder="예: 올해도 우승 가자!")
            primary = st.checkbox("대표 즐겨찾기 팀으로 설정")
            create = st.form_submit_button("⭐ 즐겨찾기 등록", type="primary")
        if create:
            try:
                if primary:
                    db.table("favorite_teams").update({"is_primary": False}).neq("team_id", selected["team_id"]).execute()
                db.table("favorite_teams").insert({"team_id": selected["team_id"], "memo": memo.strip() or None, "is_primary": primary}).execute()
                flash("즐겨찾는 팀을 등록했습니다.")
            except Exception as exc:
                st.error(f"등록 실패: {exc}")

st.caption("개인용 싱글 사용자 대시보드 · 즐겨찾기는 팀별로 한 번만 등록됩니다.")
