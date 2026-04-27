"""
Engine de cálculo do FIDC.

Metodologia de accrual (padrão ANBIMA):
- Todas as taxas são anuais com base 252 dias úteis
- Accrual diário linear: fator = 1/252 por dia útil
- Feriados nacionais: arquivo 'feriados_nacionais (2).xls' (raiz do projeto)
  Fallback: biblioteca 'holidays' (se o arquivo não existir)

Ordem do waterfall diário (por dia útil):
  1. Aportes entram no dia (aumentam PL e principal)
  2. Receita bruta = PL × taxa_ativo × (1/252)
  3. PDD = (PL + receita_bruta) × taxa_pdd × (1/252)
  4. Despesas = (PL + receita_bruta) × taxa_custos × (1/252) + outras_anuais × (1/252)
  5. Resultado líquido = receita - PDD - despesas
  6. Rendimento Sênior e Mezanino (taxas contratadas)
  7. Excedente → Subordinada
  8. Amortizações manuais programadas para o dia
  9. Pagamentos periódicos automáticos de juros (último d.u. do período)
"""

from __future__ import annotations

import bisect
import os
from dataclasses import dataclass
from datetime import date, timedelta
from collections import defaultdict
from dateutil.relativedelta import relativedelta
import numpy as np
import pandas as pd

from models import (
    ParametrosFundo, TipoCota, TipoIndexador, TipoAmortizacao,
    PeriodicidadeJuros, ConfiguracaoCota, ConfiguracaoPerformance, Amortizacao
)

def _fator_composto(taxa_anual: float) -> float:
    """Fator diário composto: (1 + taxa_anual)^(1/252) - 1"""
    return (1.0 + taxa_anual) ** (1.0 / 252) - 1.0


# ─── Feriados nacionais brasileiros ───────────────────────────────────────────

def _feriados_br(ano_ini: int, ano_fim: int) -> list[date]:
    """
    Carrega feriados nacionais do arquivo XLS (raiz do projeto) como fonte primária.
    Fallback para a biblioteca 'holidays' se o arquivo não existir.
    """
    # Caminho: engine.py está em src/, arquivo está um nível acima
    xls_path = os.path.join(os.path.dirname(__file__), "..", "feriados_nacionais (2).xls")
    xls_path = os.path.normpath(xls_path)

    if os.path.exists(xls_path):
        try:
            df = pd.read_excel(xls_path, usecols=["Data"])
            datas = pd.to_datetime(df["Data"], errors="coerce").dropna()
            return [
                d.date() for d in datas
                if ano_ini <= d.year <= ano_fim
            ]
        except Exception:
            pass  # cai no fallback abaixo

    try:
        import holidays as _hlib
        return list(_hlib.Brazil(years=range(ano_ini, ano_fim + 1)).keys())
    except ImportError:
        return []


# ─── Geração de dias úteis ────────────────────────────────────────────────────

def _gerar_dias_uteis(inicio: date, fim: date, feriados: list[date]) -> list[date]:
    """
    Retorna lista de todos os dias úteis em (inicio, fim] — exclusive inicio, inclusive fim.
    Exclui sábados, domingos e feriados.
    """
    feriados_set = set(feriados)
    todos = pd.date_range(start=inicio + timedelta(days=1), end=fim, freq="D")
    return [d.date() for d in todos if d.weekday() < 5 and d.date() not in feriados_set]


# ─── Benchmarks ───────────────────────────────────────────────────────────────

def _benchmark_anual(cota: ConfiguracaoCota, cdi: float, ipca: float) -> float:
    """
    Retorna a taxa anual efetiva da cota.
    Para indexadores flutuantes, usa capitalização composta:
      taxa = (1 + indexador) × (1 + spread) - 1
    Exemplo: CDI 14,75% + spread 5% → (1,1475 × 1,05) - 1 = 20,4875% a.a.
    """
    if cota.tipo_indexador == TipoIndexador.FIXO:
        return cota.taxa_fixa_anual
    elif cota.tipo_indexador == TipoIndexador.CDI:
        return (1.0 + cdi) * (1.0 + cota.spread_sobre_indexador) - 1.0
    elif cota.tipo_indexador == TipoIndexador.IPCA:
        return (1.0 + ipca) * (1.0 + cota.spread_sobre_indexador) - 1.0
    return 0.0


