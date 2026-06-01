import streamlit as st
from pathlib import Path

from utils.theme_manager import get_current_theme, set_theme, THEMES
from utils.profile_manager import get_profile, save_profile, photo_to_base64

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
        live_type       = "primary" if active_page == "live"       else "secondary"
        future_type     = "primary" if active_page == "future"    else "secondary"
        paris_type      = "primary" if active_page == "paris"     else "secondary"
        over25_type     = "primary" if active_page == "over25"    else "secondary"
        under25_type    = "primary" if active_page == "under25"   else "secondary"
        daily_type      = "primary" if active_page == "daily"     else "secondary"
        history_type    = "primary" if active_page == "history"   else "secondary"
        victories_type  = "primary" if active_page == "victories" else "secondary"

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
            "🏆 TOP VICTOIRES IA",
            key="victories_button",
            on_click=_set_page,
            args=("victories",),
            type=victories_type,
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
            "🔒 TOP -2.5 BUTS",
            key="under25_button",
            on_click=_set_page,
            args=("under25",),
            type=under25_type,
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

        # ── Bouton Paramètres ⚙️ ────────────────────────────────────────────
        st.markdown(
            "<div style='border-top:1px solid rgba(255,255,255,0.08);margin:8px 0;'></div>",
            unsafe_allow_html=True,
        )
        settings_open = st.session_state.get("settings_panel_open", False)
        settings_label = "⚙️ Paramètres  ▲" if settings_open else "⚙️ Paramètres  ▼"
        if st.button(settings_label, key="settings_toggle_btn", use_container_width=True):
            st.session_state["settings_panel_open"] = not settings_open
            st.rerun()

        if st.session_state.get("settings_panel_open", False):
            st.markdown(
                "<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);"
                "border-radius:12px;padding:14px 12px;margin:4px 0 8px;'>",
                unsafe_allow_html=True,
            )

            # ── Section Profil ───────────────────────────────────────────────
            username, photo = get_profile()
            initiale = username[0].upper() if username else "U"
            if photo:
                b64 = photo_to_base64(photo)
                avatar_html = (
                    f"<img src='data:image/png;base64,{b64}' "
                    f"style='width:56px;height:56px;border-radius:50%;"
                    f"border:2.5px solid #00d4ff;object-fit:cover;' />"
                )
            else:
                avatar_html = (
                    f"<div style='width:56px;height:56px;border-radius:50%;"
                    f"background:linear-gradient(135deg,#00d4ff,#7c3aed);"
                    f"border:2.5px solid #00d4ff;display:flex;align-items:center;"
                    f"justify-content:center;font-weight:900;font-size:22px;"
                    f"color:#fff;'>{initiale}</div>"
                )

            st.markdown(
                f"<div style='display:flex;align-items:center;gap:12px;margin-bottom:12px;'>"
                f"{avatar_html}"
                f"<div><div style='font-weight:700;font-size:0.95rem;'>{username}</div>"
                f"<div style='font-size:0.75rem;color:#888;'>Profil utilisateur</div></div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            new_name = st.text_input(
                "Nom d'utilisateur",
                value=username,
                key="profile_name_input",
                max_chars=32,
                label_visibility="collapsed",
                placeholder="Nom d'utilisateur",
            )
            uploaded = st.file_uploader(
                "Photo de profil",
                type=["png", "jpg", "jpeg", "webp"],
                key="profile_photo_upload",
                label_visibility="collapsed",
            )
            if st.button("💾 Enregistrer profil", key="save_profile_btn", use_container_width=True):
                photo_bytes = uploaded.read() if uploaded else None
                save_profile(new_name, photo_bytes)
                st.success("Profil mis à jour !")
                st.rerun()

            st.markdown(
                "<div style='border-top:1px solid rgba(255,255,255,0.08);margin:10px 0 8px;'></div>",
                unsafe_allow_html=True,
            )

            # ── Section Thèmes ───────────────────────────────────────────────
            st.markdown(
                "<div style='font-size:0.78rem;font-weight:600;color:#aaa;"
                "letter-spacing:0.05em;text-transform:uppercase;margin-bottom:10px;'>"
                "🎨 Apparence</div>",
                unsafe_allow_html=True,
            )

            theme_defs = [
                {
                    "key":   "dark_pro",
                    "icon":  "🌙",
                    "name":  "Dark Pro",
                    "desc":  "Sombre premium",
                    "bg":    "#0a0a0f",
                    "card":  "#1a1a24",
                    "accent":"#00d4ff",
                    "dot1":  "#00d4ff",
                    "dot2":  "#7c3aed",
                    "dot3":  "#00ff88",
                },
                {
                    "key":   "light_pro",
                    "icon":  "☀️",
                    "name":  "Light Pro",
                    "desc":  "Clair élégant",
                    "bg":    "#fafafa",
                    "card":  "#ffffff",
                    "accent":"#0066cc",
                    "dot1":  "#0066cc",
                    "dot2":  "#7c3aed",
                    "dot3":  "#28a745",
                },
                {
                    "key":   "white_clean",
                    "icon":  "⬜",
                    "name":  "Blanc Pur",
                    "desc":  "Minimaliste",
                    "bg":    "#ffffff",
                    "card":  "#f8f8f8",
                    "accent":"#1a56db",
                    "dot1":  "#1a56db",
                    "dot2":  "#6d28d9",
                    "dot3":  "#16a34a",
                },
            ]

            def _hex_to_rgb(h):
                h = h.lstrip("#")
                return int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)

            for td in theme_defs:
                is_active = td["key"] == current_theme_key
                border    = f"2px solid {td['accent']}" if is_active else "1px solid rgba(128,128,128,0.18)"
                # bg_card adapté : léger tint accent pour actif, neutre sinon
                _hex = td["accent"].lstrip("#")
                _r, _g, _b = int(_hex[0:2],16), int(_hex[2:4],16), int(_hex[4:6],16)
                bg_card   = f"rgba({_r},{_g},{_b},0.08)" if is_active else "rgba(128,128,128,0.04)"
                badge     = (
                    f"<span style='font-size:0.65rem;font-weight:700;color:{td['accent']};"
                    f"background:rgba({_r},{_g},{_b},0.15);border-radius:20px;"
                    f"padding:2px 8px;margin-left:auto;'>✓ Actif</span>"
                    if is_active else ""
                )
                # Mini preview: rectangle coloré avec des dots accent
                preview = (
                    f"<div style='width:44px;height:32px;border-radius:6px;"
                    f"background:{td['bg']};border:1px solid rgba(128,128,128,0.25);"
                    f"flex-shrink:0;display:flex;align-items:flex-end;"
                    f"padding:4px;gap:3px;'>"
                    f"<div style='width:10px;height:10px;border-radius:2px;"
                    f"background:{td['dot1']};'></div>"
                    f"<div style='width:10px;height:10px;border-radius:2px;"
                    f"background:{td['dot2']};'></div>"
                    f"<div style='width:10px;height:10px;border-radius:2px;"
                    f"background:{td['dot3']};'></div>"
                    f"</div>"
                )
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:10px;"
                    f"background:{bg_card};border:{border};"
                    f"border-radius:10px;padding:8px 10px;margin-bottom:6px;'>"
                    f"{preview}"
                    f"<div style='flex:1;min-width:0;'>"
                    f"<div style='display:flex;align-items:center;gap:4px;'>"
                    f"<span style='font-size:0.9rem;font-weight:700;'>{td['icon']} {td['name']}</span>"
                    f"{badge}</div>"
                    f"<div style='font-size:0.72rem;color:#888;margin-top:1px;'>{td['desc']}</div>"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )
                if not is_active:
                    if st.button(
                        f"Activer {td['name']}",
                        key=f"theme_btn_{td['key']}",
                        use_container_width=True,
                    ):
                        set_theme(td["key"])
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
