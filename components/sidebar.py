import streamlit as st
from pathlib import Path

from utils.theme_manager import get_current_theme, set_theme, THEMES

BASE_DIR = Path(__file__).parent.parent


def render_sidebar():
    # Using native Streamlit sidebar for accessibility; styled via CSS
    with st.sidebar:
        current_theme_key = get_current_theme()
        theme_config = THEMES.get(current_theme_key, THEMES["dark_pro"])
        
        st.markdown("<div class='sidebar-brand'>", unsafe_allow_html=True)
        png_path = BASE_DIR / "assets" / "logo3.png"
        svg_path = BASE_DIR / "assets" / "logo.svg"
        if png_path.exists():
            st.image(str(png_path), width=190)
        elif svg_path.exists():
            with open(svg_path, "r", encoding="utf-8") as f:
                svg = f.read()
            st.markdown(f"<div class='logo'>{svg}</div>", unsafe_allow_html=True)

        st.markdown("<h1 class='app-name'>PREDICT IA FOOTBALL</h1>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='sidebar-actions'>", unsafe_allow_html=True)

        # Navigation: change de page ET vide les query_params pour quitter l'analyse
        def _set_page(page: str):
            st.session_state["active_page"] = page
            st.query_params.clear()

        # Get current page for active state styling
        active_page = st.session_state.get("active_page", "live")
        
        # Navigation buttons with dynamic styling based on active state
        live_type     = "primary" if active_page == "live"     else "secondary"
        future_type   = "primary" if active_page == "future"  else "secondary"
        paris_type    = "primary" if active_page == "paris"   else "secondary"
        over25_type   = "primary" if active_page == "over25"  else "secondary"
        daily_type    = "primary" if active_page == "daily"   else "secondary"
        history_type  = "primary" if active_page == "history" else "secondary"

        if active_page == "analysis":
            st.markdown(
                "<div style='font-size:0.75rem;color:#00d4ff;text-align:center;"
                "padding:4px;border-radius:6px;background:rgba(0,212,255,0.1);"
                "margin-bottom:6px;'>📊 Analyse en cours</div>",
                unsafe_allow_html=True,
            )

        st.button(
            "🔴 Matchs en direct",
            key="live_button",
            on_click=_set_page,
            args=("live",),
            type=live_type,
            use_container_width=True,
        )
        st.button(
            "📅 Matchs futurs",
            key="future_button",
            on_click=_set_page,
            args=("future",),
            type=future_type,
            use_container_width=True,
        )

        # Séparateur + bouton PARIS
        st.markdown(
            "<div style='border-top:1px solid rgba(255,255,255,0.08);margin:8px 0;'></div>",
            unsafe_allow_html=True,
        )

        # Badge points dynamique
        try:
            from modules.betting.points_manager import get_points_info
            from modules.betting.ticket_storage import init_db
            init_db()
            pts_info = get_points_info()
            pts_label = f"🎰 PARIS  ·  {pts_info['points']} ⭐"
        except Exception:
            pts_label = "🎰 PARIS"

        st.button(
            pts_label,
            key="paris_button",
            on_click=_set_page,
            args=("paris",),
            type=paris_type,
            use_container_width=True,
        )

        st.button(
            "⚽ TOP +2.5 BUTS",
            key="over25_button",
            on_click=_set_page,
            args=("over25",),
            type=over25_type,
            use_container_width=True,
        )

        st.button(
            "🔮 PRÉDICTIONS DU JOUR",
            key="daily_button",
            on_click=_set_page,
            args=("daily",),
            type=daily_type,
            use_container_width=True,
        )

        st.button(
            "📅 HISTORIQUE",
            key="history_button",
            on_click=_set_page,
            args=("history",),
            type=history_type,
            use_container_width=True,
        )

        st.markdown("</div>", unsafe_allow_html=True)

        # --- Infos live rapides ---
        live_count = st.session_state.get("live_match_count", None)
        if live_count is not None:
            st.markdown(
                f"<div style='text-align:center;background:rgba(224,36,36,0.1);border:1px solid rgba(224,36,36,0.3);"
                f"border-radius:8px;padding:6px;margin:4px 0 8px;font-size:0.8rem;'>"
                f"<span style='color:#e02424;font-weight:700;'>● LIVE</span> "
                f"<span style='color:#ccc;'>{live_count} match(s)</span></div>",
                unsafe_allow_html=True,
            )

        # Theme selector in sidebar
        st.markdown("<div class='sidebar-section'>", unsafe_allow_html=True)
        st.markdown(f"<p class='sidebar-label'>🎨 Thème actuel: {theme_config['icon']} {theme_config['name']}</p>", unsafe_allow_html=True)
        
        # Quick theme switcher
        theme_cols = st.columns(3)
        theme_options = [
            ("dark_pro", "🌙"),
            ("light_pro", "☀️"),
            ("white_clean", "⬜"),
        ]
        
        for i, (theme_key, icon) in enumerate(theme_options):
            with theme_cols[i]:
                is_current = theme_key == current_theme_key
                if st.button(
                    icon,
                    key=f"sidebar_theme_{theme_key}",
                    type="primary" if is_current else "secondary",
                    use_container_width=True,
                ):
                    set_theme(theme_key)
                    st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)

        # Quick stats section
        st.markdown("<div class='sidebar-section'>", unsafe_allow_html=True)
        st.markdown("<p class='sidebar-label'>📊 Quick Stats</p>", unsafe_allow_html=True)

        from datetime import datetime as _dt
        _now_str = _dt.now().strftime("%H:%M:%S")

        live_count = st.session_state.get("live_match_count", None)
        future_count = st.session_state.get("future_match_count", None)

        stats_rows = []
        if live_count is not None:
            stats_rows.append(
                f"<div style='display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(128,128,128,0.15);'>"
                f"<span style='font-size:0.78rem;'>🔴 Matchs live</span>"
                f"<span style='font-size:0.78rem;font-weight:700;color:#e02424;'>{live_count}</span>"
                f"</div>"
            )
        if future_count is not None:
            stats_rows.append(
                f"<div style='display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(128,128,128,0.15);'>"
                f"<span style='font-size:0.78rem;'>📅 Matchs futurs</span>"
                f"<span style='font-size:0.78rem;font-weight:700;color:#f59e0b;'>{future_count}</span>"
                f"</div>"
            )
        stats_rows.append(
            f"<div style='display:flex;justify-content:space-between;padding:3px 0;'>"
            f"<span style='font-size:0.75rem;color:#888;'>🕐 Màj</span>"
            f"<span style='font-size:0.75rem;color:#888;'>{_now_str}</span>"
            f"</div>"
        )

        if stats_rows:
            st.markdown(
                "<div style='padding:6px 2px;'>" + "".join(stats_rows) + "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.caption("Aucune donnée disponible")

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='sidebar-footer'>© Predict IA FOOTBALL 2026</div>", unsafe_allow_html=True)
