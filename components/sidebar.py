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

        # Navigation (sans recharger l'application côté utilisateur)
        def _set_page(page: str):
            st.session_state["active_page"] = page

        # Get current page for active state styling
        active_page = st.session_state.get("active_page", "live")
        
        # Navigation buttons with dynamic styling based on active state
        live_type = "primary" if active_page == "live" else "secondary"
        future_type = "primary" if active_page == "future" else "secondary"

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

        st.markdown("</div>", unsafe_allow_html=True)

        # Theme selector in sidebar
        st.markdown("<div class='sidebar-section'>", unsafe_allow_html=True)
        st.markdown(f"<p class='sidebar-label'>🎨 Thème actuel: {theme_config['icon']} {theme_config['name']}</p>", unsafe_allow_html=True)
        
        # Quick theme switcher
        theme_cols = st.columns(3)
        theme_options = [
            ("dark_pro", "🌙"),
            ("light_pro", "☀️"),
            ("blue_sky", "🌤️"),
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
        
        # Afficher quelques stats si disponibles
        if "last_refresh" in st.session_state:
            st.caption(f"Dernière maj: {st.session_state.get('last_refresh', 'N/A')}")
        
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='sidebar-footer'>© Predict IA FOOTBALL 2024</div>", unsafe_allow_html=True)
