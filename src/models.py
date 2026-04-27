from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import date


class TipoCota(str, Enum):
    SENIOR = "senior"
    MEZANINO = "mezanino"
    SUBORDINADA = "subordinada"


class TipoIndexador(str, Enum):
    FIXO = "fixo"
    CDI = "cdi"
    IPCA = "ipca"


class PeriodicidadeJuros(str, Enum):
    NENHUMA = "nenhuma"
    MENSAL = "mensal"
    TRIMESTRAL = "trimestral"
    SEMESTRAL = "semestral"
    ANUAL = "anual"


class TipoAmortizacao(str, Enum):
    JUROS = "juros"
    JUROS_ACUMULADOS = "juros_acumulados"
    PRINCIPAL = "principal"
    TOTAL = "total"


@dataclass
class ConfiguracaoCota:
    tipo: TipoCota
    valor_inicial: float
    valor_unitario: float
    tipo_indexador: TipoIndexador = TipoIndexador.FIXO
    taxa_fixa_anual: float = 0.0
    spread_sobre_indexador: float = 0.0
    periodicidade_juros: PeriodicidadeJuros = PeriodicidadeJuros.NENHUMA

    @property
    def quantidade_cotas(self) -> float:
        if self.valor_unitario <= 0:
            return 0.0
        return self.valor_inicial / self.valor_unitario


@dataclass
class Aporte:
    data: date
    tipo_cota: TipoCota
    valor: float
    ramp_up_meses: int = 0


@dataclass
class Amortizacao:
    data: date
    tipo_cota: TipoCota
    tipo: TipoAmortizacao
    valor: float
    percentual: float = 0.0


@dataclass
class ConfiguracaoAtivo:
    taxa_anual: float
    inadimplencia_anual: float
    prazo_medio_meses: int = 12
    ociosidade_caixa: float = 0.0  # % do PL em caixa (acruando a 100% CDI)


@dataclass
class ConfiguracaoCustos:
    taxa_administracao: float = 0.005
    taxa_gestao: float = 0.01
    taxa_custodia: float = 0.002
    outras_despesas_anuais: float = 0.0
    # Mínimos mensais (R$): 0 = sem mínimo
    minimo_mensal_administracao: float = 0.0
    minimo_mensal_gestao: float = 0.0


@dataclass
class ConfiguracaoPerformance:
    ativo: bool = False
    percentual: float = 0.20                                        # ex: 20%
    periodo_apuracao: PeriodicidadeJuros = PeriodicidadeJuros.ANUAL
    hurdle_indexador: TipoIndexador = TipoIndexador.CDI
    hurdle_taxa_fixa: float = 0.0                                   # só se indexador == FIXO
    hurdle_spread: float = 0.0                                      # spread sobre CDI ou IPCA
    high_water_mark_inicial: float = 0.0                            # 0 = usa PL_sub do D+0


@dataclass
class ParametrosFundo:
    nome: str
    data_inicio: date
    prazo_meses: int

    cota_senior: Optional[ConfiguracaoCota] = None
    cota_mezanino: Optional[ConfiguracaoCota] = None
    cota_subordinada: Optional[ConfiguracaoCota] = None

    ativo: ConfiguracaoAtivo = field(default_factory=lambda: ConfiguracaoAtivo(0.18, 0.03))
    custos: ConfiguracaoCustos = field(default_factory=ConfiguracaoCustos)
    performance: ConfiguracaoPerformance = field(default_factory=ConfiguracaoPerformance)

    aportes: list[Aporte] = field(default_factory=list)
    amortizacoes: list[Amortizacao] = field(default_factory=list)

    curva_cdi: dict = field(default_factory=dict)  # {date: fator_diário} da planilha DI futuro
    ipca_anual: float = 0.045
    subordinacao_minima: float = 0.20

    @property
    def pl_inicial(self) -> float:
        return sum(
            c.valor_inicial for c in [self.cota_senior, self.cota_mezanino, self.cota_subordinada]
            if c is not None
        )

    @property
    def subordinacao_inicial(self) -> float:
        if self.pl_inicial <= 0 or not self.cota_subordinada:
            return 0.0
        return self.cota_subordinada.valor_inicial / self.pl_inicial
