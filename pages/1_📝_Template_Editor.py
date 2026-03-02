"""Template Editor – Streamlit page for managing anonymization templates."""

import sys
import json
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

# ── Session state initialisation ─────────────────────────────────────────────

if "tpl_data" not in st.session_state:
    st.session_state["tpl_data"] = get_default_template()
if "tpl_name" not in st.session_state:
    st.session_state["tpl_name"] = ""

# ── Helper ────────────────────────────────────────────────────────────────────


def _parse_list(text: str):
    """Split comma-separated text into a stripped list of non-empty strings."""
    return [t.strip() for t in text.replace("\n", ",").split(",") if t.strip()]


def _join_list(items) -> str:
    """Join a list of strings into comma-separated text."""
    return ", ".join(items) if items else ""


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
                st.session_state["tpl_data"] = data
                st.session_state["tpl_name"] = selected
                st.success(f"✅ Template '{selected}' geladen.")
                st.rerun()

    with btn_new:
        if st.button("🆕 Neu", use_container_width=True):
            st.session_state["tpl_data"] = get_default_template()
            st.session_state["tpl_name"] = ""
            st.rerun()

    with btn_delete:
        if st.button("🗑️ Löschen", use_container_width=True, disabled=(not selected)):
            if delete_template(selected):
                st.success(f"✅ Template '{selected}' gelöscht.")
                if st.session_state["tpl_name"] == selected:
                    st.session_state["tpl_data"] = get_default_template()
                    st.session_state["tpl_name"] = ""
                st.rerun()
            else:
                st.error(f"❌ Template '{selected}' konnte nicht gelöscht werden.")

tpl_name = st.text_input(
    "Template-Name",
    value=st.session_state["tpl_name"],
    help="Name für das Template (wird als Dateiname verwendet)",
    key="tpl_name_input",
)

st.divider()

# ── Working copy of the current template ─────────────────────────────────────

tpl = st.session_state["tpl_data"]
zones = tpl.get("zones", {})
whitelist = tpl.get("whitelist", {})

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_zones, tab_patterns, tab_whitelist, tab_preview = st.tabs(
    ["⚙️ Zonen-Konfiguration", "🔍 PII-Pattern Aktivierung", "📋 Whitelist-Begriffe", "🔍 Vorschau"]
)

# ── Tab 1: Zone heights ───────────────────────────────────────────────────────

with tab_zones:
    st.subheader("⚙️ Zonen-Höhen (in Pixeln)")

    c1, c2 = st.columns(2)

    with c1:
        header_page1 = st.number_input(
            "Header Seite 1 (px von oben)",
            min_value=0,
            max_value=600,
            value=int(zones.get("header_page1", 380)),
            step=10,
            help="Komplett geschwärzte Header-Zone auf Seite 1",
        )
        header_next = st.number_input(
            "Header Folgeseiten (px von oben, ab Seite 2)",
            min_value=0,
            max_value=600,
            value=int(zones.get("header_next", 100)),
            step=10,
            help="Komplett geschwärzte Header-Zone auf Seite 2 und folgende",
        )
        footer_page1 = st.number_input(
            "Footer Seite 1 (px von unten)",
            min_value=0,
            max_value=300,
            value=int(zones.get("footer_page1", 130)),
            step=10,
            help="Footer-Zone auf Seite 1 (IBAN, Bankdaten, …)",
        )
        footer_next = st.number_input(
            "Footer Folgeseiten (px von unten)",
            min_value=0,
            max_value=300,
            value=int(zones.get("footer_next", 110)),
            step=10,
            help="Footer-Zone auf Seite 2 und folgende",
        )

    with c2:
        signature = st.number_input(
            "Signatur-Block nach 'Mit freundlichen Grüßen' (px)",
            min_value=0,
            max_value=400,
            value=int(zones.get("signature", 150)),
            step=10,
            help="Höhe des Zensur-Blocks unterhalb der Grußformel",
        )
        personal = st.number_input(
            "Personal:-Block (px)",
            min_value=0,
            max_value=400,
            value=int(zones.get("personal", 100)),
            step=10,
            help="Höhe des Zensur-Blocks ab dem Keyword 'Personal:'",
        )

