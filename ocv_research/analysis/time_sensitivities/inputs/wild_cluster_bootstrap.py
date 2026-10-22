"""Seeded restricted WCLR-C Rademacher bootstrap for the current models."""

from __future__ import annotations

import numpy as np
import statsmodels.api as sm


def _cluster_scores_and_information(X, y, probabilities, groups):
    unique = np.unique(groups)
    scores, information = [], []
    for group in unique:
        mask = groups == group
        Xg, pg = X[mask], probabilities[mask]
        scores.append(Xg.T @ (y[mask] - pg))
        information.append(Xg.T @ ((pg * (1 - pg))[:, None] * Xg))
    return np.asarray(scores), np.asarray(information)


def wclr_c_pvalue(X, y, groups, fit, term_index, reps, seed):
    """Restricted WCLR-C test; returns (p, observed CV1 t-statistic)."""
    n, k = X.shape
    G = len(np.unique(groups))
    factor = G * (n - 1) / ((G - 1) * (n - k))
    unrestricted_scores, unrestricted_Jg = _cluster_scores_and_information(
        X, y, np.asarray(fit.fittedvalues), groups)
    J_hat_inv = np.linalg.inv(unrestricted_Jg.sum(axis=0))
    sandwich = factor * J_hat_inv @ (unrestricted_scores.T @ unrestricted_scores) @ J_hat_inv
    observed_t = float(fit.params.iloc[term_index] / np.sqrt(sandwich[term_index, term_index]))
    if reps == 0:
        return np.nan, observed_t

    nuisance = [i for i in range(k) if i != term_index]
    restricted_fit = sm.GLM(y, X[:, nuisance], family=sm.families.Binomial()).fit()
    restricted_probabilities = np.asarray(restricted_fit.fittedvalues)
    scores, Jg = _cluster_scores_and_information(X, y, restricted_probabilities, groups)
    J_inv = np.linalg.inv(Jg.sum(axis=0))
    rng = np.random.default_rng(seed)
    exceed = 0
    completed = 0
    while completed < reps:
        batch = min(4096, reps - completed)
        signs = rng.choice(np.array([-1.0, 1.0]), size=(batch, G))
        scores_star = signs[:, :, None] * scores[None, :, :]
        b_star = scores_star.sum(axis=1) @ J_inv.T
        # Recalculate cluster scores after the linearized model fit.
        w_star = scores_star - np.einsum("gij,bj->bgi", Jg, b_star)
        projected = w_star @ J_inv[term_index, :]
        se_star = np.sqrt(factor * np.sum(projected**2, axis=1))
        valid = se_star > 0
        if not valid.all():
            raise ArithmeticError("Zero bootstrap standard error; inspect cluster structure")
        t_star = b_star[:, term_index] / se_star
        exceed += int(np.count_nonzero(np.abs(t_star) >= abs(observed_t)))
        completed += batch
    return (exceed + 1) / (reps + 1), observed_t