def _fator_hurdle_diario(cfg: ConfiguracaoPerformance, fator_cdi: float, ipca_anual: float) -> float:
    """Fator diário do hurdle da taxa de performance."""
    if cfg.hurdle_indexador == TipoIndexador.FIXO:
        return _fator_composto(cfg.hurdle_taxa_fixa)
    elif cfg.hurdle_indexador == TipoIndexador.CDI:
        spread_d = _fator_composto(cfg.hurdle_spread)
        return (1.0 + fator_cdi) * (1.0 + spread_d) - 1.0
    elif cfg.hurdle_indexador == TipoIndexador.IPCA:
        taxa_ef = (1.0 + ipca_anual) * (1.0 + cfg.hurdle_spread) - 1.0
        return _fator_composto(taxa_ef)
    return 0.0


def _fator_benchmark_diario(cota: ConfiguracaoCota | None, fator_cdi: float, ipca_anual: float) -> float:
    """
    Retorna o fator diário do benchmark da cota, usando o fator CDI diário da curva.
    """
    if cota is None:
        return 0.0
    if cota.tipo_indexador == TipoIndexador.FIXO:
        return _fator_composto(cota.taxa_fixa_anual)
    elif cota.tipo_indexador == TipoIndexador.CDI:
        # fator_cdi já é diário; spread precisa ser diarizado
        spread_diario = _fator_composto(cota.spread_sobre_indexador)
        return (1.0 + fator_cdi) * (1.0 + spread_diario) - 1.0
    elif cota.tipo_indexador == TipoIndexador.IPCA:
        return _fator_composto(
            (1.0 + ipca_anual) * (1.0 + cota.spread_sobre_indexador) - 1.0
        )
    return 0.0


# ─── Cálculo de amortização ───────────────────────────────────────────────────

def _calcular_amortizacao(amort: Amortizacao, pl_cota: float, principal_cota: float) -> float:
    juros_acumulados = max(0.0, pl_cota - principal_cota)

    if amort.tipo == TipoAmortizacao.JUROS_ACUMULADOS:
        return juros_acumulados

    val = amort.valor if amort.valor > 0 else pl_cota * amort.percentual

    if amort.tipo == TipoAmortizacao.JUROS:
        return min(val, juros_acumulados)

    return min(val, pl_cota)


# ─── Pré-computação de últimos d.u. por período ───────────────────────────────

def _pré_computar_ultimos_du(todos_du: list[date]) -> dict[PeriodicidadeJuros, set[date]]:
    """
    Para cada periodicidade, retorna o conjunto de dias úteis que são
    o último d.u. do respectivo período (mês, trimestre, semestre, ano).
    """
    ultimos: dict[PeriodicidadeJuros, set[date]] = {
        PeriodicidadeJuros.MENSAL:     set(),
        PeriodicidadeJuros.TRIMESTRAL: set(),
        PeriodicidadeJuros.SEMESTRAL:  set(),
        PeriodicidadeJuros.ANUAL:      set(),
    }

    # Último d.u. de cada mês
    du_por_mes: dict[tuple, date] = {}
    for d in todos_du:
        du_por_mes[(d.year, d.month)] = d  # sobrescreve → fica o último
    ultimos[PeriodicidadeJuros.MENSAL] = set(du_por_mes.values())

    # Último d.u. de cada trimestre (meses 3,6,9,12)
    du_por_trim: dict[tuple, date] = {}
    for d in todos_du:
        trim = (d.month - 1) // 3
        du_por_trim[(d.year, trim)] = d
    ultimos[PeriodicidadeJuros.TRIMESTRAL] = set(du_por_trim.values())

    # Último d.u. de cada semestre
    du_por_sem: dict[tuple, date] = {}
    for d in todos_du:
        sem = (d.month - 1) // 6
        du_por_sem[(d.year, sem)] = d
    ultimos[PeriodicidadeJuros.SEMESTRAL] = set(du_por_sem.values())

    # Último d.u. de cada ano
    du_por_ano: dict[int, date] = {}
    for d in todos_du:
        du_por_ano[d.year] = d
    ultimos[PeriodicidadeJuros.ANUAL] = set(du_por_ano.values())

    return ultimos