# ── Tab 2: PII-Pattern Aktivierung ───────────────────────────────────────────

_DEFAULT_PATTERNS = [
    "patient_block", "case_id", "address",
    "doctor_name", "doctor_with_location", "doctor_signature", "referring_doctor",
    "postal_code_with_city", "postal_code_standalone",
    "city_facility_simple", "university_hospital", "medical_facility_with_city",
]

with tab_patterns:
    st.subheader("🔍 PII-Pattern Aktivierung")
    st.info(
        "Wähle, welche Muster zur PII-Erkennung verwendet werden sollen. "
        "Standard: Alle aktiviert."
    )

    # Initialize active_patterns from template or defaults
    _stored_patterns = tpl.get("active_patterns", {})
    active_patterns = {p: _stored_patterns.get(p, True) for p in _DEFAULT_PATTERNS}

    # Bulk actions
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Alle aktivieren", key="pat_all_on"):
            for key in active_patterns:
                active_patterns[key] = True
            tpl["active_patterns"] = active_patterns
            st.rerun()
    with col2:
        if st.button("❌ Alle deaktivieren", key="pat_all_off"):
            for key in active_patterns:
                active_patterns[key] = False
            tpl["active_patterns"] = active_patterns
            st.rerun()

    with st.expander("📄 Patienten-Informationen", expanded=True):
        active_patterns["patient_block"] = st.checkbox(
            "Patient Block",
            value=active_patterns.get("patient_block", True),
            help="Erkennt: Herr Müller, Max, *01.01.1960",
            key="pat_patient_block",
        )
        active_patterns["case_id"] = st.checkbox(
            "Fall-Nummer",
            value=active_patterns.get("case_id", True),
            help="Erkennt: Pat.-Nr. 123456789 (6-10 Ziffern)",
            key="pat_case_id",
        )
        active_patterns["address"] = st.checkbox(
            "Adresse",
            value=active_patterns.get("address", True),
            help="Erkennt: Hauptstraße 123, 37075 Göttingen",
            key="pat_address",
        )

    with st.expander("👨‍⚕️ Arzt-Informationen", expanded=True):
        active_patterns["doctor_name"] = st.checkbox(
            "Arzt-Name",
            value=active_patterns.get("doctor_name", True),
            help="Erkennt: Dr. med. Karl Müller, Prof. Schmidt",
            key="pat_doctor_name",
        )
        active_patterns["doctor_with_location"] = st.checkbox(
            "Arzt mit Standort",
            value=active_patterns.get("doctor_with_location", True),
            help="Erkennt: Dr. Führig, MVZ Hannover",
            key="pat_doctor_location",
        )
        active_patterns["doctor_signature"] = st.checkbox(
            "Unterschrift (nach 'Mit freundlichen Grüßen')",
            value=active_patterns.get("doctor_signature", True),
            help="Kontext-basiert: Nur nach Grußformel",
            key="pat_doctor_sig",
        )
        active_patterns["referring_doctor"] = st.checkbox(
            "Zuweiser (nach 'Zuweiser:')",
            value=active_patterns.get("referring_doctor", True),
            help="Kontext-basiert: Dr. nach 'Zuweiser'",
            key="pat_referring",
        )

    with st.expander("📍 Orts-Erkennung", expanded=True):
        st.warning(
            "⚠️ Bei Dokumenten mit vielen Zahlen (Radiologie, Labor) "
            "'PLZ alleinstehend' deaktivieren!"
        )
        active_patterns["postal_code_with_city"] = st.checkbox(
            "PLZ + Stadt",
            value=active_patterns.get("postal_code_with_city", True),
            help="Erkennt: 12345 Berlin, 37075 Göttingen",
            key="pat_plz_city",
        )
        active_patterns["postal_code_standalone"] = st.checkbox(
            "PLZ alleinstehend",
            value=active_patterns.get("postal_code_standalone", True),
            help="⚠️ Erkennt: 12345 (ACHTUNG: Kann Zahlen wie 10000 IU erfassen!)",
            key="pat_plz_alone",
        )
        active_patterns["city_facility_simple"] = st.checkbox(
            "Stadt-Adjektiv + Klinik",
            value=active_patterns.get("city_facility_simple", True),
            help="Erkennt: Hamburger Krankenhaus, Berliner Klinik",
            key="pat_city_facility",
        )
        active_patterns["university_hospital"] = st.checkbox(
            "Universitätsklinikum + Stadt",
            value=active_patterns.get("university_hospital", True),
            help="Erkennt: Universitätsklinikum Göttingen, UKE Hamburg",
            key="pat_uni_hospital",
        )
        active_patterns["medical_facility_with_city"] = st.checkbox(
            "Generische Einrichtung mit Stadt",
            value=active_patterns.get("medical_facility_with_city", True),
            help="Erkennt: Hamburger Herzzentrum, Göttinger MVZ",
            key="pat_facility_generic",
        )

