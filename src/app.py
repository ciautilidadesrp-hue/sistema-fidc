"""
Sistema de Modelagem de FIDCs
Interface principal - Streamlit
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date
from dateutil.relativedelta import relativedelta

from models import (
    ParametrosFundo, ConfiguracaoCota, ConfiguracaoAtivo,
    ConfiguracaoCustos, ConfiguracaoPerformance, Aporte, Amortizacao,
    TipoCota, TipoIndexador, TipoAmortizacao, PeriodicidadeJuros
)
from engine import rodar_simulacao, calcular_metricas_resumo
from dados_mercado import buscar_curvas

# ─────────────────────────────────────────────
# Configuração da página
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="ICE | Modelagem de FIDCs",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Tela de Login
# ─────────────────────────────────────────────
def _tela_login():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700&display=swap');
    html, body, [class*="css"], .stApp {
        background-color: #00183C !important;
        font-family: "Futura Bk BT", "Futura", "Nunito", "Segoe UI", sans-serif;
    }
    [data-testid="stSidebar"] { display: none; }
    header[data-testid="stHeader"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 1.2, 1])
    with col_c:
        # Logo
        _logo_path = os.path.join(os.path.dirname(__file__), "..", "LOGO ICE _ NOVO FUNDO TRANSPARENTE.png")
        if os.path.exists(_logo_path):
            st.image(_logo_path, width=260)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            "<h3 style='color:#C7DDEB;text-align:center;margin-bottom:4px;'>Sistema de Modelagem de FIDCs</h3>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='color:#81BDDB;text-align:center;font-size:13px;margin-bottom:24px;'>Acesso restrito — ICE Asset Management</p>",
            unsafe_allow_html=True,
        )

        codigo = st.text_input(
            "Código de acesso",
            type="password",
            placeholder="Digite o código de acesso",
            key="_login_codigo",
        )
        entrar = st.button("Entrar", use_container_width=True, type="primary")

        if entrar or codigo:
            if codigo.strip() == "@iceassetmanagement.com":
                st.session_state["_autenticado"] = True
                st.rerun()
            elif codigo.strip():
                st.error("Código de acesso inválido.")

if not st.session_state.get("_autenticado", False):
    _tela_login()
    st.stop()

# ─────────────────────────────────────────────
# Identidade Visual ICE
# Paleta: #2379AF | #C7DDEB | #81BDDB | #00183C | #084073
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700&display=swap');

/* Fallback quando Futura Bk BT está instalada localmente */
:root {
    --ice-blue:        #2379AF;
    --ice-blue-light:  #C7DDEB;
    --ice-blue-mid:    #81BDDB;
    --ice-dark:        #00183C;
    --ice-deep:        #084073;
    --font-main: "Futura Bk BT", "Futura", "Nunito", "Segoe UI", sans-serif;
}

html, body, [class*="css"], .stApp {
    font-family: var(--font-main) !important;
    background-color: #F4F8FC;
    color: var(--ice-dark);
}

/* Header / topo */
header[data-testid="stHeader"] {
    background-color: var(--ice-dark) !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: var(--ice-dark) !important;
}
/* Texto geral na sidebar — apenas elementos de texto, não SVG nem estruturais */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span:not([data-testid]),
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] small {
    color: var(--ice-blue-light) !important;
    font-family: var(--font-main) !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] [data-testid="stHeading"],
[data-testid="stSidebar"] [data-testid="stSubheader"] {
    color: #FFFFFF !important;
    font-family: var(--font-main) !important;
}
[data-testid="stSidebar"] hr {
    border-color: var(--ice-blue-mid) !important;
    opacity: 0.4;
}
[data-testid="stSidebar"] .stNumberInput input,
[data-testid="stSidebar"] .stTextInput input,
[data-testid="stSidebar"] .stDateInput input {
    background-color: #0D2A4A !important;
    color: #FFFFFF !important;
    border-color: var(--ice-blue-mid) !important;
    border-radius: 6px !important;
    font-family: var(--font-main) !important;
}
/* Botão principal da sidebar (ex: Buscar IPCA) */
[data-testid="stSidebar"] .stButton > button {
    background-color: var(--ice-blue) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: var(--font-main) !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background-color: var(--ice-deep) !important;
}
/* Ícones SVG na sidebar — preservar visibilidade */
[data-testid="stSidebar"] svg {
    fill: var(--ice-blue-light) !important;
}
/* Expander na sidebar */
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    color: var(--ice-blue-light) !important;
}
/* Spinner na sidebar */
[data-testid="stSidebar"] [data-testid="stSpinner"] {
    color: var(--ice-blue-light) !important;
}

/* Abas */
.stTabs [data-baseweb="tab-list"] {
    background-color: var(--ice-dark);
    border-radius: 8px 8px 0 0;
    padding: 4px 8px 0;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    font-family: var(--font-main) !important;
    font-weight: 600;
    color: var(--ice-blue-light) !important;
    background-color: transparent !important;
    border-radius: 6px 6px 0 0 !important;
    padding: 8px 18px !important;
    transition: background 0.2s;
}
.stTabs [aria-selected="true"] {
    background-color: var(--ice-blue) !important;
    color: #FFFFFF !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    background-color: var(--ice-blue) !important;
}
.stTabs [data-baseweb="tab-panel"] {
    background-color: #FFFFFF;
    border: 1px solid var(--ice-blue-light);
    border-radius: 0 0 8px 8px;
    padding: 20px;
}

/* Botões primários */
button[kind="primary"],
.stButton > button[kind="primary"] {
    background-color: var(--ice-blue) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: var(--font-main) !important;
    font-weight: 600 !important;
}
button[kind="primary"]:hover {
    background-color: var(--ice-deep) !important;
}

/* Botões secundários */
.stButton > button {
    background-color: #FFFFFF !important;
    color: var(--ice-deep) !important;
    border: 1.5px solid var(--ice-blue) !important;
    border-radius: 6px !important;
    font-family: var(--font-main) !important;
}
.stButton > button:hover {
    background-color: var(--ice-blue-light) !important;
}

/* Métricas */
[data-testid="stMetric"] {
    background-color: #FFFFFF;
    border-left: 4px solid var(--ice-blue);
    border-radius: 6px;
    padding: 12px 16px !important;
    box-shadow: 0 1px 4px rgba(0,24,60,0.08);
}
[data-testid="stMetricLabel"] {
    font-family: var(--font-main) !important;
    color: var(--ice-deep) !important;
    font-weight: 600;
}
[data-testid="stMetricValue"] {
    font-family: var(--font-main) !important;
    color: var(--ice-blue) !important;
    font-weight: 700;
}

/* Títulos e subtítulos */
h1, h2, h3, h4 {
    font-family: var(--font-main) !important;
    color: var(--ice-dark) !important;
}

/* Divider */
hr {
    border-color: var(--ice-blue-light) !important;
}

/* Dataframe / tabelas */
[data-testid="stDataFrame"] {
    border: 1px solid var(--ice-blue-light);
    border-radius: 6px;
    overflow: hidden;
}

/* Info / success / warning */
[data-testid="stAlert"] {
    border-radius: 6px !important;
    font-family: var(--font-main) !important;
}

/* Inputs */
.stNumberInput input, .stTextInput input, .stDateInput input, .stSelectbox select {
    border-color: var(--ice-blue-mid) !important;
    border-radius: 6px !important;
    font-family: var(--font-main) !important;
}
.stNumberInput input:focus, .stTextInput input:focus {
    border-color: var(--ice-blue) !important;
    box-shadow: 0 0 0 2px rgba(35,121,175,0.2) !important;
}

/* Caption */
.stCaption {
    color: var(--ice-blue) !important;
    font-family: var(--font-main) !important;
}

/* Download button */
.stDownloadButton > button {
    background-color: var(--ice-deep) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: var(--font-main) !important;
    font-weight: 600 !important;
}
.stDownloadButton > button:hover {
    background-color: var(--ice-blue) !important;
}
</style>
""", unsafe_allow_html=True)