# ─── Número do mês sequencial ─────────────────────────────────────────────────

def _mes_seq(data_inicio: date, dia: date) -> int:
    """Retorna o número do mês sequencial da simulação (1-based)."""
    delta = relativedelta(dia, data_inicio)
    return delta.years * 12 + delta.months + 1


# ─── Dataclass de resultado ───────────────────────────────────────────────────

@dataclass
class LinhaResultado:
    mes: int                 # número sequencial do mês (1-based; 0 = D+0)
    data: date
    dias_uteis: int          # sempre 1 por linha (cada linha = 1 d.u.), 0 no D+0

    pl_senior: float
    pl_mezanino: float
    pl_subordinada: float
    pl_total: float

    aporte_senior: float
    aporte_mezanino: float
    aporte_subordinada: float

    amort_senior: float
    amort_mezanino: float
    amort_subordinada: float

    # Juros pagos via pagamento periódico automático (subconjunto de amort_X)
    juros_senior: float
    juros_mezanino: float
    juros_subordinada: float

    receita_ativo: float     # receita da parcela investida nos ativos
    receita_caixa: float     # receita da parcela ociosa em caixa (100% CDI)
    receita_bruta: float     # receita_ativo + receita_caixa
    pdd: float
    despesas_totais: float
    resultado_liquido: float

    rendimento_senior: float
    rendimento_mezanino: float
    rendimento_subordinada: float

    subordinacao: float
    retorno_subordinada_mensal: float   # NaN nos dias que não são último d.u. do mês
    retorno_subordinada_anual: float    # NaN idem
    alerta_subordinacao: bool
    cdi_utilizado: float                # CDI % a.a. (decimal) utilizado na linha
    taxa_performance: float = 0.0       # R$ cobrado de taxa de performance no dia (0 na maioria)


def _linha_d0(params: ParametrosFundo) -> LinhaResultado:
    pl_s   = params.cota_senior.valor_inicial      if params.cota_senior      else 0.0
    pl_m   = params.cota_mezanino.valor_inicial    if params.cota_mezanino    else 0.0
    pl_sub = params.cota_subordinada.valor_inicial if params.cota_subordinada else 0.0
    pl_tot = pl_s + pl_m + pl_sub
    sub = pl_sub / pl_tot if pl_tot > 0 else 0.0
    nan = float("nan")
    return LinhaResultado(
        mes=0, data=params.data_inicio, dias_uteis=0,
        pl_senior=pl_s, pl_mezanino=pl_m, pl_subordinada=pl_sub, pl_total=pl_tot,
        aporte_senior=0.0, aporte_mezanino=0.0, aporte_subordinada=0.0,
        amort_senior=0.0, amort_mezanino=0.0, amort_subordinada=0.0,
        juros_senior=0.0, juros_mezanino=0.0, juros_subordinada=0.0,
        receita_ativo=0.0, receita_caixa=0.0, receita_bruta=0.0,
        pdd=0.0, despesas_totais=0.0, resultado_liquido=0.0,
        rendimento_senior=0.0, rendimento_mezanino=0.0, rendimento_subordinada=0.0,
        subordinacao=sub, retorno_subordinada_mensal=nan, retorno_subordinada_anual=nan,
        alerta_subordinacao=sub < params.subordinacao_minima,
        cdi_utilizado=0.0,
    )


# ─── Simulação principal ──────────────────────────────────────────────────────

