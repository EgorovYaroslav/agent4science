# Hypotheses H1–H9

## H1 — Self-consistency
**Statement:** $S_{3000,3000} \geq 0.95$ — модель детерминирована.
**Test:** 100 повторных инференсов на одних и тех же 3000 МГц изображениях.
**Expectation:** $S = 1.0$.

## H2 — Symmetry of agreement
**Statement:** $S_{3000,6000} = S_{3000,12200}$ — согласованность не зависит от целевой частоты.
**Test:** $\chi^2$ test for equality of proportions.
**Expectation:** $p \geq 0.05$ (not rejected).

## H3 — Practical usability thresholds
**Statement:** $S_{3000,6000} \geq 0.90$ и $S_{3000,12200} \geq 0.85$.
**Test:** One-sided z-test + bootstrap CI.
**Expectation:** Both thresholds met.

## H4 — Class-stratified asymmetry
**Statement:** $S^{(Ok)}_{3000,6000} \neq S^{(Bad)}_{3000,6000}$ или $S^{(Ok)}_{3000,12200} \neq S^{(Bad)}_{3000,12200}$.
**Test:** Stratified agreement by 3000 MHz predicted class.
**Expectation:** Significant asymmetry — Bad class transfers better.

## H5 — Confidence degradation
**Statement:** $\mathbb{E}[p_{3000}] \geq \mathbb{E}[p_{6000}] \geq \mathbb{E}[p_{12200}]$.
**Test:** Paired $t$-test.
**Expectation:** $p_{3000} > p_{6000} > p_{12200}$, significant for 3000 vs 12200.

## H6 — Temporal sensitivity
**Statement:** $\operatorname{corr}(S, \Delta t) < 0$ — больше $\Delta t$ → меньше согласованность.
**Test:** Spearman correlation.
**Expectation:** $\rho \approx 0$ (within $\pm 3$ min).

## H7 — Distribution shift
**Statement:** $P(\hat{y}^{(3000)}=Ok) \neq P(\hat{y}^{(6000)}=Ok) \neq P(\hat{y}^{(12200)}=Ok)$.
**Test:** $\chi^2$ homogeneity test.
**Expectation:** Significant shift — Ok rate drops at higher frequencies.

## H8 — Seasonal stability
**Statement:** $S_{3000,6000}$ does not vary across months.
**Test:** Kruskal-Wallis test.
**Expectation:** Significant variation ($p < 0.05$).

## H9 — Baseline comparison
**Statement:** $S^{(f_{3000})} > S^{(majority)}$ for both 6000 and 12200 MHz.
**Test:** z-test for two proportions.
**Expectation:** Model significantly outperforms baseline ($p < 0.05$).
