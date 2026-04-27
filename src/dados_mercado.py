"""
Módulo para buscar taxas e curvas de mercado.

Fontes (sem autenticação):
  1. BCB SGS série 4389  → CDI % a.a. (spot)
  2. BCB SGS série 432   → SELIC over % a.a. (spot, fallback)
  3. BCB SGS série 433   → IPCA % a.m. dos últimos 12 meses → anualizado
  4. BCB OLINDA Expectativas → curva forward de SELIC e IPCA (Focus Report)
  5. B3 UP2DATA → Curva DI1 (futuros de DI)
"""

from __future__ import annotations

import urllib.request
import urllib.parse
import json
from datetime import datetime, date
from typing import Optional

# ─── Constantes ───────────────────────────────────────────────────────────────

_SGS_BASE    = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{}/dados/ultimos/{}?formato=json"
_OLINDA_BASE = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
_TIMEOUT     = 8  # segundos


# ─── Helpers internos ─────────────────────────────────────────────────────────

def _get_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def _sgs(serie: int, n: int = 1) -> list[dict]:
    """Retorna os últimos n registros de uma série SGS."""
    try:
        return _get_json(_SGS_BASE.format(serie, n))  # type: ignore[return-value]
    except Exception:
        return []


def _olinda_expectativas_mensais(indicador: str) -> dict[str, float]:
    """
    Busca expectativas mensais do Focus Report via OLINDA para um dado indicador.
    Retorna {MM/YYYY: mediana_decimal} ou {} se o serviço estiver indisponível.
    """
    try:
        filtro = f"Indicador eq '{indicador}' and baseCalculo eq 0"
        campos = "Data,DataReferencia,Mediana"
        url = (
            f"{_OLINDA_BASE}ExpectativaMercadoMensais"
            f"?$format=json"
            f"&$filter={urllib.parse.quote(filtro)}"
            f"&$select={urllib.parse.quote(campos)}"
            f"&$orderby=DataReferencia%20asc"
            f"&$top=60"
        )
        dados = _get_json(url)
        result: dict[str, float] = {}
        for item in dados.get("value", []):
            ref     = item.get("DataReferencia", "")
            mediana = item.get("Mediana")
            if ref and mediana is not None:
                result[ref] = float(mediana) / 100
        return result
    except Exception:
        return {}


# ─── Funções públicas ──────────────────────────────────────────────────────────

def buscar_cdi_spot() -> Optional[float]:
    """
    CDI/SELIC anual spot.
    Tenta SGS 4389 (CDI % a.a.); fallback para SGS 432 (SELIC over % a.a.).
    Retorna taxa decimal (ex: 0.1465 para 14,65%) ou None.
    """
    for serie in (4389, 432):
        dados = _sgs(serie, 1)
        if dados:
            try:
                return float(dados[-1]["valor"]) / 100
            except (KeyError, ValueError):
                continue
    return None


def buscar_ipca_acumulado_12m() -> Optional[float]:
    """
    IPCA acumulado dos últimos 12 meses (SGS série 433, variação % mensal).
    Retorna taxa anual decimal ou None.
    """
    dados = _sgs(433, 12)
    if not dados:
        return None
    try:
        acumulado = 1.0
        for item in dados:
            acumulado *= (1 + float(item["valor"]) / 100)
        return acumulado - 1
    except (KeyError, ValueError):
        return None


def buscar_expectativas_selic() -> dict[str, float]:
    """
    Expectativas mensais de SELIC via Focus Report (BCB OLINDA).
    Retorna {MM/YYYY: taxa_anual_decimal} ou {} em caso de falha.
    """
    return _olinda_expectativas_mensais("Selic")


def buscar_expectativas_ipca() -> dict[str, float]:
    """
    Expectativas mensais de IPCA via Focus Report (BCB OLINDA).
    Retorna {MM/YYYY: variacao_mensal_decimal} ou {} em caso de falha.
    """
    return _olinda_expectativas_mensais("IPCA")