def rodar_simulacao(params: ParametrosFundo) -> pd.DataFrame:
    """
    Simula o FIDC dia útil a dia útil (padrão ANBIMA, base 252).
    Retorna DataFrame com linha D+0 + uma linha por dia útil simulado.
    """
    pl_senior      = params.cota_senior.valor_inicial      if params.cota_senior      else 0.0
    pl_mezanino    = params.cota_mezanino.valor_inicial    if params.cota_mezanino    else 0.0
    pl_subordinada = params.cota_subordinada.valor_inicial if params.cota_subordinada else 0.0

    principal_senior      = pl_senior
    principal_mezanino    = pl_mezanino
    principal_subordinada = pl_subordinada

    taxa_ativo    = params.ativo.taxa_anual
    taxa_pdd      = params.ativo.inadimplencia_anual
    taxa_adm      = params.custos.taxa_administracao
    taxa_gest     = params.custos.taxa_gestao
    taxa_cust     = params.custos.taxa_custodia
    taxa_custos   = taxa_adm + taxa_gest + taxa_cust
    outras_anuais = params.custos.outras_despesas_anuais
    min_adm_dia   = params.custos.minimo_mensal_administracao * 12 / 252  # R$/d.u.
    min_gest_dia  = params.custos.minimo_mensal_gestao        * 12 / 252  # R$/d.u.

    # Fatores diários compostos pré-calculados (fixos)
    fator_ativo  = _fator_composto(taxa_ativo)
    fator_pdd    = _fator_composto(taxa_pdd)
    fator_outras = outras_anuais / 252                  # despesa fixa: linear (R$/dia útil)

    # Fatores fixos para cotas com indexador FIXO ou IPCA (não dependem da curva CDI)
    fator_s_fixo = _fator_composto(params.cota_senior.taxa_fixa_anual) if (params.cota_senior and params.cota_senior.tipo_indexador == TipoIndexador.FIXO) else None
    fator_m_fixo = _fator_composto(params.cota_mezanino.taxa_fixa_anual) if (params.cota_mezanino and params.cota_mezanino.tipo_indexador == TipoIndexador.FIXO) else None

    ociosidade   = params.ativo.ociosidade_caixa        # ex: 0.05 = 5%
    curva_cdi    = params.curva_cdi                      # {date: fator_diário}

    # ── Feriados e dias úteis ──
    data_fim = params.data_inicio + relativedelta(months=params.prazo_meses)
    feriados = _feriados_br(params.data_inicio.year, data_fim.year)
    todos_du = _gerar_dias_uteis(params.data_inicio, data_fim, feriados)

    if not todos_du:
        return pd.DataFrame()

    # ── Pré-computa últimos d.u. por periodicidade ──
    ultimos_du = _pré_computar_ultimos_du(todos_du)

    # ── Indexa aportes e amortizações por data exata (ajusta para próximo d.u.) ──
    aportes_por_data: dict[date, list] = defaultdict(list)
    for a in params.aportes:
        idx = bisect.bisect_left(todos_du, a.data)
        if idx < len(todos_du):
            aportes_por_data[todos_du[idx]].append(a)

    amorts_por_data: dict[date, list] = defaultdict(list)
    for a in params.amortizacoes:
        idx = bisect.bisect_left(todos_du, a.data)
        if idx < len(todos_du):
            amorts_por_data[todos_du[idx]].append(a)

    # ── PL da subordinada no fim do período anterior (para retornos) ──
    # Compara último d.u. do período com último d.u. do período anterior (ou D+0)
    pl_sub_fim_mes_anterior = pl_subordinada  # D+0 como base do primeiro mês
    pl_sub_d0 = pl_subordinada               # D+0 como base para retorno anualizado
    pl_total_anterior = pl_senior + pl_mezanino + pl_subordinada  # PL do D+0

    # ── Acumuladores para taxa de performance ──
    cfg_perf = params.performance
    hwm_subordinada = (cfg_perf.high_water_mark_inicial
                       if cfg_perf.high_water_mark_inicial > 0
                       else pl_subordinada)
    fator_acum_sub    = 1.0
    fator_acum_hurdle = 1.0
    dias_apuracao_perf: set = set()
    if cfg_perf.ativo and cfg_perf.periodo_apuracao != PeriodicidadeJuros.NENHUMA:
        dias_apuracao_perf = ultimos_du[cfg_perf.periodo_apuracao]

    resultados: list[LinhaResultado] = [_linha_d0(params)]
    nan = float("nan")

    for dia in todos_du:
        mes = _mes_seq(params.data_inicio, dia)

        # ── 1. Aportes ──
        aporte_s = aporte_m = aporte_sub = 0.0
        for a in aportes_por_data[dia]:
            if a.tipo_cota == TipoCota.SENIOR:
                aporte_s   += a.valor
            elif a.tipo_cota == TipoCota.MEZANINO:
                aporte_m   += a.valor
            else:
                aporte_sub += a.valor

        pl_senior      += aporte_s
        pl_mezanino    += aporte_m
        pl_subordinada += aporte_sub
        principal_senior   += aporte_s
        principal_mezanino += aporte_m

        pl_total = pl_senior + pl_mezanino + pl_subordinada
        if pl_total <= 0:
            break

        # Guarda PLs do dia anterior (antes de creditar rendimentos) para calcular
        # rendimento_senior e rendimento_mezanino sobre a base correta
        pl_senior_anterior   = pl_senior
        pl_mezanino_anterior = pl_mezanino

        # ── 2. Fator CDI do dia (da curva DI futuro) ──
        fator_cdi_dia = curva_cdi.get(dia, 0.0)
        # CDI anualizado para exibição: (1 + fator_diário)^252 - 1
        cdi_anual_dia = (1.0 + fator_cdi_dia) ** 252 - 1.0

        # Fatores de benchmark das cotas (recalculados com CDI do dia)
        fator_s = fator_s_fixo if fator_s_fixo is not None else _fator_benchmark_diario(params.cota_senior, fator_cdi_dia, params.ipca_anual)
        fator_m = fator_m_fixo if fator_m_fixo is not None else _fator_benchmark_diario(params.cota_mezanino, fator_cdi_dia, params.ipca_anual)

        # ── Receita bruta (composta, com ociosidade de caixa) ──
        receita_ativo  = pl_total * (1.0 - ociosidade) * fator_ativo
        receita_caixa  = pl_total * ociosidade          * fator_cdi_dia
        receita_bruta  = receita_ativo + receita_caixa

        # ── 3. PDD (sobre exposição total: PL + receita gerada) ──
        base_calculo  = pl_total + receita_bruta
        pdd           = base_calculo * fator_pdd

        # ── 4. Despesas (taxas sobre PL do dia anterior, linear base 252) ──
        # Administração e gestão: max(% sobre PL, mínimo mensal)
        desp_adm  = max(pl_total_anterior * taxa_adm  / 252, min_adm_dia)
        desp_gest = max(pl_total_anterior * taxa_gest / 252, min_gest_dia)
        desp_cust = pl_total_anterior * taxa_cust / 252
        despesas_totais = desp_adm + desp_gest + desp_cust + fator_outras

        # ── 5. Resultado líquido ──
        resultado_liquido = receita_bruta - pdd - despesas_totais

        # ── 6. Waterfall: rendimentos sênior e mezanino (sobre PL do dia anterior) ──
        rendimento_senior   = pl_senior_anterior   * fator_s if pl_senior_anterior   > 0 else 0.0
        rendimento_mezanino = pl_mezanino_anterior * fator_m if pl_mezanino_anterior > 0 else 0.0
        rendimento_subordinada = resultado_liquido - rendimento_senior - rendimento_mezanino

        pl_sub_pre_rendimento = pl_subordinada      # salva antes de creditar
        pl_senior      += rendimento_senior
        pl_mezanino    += rendimento_mezanino
        pl_subordinada += rendimento_subordinada

        # ── 6b. Taxa de performance ──
        taxa_performance_dia = 0.0
        if cfg_perf.ativo:
            # Atualiza acumuladores do período
            if pl_sub_pre_rendimento > 0:
                fator_dia_sub = pl_subordinada / pl_sub_pre_rendimento
                fator_acum_sub    *= fator_dia_sub
                fator_acum_hurdle *= (1.0 + _fator_hurdle_diario(cfg_perf, fator_cdi_dia, params.ipca_anual))

            # Apuração no fechamento do período
            if dia in dias_apuracao_perf and pl_subordinada > 0:
                excesso    = (fator_acum_sub - 1.0) - (fator_acum_hurdle - 1.0)
                supera_hwm = pl_subordinada > hwm_subordinada
                if excesso > 0 and supera_hwm:
                    bruto = cfg_perf.percentual * excesso * pl_subordinada
                    # Cap: não arrastar PL sub abaixo do HWM
                    taxa_performance_dia = min(bruto, pl_subordinada - hwm_subordinada)
                    rendimento_subordinada -= taxa_performance_dia
                    pl_subordinada         -= taxa_performance_dia
                    despesas_totais        += taxa_performance_dia
                # Atualiza HWM e reinicia acumuladores para o próximo período
                hwm_subordinada = max(hwm_subordinada, pl_subordinada)
                fator_acum_sub    = 1.0
                fator_acum_hurdle = 1.0

        # ── 7. Amortizações manuais ──
        amort_s = amort_m = amort_sub = 0.0
        for amort in amorts_por_data[dia]:
            if amort.tipo_cota == TipoCota.SENIOR:
                val = _calcular_amortizacao(amort, pl_senior, principal_senior)
                pl_senior -= val
                amort_s   += val
                if amort.tipo in (TipoAmortizacao.PRINCIPAL, TipoAmortizacao.TOTAL):
                    principal_senior = max(0.0, principal_senior - val)
            elif amort.tipo_cota == TipoCota.MEZANINO:
                val = _calcular_amortizacao(amort, pl_mezanino, principal_mezanino)
                pl_mezanino -= val
                amort_m     += val
                if amort.tipo in (TipoAmortizacao.PRINCIPAL, TipoAmortizacao.TOTAL):
                    principal_mezanino = max(0.0, principal_mezanino - val)
            elif amort.tipo_cota == TipoCota.SUBORDINADA:
                val = _calcular_amortizacao(amort, pl_subordinada, principal_subordinada)
                pl_subordinada -= val
                amort_sub      += val
                if amort.tipo in (TipoAmortizacao.PRINCIPAL, TipoAmortizacao.TOTAL):
                    principal_subordinada = max(0.0, principal_subordinada - val)

        # ── 8. Pagamentos periódicos automáticos de juros ──
        juros_s = juros_m = juros_sub = 0.0
        if params.cota_senior and pl_senior > 0:
            per_s = params.cota_senior.periodicidade_juros
            if per_s != PeriodicidadeJuros.NENHUMA and dia in ultimos_du[per_s]:
                juros_s    = max(0.0, pl_senior - principal_senior)
                pl_senior -= juros_s
                amort_s   += juros_s

        if params.cota_mezanino and pl_mezanino > 0:
            per_m = params.cota_mezanino.periodicidade_juros
            if per_m != PeriodicidadeJuros.NENHUMA and dia in ultimos_du[per_m]:
                juros_m     = max(0.0, pl_mezanino - principal_mezanino)
                pl_mezanino -= juros_m
                amort_m     += juros_m

        if params.cota_subordinada and pl_subordinada > 0:
            per_sub = params.cota_subordinada.periodicidade_juros
            if per_sub != PeriodicidadeJuros.NENHUMA and dia in ultimos_du[per_sub]:
                juros_sub      = max(0.0, pl_subordinada - principal_subordinada)
                pl_subordinada -= juros_sub
                amort_sub      += juros_sub

        pl_senior      = max(0.0, pl_senior)
        pl_mezanino    = max(0.0, pl_mezanino)
        pl_subordinada = max(0.0, pl_subordinada)
        pl_total       = pl_senior + pl_mezanino + pl_subordinada

        subordinacao = pl_subordinada / pl_total if pl_total > 0 else 0.0

        # ── 9. Retorno da subordinada ──
        # Mensal: último d.u. mês X vs último d.u. mês X-1 (ou D+0)
        e_ultimo_du_mes = dia in ultimos_du[PeriodicidadeJuros.MENSAL]
        if e_ultimo_du_mes and pl_sub_fim_mes_anterior > 0:
            retorno_sub_mensal = (pl_subordinada / pl_sub_fim_mes_anterior) - 1
            pl_sub_fim_mes_anterior = pl_subordinada
            # Anualizado: retorno acumulado desde D+0, anualizado pelo nº de meses
            if pl_sub_d0 > 0:
                retorno_acum = pl_subordinada / pl_sub_d0
                retorno_sub_anual = retorno_acum ** (12 / mes) - 1
            else:
                retorno_sub_anual = nan
        else:
            retorno_sub_mensal = nan
            retorno_sub_anual = nan

        pl_total_anterior = pl_total  # atualiza para o próximo dia

        resultados.append(LinhaResultado(
            mes=mes, data=dia, dias_uteis=1,
            pl_senior=pl_senior, pl_mezanino=pl_mezanino,
            pl_subordinada=pl_subordinada, pl_total=pl_total,
            aporte_senior=aporte_s, aporte_mezanino=aporte_m, aporte_subordinada=aporte_sub,
            amort_senior=amort_s, amort_mezanino=amort_m, amort_subordinada=amort_sub,
            juros_senior=juros_s, juros_mezanino=juros_m, juros_subordinada=juros_sub,
            receita_ativo=receita_ativo, receita_caixa=receita_caixa,
            receita_bruta=receita_bruta, pdd=pdd,
            despesas_totais=despesas_totais, resultado_liquido=resultado_liquido,
            rendimento_senior=rendimento_senior, rendimento_mezanino=rendimento_mezanino,
            rendimento_subordinada=rendimento_subordinada,
            subordinacao=subordinacao,
            retorno_subordinada_mensal=retorno_sub_mensal,
            retorno_subordinada_anual=retorno_sub_anual,
            alerta_subordinacao=subordinacao < params.subordinacao_minima,
            cdi_utilizado=cdi_anual_dia,
            taxa_performance=taxa_performance_dia,
        ))

    df = pd.DataFrame([vars(r) for r in resultados])
    df["data"] = pd.to_datetime(df["data"])
    return df


