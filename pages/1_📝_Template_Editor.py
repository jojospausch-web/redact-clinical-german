"""Template Editor – Streamlit page for managing anonymization templates.

State-Modell (wichtig wegen historischer Bugs):
- Streamlit-Widgets mit ``key=X`` lesen IMMER aus ``st.session_state[X]``,
  sobald sie einmal gerendert wurden — das ``value=``-Argument wird in dem
  Moment ignoriert.
- Daher: wir lassen ``value=`` weg, sobald ein Widget einen ``key`` hat, und
  schreiben den Initial-/Lade-/Reset-State über ``_apply_state`` direkt nach
  ``st.session_state``. Sonst zeigen die Widgets nach „Laden" / „Neu" /
  „Löschen" / „Alle (de)aktivieren" weiter den vorigen Inhalt.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st

# Make sure the project root is on the path so we can import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.template_manager import (
    list_templates,
    load_template,
    save_template,
    delete_template,
    get_default_template,
)

# ── Page configuration ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Template Editor – Redact Clinical German",
    page_icon="📝",
    layout="wide",
)

st.title("📝 Template Editor")
st.markdown("Erstellen und verwalten Sie Anonymisierungs-Templates.")

# ── Constants ─────────────────────────────────────────────────────────────────

_DEFAULT_PATTERNS = [
    "patient_block", "case_id", "address",
    "doctor_name", "doctor_name_parentheses", "salutation_with_name",
    "doctor_with_location", "doctor_signature", "referring_doctor",
    "postal_code_with_city", "postal_code_standalone",
    "city_facility_simple", "university_hospital", "medical_facility_with_city",
    "medical_facility",
    "phone_landline", "phone_mobile", "phone_context", "email", "fax", "hk_number",
    "pacemaker_id",
]

_DEFAULT_HUK_TRIGGERS = [
    "Sehr geehrte Kollegin",
    "Sehr geehrter Kollege",
    "Sehr geehrter Herr Kollege",
    "Untersucher",
    "Herzkatheterbriefe",
    "Arztbrief",
]

# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_list(text: str):
    """Komma- oder Zeilen-getrennten Text → bereinigte Liste."""
    return [t.strip() for t in text.replace("\n", ",").split(",") if t.strip()]


def _join_list(items) -> str:
    return ", ".join(items) if items else ""


def _parse_lines(text: str):
    return [line.strip() for line in text.splitlines() if line.strip()]


def _join_lines(items) -> str:
    return "\n".join(items) if items else ""


def _pat_key(pattern_name: str) -> str:
    """Konsistente Widget-Keys für Pattern-Checkboxes."""
    return f"pat_{pattern_name}"


def _apply_state(name: str, data: dict) -> None:
    """Spielt einen Template-Stand in die Streamlit-Widget-Keys ein.

    Wird aufgerufen beim Init und nach jeder Aktion, die die Eingabefelder
    neu setzen soll (Laden, Neu, Löschen). Ohne diesen expliziten Reset
    blieben die Widgets auf ihrem vorigen Inhalt stehen.
    """
    # Template-Identität
    st.session_state["tpl_name_input"] = name or ""
    st.session_state["tpl_data"] = data or {}

    zones = (data or {}).get("zones", {}) or {}
    st.session_state["zone_header_page1"] = int(zones.get("header_page1", 380))
    st.session_state["zone_header_next"] = int(zones.get("header_next", 100))
    st.session_state["zone_footer_page1"] = int(zones.get("footer_page1", 130))
    st.session_state["zone_footer_next"] = int(zones.get("footer_next", 200))
    st.session_state["zone_signature"] = int(zones.get("signature", 150))
    st.session_state["zone_personal"] = int(zones.get("personal", 100))

    huk = (data or {}).get("header_until_keyword", {}) or {}
    st.session_state["huk_enabled"] = bool(huk.get("enabled", False))
    st.session_state["huk_triggers"] = "\n".join(
        huk.get("triggers") or _DEFAULT_HUK_TRIGGERS
    )

    ap = (data or {}).get("active_patterns", {}) or {}
    for pattern_name in _DEFAULT_PATTERNS:
        st.session_state[_pat_key(pattern_name)] = bool(ap.get(pattern_name, True))

    wl = (data or {}).get("whitelist", {}) or {}
    st.session_state["wl_medical"] = _join_list(wl.get("medical", []))
    st.session_state["wl_anatomical"] = _join_list(wl.get("anatomical", []))
    st.session_state["wl_devices"] = _join_list(wl.get("devices", []))

    st.session_state["bl_exact"] = _join_lines(
        (data or {}).get("blacklist_exact", []) or []
    )


def _collect_state() -> dict:
    """Aktuellen UI-Zustand als Template-Dict einsammeln."""
    return {
        "zones": {
            "header_page1": int(st.session_state["zone_header_page1"]),
            "header_next": int(st.session_state["zone_header_next"]),
            "footer_page1": int(st.session_state["zone_footer_page1"]),
            "footer_next": int(st.session_state["zone_footer_next"]),
            "signature": int(st.session_state["zone_signature"]),
            "personal": int(st.session_state["zone_personal"]),
        },
        "header_until_keyword": {
            "enabled": bool(st.session_state["huk_enabled"]),
            "triggers": _parse_lines(st.session_state["huk_triggers"]),
        },
        "active_patterns": {
            p: bool(st.session_state[_pat_key(p)]) for p in _DEFAULT_PATTERNS
        },
        "whitelist": {
            "medical": _parse_list(st.session_state["wl_medical"]),
            "anatomical": _parse_list(st.session_state["wl_anatomical"]),
            "devices": _parse_list(st.session_state["wl_devices"]),
        },
        "blacklist_exact": _parse_lines(st.session_state["bl_exact"]),
    }


# ── Session state initialisation ──────────────────────────────────────────────

if "tpl_data" not in st.session_state:
    _apply_state("", get_default_template())

# ── Template management section ───────────────────────────────────────────────

st.header("🗂️ Template verwalten")

col_left, col_right = st.columns([2, 1])

with col_left:
    available = list_templates()
    selected = st.selectbox(
        "Vorhandene Templates",
        options=[""] + available,
        format_func=lambda x: "– auswählen –" if x == "" else x,
        help="Wählen Sie ein Template zum Laden oder Löschen",
        key="tpl_select",
    )

with col_right:
    st.markdown("&nbsp;", unsafe_allow_html=True)  # vertical spacer
    btn_load, btn_new, btn_delete = st.columns(3)

    with btn_load:
        if st.button("📂 Laden", use_container_width=True, disabled=(not selected)):
            data = load_template(selected)
            if data is None:
                st.error(f"❌ Template '{selected}' konnte nicht geladen werden.")
            else:
                _apply_state(selected, data)
                st.success(f"✅ Template '{selected}' geladen.")
                st.rerun()

    with btn_new:
        if st.button("🆕 Neu", use_container_width=True):
            _apply_state("", get_default_template())
            st.rerun()

    with btn_delete:
        if st.button("🗑️ Löschen", use_container_width=True, disabled=(not selected)):
            if delete_template(selected):
                st.success(f"✅ Template '{selected}' gelöscht.")
                # If the deleted template was the one currently loaded, reset
                if st.session_state.get("tpl_name_input") == selected:
                    _apply_state("", get_default_template())
                st.rerun()
            else:
                st.error(f"❌ Template '{selected}' konnte nicht gelöscht werden.")

st.text_input(
    "Template-Name",
    help="Name für das Template (wird als Dateiname verwendet)",
    key="tpl_name_input",
)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_zones, tab_patterns, tab_whitelist, tab_blacklist, tab_preview = st.tabs(
    [
        "⚙️ Zonen-Konfiguration",
        "🔍 PII-Pattern Aktivierung",
        "📋 Whitelist-Begriffe",
        "🚫 Blacklist (exakt)",
        "🔍 Vorschau",
    ]
)

# ── Tab 1: Zone heights ───────────────────────────────────────────────────────

with tab_zones:
    st.subheader("⚙️ Zonen-Höhen (in PDF-Punkten)")

    c1, c2 = st.columns(2)
    with c1:
        st.number_input(
            "Header Seite 1 (pt von oben)",
            min_value=0, max_value=600, step=10,
            help="Komplett geschwärzte Header-Zone auf Seite 1",
            key="zone_header_page1",
        )
        st.number_input(
            "Header Folgeseiten (pt von oben, ab Seite 2)",
            min_value=0, max_value=600, step=10,
            help="Komplett geschwärzte Header-Zone auf Seite 2 und folgende",
            key="zone_header_next",
        )
        st.number_input(
            "Footer Seite 1 (pt von unten)",
            min_value=0, max_value=300, step=10,
            help="Footer-Zone auf Seite 1 (IBAN, Bankdaten, …)",
            key="zone_footer_page1",
        )
        st.number_input(
            "Footer Folgeseiten (pt von unten)",
            min_value=0, max_value=300, step=10,
            help="Footer-Zone auf Seite 2 und folgende",
            key="zone_footer_next",
        )

    with c2:
        st.number_input(
            "Signatur-Block nach 'Mit freundlichen Grüßen' (pt)",
            min_value=0, max_value=400, step=10,
            help="Höhe des Zensur-Blocks unterhalb der Grußformel",
            key="zone_signature",
        )
        st.number_input(
            "Personal:-Block (pt)",
            min_value=0, max_value=400, step=10,
            help="Höhe des Zensur-Blocks ab dem Keyword 'Personal:'",
            key="zone_personal",
        )

    st.subheader("⚙️ Header bis Keyword")
    st.checkbox(
        "Aktivieren",
        help=(
            "Schwärzt alles ÜBER dem obersten Vorkommen eines beliebigen "
            "Triggers auf der Seite. Praktisch für Header mit variabler Höhe "
            "(z. B. mehrzeilige Adressblöcke)."
        ),
        key="huk_enabled",
    )
    st.text_area(
        "Trigger-Keywords (einer pro Zeile)",
        height=140,
        help=(
            "Es gewinnt das oberste Vorkommen auf der Seite — Reihenfolge "
            "in der Liste ist egal. Bei mehrzeiligen Triggern bitte exakt "
            "die Schreibweise im PDF verwenden."
        ),
        key="huk_triggers",
        disabled=not st.session_state.get("huk_enabled", False),
    )

# ── Tab 2: PII-Pattern Aktivierung ────────────────────────────────────────────

with tab_patterns:
    st.subheader("🔍 PII-Pattern Aktivierung")
    st.info(
        "Wähle, welche Muster zur PII-Erkennung verwendet werden sollen. "
        "Standard: Alle aktiviert."
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Alle aktivieren", key="btn_pat_all_on", use_container_width=True):
            for pattern_name in _DEFAULT_PATTERNS:
                st.session_state[_pat_key(pattern_name)] = True
            st.rerun()
    with col2:
        if st.button("❌ Alle deaktivieren", key="btn_pat_all_off", use_container_width=True):
            for pattern_name in _DEFAULT_PATTERNS:
                st.session_state[_pat_key(pattern_name)] = False
            st.rerun()

    with st.expander("📄 Patienten-Informationen", expanded=True):
        st.checkbox(
            "Patient Block",
            help="Erkennt: Herr Müller, Max, *01.01.1960",
            key=_pat_key("patient_block"),
        )
        st.checkbox(
            "Fall-Nummer",
            help="Erkennt: Pat.-Nr. 123456789 (6-10 Ziffern)",
            key=_pat_key("case_id"),
        )
        st.checkbox(
            "Adresse",
            help="Erkennt: Hauptstraße 123, 37075 Göttingen",
            key=_pat_key("address"),
        )

    with st.expander("👨‍⚕️ Arzt-Informationen", expanded=True):
        st.checkbox(
            "Arzt-Name",
            help="Erkennt: Dr. med. Karl Müller, Prof. Schmidt",
            key=_pat_key("doctor_name"),
        )
        st.checkbox(
            "Arzt-Name in Klammern",
            help="Erkennt: (PD Dr. Christoph Jensen)",
            key=_pat_key("doctor_name_parentheses"),
        )
        st.checkbox(
            "Anrede + Name (Herr/Frau X)",
            help="Erkennt: Herr Müller, Frau Schmidt-Bayer",
            key=_pat_key("salutation_with_name"),
        )
        st.checkbox(
            "Arzt mit Standort",
            help="Erkennt: Dr. Führig, MVZ Hannover",
            key=_pat_key("doctor_with_location"),
        )
        st.checkbox(
            "Unterschrift (nach 'Mit freundlichen Grüßen')",
            help="Kontext-basiert: Nur nach Grußformel",
            key=_pat_key("doctor_signature"),
        )
        st.checkbox(
            "Zuweiser (nach 'Zuweiser:')",
            help="Kontext-basiert: Dr. nach 'Zuweiser'",
            key=_pat_key("referring_doctor"),
        )

    with st.expander("📍 Orts-Erkennung", expanded=True):
        st.warning(
            "⚠️ Bei Dokumenten mit vielen Zahlen (Radiologie, Labor) "
            "'PLZ alleinstehend' deaktivieren!"
        )
        st.checkbox(
            "PLZ + Stadt",
            help="Erkennt: 12345 Berlin, 37075 Göttingen",
            key=_pat_key("postal_code_with_city"),
        )
        st.checkbox(
            "PLZ alleinstehend",
            help="⚠️ Kann Zahlen wie '10000 IU' miterfassen",
            key=_pat_key("postal_code_standalone"),
        )
        st.checkbox(
            "Stadt-Adjektiv + Klinik",
            help="Erkennt: Hamburger Krankenhaus, Berliner Klinik",
            key=_pat_key("city_facility_simple"),
        )
        st.checkbox(
            "Universitätsklinikum + Stadt",
            help="Erkennt: Universitätsklinikum Göttingen, UKE Hamburg",
            key=_pat_key("university_hospital"),
        )
        st.checkbox(
            "Generische Einrichtung mit Stadt",
            help="Erkennt: Hamburger Herzzentrum, Göttinger MVZ",
            key=_pat_key("medical_facility_with_city"),
        )
        st.checkbox(
            "Einrichtung + Ort (Typ-basiert)",
            help="Erkennt: Herzzentrum Bad Oeynhausen, Rehaklinik Bad Salzuflen",
            key=_pat_key("medical_facility"),
        )

    with st.expander("📞 Kontakt-Informationen", expanded=True):
        st.warning(
            "⚠️ Telefon-Patterns können auch medizinische Messwerte erfassen "
            "(z.B. '120/80'). Bei Labor-/Kardiologie-Dokumenten ggf. deaktivieren!"
        )
        st.checkbox(
            "Telefon Festnetz",
            help="Erkennt: 0561/937690, Tel.: 030-12345678, +49 561 937690",
            key=_pat_key("phone_landline"),
        )
        st.checkbox(
            "Telefon Mobil",
            help="Erkennt: 0173/1234567, Mobil: 0151-98765432",
            key=_pat_key("phone_mobile"),
        )
        st.checkbox(
            "Telefon (kontext-basiert)",
            help="Erkennt: 'unter 937690 erreichbar', 'telefonisch unter 12345'",
            key=_pat_key("phone_context"),
        )
        st.checkbox(
            "E-Mail-Adressen",
            help="Erkennt: max.mustermann@klinikum.de",
            key=_pat_key("email"),
        )
        st.checkbox(
            "Fax-Nummern",
            help="Erkennt: Fax: 0561/937691, Telefax: 030-12345679",
            key=_pat_key("fax"),
        )
        st.checkbox(
            "HK-Nummer (Format: 1234/56)",
            help="Erkennt: HK-Nr.: 1234/56",
            key=_pat_key("hk_number"),
        )

    with st.expander("🔬 Geräte-IDs", expanded=False):
        st.checkbox(
            "Schrittmacher / ICD-Seriennummern",
            help="Erkennt: DR 268880, VR 123456, ICD 987654, CRT 456789, PM/SM …",
            key=_pat_key("pacemaker_id"),
        )

# ── Tab 3: Whitelist ──────────────────────────────────────────────────────────

with tab_whitelist:
    st.subheader("📋 Whitelist-Begriffe")
    st.markdown(
        "Begriffe, die **nie** anonymisiert werden sollen "
        "(komma-separiert oder ein Begriff pro Zeile)."
    )

    st.text_area(
        "Medizinische Begriffe",
        height=100,
        help="z.B. CT, MRT, Angiographie",
        key="wl_medical",
    )
    st.text_area(
        "Anatomische Begriffe",
        height=100,
        help="z.B. Herz, Lunge, Leber",
        key="wl_anatomical",
    )
    st.text_area(
        "Geräte / Hersteller",
        height=100,
        help="z.B. Stent, Katheter, Defibrillator",
        key="wl_devices",
    )

# ── Tab 4: Blacklist ──────────────────────────────────────────────────────────

with tab_blacklist:
    st.subheader("🚫 Blacklist (exakt, case-sensitiv)")
    st.markdown(
        "Begriffe, die **immer** anonymisiert werden sollen — unabhängig von "
        "Whitelist und Pattern-Toggles. Eine Zeile = ein Eintrag. "
        "Groß-/Kleinschreibung wird beachtet, ganze Wörter (z.B. `UMG` schwärzt "
        "`UMG`, lässt `Umgeben` stehen)."
    )

    st.text_area(
        "Blacklist (exakt, case-sensitiv)",
        height=200,
        help="ein Eintrag pro Zeile",
        key="bl_exact",
    )

# ── Tab 5: Preview ────────────────────────────────────────────────────────────

with tab_preview:
    st.subheader("🔍 Aktuelle Einstellungen (Live-Vorschau)")
    preview = _collect_state()
    preview["name"] = (st.session_state.get("tpl_name_input") or "Unbenannt").strip() or "Unbenannt"
    st.json(preview)

st.divider()

# ── Save button ───────────────────────────────────────────────────────────────

if st.button("💾 Template speichern", type="primary", use_container_width=True):
    save_name = (st.session_state.get("tpl_name_input") or "").strip()
    if not save_name:
        st.error("❌ Bitte geben Sie einen Template-Namen ein.")
    else:
        new_tpl = _collect_state()
        new_tpl["name"] = save_name
        new_tpl["created"] = st.session_state["tpl_data"].get(
            "created",
            datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        if save_template(save_name, new_tpl):
            st.session_state["tpl_data"] = new_tpl
            st.success(f"✅ Template '{save_name}' gespeichert.")
            st.rerun()
        else:
            st.error("❌ Template konnte nicht gespeichert werden.")