# ── Header principal (sem logo — logo está apenas na sidebar) ──
st.markdown(
    """
    <div style="padding-top:8px">
      <h1 style="margin:0;font-size:1.8rem;color:#00183C;">Sistema de Modelagem de FIDCs</h1>
      <p style="margin:4px 0 0;color:#2379AF;font-size:0.95rem;">
        Monte a estrutura do fundo e projete a evolução das cotas ao longo do tempo.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown("<hr style='margin:12px 0 20px;border-color:#C7DDEB;'>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
LABEL_INDEXADOR = {
    "Taxa Fixa": TipoIndexador.FIXO,
    "CDI +": TipoIndexador.CDI,
    "IPCA +": TipoIndexador.IPCA,
}

LABEL_PERIODICIDADE = {
    "Sem pagamento periódico": PeriodicidadeJuros.NENHUMA,
    "Mensal": PeriodicidadeJuros.MENSAL,
    "Trimestral": PeriodicidadeJuros.TRIMESTRAL,
    "Semestral": PeriodicidadeJuros.SEMESTRAL,
    "Anual": PeriodicidadeJuros.ANUAL,
}

LABEL_TIPO_AMORT = {
    "Juros (valor fixo)": TipoAmortizacao.JUROS,
    "Juros Acumulados (total)": TipoAmortizacao.JUROS_ACUMULADOS,
    "Principal": TipoAmortizacao.PRINCIPAL,
    "Juros + Principal": TipoAmortizacao.TOTAL,
}

def fmt_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%".replace(".", ",")

def _parse_brl(text: str) -> float:
    """Converte string formatada em BRL para float. Ex: 'R$ 1.000.000,00' -> 1000000.0"""
    clean = text.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return 0.0

def brl_input(label: str, default: float, key: str, min_val: float = 0.0) -> float:
    """
    Campo de texto com máscara BRL (R$ 1.000.000,00).
    Armazena o valor formatado no session_state e retorna o float correspondente.
    """
    ss_key = f"_brl_{key}"
    reset_flag = f"_reset_{key}"

    # Se há uma flag de reset pendente, aplica antes de criar o widget
    if st.session_state.pop(reset_flag, False):
        st.session_state[ss_key] = fmt_brl(default)
    elif ss_key not in st.session_state:
        st.session_state[ss_key] = fmt_brl(default)

    raw = st.text_input(label, key=ss_key)
    val = _parse_brl(raw)
    if val < min_val:
        val = min_val
    return val


# ─────────────────────────────────────────────
# Sidebar — Parâmetros Gerais
# ─────────────────────────────────────────────
with st.sidebar:
    # Logo ICE no topo da sidebar
    _logo_path_sb = os.path.join(os.path.dirname(os.path.dirname(__file__)), "LOGO ICE _ NOVO FUNDO TRANSPARENTE.png")
    if os.path.exists(_logo_path_sb):
        import base64 as _b64
        with open(_logo_path_sb, "rb") as _f:
            _logo_b64 = _b64.b64encode(_f.read()).decode()
        st.markdown(
            f"""<div style="background:#FFFFFF;border-radius:12px;padding:14px 20px;margin-bottom:12px;text-align:center;">
              <img src="data:image/png;base64,{_logo_b64}" style="max-width:100%;height:auto;">
            </div>""",
            unsafe_allow_html=True,
        )
    st.header("⚙️ Parâmetros Gerais")

    nome_fundo = st.text_input("Nome do Fundo", value="FIDC Exemplo")
    data_inicio = st.date_input("Data de Início", value=date.today(), format="DD/MM/YYYY")
    prazo_meses = st.number_input("Prazo da Simulação (meses)", min_value=1, max_value=360, value=24, step=1)

    st.divider()
    st.subheader("📈 Curva DI Futuro")

    # Carrega a planilha automaticamente da pasta do projeto
    import os as _os
    _curva_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "CURVA DI FUTURO.csv")
    curva_cdi: dict = {}
    _curva_info = ""

    if _os.path.exists(_curva_path):
        try:
            _df_curva = pd.read_csv(_curva_path, sep=";", decimal=",")
            _df_curva["Data"] = pd.to_datetime(_df_curva["Data"], dayfirst=True)
            curva_cdi = {
                row["Data"].date(): float(row["Taxa"])
                for _, row in _df_curva.iterrows()
            }
            _datas = sorted(curva_cdi.keys())
            _curva_info = f"{_datas[0].strftime('%d/%m/%Y')} a {_datas[-1].strftime('%d/%m/%Y')} — {len(curva_cdi)} dias úteis"
            # CDI anualizado do primeiro dia para referência
            _cdi_ref = (1.0 + list(curva_cdi.values())[0]) ** 252 - 1.0
            st.caption(f"🟢 Curva carregada: {_curva_info}")
            st.caption(f"CDI curto: {fmt_pct(_cdi_ref)}")
            with st.expander("Ver Curva DI Futuro"):
                _df_show = _df_curva.copy()
                _df_show["Data"] = _df_show["Data"].dt.strftime("%d/%m/%Y")
                _df_show["CDI Anualizado"] = _df_show["Taxa"].apply(
                    lambda x: fmt_pct((1.0 + x) ** 252 - 1.0)
                )
                _df_show = _df_show.rename(columns={"Data": "Data", "Taxa": "Fator Diário"})
                st.dataframe(_df_show, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Erro ao ler curva DI: {e}")
    else:
        st.warning("Arquivo 'CURVA DI FUTURO.csv' não encontrado na pasta do projeto.")

    st.divider()
    st.subheader("🏦 IPCA")

    if st.button("🔄 Buscar IPCA do BCB"):
        with st.spinner("Consultando BCB..."):
            curvas = buscar_curvas()
        st.session_state["curvas_mercado"] = curvas

    curvas_cache = st.session_state.get("curvas_mercado")
    _ipca_default = 4.50

    if curvas_cache:
        if curvas_cache.get("ipca_anual_medio") is not None:
            _ipca_default = round(curvas_cache["ipca_anual_medio"] * 100, 2)
        st.caption(f"Atualizado em {curvas_cache['data_consulta']}")

    _ipca_input = st.number_input("IPCA Projetado (% a.a.)", min_value=0.0, max_value=50.0, value=_ipca_default, step=0.25, format="%.2f")
    _ipca_fonte = curvas_cache.get("fonte_ipca", "") if curvas_cache else ""
    st.caption(f"{fmt_pct(_ipca_input / 100)}" + (f"  —  {_ipca_fonte}" if _ipca_fonte else ""))
    ipca_anual = _ipca_input / 100

    st.divider()
    st.subheader("📋 Regulatório")
    _sub_min_input = st.number_input("Subordinação Mínima (%)", min_value=0.0, max_value=100.0, value=20.0, step=1.0, format="%.1f")
    st.caption(fmt_pct(_sub_min_input / 100))
    subordinacao_minima = _sub_min_input / 100


# ─────────────────────────────────────────────
# Abas principais
# ─────────────────────────────────────────────
tab_descricao, tab_estrutura, tab_ativo, tab_custos, tab_aportes, tab_amort, tab_resultado = st.tabs([
    "📝 Descrição",
    "🏗️ Estrutura do Fundo",
    "📈 Ativo & Carteira",
    "💸 Custos & Despesas",
    "➕ Aportes",
    "📉 Amortizações",
    "📊 Resultados",
])


# ─────────────────────────────────────────────
# Aba 0: Descrição do Fundo
# ─────────────────────────────────────────────
with tab_descricao:
    st.subheader("Descrição do Fundo")
    st.caption(
        "Descreva o fundo de forma completa: estratégia, ativos-objeto, política de "
        "investimento, público-alvo, prazos, garantias, etc. Esta descrição aparecerá "
        "como primeiro item do relatório PDF."
    )

    if "descricao_fundo" not in st.session_state:
        st.session_state.descricao_fundo = ""

    def _revisar_descricao_callback():
        texto = st.session_state.get("descricao_fundo", "")
        if not texto.strip():
            st.session_state["_desc_warn"] = "Insira uma descrição antes de pedir revisão."
            return
        try:
            import anthropic
            client = anthropic.Anthropic()
            resp = client.messages.create(
                model="claude-opus-4-7",
                max_tokens=4096,
                system=(
                    "Você é um redator profissional especializado em descrições de "
                    "fundos de investimento (FIDCs) no Brasil. Revise e reescreva o "
                    "texto fornecido pelo usuário de forma mais formal, concisa e "
                    "clara, mantendo TODAS as informações originais. Use português "
                    "brasileiro em registro técnico-financeiro. Responda APENAS com "
                    "o texto revisado, sem comentários, introduções, observações "
                    "adicionais ou marcações em markdown."
                ),
                messages=[{"role": "user", "content": texto}],
            )
            novo = next(
                (b.text for b in resp.content if b.type == "text"),
                texto,
            ).strip()
            # Em callbacks o estado pode ser modificado antes do próximo render
            st.session_state.descricao_fundo = novo
            st.session_state["_desc_success"] = True
        except Exception as e:
            st.session_state["_desc_error"] = str(e)

    st.text_area(
        "Texto da descrição",
        height=300,
        key="descricao_fundo",
        placeholder=(
            "Ex.: O FIDC XYZ é um fundo de investimento em direitos creditórios "
            "destinado a investidores qualificados, com estratégia focada em..."
        ),
    )

    _api_key_disponivel = bool(os.environ.get("ANTHROPIC_API_KEY"))

    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        st.button(
            "✨ Revisar com Claude",
            use_container_width=True,
            disabled=not _api_key_disponivel,
            on_click=_revisar_descricao_callback,
            help=(
                "Reescreve o texto de forma mais formal, concisa e clara usando o Claude."
                if _api_key_disponivel
                else "Defina a variável de ambiente ANTHROPIC_API_KEY para habilitar."
            ),
        )
    with col_info:
        if not _api_key_disponivel:
            st.caption("⚠️ Variável `ANTHROPIC_API_KEY` não configurada — defina-a no ambiente para habilitar a revisão.")

    # Mensagens da última execução do callback
    if st.session_state.pop("_desc_success", False):
        st.success("Texto revisado pelo Claude.")
    if _msg := st.session_state.pop("_desc_warn", None):
        st.warning(_msg)
    if _msg := st.session_state.pop("_desc_error", None):
        st.error(f"Erro ao revisar com Claude: {_msg}")


# ─────────────────────────────────────────────
# Aba 1: Estrutura do Fundo
# ─────────────────────────────────────────────
with tab_estrutura:
    st.subheader("Capitalização Inicial por Cota")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 🟦 Cota Sênior")
        usar_senior = st.checkbox("Emitir Cota Sênior", value=True, key="usar_senior")
        if usar_senior:
            val_inicial_senior = brl_input("Valor Inicial (R$)", 8_000_000.0, "val_senior")
            val_unit_senior = brl_input("Valor Unitário da Cota (R$)", 1_000.0, "unit_senior", min_val=0.01)
            idx_senior_label = st.selectbox("Indexador", list(LABEL_INDEXADOR.keys()), index=1, key="idx_senior")
            idx_senior = LABEL_INDEXADOR[idx_senior_label]
            if idx_senior == TipoIndexador.FIXO:
                _taxa_s = st.number_input("Taxa Fixa (% a.a.)", min_value=0.0, value=12.0, step=0.25, key="taxa_senior", format="%.2f")
                st.caption(fmt_pct(_taxa_s / 100))
                taxa_senior = _taxa_s / 100
                spread_senior = 0.0
            else:
                _spread_s = st.number_input(f"Spread sobre {idx_senior_label} (% a.a.)", min_value=-10.0, value=2.0, step=0.25, key="spread_senior", format="%.2f")
                st.caption(fmt_pct(_spread_s / 100))
                spread_senior = _spread_s / 100
                taxa_senior = 0.0
            periodicidade_senior_label = st.selectbox(
                "Pagamento de Juros",
                list(LABEL_PERIODICIDADE.keys()),
                index=0,
                key="period_senior",
                help="Define a frequência com que os juros acumulados são pagos automaticamente, mantendo o principal intacto.",
            )
            periodicidade_senior = LABEL_PERIODICIDADE[periodicidade_senior_label]
            qtd = val_inicial_senior / val_unit_senior if val_unit_senior > 0 else 0
            st.caption(f"Quantidade de cotas: {qtd:,.0f}")
        else:
            val_inicial_senior = 0.0
            idx_senior = TipoIndexador.CDI
            taxa_senior = 0.0
            spread_senior = 0.0
            val_unit_senior = 1_000.0
            periodicidade_senior = PeriodicidadeJuros.NENHUMA

    with col2:
        st.markdown("#### 🟨 Cota Mezanino")
        usar_mezanino = st.checkbox("Emitir Cota Mezanino", value=False, key="usar_mezanino")
        if usar_mezanino:
            val_inicial_mezanino = brl_input("Valor Inicial (R$)", 1_000_000.0, "val_mezanino")
            val_unit_mezanino = brl_input("Valor Unitário da Cota (R$)", 1_000.0, "unit_mezanino", min_val=0.01)
            idx_mezanino_label = st.selectbox("Indexador", list(LABEL_INDEXADOR.keys()), index=1, key="idx_mezanino")
            idx_mezanino = LABEL_INDEXADOR[idx_mezanino_label]
            if idx_mezanino == TipoIndexador.FIXO:
                _taxa_m = st.number_input("Taxa Fixa (% a.a.)", min_value=0.0, value=14.0, step=0.25, key="taxa_mezanino", format="%.2f")
                st.caption(fmt_pct(_taxa_m / 100))
                taxa_mezanino = _taxa_m / 100
                spread_mezanino = 0.0
            else:
                _spread_m = st.number_input(f"Spread sobre {idx_mezanino_label} (% a.a.)", min_value=-10.0, value=4.0, step=0.25, key="spread_mezanino", format="%.2f")
                st.caption(fmt_pct(_spread_m / 100))
                spread_mezanino = _spread_m / 100
                taxa_mezanino = 0.0
            periodicidade_mezanino_label = st.selectbox(
                "Pagamento de Juros",
                list(LABEL_PERIODICIDADE.keys()),
                index=0,
                key="period_mezanino",
                help="Define a frequência com que os juros acumulados são pagos automaticamente, mantendo o principal intacto.",
            )
            periodicidade_mezanino = LABEL_PERIODICIDADE[periodicidade_mezanino_label]
            qtd_m = val_inicial_mezanino / val_unit_mezanino if val_unit_mezanino > 0 else 0
            st.caption(f"Quantidade de cotas: {qtd_m:,.0f}")
        else:
            val_inicial_mezanino = 0.0
            idx_mezanino = TipoIndexador.CDI
            taxa_mezanino = 0.0
            spread_mezanino = 0.0
            val_unit_mezanino = 1_000.0
            periodicidade_mezanino = PeriodicidadeJuros.NENHUMA

    with col3:
        st.markdown("#### 🟥 Cota Subordinada")
        val_inicial_sub = brl_input("Valor Inicial (R$)", 2_000_000.0, "val_sub")
        val_unit_sub = brl_input("Valor Unitário da Cota (R$)", 1_000.0, "unit_sub", min_val=0.01)
        qtd_s = val_inicial_sub / val_unit_sub if val_unit_sub > 0 else 0
        st.caption(f"Quantidade de cotas: {qtd_s:,.0f}")
        periodicidade_sub_label = st.selectbox(
            "Periodicidade de Distribuição de Juros",
            list(LABEL_PERIODICIDADE.keys()),
            index=0,
            key="periodicidade_sub",
        )
        periodicidade_sub = LABEL_PERIODICIDADE[periodicidade_sub_label]

    st.divider()
    pl_total_ini = val_inicial_senior + val_inicial_mezanino + val_inicial_sub
    sub_ratio = val_inicial_sub / pl_total_ini if pl_total_ini > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PL Total Inicial", fmt_brl(pl_total_ini))
    c2.metric("Sênior", fmt_brl(val_inicial_senior), f"{val_inicial_senior/pl_total_ini*100:.1f}%" if pl_total_ini > 0 else "")
    c3.metric("Subordinada", fmt_brl(val_inicial_sub), f"{sub_ratio*100:.1f}%")
    c4.metric(
        "Subordinação Mínima Atendida?",
        "✅ Sim" if sub_ratio >= subordinacao_minima else "⚠️ Não",
        f"Mín: {subordinacao_minima*100:.0f}%",
        delta_color="off",
    )


# ─────────────────────────────────────────────
# Aba 2: Ativo & Carteira
# ─────────────────────────────────────────────
with tab_ativo:
    st.subheader("Parâmetros da Carteira de Crédito")
    col1, col2 = st.columns(2)
    with col1:
        _taxa_ativo_input = st.number_input("Taxa de Retorno do Ativo (% a.a.)", min_value=0.0, value=18.0, step=0.5, format="%.2f")
        st.caption(fmt_pct(_taxa_ativo_input / 100))
        taxa_ativo = _taxa_ativo_input / 100
        _inadimplencia_input = st.number_input("Inadimplência Esperada (% a.a.)", min_value=0.0, value=3.0, step=0.5, format="%.2f")
        st.caption(fmt_pct(_inadimplencia_input / 100))
        inadimplencia = _inadimplencia_input / 100
    with col2:
        prazo_medio = st.number_input("Prazo Médio dos Recebíveis (meses)", min_value=1, max_value=120, value=6, step=1)
        _ociosidade_input = st.number_input(
            "Ociosidade de Caixa (%)",
            min_value=0.0, max_value=100.0, value=0.0, step=1.0, format="%.1f",
            help="% do PL mantido em caixa (acruando a 100% CDI). O restante acruará à taxa do ativo.",
        )
        st.caption(fmt_pct(_ociosidade_input / 100))
        ociosidade_caixa = _ociosidade_input / 100

    taxa_liquida = taxa_ativo - inadimplencia
    # CDI de referência para estimativa (primeiro dia da curva, se disponível)
    _cdi_ref_est = ((1.0 + list(curva_cdi.values())[0]) ** 252 - 1.0) if curva_cdi else 0.0
    taxa_efetiva = taxa_ativo * (1 - ociosidade_caixa) + _cdi_ref_est * ociosidade_caixa
    st.info(
        f"**Taxa Líquida de Perdas estimada:** {taxa_liquida*100:.2f}% a.a.  "
        f"|  **Taxa Efetiva da Carteira:** {taxa_efetiva*100:.2f}% a.a. "
        f"({fmt_pct(1 - ociosidade_caixa)} ativo + {fmt_pct(ociosidade_caixa)} caixa)"
    )


# ─────────────────────────────────────────────
# Aba 3: Custos & Despesas
# ─────────────────────────────────────────────
with tab_custos:
    st.subheader("Custos e Despesas do Fundo")
    col1, col2 = st.columns(2)
    with col1:
        _taxa_adm_input = st.number_input("Taxa de Administração (% a.a.)", min_value=0.0, value=0.50, step=0.05, format="%.2f")
        st.caption(fmt_pct(_taxa_adm_input / 100))
        taxa_adm = _taxa_adm_input / 100
        _taxa_gest_input = st.number_input("Taxa de Gestão (% a.a.)", min_value=0.0, value=1.00, step=0.05, format="%.2f")
        st.caption(fmt_pct(_taxa_gest_input / 100))
        taxa_gest = _taxa_gest_input / 100
    with col2:
        _taxa_cust_input = st.number_input("Taxa de Custódia (% a.a.)", min_value=0.0, value=0.20, step=0.05, format="%.2f")
        st.caption(fmt_pct(_taxa_cust_input / 100))
        taxa_cust = _taxa_cust_input / 100
        outras_despesas = brl_input("Outras Despesas (R$/ano)", 50_000.0, "outras_despesas")

    custo_total_pct = taxa_adm + taxa_gest + taxa_cust
    st.info(f"**Total de custos percentuais:** {custo_total_pct*100:.2f}% a.a.  |  **Despesas fixas:** {fmt_brl(outras_despesas)}/ano")

    st.divider()
    st.subheader("Mínimos Mensais")
    st.caption(
        "Defina um valor mínimo mensal (R$) para administração e/ou gestão. "
        "O sistema cobrará o **maior** entre o percentual sobre o PL e o mínimo informado. "
        "Deixe em R$ 0,00 para não aplicar mínimo."
    )
    col_min1, col_min2 = st.columns(2)
    with col_min1:
        minimo_adm = brl_input("Mínimo de Administração (R$/mês)", 0.0, "minimo_adm")
        if minimo_adm > 0:
            st.caption(f"Equivale a {fmt_pct(minimo_adm * 12 / max(1.0, val_inicial_sub))} a.a. sobre o PL inicial da Subordinada")
    with col_min2:
        minimo_gest = brl_input("Mínimo de Gestão (R$/mês)", 0.0, "minimo_gest")
        if minimo_gest > 0:
            st.caption(f"Equivale a {fmt_pct(minimo_gest * 12 / max(1.0, val_inicial_sub))} a.a. sobre o PL inicial da Subordinada")

    st.divider()
    st.subheader("Taxa de Performance")
    cobrar_performance = st.checkbox("Cobrar taxa de performance?", value=False, key="cobrar_perf")

    if cobrar_performance:
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            _pct_perf = st.number_input("Percentual sobre o excesso (%)", min_value=0.0, max_value=100.0, value=20.0, step=1.0, format="%.1f", key="pct_perf")
            st.caption(fmt_pct(_pct_perf / 100))
            perf_pct = _pct_perf / 100
            periodo_perf_label = st.selectbox(
                "Período de Apuração",
                ["Mensal", "Trimestral", "Semestral", "Anual"],
                index=3, key="periodo_perf",
            )
            _mapa_periodo_perf = {
                "Mensal":     PeriodicidadeJuros.MENSAL,
                "Trimestral": PeriodicidadeJuros.TRIMESTRAL,
                "Semestral":  PeriodicidadeJuros.SEMESTRAL,
                "Anual":      PeriodicidadeJuros.ANUAL,
            }
            perf_periodo = _mapa_periodo_perf[periodo_perf_label]
        with col_p2:
            idx_hurdle_label = st.selectbox(
                "Hurdle (indexador)", list(LABEL_INDEXADOR.keys()),
                index=1, key="idx_hurdle_perf",
            )
            idx_hurdle = LABEL_INDEXADOR[idx_hurdle_label]
            if idx_hurdle == TipoIndexador.FIXO:
                _hurdle_fixa = st.number_input("Taxa Fixa Hurdle (% a.a.)", min_value=0.0, value=12.0, step=0.25, format="%.2f", key="hurdle_taxa_fixa")
                st.caption(fmt_pct(_hurdle_fixa / 100))
                hurdle_taxa_fixa = _hurdle_fixa / 100
                hurdle_spread = 0.0
            else:
                _hurdle_spread = st.number_input(f"Spread sobre {idx_hurdle_label} (% a.a.)", min_value=-10.0, value=0.0, step=0.25, format="%.2f", key="hurdle_spread")
                st.caption(fmt_pct(_hurdle_spread / 100))
                hurdle_spread = _hurdle_spread / 100
                hurdle_taxa_fixa = 0.0
            hwm_inicial = brl_input("High-Water Mark Inicial (R$, 0 = PL D+0)", 0.0, "hwm_inicial_perf")
        st.caption("Com High-Water Mark ativado: a performance só é cobrada se o PL da cota Subordinada superar o valor máximo histórico anterior.")
    else:
        perf_pct = 0.20
        perf_periodo = PeriodicidadeJuros.ANUAL
        idx_hurdle = TipoIndexador.CDI
        hurdle_taxa_fixa = 0.0
        hurdle_spread = 0.0
        hwm_inicial = 0.0


# ─────────────────────────────────────────────
# Aba 4: Aportes
# ─────────────────────────────────────────────
with tab_aportes:
    st.subheader("Cronograma de Aportes")
    st.caption("Adicione aportes programados para qualquer cota ao longo do prazo da simulação.")

    if "aportes_lista" not in st.session_state:
        st.session_state.aportes_lista = []

    with st.form("form_aporte", clear_on_submit=False):
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        with col1:
            data_aporte = st.date_input("Data do Aporte", value=date.today() + relativedelta(months=3), format="DD/MM/YYYY")
        with col2:
            tipo_aporte = st.selectbox("Cota", ["Sênior", "Mezanino", "Subordinada"])
        with col3:
            valor_aporte = brl_input("Valor (R$)", 1_000_000.0, "form_aporte_valor")
        with col4:
            st.markdown("<br>", unsafe_allow_html=True)
            submitted_aporte = st.form_submit_button("➕ Adicionar")

        if submitted_aporte and valor_aporte > 0:
            mapa_tipo = {"Sênior": TipoCota.SENIOR, "Mezanino": TipoCota.MEZANINO, "Subordinada": TipoCota.SUBORDINADA}
            st.session_state.aportes_lista.append({
                "data": data_aporte,
                "cota": tipo_aporte,
                "valor": valor_aporte,
                "tipo_cota": mapa_tipo[tipo_aporte],
            })
            # Sinaliza reset do campo para o próximo render
            st.session_state["_reset_form_aporte_valor"] = True
            st.success(f"Aporte de {fmt_brl(valor_aporte)} em {tipo_aporte} adicionado para {data_aporte}.")

    if "aporte_editando" not in st.session_state:
        st.session_state.aporte_editando = None

    if st.session_state.aportes_lista:
        st.markdown("##### Aportes programados")
        mapa_tipo = {"Sênior": TipoCota.SENIOR, "Mezanino": TipoCota.MEZANINO, "Subordinada": TipoCota.SUBORDINADA}

        for i, a in enumerate(st.session_state.aportes_lista):
            col_data, col_cota, col_valor, col_edit, col_del = st.columns([2, 2, 2, 1, 1])
            col_data.write(a["data"].strftime("%d/%m/%Y"))
            col_cota.write(a["cota"])
            col_valor.write(fmt_brl(a["valor"]))
            if col_edit.button("✏️", key=f"edit_a_{i}", help="Editar"):
                st.session_state.aporte_editando = i
                st.rerun()
            if col_del.button("🗑️", key=f"del_a_{i}", help="Excluir"):
                st.session_state.aportes_lista.pop(i)
                if st.session_state.aporte_editando == i:
                    st.session_state.aporte_editando = None
                st.rerun()

        # Formulário de edição inline
        if st.session_state.aporte_editando is not None:
            idx = st.session_state.aporte_editando
            if idx < len(st.session_state.aportes_lista):
                a_edit = st.session_state.aportes_lista[idx]
                st.divider()
                st.markdown(f"**Editando aporte #{idx + 1}**")
                with st.form("form_editar_aporte"):
                    ec1, ec2, ec3 = st.columns([2, 2, 2])
                    with ec1:
                        nova_data = st.date_input("Data", value=a_edit["data"], format="DD/MM/YYYY")
                    with ec2:
                        nova_cota = st.selectbox(
                            "Cota",
                            ["Sênior", "Mezanino", "Subordinada"],
                            index=["Sênior", "Mezanino", "Subordinada"].index(a_edit["cota"]),
                        )
                    with ec3:
                        novo_valor = brl_input("Valor (R$)", a_edit["valor"], f"edit_aporte_valor_{idx}")
                    col_salvar, col_cancelar = st.columns([1, 1])
                    salvar = col_salvar.form_submit_button("💾 Salvar", use_container_width=True)
                    cancelar = col_cancelar.form_submit_button("Cancelar", use_container_width=True)

                if salvar and novo_valor > 0:
                    st.session_state.aportes_lista[idx] = {
                        "data": nova_data,
                        "cota": nova_cota,
                        "valor": novo_valor,
                        "tipo_cota": mapa_tipo[nova_cota],
                    }
                    st.session_state.aporte_editando = None
                    st.rerun()
                if cancelar:
                    st.session_state.aporte_editando = None
                    st.rerun()

        st.divider()
        if st.button("🗑️ Limpar todos os aportes"):
            st.session_state.aportes_lista = []
            st.session_state.aporte_editando = None
            st.rerun()
    else:
        st.info("Nenhum aporte programado. A simulação rodará apenas com a capitalização inicial.")


# ─────────────────────────────────────────────
# Aba 5: Amortizações
# ─────────────────────────────────────────────
with tab_amort:
    st.subheader("Cronograma de Amortizações")
    st.caption(
        "Programe pagamentos de juros e/ou principal para as cotas Sênior, Mezanino e Subordinada. "
        "Cada amortização sai do PL da cota correspondente."
    )

    if "amort_lista" not in st.session_state:
        st.session_state.amort_lista = []

    with st.form("form_amort", clear_on_submit=False):
        col1, col2, col3 = st.columns([2, 2, 2])
        with col1:
            data_amort = st.date_input("Data da Amortização", value=date.today() + relativedelta(months=6), key="data_amort_form", format="DD/MM/YYYY")
        with col2:
            cota_amort = st.selectbox("Cota", ["Sênior", "Mezanino", "Subordinada"], key="cota_amort_form")
        with col3:
            tipo_amort_label = st.selectbox("Tipo", list(LABEL_TIPO_AMORT.keys()), key="tipo_amort_form")

        # Campos de valor só aparecem para tipos que precisam de um montante informado
        tipo_amort_selecionado = LABEL_TIPO_AMORT[tipo_amort_label]
        precisa_valor = tipo_amort_selecionado != TipoAmortizacao.JUROS_ACUMULADOS

        valor_amort = 0.0
        pct_amort = 0.0

        if precisa_valor:
            col4a, col4b = st.columns(2)
            with col4a:
                valor_amort = brl_input("Valor (R$)", 0.0, "form_amort_valor")
            with col4b:
                _pct_amort_input = st.number_input(
                    "% do PL", min_value=0.0, max_value=100.0, value=0.0, step=1.0,
                    format="%.1f", key="pct_amort_form",
                )
                st.caption(fmt_pct(_pct_amort_input / 100))
                pct_amort = _pct_amort_input / 100
        else:
            st.info(
                "**Juros Acumulados (total):** o sistema calculará automaticamente "
                "o excedente sobre o principal original (PL atual − principal) e amortizará esse valor integralmente.",
                icon="ℹ️",
            )

        submitted_amort = st.form_submit_button("➕ Adicionar")

        pode_adicionar = submitted_amort and (
            not precisa_valor or valor_amort > 0 or pct_amort > 0
        )
        if pode_adicionar:
            # Sinaliza reset do campo para o próximo render
            st.session_state["_reset_form_amort_valor"] = True
            mapa_cota = {"Sênior": TipoCota.SENIOR, "Mezanino": TipoCota.MEZANINO, "Subordinada": TipoCota.SUBORDINADA}
            st.session_state.amort_lista.append({
                "data": data_amort,
                "cota": cota_amort,
                "tipo": tipo_amort_label,
                "valor": valor_amort,
                "percentual": pct_amort,
                "tipo_cota": mapa_cota[cota_amort],
                "tipo_amort": tipo_amort_selecionado,
            })
            if not precisa_valor:
                desc_valor = "todos os juros acumulados"
            elif valor_amort > 0:
                desc_valor = fmt_brl(valor_amort)
            else:
                desc_valor = f"{pct_amort*100:.1f}% do PL"
            st.success(f"Amortização de {desc_valor} ({tipo_amort_label}) em {cota_amort} adicionada para {data_amort}.")

    if st.session_state.amort_lista:
        df_amort_view = pd.DataFrame([
            {
                "Data": a["data"].strftime("%d/%m/%Y"),
                "Cota": a["cota"],
                "Tipo": a["tipo"],
                "Valor (R$)": (
                    "Automático (PL − principal)"
                    if a["tipo_amort"] == TipoAmortizacao.JUROS_ACUMULADOS
                    else (fmt_brl(a["valor"]) if a["valor"] > 0 else "-")
                ),
                "% do PL": (
                    "-"
                    if a["tipo_amort"] == TipoAmortizacao.JUROS_ACUMULADOS
                    else (f"{a['percentual']*100:.1f}%" if a["percentual"] > 0 else "-")
                ),
            }
            for a in st.session_state.amort_lista
        ])
        st.dataframe(df_amort_view, use_container_width=True, hide_index=True)

        col_limpar2, _ = st.columns([1, 4])
        with col_limpar2:
            if st.button("🗑️ Limpar amortizações"):
                st.session_state.amort_lista = []
                st.rerun()
    else:
        st.info("Nenhuma amortização programada.")


# ─────────────────────────────────────────────
# Aba 6: Resultados
# ─────────────────────────────────────────────
with tab_resultado:
    st.subheader("Rodar Simulação")

    rodar = st.button("▶️ Simular", type="primary", use_container_width=False)

    if rodar:
        cota_senior_obj = None
        if usar_senior:
            cota_senior_obj = ConfiguracaoCota(
                tipo=TipoCota.SENIOR,
                valor_inicial=val_inicial_senior,
                valor_unitario=val_unit_senior,
                tipo_indexador=idx_senior,
                taxa_fixa_anual=taxa_senior if idx_senior == TipoIndexador.FIXO else 0.0,
                spread_sobre_indexador=spread_senior if idx_senior != TipoIndexador.FIXO else 0.0,
                periodicidade_juros=periodicidade_senior,
            )

        cota_mezanino_obj = None
        if usar_mezanino:
            cota_mezanino_obj = ConfiguracaoCota(
                tipo=TipoCota.MEZANINO,
                valor_inicial=val_inicial_mezanino,
                valor_unitario=val_unit_mezanino,
                tipo_indexador=idx_mezanino,
                taxa_fixa_anual=taxa_mezanino if idx_mezanino == TipoIndexador.FIXO else 0.0,
                spread_sobre_indexador=spread_mezanino if idx_mezanino != TipoIndexador.FIXO else 0.0,
                periodicidade_juros=periodicidade_mezanino,
            )

        cota_sub_obj = ConfiguracaoCota(
            tipo=TipoCota.SUBORDINADA,
            valor_inicial=val_inicial_sub,
            valor_unitario=val_unit_sub,
            periodicidade_juros=periodicidade_sub,
        )

        aportes_objs = [
            Aporte(data=a["data"], tipo_cota=a["tipo_cota"], valor=a["valor"])
            for a in st.session_state.aportes_lista
        ]

        amort_objs = [
            Amortizacao(
                data=a["data"],
                tipo_cota=a["tipo_cota"],
                tipo=a["tipo_amort"],
                valor=a["valor"],
                percentual=a["percentual"],
            )
            for a in st.session_state.amort_lista
        ]

        params = ParametrosFundo(
            nome=nome_fundo,
            data_inicio=data_inicio,
            prazo_meses=prazo_meses,
            cota_senior=cota_senior_obj,
            cota_mezanino=cota_mezanino_obj,
            cota_subordinada=cota_sub_obj,
            ativo=ConfiguracaoAtivo(taxa_ativo, inadimplencia, prazo_medio, ociosidade_caixa),
            custos=ConfiguracaoCustos(
                taxa_administracao=taxa_adm,
                taxa_gestao=taxa_gest,
                taxa_custodia=taxa_cust,
                outras_despesas_anuais=outras_despesas,
                minimo_mensal_administracao=minimo_adm,
                minimo_mensal_gestao=minimo_gest,
            ),
            performance=ConfiguracaoPerformance(
                ativo=cobrar_performance,
                percentual=perf_pct,
                periodo_apuracao=perf_periodo,
                hurdle_indexador=idx_hurdle,
                hurdle_taxa_fixa=hurdle_taxa_fixa,
                hurdle_spread=hurdle_spread,
                high_water_mark_inicial=hwm_inicial,
            ),
            aportes=aportes_objs,
            amortizacoes=amort_objs,
            curva_cdi=curva_cdi,
            ipca_anual=ipca_anual,
            subordinacao_minima=subordinacao_minima,
        )

        with st.spinner("Calculando..."):
            df_result = rodar_simulacao(params)
            metricas = calcular_metricas_resumo(df_result, params)

        st.session_state["df_result"] = df_result
        st.session_state["metricas"] = metricas
        st.session_state["params_nome"] = nome_fundo
        st.session_state["sub_minima"] = subordinacao_minima
        st.session_state["params_data_inicio"] = data_inicio
        st.session_state["params_obj"] = params
        st.session_state["usar_senior_saved"] = usar_senior
        st.session_state["usar_mezanino_saved"] = usar_mezanino

    # ── Exibe resultados ──
    if "df_result" in st.session_state:
        df = st.session_state["df_result"]
        metricas = st.session_state["metricas"]
        sub_min_saved = st.session_state.get("sub_minima", subordinacao_minima)

        st.success(f"Simulação concluída: **{st.session_state['params_nome']}**")

        # Métricas de resumo
        st.subheader("Métricas de Resumo")
        cols = st.columns(4)
        destaques = [
            ("PL Final", fmt_brl(metricas.get("PL Final (R$)", 0))),
            ("Sub. Final", fmt_pct(metricas.get("Subordinação Final", 0))),
            ("D.U. com Alerta Sub.", str(int(metricas.get("Dias Úteis com Alerta de Subordinação", 0)))),
        ]
        _perf_total = metricas.get("Total Taxa de Performance (R$)", 0)
        if _perf_total > 0:
            destaques.append(("Tx. Performance Total", fmt_brl(_perf_total)))
        for col, (label, valor) in zip(cols, destaques):
            col.metric(label, valor)

        # ── TIR da Subordinada por ano de projeção ──
        st.markdown("**Retorno da Cota Subordinada por Ano**")
        _data_inicio_sim = st.session_state.get("params_data_inicio", data_inicio)

        # DataFrame com todos os dias úteis: data + PL subordinada
        _df_du_datas = df[df["mes"] > 0][["data", "pl_subordinada"]].copy()
        _df_du_datas["data"] = pd.to_datetime(_df_du_datas["data"])
        _df_du_datas = _df_du_datas.sort_values("data").reset_index(drop=True)
        _datas_du = _df_du_datas["data"].tolist()

        def _primeiro_du_apos(alvo_date):
            """Retorna (índice, Timestamp) do primeiro dia útil >= alvo_date."""
            ts = pd.Timestamp(alvo_date)
            idx = next((i for i, d in enumerate(_datas_du) if d >= ts), None)
            if idx is None:
                return None, None
            return idx, _datas_du[idx]

        # Marcos anuais: D+0 (início), D+1ano, D+2anos, ...
        # Cada marco é o primeiro d.u. >= data_inicio + N anos
        _marcos = []  # lista de (date_alvo_calendário, idx_du, timestamp_du)
        # Marco 0 = D+0 (início da simulação, usando PL inicial)
        _marcos.append((_data_inicio_sim, -1, None))  # -1 = usa pl_sub_d0
        _data_fim_sim = _datas_du[-1].date()
        for _n in range(1, 20):
            _alvo = _data_inicio_sim + relativedelta(years=_n)
            if _alvo > _data_fim_sim:
                break
            _idx, _ts = _primeiro_du_apos(_alvo)
            if _idx is None:
                break
            _marcos.append((_alvo, _idx, _ts))

        _n_anos = len(_marcos) - 1  # quantos anos completos existem
        if _n_anos == 0:
            st.info("Prazo de simulação menor que 1 ano — retorno anual não disponível.")
        else:
            _tir_cols = st.columns(min(_n_anos, 6))
            _pl_sub_d0 = metricas.get("PL Sub. Inicial (R$)", 0)
            for _i in range(1, len(_marcos)):
                _alvo_ini, _idx_ini, _ts_ini = _marcos[_i - 1]
                _alvo_fim, _idx_fim, _ts_fim = _marcos[_i]

                # PL no início do período (marco anterior)
                if _idx_ini == -1:
                    _pl_ini = _pl_sub_d0
                    _data_ini_str = _data_inicio_sim.strftime("%d/%m/%Y")
                else:
                    _pl_ini = _df_du_datas.iloc[_idx_ini]["pl_subordinada"]
                    _data_ini_str = _ts_ini.strftime("%d/%m/%Y")

                # PL no fim do período (marco atual)
                _pl_fim = _df_du_datas.iloc[_idx_fim]["pl_subordinada"]
                _data_fim_str = _ts_fim.strftime("%d/%m/%Y")

                if _pl_ini > 0 and _pl_fim > 0:
                    _retorno_ano = (_pl_fim / _pl_ini) - 1
                    _label = f"Ano {_i}  ·  {_data_ini_str} → {_data_fim_str}"
                    _tir_cols[(_i - 1) % len(_tir_cols)].metric(_label, fmt_pct(_retorno_ano))

        with st.expander("Ver todas as métricas"):
            for k, v in metricas.items():
                if isinstance(v, float):
                    st.write(f"**{k}:** {fmt_brl(v)}" if "R$" in k else f"**{k}:** {fmt_pct(v)}")
                else:
                    st.write(f"**{k}:** {v}")

        st.divider()

        df_du = df[df["mes"] > 0].copy()

        # ── Prepare data para gráficos compactos (sem dias não-úteis) ──
        # Converte datas em rótulos categóricos, mantendo a data no hover
        df_du["data_label"] = df_du["data"].dt.strftime("%d/%m/%Y")
        x_indices = list(range(len(df_du)))

        # ── Gráfico 1: Evolução do PL — barras empilhadas diárias ──
        # Ordem de adição = ordem visual de baixo para cima: Subordinada → Mezanino → Sênior
        st.subheader("Evolução do PL por Cota")
        fig_pl = go.Figure()
        fig_pl.add_trace(go.Bar(
            x=x_indices, y=df_du["pl_subordinada"],
            name="Subordinada", marker_color="#00183C",
            customdata=df_du[["data_label", "pl_subordinada"]].values,
            hovertemplate="<b>%{customdata[0]}</b><br>Subordinada: %{customdata[1]:,.0f}<extra></extra>",
        ))
        if df_du["pl_mezanino"].max() > 0:
            fig_pl.add_trace(go.Bar(
                x=x_indices, y=df_du["pl_mezanino"],
                name="Mezanino", marker_color="#2379AF",
                customdata=df_du[["data_label", "pl_mezanino"]].values,
                hovertemplate="<b>%{customdata[0]}</b><br>Mezanino: %{customdata[1]:,.0f}<extra></extra>",
            ))
        if df_du["pl_senior"].max() > 0:
            fig_pl.add_trace(go.Bar(
                x=x_indices, y=df_du["pl_senior"],
                name="Sênior", marker_color="#C7DDEB",
                customdata=df_du[["data_label", "pl_senior"]].values,
                hovertemplate="<b>%{customdata[0]}</b><br>Sênior: %{customdata[1]:,.0f}<extra></extra>",
            ))
        fig_pl.update_layout(
            barmode="stack", yaxis_title="R$", xaxis_title="Data",
            hovermode="x unified", height=420, legend=dict(traceorder="reversed"),
            yaxis=dict(tickformat=",.0f", tickprefix="R$ "),
            separators=",.",
            xaxis=dict(tickmode="linear", tick0=0, dtick=max(1, len(df_du) // 20)),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F4F8FC",
            font=dict(family="Futura Bk BT, Futura, Segoe UI, sans-serif", color="#00183C"),
        )
        st.plotly_chart(fig_pl, use_container_width=True)

        # ── Gráfico 2: Subordinação diária ──
        st.subheader("Índice de Subordinação (Diário)")
        fig_sub = go.Figure()
        fig_sub.add_trace(go.Bar(
            x=x_indices, y=df_du["subordinacao"] * 100,
            name="Subordinação (%)", marker_color="rgba(0,24,60,0.80)",
            customdata=df_du["data_label"],
            hovertemplate="<b>%{customdata}</b><br>Subordinação: %{y:.2f}%<extra></extra>",
        ))
        fig_sub.add_hline(
            y=sub_min_saved * 100, line_dash="dash", line_color="#81BDDB",
            annotation_text=f"Mínimo: {sub_min_saved*100:.0f}%",
        )
        fig_sub.update_layout(
            yaxis_title="%", xaxis_title="Data", height=350,
            xaxis=dict(tickmode="linear", tick0=0, dtick=max(1, len(df_du) // 20)),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F4F8FC",
            font=dict(family="Futura Bk BT, Futura, Segoe UI, sans-serif", color="#00183C"),
        )
        st.plotly_chart(fig_sub, use_container_width=True)

        # ── Gráfico 3: Retorno mensal da subordinada ──
        st.subheader("Retorno Mensal da Cota Subordinada")
        df_ret = df_du[df_du["retorno_subordinada_mensal"].notna()].copy()
        # Mapeia os índices originais de df_ret para posições em x_indices
        ret_indices = [list(df_du.index).index(idx) for idx in df_ret.index]
        fig_ret = go.Figure()
        fig_ret.add_trace(go.Bar(
            x=ret_indices,
            y=df_ret["retorno_subordinada_mensal"] * 100,
            name="Retorno mensal (%)",
            marker_color=np.where(df_ret["retorno_subordinada_mensal"] >= 0, "#00183C", "#81BDDB"),
            customdata=df_ret["data_label"],
            hovertemplate="<b>%{customdata}</b><br>Retorno: %{y:.2f}%<extra></extra>",
        ))
        fig_ret.update_layout(
            yaxis_title="%", xaxis_title="Data", height=350,
            xaxis=dict(tickmode="linear", tick0=0, dtick=max(1, len(df_du) // 20)),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F4F8FC",
            font=dict(family="Futura Bk BT, Futura, Segoe UI, sans-serif", color="#00183C"),
        )
        st.plotly_chart(fig_ret, use_container_width=True)

        # ── Gráfico 4: Waterfall diário ──
        st.subheader("Distribuição de Resultados (Waterfall Diário)")
        fig_wf = go.Figure()
        fig_wf.add_trace(go.Bar(
            x=x_indices, y=df_du["rendimento_senior"], name="Rend. Sênior", marker_color="#C7DDEB",
            customdata=df_du["data_label"],
            hovertemplate="<b>%{customdata}</b><br>Rend. Sênior: %{y:,.0f}<extra></extra>",
        ))
        if df_du["rendimento_mezanino"].max() > 0:
            fig_wf.add_trace(go.Bar(
                x=x_indices, y=df_du["rendimento_mezanino"], name="Rend. Mezanino", marker_color="#2379AF",
                customdata=df_du["data_label"],
                hovertemplate="<b>%{customdata}</b><br>Rend. Mezanino: %{y:,.0f}<extra></extra>",
            ))
        fig_wf.add_trace(go.Bar(
            x=x_indices, y=df_du["rendimento_subordinada"], name="Excesso Sub.", marker_color="#00183C",
            customdata=df_du["data_label"],
            hovertemplate="<b>%{customdata}</b><br>Excesso Sub.: %{y:,.0f}<extra></extra>",
        ))
        fig_wf.add_trace(go.Bar(
            x=x_indices, y=-df_du["pdd"], name="PDD", marker_color="#7B1C1C",
            customdata=df_du["data_label"],
            hovertemplate="<b>%{customdata}</b><br>PDD: %{y:,.0f}<extra></extra>",
        ))
        fig_wf.add_trace(go.Bar(
            x=x_indices, y=-df_du["despesas_totais"], name="Despesas", marker_color="#5A3E8A",
            customdata=df_du["data_label"],
            hovertemplate="<b>%{customdata}</b><br>Despesas: %{y:,.0f}<extra></extra>",
        ))
        if df_du["amort_senior"].max() > 0:
            fig_wf.add_trace(go.Bar(
                x=x_indices, y=-df_du["amort_senior"], name="Amort. Sênior", marker_color="#A8C8D8",
                customdata=df_du["data_label"],
                hovertemplate="<b>%{customdata}</b><br>Amort. Sênior: %{y:,.0f}<extra></extra>",
            ))
        if df_du["amort_mezanino"].max() > 0:
            fig_wf.add_trace(go.Bar(
                x=x_indices, y=-df_du["amort_mezanino"], name="Amort. Mezanino", marker_color="#81BDDB",
                customdata=df_du["data_label"],
                hovertemplate="<b>%{customdata}</b><br>Amort. Mezanino: %{y:,.0f}<extra></extra>",
            ))
        if "taxa_performance" in df_du.columns and df_du["taxa_performance"].max() > 0:
            fig_wf.add_trace(go.Bar(
                x=x_indices, y=-df_du["taxa_performance"], name="Tx. Performance", marker_color="#8B4513",
                customdata=df_du["data_label"],
                hovertemplate="<b>%{customdata}</b><br>Tx. Performance: %{y:,.0f}<extra></extra>",
            ))
        fig_wf.update_layout(
            barmode="relative", yaxis_title="R$", xaxis_title="Data", height=420,
            xaxis=dict(tickmode="linear", tick0=0, dtick=max(1, len(df_du) // 20)),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F4F8FC",
            font=dict(family="Futura Bk BT, Futura, Segoe UI, sans-serif", color="#00183C"),
        )
        st.plotly_chart(fig_wf, use_container_width=True)

        # ── Tabela detalhada ──
        st.subheader("Tabela de Evolução Diária")

        # Seletor de visualização
        visao = st.radio(
            "Visualização",
            ["Diária (todos os dias úteis)", "Mensal (último d.u. do mês)"],
            horizontal=True,
        )
        if visao == "Mensal (último d.u. do mês)":
            df_tabela = df[df["retorno_subordinada_mensal"].notna() | (df["mes"] == 0)].copy()
        else:
            df_tabela = df.copy()

        df_display = df_tabela.copy()
        df_display["data"] = df_display["data"].dt.strftime("%d/%m/%Y")
        df_display.loc[df_display["mes"] == 0, "data"] += " (D+0)"
        df_display["subordinacao"] = (df_display["subordinacao"] * 100).round(2).astype(str) + "%"
        df_display["retorno_subordinada_anual"] = df_display["retorno_subordinada_anual"].apply(
            lambda x: f"{x*100:.2f}%" if pd.notna(x) else "-"
        )
        if "cdi_utilizado" not in df_display.columns:
            df_display["cdi_utilizado"] = 0.0
        df_display["cdi_utilizado"] = df_display["cdi_utilizado"].apply(
            lambda x: f"{x*100:.2f}%"
        )

        colunas_exibir = {
            "mes": "Mês",
            "data": "Data",
            "cdi_utilizado": "CDI (a.a.)",
            "pl_senior": "PL Sênior (R$)",
            "pl_mezanino": "PL Mezanino (R$)",
            "pl_subordinada": "PL Subordinada (R$)",
            "pl_total": "PL Total (R$)",
            "aporte_senior": "Aporte Sênior (R$)",
            "aporte_mezanino": "Aporte Mez. (R$)",
            "aporte_subordinada": "Aporte Sub. (R$)",
            "amort_senior": "Amort. Sênior (R$)",
            "amort_mezanino": "Amort. Mez. (R$)",
            "receita_ativo": "Receita Ativo (R$)",
            "receita_caixa": "Receita Caixa (R$)",
            "receita_bruta": "Receita Bruta (R$)",
            "pdd": "PDD (R$)",
            "despesas_totais": "Despesas (R$)",
            "rendimento_senior": "Rend. Sênior (R$)",
            "rendimento_mezanino": "Rend. Mezanino (R$)",
            "rendimento_subordinada": "Excesso Sub. (R$)",
            "subordinacao": "Subordinação",
            "retorno_subordinada_anual": "Retorno Sub. (a.a.)",
            "alerta_subordinacao": "⚠️ Alerta",
            "taxa_performance": "Tx. Performance (R$)",
        }
        df_show = df_display[
            [c for c in colunas_exibir.keys() if c in df_display.columns]
        ].rename(columns=colunas_exibir)

        cols_brl = [
            "PL Sênior (R$)", "PL Mezanino (R$)", "PL Subordinada (R$)", "PL Total (R$)",
            "Aporte Sênior (R$)", "Aporte Mez. (R$)", "Aporte Sub. (R$)",
            "Amort. Sênior (R$)", "Amort. Mez. (R$)",
            "Receita Ativo (R$)", "Receita Caixa (R$)", "Receita Bruta (R$)", "PDD (R$)", "Despesas (R$)",
            "Rend. Sênior (R$)", "Rend. Mezanino (R$)", "Excesso Sub. (R$)", "Tx. Performance (R$)",
        ]
        for col in cols_brl:
            if col in df_show.columns:
                df_show[col] = df_show[col].apply(
                    lambda x: fmt_brl(x) if isinstance(x, float) else x
                )

        st.dataframe(df_show, use_container_width=True, hide_index=True)

        # ── Exportação ──
        st.divider()
        st.subheader("📥 Exportar Resultados")

        def gerar_excel(df_result: pd.DataFrame) -> bytes:
            import io
            # Formata apenas a coluna de data; demais colunas são numéricas e exportam sem alteração
            df_exp = df_result.assign(data=df_result["data"].dt.strftime("%d/%m/%Y"))
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_exp.to_excel(writer, index=False, sheet_name="Evolução Mensal")
            return output.getvalue()

        def _grafico_pl_bytes(df_du: pd.DataFrame, tem_senior: bool, tem_mezanino: bool, data_inicio) -> bytes:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import io as _io

            x = list(range(len(df_du)))
            fig, ax = plt.subplots(figsize=(9, 3.2), facecolor="#FFFFFF")
            ax.set_facecolor("#F4F8FC")

            bottom = np.zeros(len(df_du))
            ax.bar(x, df_du["pl_subordinada"].values, bottom=bottom, color="#00183C", label="Subordinada", width=1.0)
            bottom += df_du["pl_subordinada"].values
            if tem_mezanino and df_du["pl_mezanino"].max() > 0:
                ax.bar(x, df_du["pl_mezanino"].values, bottom=bottom, color="#2379AF", label="Mezanino", width=1.0)
                bottom += df_du["pl_mezanino"].values
            if tem_senior and df_du["pl_senior"].max() > 0:
                ax.bar(x, df_du["pl_senior"].values, bottom=bottom, color="#C7DDEB", label="Sênior", width=1.0)

            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"R$ {v/1e6:.1f}M" if v >= 1e6 else f"R$ {v:,.0f}"))
            n = len(x)
            step = max(1, n // 10)
            tick_pos = list(range(0, n, step))
            tick_labels = [df_du["data_label"].iloc[i] for i in tick_pos]
            ax.set_xticks(tick_pos)
            ax.set_xticklabels(tick_labels, rotation=30, ha="right", fontsize=7)
            ax.tick_params(axis="y", labelsize=7)
            # Legenda invertida: Sênior (topo) → Mezanino → Subordinada (base),
            # acompanhando a ordem visual do empilhamento das barras.
            _handles, _labels = ax.get_legend_handles_labels()
            ax.legend(_handles[::-1], _labels[::-1], fontsize=7, loc="upper left", framealpha=0.7)
            ax.set_xlim(-1, n)

            # Rótulos anuais com PL total a cada aniversário da constituição
            _datas_du = pd.to_datetime(df_du["data"]).reset_index(drop=True)
            _data_inicio_ts = pd.Timestamp(data_inicio)
            _data_fim_ts = _datas_du.iloc[-1]
            _pl_total_arr = df_du["pl_total"].values
            _y_max = float(_pl_total_arr.max()) if len(_pl_total_arr) else 0.0
            _offset = _y_max * 0.02
            _ano_n = 1
            while True:
                _alvo = _data_inicio_ts + pd.DateOffset(years=_ano_n)
                if _alvo > _data_fim_ts:
                    break
                _mask = _datas_du >= _alvo
                if not _mask.any():
                    break
                _idx = int(_mask.idxmax())
                _pl_total_dia = float(_pl_total_arr[_idx])
                _label = (f"R$ {_pl_total_dia/1e9:.2f}B" if _pl_total_dia >= 1e9
                          else f"R$ {_pl_total_dia/1e6:.1f}M" if _pl_total_dia >= 1e6
                          else f"R$ {_pl_total_dia:,.0f}")
                ax.text(_idx, _pl_total_dia + _offset, _label,
                        ha="center", va="bottom", fontsize=6.5, color="#00183C",
                        fontweight="bold")
                _ano_n += 1

            # Margem superior para acomodar os rótulos
            if _y_max > 0:
                ax.set_ylim(top=_y_max * 1.10)

            fig.tight_layout(pad=0.5)

            buf = _io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()

        def _grafico_ret_bytes(df_du: pd.DataFrame) -> bytes:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import io as _io

            df_ret = df_du[df_du["retorno_subordinada_mensal"].notna()].copy()
            x = list(range(len(df_ret)))
            vals = df_ret["retorno_subordinada_mensal"].values * 100
            colors = ["#00183C" if v >= 0 else "#81BDDB" for v in vals]

            fig, ax = plt.subplots(figsize=(9, 2.8), facecolor="#FFFFFF")
            ax.set_facecolor("#F4F8FC")
            bars = ax.bar(x, vals, color=colors, width=0.8)
            ax.axhline(0, color="#2379AF", linewidth=0.8)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.1f}%"))
            n = len(x)
            step = max(1, n // 10)
            tick_pos = list(range(0, n, step))
            tick_labels = [df_ret["data_label"].iloc[i] for i in tick_pos]
            ax.set_xticks(tick_pos)
            ax.set_xticklabels(tick_labels, rotation=30, ha="right", fontsize=7)
            ax.tick_params(axis="y", labelsize=7)
            ax.set_xlim(-1, n)
            # Rótulos de dados na parte exterior das colunas (vertical, evita sobreposição)
            for bar, v in zip(bars, vals):
                label = f"{v:.2f}%"
                if v >= 0:
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                            label, ha="center", va="bottom", fontsize=5.5, color="#00183C",
                            rotation=90, rotation_mode="anchor")
                else:
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() - 0.05,
                            label, ha="center", va="top", fontsize=5.5, color="#2379AF",
                            rotation=90, rotation_mode="anchor")
            fig.tight_layout(pad=0.5)

            buf = _io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()

        def gerar_pdf(
            df_result: pd.DataFrame,
            metricas_dict: dict,
            params_obj,
            df_du_graf: pd.DataFrame,
            tem_senior: bool,
            tem_mezanino: bool,
            descricao_fundo: str = "",
            secoes: dict | None = None,
            ordem_secoes: list | None = None,
        ) -> bytes:
            # secoes: dict {chave_secao: bool} controla inclusão.
            # ordem_secoes: lista de chaves na ordem desejada de aparição.
            secoes = secoes if secoes is not None else {}
            def _inc(k: str) -> bool:
                return secoes.get(k, True)
            # Coletor por seção: cada seção escreve flowables aqui em vez de em `story`,
            # e a ordem final é resolvida na montagem ao fim da função.
            _sec_flow: dict[str, list] = {
                "descricao": [], "indicadores": [], "cronograma_aportes": [],
                "juros_amortizacoes": [], "estrutura_cotas": [], "metricas": [],
                "grafico_pl": [], "grafico_retorno": [], "tabela_semestral": [],
            }
            import io as _io
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph,
                Image as RLImage, KeepTogether,
            )
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib.colors import HexColor, white
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.enums import TA_LEFT, TA_CENTER

            # Gerar gráficos via matplotlib (sem kaleido)
            fig_pl_bytes = _grafico_pl_bytes(df_du_graf, tem_senior, tem_mezanino, params_obj.data_inicio)
            fig_ret_bytes = _grafico_ret_bytes(df_du_graf)

            # ── Cores ICE ──
            C_DARK  = HexColor("#00183C")
            C_DEEP  = HexColor("#084073")
            C_BLUE  = HexColor("#2379AF")
            C_LIGHT = HexColor("#C7DDEB")
            C_MID   = HexColor("#81BDDB")
            C_WHITE = white

            PAGE_W, PAGE_H = A4
            MARGIN = 15 * mm
            CONTENT_W = PAGE_W - 2 * MARGIN

            def _ps(name, size=9, color=C_DARK, bold=False, align=TA_LEFT, leading=None):
                return ParagraphStyle(
                    name, fontSize=size, textColor=color,
                    fontName="Helvetica-Bold" if bold else "Helvetica",
                    alignment=align, leading=leading or size * 1.35, spaceAfter=0,
                )

            ps_titulo        = _ps("titulo", 10, C_DARK, bold=True)
            ps_hdr_lg        = _ps("hdr_lg", 13, C_WHITE, bold=True)
            ps_branco        = _ps("branco", 8, C_WHITE)
            ps_cinza         = _ps("cinza", 7, C_MID)
            ps_normal        = _ps("normal", 8, C_DARK)
            ps_ind_label     = _ps("ind_label", 7, C_BLUE)
            ps_ind_val       = _ps("ind_val", 13, C_DARK, bold=True)
            ps_ind_sub       = _ps("ind_sub", 7, HexColor("#888888"))
            ps_metric_label  = _ps("ml", 7, C_LIGHT, bold=True)
            ps_metric_val    = _ps("mv", 9, C_WHITE, bold=True)

            output = _io.BytesIO()
            doc = SimpleDocTemplate(
                output, pagesize=A4,
                leftMargin=MARGIN, rightMargin=MARGIN,
                topMargin=10 * mm, bottomMargin=22 * mm,
            )

            def _rodape(canvas, doc):
                canvas.saveState()
                canvas.setStrokeColor(C_BLUE)
                canvas.setLineWidth(1)
                y_text = 14 * mm
                y_line = y_text + 3 * mm  # linha 3mm acima do texto, evita sobreposição
                canvas.line(MARGIN, y_line, PAGE_W - MARGIN, y_line)
                canvas.setFont("Helvetica", 7)
                canvas.setFillColor(C_DEEP)
                canvas.drawString(MARGIN, y_text - 5,
                    "ICE Asset Management — Documento gerado automaticamente pelo Sistema de Modelagem de FIDCs")
                canvas.drawRightString(PAGE_W - MARGIN, y_text - 5, f"Pág. {doc.page}")
                canvas.restoreState()

            story = []

            # ── SEÇÃO 1: Cabeçalho ──────────────────
            # Logo em fundo branco à esquerda; bloco azul escuro apenas com os textos à direita
            logo_path = os.path.join(os.path.dirname(__file__), "..", "LOGO ICE _ NOVO FUNDO TRANSPARENTE.png")
            if os.path.exists(logo_path):
                from PIL import Image as _PILImage
                _pil = _PILImage.open(logo_path)
                _orig_w, _orig_h = _pil.size
                _logo_h = 40.0
                _logo_w = _logo_h * _orig_w / _orig_h
                logo_cell = RLImage(logo_path, width=_logo_w, height=_logo_h)
            else:
                _logo_w = 60.0
                logo_cell = Paragraph("ICE", _ps("ico", 13, C_DARK, bold=True))

            nome_pdf = params_obj.nome
            data_ger = date.today().strftime("%d/%m/%Y")
            texto_hdr = [
                Paragraph(nome_pdf, ps_hdr_lg),
                Paragraph("Veículo: FIDC", ps_branco),
                Paragraph("Gestão: ICE Asset Management", ps_branco),
                Paragraph(f"Gerado em {data_ger}", ps_cinza),
            ]

            _logo_col_w = _logo_w + 12
            _txt_col_w  = CONTENT_W - _logo_col_w

            hdr_tbl = Table(
                [[logo_cell, texto_hdr]],
                colWidths=[_logo_col_w, _txt_col_w],
            )
            hdr_tbl.setStyle(TableStyle([
                # Coluna 0 (logo): fundo branco
                ("BACKGROUND", (0, 0), (0, -1), white),
                # Coluna 1 (texto): fundo azul escuro
                ("BACKGROUND", (1, 0), (1, -1), C_DARK),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, -1), 6),
                ("RIGHTPADDING", (0, 0), (0, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (1, 0), (1, -1), 12),
                ("RIGHTPADDING", (1, 0), (1, -1), 8),
            ]))
            story.append(hdr_tbl)
            story.append(Spacer(1, 4 * mm))

            # ── SEÇÃO 1b: Descrição do Fundo ──
            if _inc("descricao") and descricao_fundo and descricao_fundo.strip():
                _flow_desc = _sec_flow["descricao"]
                _flow_desc.append(Paragraph("Descrição do Fundo", ps_titulo))
                _flow_desc.append(Spacer(1, 1 * mm))

                _desc_html = (
                    descricao_fundo
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\n", "<br/>")
                )
                _ps_desc = ParagraphStyle(
                    "ps_desc",
                    fontName="Helvetica",
                    fontSize=9,
                    leading=12,
                    textColor=C_DARK,
                    alignment=TA_LEFT,
                )
                desc_tbl = Table(
                    [[Paragraph(_desc_html, _ps_desc)]],
                    colWidths=[CONTENT_W],
                )
                desc_tbl.setStyle(TableStyle([
                    ("BOX", (0, 0), (-1, -1), 0.5, C_MID),
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F4F8FC")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]))
                _flow_desc.append(desc_tbl)
                _flow_desc.append(Spacer(1, 4 * mm))

            # ── SEÇÃO 2: Indicadores (estilo métricas da UI) ─────────────
            # Seleciona indicadores-chave do dicionário metricas
            def _fmt_ind(k, v):
                if "R$" in k:
                    return fmt_brl(v)
                if isinstance(v, float):
                    return fmt_pct(v)
                return str(v)

            _ind_keys = [
                "PL Final (R$)", "Subordinação Final",
                "Dias Úteis com Alerta de Subordinação", "Total Taxa de Performance (R$)",
            ]
            _ind_labels = ["PL Final", "Sub. Final", "D.U. com Alerta Sub.", "Tx. Performance Total"]
            _ind_items = []
            for lbl, key in zip(_ind_labels, _ind_keys):
                if key in metricas_dict:
                    _ind_items.append((lbl, _fmt_ind(key, metricas_dict[key])))

            # Retorno anual da subordinada
            _df_du_ind = df_du_graf.copy()
            _df_du_ind["data"] = pd.to_datetime(_df_du_ind["data"])
            _datas_du_ind = _df_du_ind["data"].tolist()
            _data_ini_ind = pd.Timestamp(params_obj.data_inicio)
            _pl_sub_d0_ind = float(params_obj.cota_subordinada.valor_inicial) if params_obj.cota_subordinada else 0.0
            _anos_retorno = []
            for _n in range(1, 20):
                _alvo = _data_ini_ind + relativedelta(years=_n)
                _idx = next((i for i, d in enumerate(_datas_du_ind) if d >= _alvo), None)
                if _idx is None:
                    break
                _ts = _datas_du_ind[_idx]
                if _n == 1:
                    _pl_ini_a = _pl_sub_d0_ind
                    _ts_ini_a = _data_ini_ind
                else:
                    _alvo_prev = _data_ini_ind + relativedelta(years=_n - 1)
                    _idx_prev = next((i for i, d in enumerate(_datas_du_ind) if d >= _alvo_prev), None)
                    if _idx_prev is None:
                        break
                    _pl_ini_a = float(_df_du_ind.iloc[_idx_prev]["pl_subordinada"])
                    _ts_ini_a = _datas_du_ind[_idx_prev]
                _pl_fim_a = float(_df_du_ind.iloc[_idx]["pl_subordinada"])
                if _pl_ini_a > 0:
                    _ret = (_pl_fim_a / _pl_ini_a) - 1
                    _ini_str = _ts_ini_a.strftime("%d/%m/%Y") if hasattr(_ts_ini_a, "strftime") else str(_ts_ini_a)[:10]
                    _fim_str = _ts.strftime("%d/%m/%Y")
                    _anos_retorno.append((f"Ano {_n}", fmt_pct(_ret), f"{_ini_str} → {_fim_str}"))

            # Montar linha de indicadores principais (4 células)
            n_ind = len(_ind_items)
            _flow_ind = _sec_flow["indicadores"]
            if _inc("indicadores") and n_ind > 0:
                ind_col_w = CONTENT_W / n_ind
                ind_cells = []
                for lbl, val in _ind_items:
                    cell = [
                        Paragraph(lbl, ps_ind_label),
                        Paragraph(val, ps_ind_val),
                    ]
                    ind_cells.append(cell)
                ind_tbl = Table([ind_cells], colWidths=[ind_col_w] * n_ind)
                ind_tbl.setStyle(TableStyle([
                    ("LINEAFTER", (0, 0), (-2, -1), 0.5, C_LIGHT),
                    ("LINEBEFORE", (0, 0), (0, -1), 2, C_BLUE),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (-1, -1), C_WHITE),
                ]))
                _flow_ind.append(ind_tbl)
                _flow_ind.append(Spacer(1, 2 * mm))

            # Retornos anuais
            if _inc("indicadores") and _anos_retorno:
                n_anos = len(_anos_retorno)
                ano_col_w = CONTENT_W / n_anos
                ano_cells = []
                for titulo_ano, ret_val, datas_str in _anos_retorno:
                    cell = [
                        Paragraph(f"{titulo_ano}  ·  {datas_str}", ps_ind_label),
                        Paragraph(ret_val, ps_ind_val),
                    ]
                    ano_cells.append(cell)
                ano_tbl = Table([ano_cells], colWidths=[ano_col_w] * n_anos)
                ano_tbl.setStyle(TableStyle([
                    ("LINEAFTER", (0, 0), (-2, -1), 0.5, C_LIGHT),
                    ("LINEBEFORE", (0, 0), (0, -1), 2, C_BLUE),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (-1, -1), C_WHITE),
                ]))
                _flow_ind.append(ano_tbl)
                _flow_ind.append(Spacer(1, 4 * mm))

            # MAPA_COTA_LABEL é usado pelas SEÇÕES 3 e 3b — definir sempre
            MAPA_COTA_LABEL = {"senior": "Sênior", "mezanino": "Mezanino", "subordinada": "Subordinada"}

            # ── SEÇÃO 3: Cronograma de Aportes ──────
            if _inc("cronograma_aportes"):
                aportes_rows = [["Data", "Cota", "Valor (R$)"]]
                for cfg_label, cfg_cota in [
                    ("Sênior", params_obj.cota_senior),
                    ("Mezanino", params_obj.cota_mezanino),
                    ("Subordinada", params_obj.cota_subordinada),
                ]:
                    if cfg_cota and cfg_cota.valor_inicial > 0:
                        aportes_rows.append([
                            params_obj.data_inicio.strftime("%d/%m/%Y"),
                            cfg_label, fmt_brl(cfg_cota.valor_inicial),
                        ])
                for ap in sorted(params_obj.aportes, key=lambda a: a.data):
                    label = MAPA_COTA_LABEL.get(ap.tipo_cota.value, ap.tipo_cota.value)
                    aportes_rows.append([ap.data.strftime("%d/%m/%Y"), label, fmt_brl(ap.valor)])

                # Só emite a seção se houver ao menos um aporte (além do cabeçalho)
                if len(aportes_rows) > 1:
                    _flow_apt = _sec_flow["cronograma_aportes"]
                    _flow_apt.append(Paragraph("Cronograma de Aportes", ps_titulo))
                    _flow_apt.append(Spacer(1, 1 * mm))

                    aporte_col_w = [CONTENT_W * 0.22, CONTENT_W * 0.22, CONTENT_W * 0.56]
                    aporte_tbl = Table(aportes_rows, colWidths=aporte_col_w, repeatRows=1)
                    aporte_tbl.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), C_DARK),
                        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.3, C_MID),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHT]),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ]))
                    _flow_apt.append(aporte_tbl)
                    _flow_apt.append(Spacer(1, 4 * mm))

            # ── SEÇÃO 3b: Cronograma de Juros e Amortizações ──
            if _inc("juros_amortizacoes"):
                MAPA_TIPO_AMORT_LABEL = {
                    "juros": "Amortização — Juros",
                    "juros_acumulados": "Amortização — Juros Acumulados",
                    "principal": "Amortização — Principal",
                    "total": "Amortização — Juros + Principal",
                }
                ORDEM_COTA = {"Sênior": 0, "Mezanino": 1, "Subordinada": 2}

                eventos_ja: list[tuple] = []  # (data, cota_label, tipo_label, valor)

                # Amortizações manuais (programadas pelo usuário)
                for am in params_obj.amortizacoes:
                    cota_lbl = MAPA_COTA_LABEL.get(am.tipo_cota.value, am.tipo_cota.value)
                    tipo_lbl = MAPA_TIPO_AMORT_LABEL.get(am.tipo.value, am.tipo.value)
                    eventos_ja.append((am.data, cota_lbl, tipo_lbl, float(am.valor)))

                # Pagamentos periódicos de juros (calculados pela simulação)
                for _, _row in df_du_graf.iterrows():
                    _d_raw = _row["data"]
                    _d = _d_raw.date() if hasattr(_d_raw, "date") else _d_raw
                    for _key, _cota_lbl in (
                        ("juros_senior", "Sênior"),
                        ("juros_mezanino", "Mezanino"),
                        ("juros_subordinada", "Subordinada"),
                    ):
                        _v = _row.get(_key, 0.0) or 0.0
                        if _v > 0:
                            eventos_ja.append((_d, _cota_lbl, "Juros (periódico)", float(_v)))

                eventos_ja.sort(key=lambda e: (e[0], ORDEM_COTA.get(e[1], 9), e[2]))

                # Só emite a seção se houver pelo menos um evento
                if eventos_ja:
                    _flow_ja = _sec_flow["juros_amortizacoes"]
                    _flow_ja.append(Paragraph("Cronograma de Juros e Amortizações", ps_titulo))
                    _flow_ja.append(Spacer(1, 1 * mm))

                    ja_rows = [["Data", "Cota", "Tipo", "Valor (R$)"]]
                    for _d, _cota, _tipo, _valor in eventos_ja:
                        ja_rows.append([_d.strftime("%d/%m/%Y"), _cota, _tipo, fmt_brl(_valor)])

                    ja_col_w = [CONTENT_W * 0.16, CONTENT_W * 0.16, CONTENT_W * 0.40, CONTENT_W * 0.28]
                    ja_tbl = Table(ja_rows, colWidths=ja_col_w, repeatRows=1)
                    ja_tbl.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), C_DARK),
                        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.3, C_MID),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHT]),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ]))
                    _flow_ja.append(ja_tbl)
                    _flow_ja.append(Spacer(1, 4 * mm))

            # ── SEÇÃO 4: Estrutura das Cotas ────────
            if _inc("estrutura_cotas"):
                _flow_ec = _sec_flow["estrutura_cotas"]
                _flow_ec.append(Paragraph("Estrutura das Cotas", ps_titulo))
                _flow_ec.append(Spacer(1, 1 * mm))

                MAPA_IDX = {"fixo": "Fixo", "cdi": "CDI", "ipca": "IPCA"}
                MAPA_PERIOD = {
                    "nenhuma": "Nenhuma", "mensal": "Mensal", "trimestral": "Trimestral",
                    "semestral": "Semestral", "anual": "Anual",
                }

                def _cota_block(titulo_c, cor_borda, cfg):
                    w = CONTENT_W / 3 - 4
                    rows = [[Paragraph(titulo_c, _ps(f"ct_{titulo_c}", 9, cor_borda, bold=True))]]
                    if cfg:
                        rows.append([Paragraph(f"Valor: {fmt_brl(cfg.valor_inicial)}", ps_normal)])
                        rows.append([Paragraph(f"Indexador: {MAPA_IDX.get(cfg.tipo_indexador.value, '')}", ps_normal)])
                        if cfg.taxa_fixa_anual:
                            rows.append([Paragraph(f"Taxa: {fmt_pct(cfg.taxa_fixa_anual)} a.a.", ps_normal)])
                        if cfg.spread_sobre_indexador:
                            rows.append([Paragraph(f"Spread: {fmt_pct(cfg.spread_sobre_indexador)} a.a.", ps_normal)])
                        rows.append([Paragraph(f"Juros: {MAPA_PERIOD.get(cfg.periodicidade_juros.value, '')}", ps_normal)])
                    t = Table(rows, colWidths=[w])
                    t.setStyle(TableStyle([
                        ("LINEBEFORE", (0, 0), (0, -1), 3, cor_borda),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F4F8FC")),
                    ]))
                    return t

                cotas_row = []
                if tem_senior and params_obj.cota_senior:
                    cotas_row.append(_cota_block("Sênior", C_LIGHT, params_obj.cota_senior))
                if tem_mezanino and params_obj.cota_mezanino:
                    cotas_row.append(_cota_block("Mezanino", C_BLUE, params_obj.cota_mezanino))
                cotas_row.append(_cota_block("Subordinada", C_DARK, params_obj.cota_subordinada))
                n_cotas = len(cotas_row)
                cotas_tbl = Table([cotas_row], colWidths=[CONTENT_W / n_cotas] * n_cotas)
                cotas_tbl.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ]))
                _flow_ec.append(cotas_tbl)
                _flow_ec.append(Spacer(1, 4 * mm))

            # ── SEÇÃO 5: Métricas de Resumo ─────────
            if _inc("metricas"):
                _flow_met = _sec_flow["metricas"]
                _flow_met.append(Paragraph("Métricas de Resumo", ps_titulo))
                _flow_met.append(Spacer(1, 1 * mm))

                def _fmt_metrica(k, v):
                    if "R$" in k:
                        return fmt_brl(v)
                    if isinstance(v, float):
                        return fmt_pct(v)
                    return str(v)

                met_items = [(k, _fmt_metrica(k, v)) for k, v in metricas_dict.items()]
                met_rows = []
                for i in range(0, len(met_items), 2):
                    row = []
                    for j in range(2):
                        if i + j < len(met_items):
                            k, v = met_items[i + j]
                            row += [Paragraph(k, ps_metric_label), Paragraph(v, ps_metric_val)]
                        else:
                            row += ["", ""]
                    met_rows.append(row)

                met_tbl = Table(met_rows, colWidths=[CONTENT_W * 0.30, CONTENT_W * 0.20] * 2)
                met_tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), C_DEEP),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("GRID", (0, 0), (-1, -1), 0.3, C_MID),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]))
                _flow_met.append(met_tbl)
                _flow_met.append(Spacer(1, 4 * mm))

            # ── SEÇÃO 6: Gráfico PL (título + gráfico juntos) ──
            if _inc("grafico_pl"):
                _flow_gpl = _sec_flow["grafico_pl"]
                img_pl = RLImage(_io.BytesIO(fig_pl_bytes), width=CONTENT_W, height=CONTENT_W * 280 / 700)
                _flow_gpl.append(KeepTogether([
                    Paragraph("Evolução do PL por Cota", ps_titulo),
                    Spacer(1, 1 * mm),
                    img_pl,
                ]))
                _flow_gpl.append(Spacer(1, 3 * mm))

            # ── SEÇÃO 7: Gráfico Retorno (título + gráfico juntos) ──
            if _inc("grafico_retorno"):
                _flow_gret = _sec_flow["grafico_retorno"]
                img_ret = RLImage(_io.BytesIO(fig_ret_bytes), width=CONTENT_W, height=CONTENT_W * 200 / 700)
                _flow_gret.append(KeepTogether([
                    Paragraph("Retorno Mensal da Cota Subordinada", ps_titulo),
                    Spacer(1, 1 * mm),
                    img_ret,
                ]))
                _flow_gret.append(Spacer(1, 3 * mm))

            # ── SEÇÃO 8: Tabela Semestral ────────────
            if _inc("tabela_semestral"):
                # Filtro: D+0 + último DU de cada período de 6 meses a partir de data_inicio
                _datas_all = pd.to_datetime(df_result["data"])
                _marcos_sem = [params_obj.data_inicio]
                for _n in range(1, 200):
                    _alvo = params_obj.data_inicio + relativedelta(months=_n * 6)
                    if _alvo > _datas_all.max().date():
                        break
                    _marcos_sem.append(_alvo)

                # Para cada marco, pega o último DU <= marco (ou o mais próximo >= marco se não existe)
                _sem_indices = set()
                _sem_indices.add(df_result[df_result["mes"] == 0].index[0])
                for _marco in _marcos_sem[1:]:
                    _ts_marco = pd.Timestamp(_marco)
                    _candidatos = df_result[
                        _datas_all <= _ts_marco + pd.Timedelta(days=5)
                    ]
                    _candidatos_du = _candidatos[_candidatos["retorno_subordinada_mensal"].notna()]
                    if len(_candidatos_du) > 0:
                        _sem_indices.add(_candidatos_du.index[-1])

                df_sem = df_result.loc[sorted(_sem_indices)].copy()

                # Calcular taxa de performance acumulada no semestre para cada linha
                # (soma dos dias daquele período semestral)
                _perf_acum = []
                _sorted_sem_idx = sorted(_sem_indices)
                for _ii, _idx in enumerate(_sorted_sem_idx):
                    if _ii == 0:
                        _perf_acum.append(0.0)
                    else:
                        _idx_prev = _sorted_sem_idx[_ii - 1]
                        _perf_periodo = df_result.loc[_idx_prev + 1:_idx, "taxa_performance"].sum() if "taxa_performance" in df_result.columns else 0.0
                        _perf_acum.append(_perf_periodo)
                df_sem["taxa_performance_semestre"] = _perf_acum

                sem_cols_map = {
                    "mes": "Mês",
                    "data": "Data",
                    "cdi_utilizado": "CDI (a.a.)",
                    "pl_senior": "PL Sênior",
                    "pl_mezanino": "PL Mez.",
                    "pl_subordinada": "PL Sub.",
                    "pl_total": "PL Total",
                    "subordinacao": "Sub.%",
                    "taxa_performance_semestre": "Tx.Perf.",
                }
                sem_cols = [c for c in sem_cols_map if c in df_sem.columns]
                df_sem = df_sem[sem_cols].copy().rename(columns=sem_cols_map)

                _brl_cols = {"PL Sênior", "PL Mez.", "PL Sub.", "PL Total", "Tx.Perf."}
                _pct_cols = {"CDI (a.a.)", "Sub.%"}

                def _fmt_sem(col, val):
                    if pd.isna(val):
                        return "-"
                    if col in _brl_cols:
                        return fmt_brl(float(val))
                    if col in _pct_cols:
                        return fmt_pct(float(val))
                    if col == "Data":
                        return pd.Timestamp(val).strftime("%d/%m/%Y")
                    return str(int(val))

                sem_header = list(df_sem.columns)
                sem_data = [sem_header]
                for _, row in df_sem.iterrows():
                    sem_data.append([_fmt_sem(col, row[col]) for col in sem_header])

                n_sem = len(sem_header)
                # Larguras proporcionais ao conteúdo
                _sem_w_map = {
                    "Mês": 0.06, "Data": 0.11, "CDI (a.a.)": 0.09,
                    "PL Sênior": 0.14, "PL Mez.": 0.13, "PL Sub.": 0.13,
                    "PL Total": 0.14, "Sub.%": 0.09, "Tx.Perf.": 0.11,
                }
                sem_col_w = [CONTENT_W * _sem_w_map.get(h, 1.0 / n_sem) for h in sem_header]
                # Normalizar para CONTENT_W
                _total_w = sum(sem_col_w)
                sem_col_w = [w * CONTENT_W / _total_w for w in sem_col_w]

                sem_tbl = Table(sem_data, colWidths=sem_col_w, repeatRows=1)
                sem_tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), C_DARK),
                    ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 6.5),
                    ("GRID", (0, 0), (-1, -1), 0.3, C_MID),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHT]),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("WORDWRAP", (0, 0), (-1, -1), True),
                ]))
                _sec_flow["tabela_semestral"].append(KeepTogether([
                    Paragraph("Evolução do Fundo — Visão Semestral", ps_titulo),
                    Spacer(1, 1 * mm),
                    sem_tbl,
                ]))

            # ── Montagem final na ordem desejada pelo usuário ──
            _ordem_padrao = list(_sec_flow.keys())
            _ordem_final = ordem_secoes if ordem_secoes is not None else _ordem_padrao
            # Garante que toda chave conhecida apareça (anexa ao fim caso falte)
            for _k in _ordem_padrao:
                if _k not in _ordem_final:
                    _ordem_final.append(_k)
            for _k in _ordem_final:
                story.extend(_sec_flow.get(_k, []))

            doc.build(story, onFirstPage=_rodape, onLaterPages=_rodape)
            return output.getvalue()

        # ── Personalizar conteúdo e ordem do PDF ──
        SECOES_PDF_LABELS = {
            "descricao":          "Descrição do Fundo",
            "indicadores":        "Indicadores-chave (PL Final, Sub. Final, Retornos Anuais…)",
            "cronograma_aportes": "Cronograma de Aportes",
            "juros_amortizacoes": "Cronograma de Juros e Amortizações",
            "estrutura_cotas":    "Estrutura das Cotas",
            "metricas":           "Métricas de Resumo",
            "grafico_pl":         "Gráfico: Evolução do PL por Cota",
            "grafico_retorno":    "Gráfico: Retorno Mensal da Subordinada",
            "tabela_semestral":   "Tabela Semestral",
        }
        ORDEM_PADRAO_PDF = list(SECOES_PDF_LABELS.keys())

        if "ordem_secoes_pdf" not in st.session_state:
            st.session_state.ordem_secoes_pdf = list(ORDEM_PADRAO_PDF)
        else:
            # Sanitiza: remove desconhecidas, anexa novas no fim
            _ord = [k for k in st.session_state.ordem_secoes_pdf if k in SECOES_PDF_LABELS]
            for _k in ORDEM_PADRAO_PDF:
                if _k not in _ord:
                    _ord.append(_k)
            st.session_state.ordem_secoes_pdf = _ord

        with st.expander("🧩 Personalizar conteúdo e ordem do PDF", expanded=False):
            st.caption(
                "Marque/desmarque seções e use as setas para reordenar. O cabeçalho com "
                "logo e nome do fundo é sempre o primeiro item e não pode ser movido."
            )
            col_reset, _ = st.columns([1, 4])
            with col_reset:
                if st.button("↺ Restaurar ordem padrão", use_container_width=True):
                    st.session_state.ordem_secoes_pdf = list(ORDEM_PADRAO_PDF)
                    st.rerun()

            _secoes_sel = {}
            _ordem_atual = st.session_state.ordem_secoes_pdf
            _n_sec = len(_ordem_atual)
            for _i, _key in enumerate(_ordem_atual):
                _label = SECOES_PDF_LABELS[_key]
                col_pos, col_chk, col_lbl, col_up, col_down = st.columns([0.3, 0.3, 3, 0.5, 0.5])
                with col_pos:
                    st.markdown(f"**{_i + 1}.**")
                with col_chk:
                    _secoes_sel[_key] = st.checkbox(
                        " ",
                        value=st.session_state.get(f"_pdf_sec_{_key}", True),
                        key=f"_pdf_sec_{_key}",
                        label_visibility="collapsed",
                    )
                with col_lbl:
                    st.write(_label)
                with col_up:
                    if st.button("⬆️", key=f"_up_{_key}", disabled=_i == 0, use_container_width=True):
                        _ordem_atual[_i - 1], _ordem_atual[_i] = _ordem_atual[_i], _ordem_atual[_i - 1]
                        st.rerun()
                with col_down:
                    if st.button("⬇️", key=f"_dn_{_key}", disabled=_i == _n_sec - 1, use_container_width=True):
                        _ordem_atual[_i + 1], _ordem_atual[_i] = _ordem_atual[_i], _ordem_atual[_i + 1]
                        st.rerun()

        col_excel, col_pdf = st.columns([1, 1])
        with col_excel:
            excel_bytes = gerar_excel(df)
            st.download_button(
                label="⬇️ Baixar Excel",
                data=excel_bytes,
                file_name=f"modelagem_{nome_fundo.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        with col_pdf:
            _params_pdf = st.session_state.get("params_obj")
            if _params_pdf:
                pdf_bytes = gerar_pdf(
                    df, metricas, _params_pdf, df_du,
                    st.session_state.get("usar_senior_saved", False),
                    st.session_state.get("usar_mezanino_saved", False),
                    st.session_state.get("descricao_fundo", ""),
                    _secoes_sel,
                    list(st.session_state.ordem_secoes_pdf),
                )
                st.download_button(
                    label="⬇️ Baixar PDF (One-Page)",
                    data=pdf_bytes,
                    file_name=f"onepage_{nome_fundo.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                )
            else:
                st.info("Rode a simulação para habilitar o PDF.")