# ─── Métricas de resumo ───────────────────────────────────────────────────────

def calcular_metricas_resumo(df: pd.DataFrame, params: ParametrosFundo) -> dict:
    if df.empty:
        return {}

    df_du = df[df["mes"] > 0]  # exclui D+0
    n_meses = int(df_du["mes"].nunique())

    sub_inicial = params.cota_subordinada.valor_inicial if params.cota_subordinada else 0.0
    sub_final   = df.iloc[-1]["pl_subordinada"]

    tir_sub_mensal = (sub_final / sub_inicial) ** (1 / n_meses) - 1 if sub_inicial > 0 and n_meses > 0 else 0.0

    # Retorno médio mensal: média dos valores calculados no último d.u. de cada mês
    df_fim_mes = df_du[df_du["retorno_subordinada_mensal"].notna()]

    return {
        "PL Inicial (R$)":                    params.pl_inicial,
        "PL Final (R$)":                      df.iloc[-1]["pl_total"],
        "PL Sub. Inicial (R$)":               sub_inicial,
        "PL Sub. Final (R$)":                 sub_final,
        "TIR Subordinada (a.a.)":             (1 + tir_sub_mensal) ** 12 - 1,
        "Retorno Sub. Médio Mensal":          df_fim_mes["retorno_subordinada_mensal"].mean(),
        "Total Receita Bruta (R$)":           df_du["receita_bruta"].sum(),
        "Total PDD (R$)":                     df_du["pdd"].sum(),
        "Total Despesas (R$)":                df_du["despesas_totais"].sum(),
        "Total Amortizado Sênior (R$)":       df_du["amort_senior"].sum(),
        "Total Amortizado Mezanino (R$)":     df_du["amort_mezanino"].sum(),
        "Subordinação Inicial":               params.subordinacao_inicial,
        "Subordinação Final":                 df.iloc[-1]["subordinacao"],
        "Subordinação Mínima no Período":     df_du["subordinacao"].min(),
        "Dias Úteis com Alerta de Subordinação": int(df_du["alerta_subordinacao"].sum()),
        "Dias Úteis Simulados":               int(df_du["dias_uteis"].sum()),
        "Meses Simulados":                    n_meses,
        "Total Taxa de Performance (R$)":     df_du["taxa_performance"].sum(),
    }