# ── Tab 3: Whitelist ──────────────────────────────────────────────────────────

with tab_whitelist:
    st.subheader("📋 Whitelist-Begriffe")
    st.markdown(
        "Geben Sie Begriffe ein, die **nicht** anonymisiert werden sollen "
        "(komma-separiert oder ein Begriff pro Zeile)."
    )

    wl_medical = st.text_area(
        "Medizinische Begriffe",
        value=_join_list(whitelist.get("medical", [])),
        height=100,
        help="z.B. CT, MRT, Angiographie",
    )
    wl_anatomical = st.text_area(
        "Anatomische Begriffe",
        value=_join_list(whitelist.get("anatomical", [])),
        height=100,
        help="z.B. Herz, Lunge, Leber",
    )
    wl_devices = st.text_area(
        "Geräte / Hersteller",
        value=_join_list(whitelist.get("devices", [])),
        height=100,
        help="z.B. Stent, Katheter, Defibrillator",
    )

# ── Tab 4: Preview ────────────────────────────────────────────────────────────

with tab_preview:
    st.subheader("🔍 Aktuelle Einstellungen (Live-Vorschau)")

    preview_data = {
        "name": tpl_name or tpl.get("name", "Unbenannt"),
        "zones": {
            "header_page1": header_page1,
            "header_next": header_next,
            "footer_page1": footer_page1,
            "footer_next": footer_next,
            "signature": signature,
            "personal": personal,
        },
        "active_patterns": active_patterns,
        "whitelist": {
            "medical": _parse_list(wl_medical),
            "anatomical": _parse_list(wl_anatomical),
            "devices": _parse_list(wl_devices),
        },
    }
    st.json(preview_data)

st.divider()

# ── Save button ───────────────────────────────────────────────────────────────

save_name = tpl_name.strip()

if st.button("💾 Template speichern", type="primary", use_container_width=True):
    if not save_name:
        st.error("❌ Bitte geben Sie einen Template-Namen ein.")
    else:
        new_tpl = {
            "name": save_name,
            "created": tpl.get(
                "created",
                datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
            "zones": {
                "header_page1": header_page1,
                "header_next": header_next,
                "footer_page1": footer_page1,
                "footer_next": footer_next,
                "signature": signature,
                "personal": personal,
            },
            "active_patterns": active_patterns,
            "whitelist": {
                "medical": _parse_list(wl_medical),
                "anatomical": _parse_list(wl_anatomical),
                "devices": _parse_list(wl_devices),
            },
        }
        if save_template(save_name, new_tpl):
            st.session_state["tpl_data"] = new_tpl
            st.session_state["tpl_name"] = save_name
            st.success(f"✅ Template '{save_name}' gespeichert.")
            st.rerun()
        else:
            st.error("❌ Template konnte nicht gespeichert werden.")