def buscar_curva_di1() -> dict:
    """
    Busca a curva DI1 da B3 via API pública.
    Os valores retornados pela B3 já são taxas em % a.a.
    Retorna:
      {
        "data_referencia": str,
        "vertices": [
            {"ticker": str, "vencimento": str, "taxa": float (decimal)},
            ...
        ]
      }
    ou {} em caso de falha.
    """
    url = "https://cotacao.b3.com.br/mds/api/v1/DerivativeQuotation/DI1"
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return {}

    msg = data.get("Msg", {})
    data_ref = msg.get("dtTm", "") if isinstance(msg, dict) else str(msg)

    vertices = []
    for item in data.get("Scty", []):
        qtn = item.get("SctyQtn", {})
        taxa_pct = qtn.get("curPrc") or qtn.get("prvsDayAdjstmntPric")
        mtrty = item.get("asset", {}).get("AsstSummry", {}).get("mtrtyCode", "")

        if not mtrty or not taxa_pct or taxa_pct <= 0:
            continue

        try:
            venc = datetime.strptime(mtrty, "%Y-%m-%d").date()
        except ValueError:
            continue

        vertices.append({
            "ticker": item.get("symb", ""),
            "vencimento": venc.strftime("%d/%m/%Y"),
            "taxa": round(taxa_pct / 100, 6),  # converte % → decimal
        })

    vertices.sort(key=lambda x: datetime.strptime(x["vencimento"], "%d/%m/%Y"))

    return {
        "data_referencia": data_ref,
        "vertices": vertices,
    }


def buscar_curvas() -> dict:
    """
    Consolida todas as fontes e retorna:
      {
        "cdi_spot":         float | None   — CDI/SELIC % a.a. (decimal)
        "ipca_acumulado":   float | None   — IPCA acum. 12m % a.a. (decimal)
        "selic_forward":    {MM/YYYY: float}  — curva forward SELIC (Focus)
        "ipca_forward":     {MM/YYYY: float}  — curva forward IPCA mensal (Focus)
        "cdi_anual_medio":  float | None   — média SELIC forward 12m (ou spot)
        "ipca_anual_medio": float | None   — IPCA forward anualizado 12m (ou acum.)
        "fonte_cdi":        str            — descreve de onde veio o CDI
        "fonte_ipca":       str            — descreve de onde veio o IPCA
        "data_consulta":    str
      }
    """
    cdi_spot       = buscar_cdi_spot()
    ipca_acum      = buscar_ipca_acumulado_12m()
    selic_fwd      = buscar_expectativas_selic()
    ipca_fwd       = buscar_expectativas_ipca()

    # ── CDI médio forward ──
    cdi_anual_medio: Optional[float]
    fonte_cdi: str
    if selic_fwd:
        valores = sorted(selic_fwd.items())[:12]
        cdi_anual_medio = sum(v for _, v in valores) / len(valores)
        fonte_cdi = f"Focus Report BCB — média {len(valores)} meses"
    elif cdi_spot is not None:
        cdi_anual_medio = cdi_spot
        fonte_cdi = "BCB SGS (taxa spot — Focus indisponível)"
    else:
        cdi_anual_medio = None
        fonte_cdi = "Indisponível"

    # ── IPCA médio anualizado ──
    ipca_anual_medio: Optional[float]
    fonte_ipca: str
    if ipca_fwd:
        valores_ipca = sorted(ipca_fwd.items())[:12]
        acumulado = 1.0
        for _, v in valores_ipca:
            acumulado *= (1 + v)
        n = len(valores_ipca)
        ipca_anual_medio = acumulado ** (12 / n) - 1
        fonte_ipca = f"Focus Report BCB — {n} meses"
    elif ipca_acum is not None:
        ipca_anual_medio = ipca_acum
        fonte_ipca = "BCB SGS — IPCA acumulado últimos 12 meses"
    else:
        ipca_anual_medio = None
        fonte_ipca = "Indisponível"

    return {
        "cdi_spot":         cdi_spot,
        "ipca_acumulado":   ipca_acum,
        "selic_forward":    selic_fwd,
        "ipca_forward":     ipca_fwd,
        "cdi_anual_medio":  cdi_anual_medio,
        "ipca_anual_medio": ipca_anual_medio,
        "fonte_cdi":        fonte_cdi,
        "fonte_ipca":       fonte_ipca,
        "data_consulta":    datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
