class EMAEstimator:
    """
    Exponential moving average estimator for failure rate.

    update(observed_failure_rate) -> float
        Returns the new EMA value.
    relative_deviation(nominal) -> float
        Returns |ema - nominal| / nominal (or 0 if nominal == 0).
    """

    def __init__(self, beta: float = 0.3):
        self.beta = beta
        self._ema: float | None = None

    def update(self, observed_failure_rate: float) -> float:
        if self._ema is None:
            self._ema = observed_failure_rate
        else:
            self._ema = self.beta * observed_failure_rate + (1.0 - self.beta) * self._ema
        return self._ema

    @property
    def value(self) -> float | None:
        return self._ema

    def relative_deviation(self, nominal: float) -> float:
        if nominal == 0:
            return 0.0
        if self._ema is None:
            return 0.0
        return abs(self._ema - nominal) / nominal
