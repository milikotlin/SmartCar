"""Synthetic training data (data augmentation) by sequential CART synthesis, the standard method for realistic tabular data (Reiter 2005; R package `synthpop`).

Every column is generated conditionally on the columns before it: a decision tree is fitted on REAL rows, a synthetic row is sent down the tree, and its value is
drawn from the real values of the leaf it lands in. That preserves marginal distributions AND the (non-linear) correlations, without assuming a formula.
Continuous values are interpolated towards another real vehicle of the same leaf (as SMOTE does) plus a 2% noise, so no real vehicle is copied.

Synthetic rows carry `synthetic=True` and are used for TRAINING ONLY. `fidelity()` checks them against real rows that the generator never saw.
"""
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor


class SequentialCART:
    def __init__(self, order, categorical, continuous, min_leaf=30, jitter=0.25, log_columns=("km",), seed=42):
        self.order, self.categorical, self.continuous = list(order), set(categorical), set(continuous)
        self.min_leaf, self.jitter, self.log_columns, self.seed = min_leaf, jitter, set(log_columns), seed

    def _x(self, d, cols):
        return np.column_stack([d[c].map(self.codes[c]).fillna(-1).to_numpy(float) if c in self.categorical else pd.to_numeric(d[c]).fillna(-1).to_numpy(float) for c in cols])

    def fit(self, real):
        real = real[self.order].reset_index(drop=True)
        target = pd.to_numeric(real[self.order[-1]], errors="coerce")
        self.codes = {c: target.groupby(real[c]).mean().rank().to_dict() for c in self.categorical}       # ordered codes, so that the trees can split categories
        self.first = real[self.order[0]].to_numpy()
        self.models = {}
        for i, c in enumerate(self.order[1:], 1):
            prev = self.order[:i]
            X, y = self._x(real, prev), real[c]
            if c in self.categorical:
                lab = y.astype(str)
                top = lab.value_counts().index[:40]               # the tree is grown on the frequent categories; the draw uses ALL the real values of the leaf
                tree = DecisionTreeClassifier(min_samples_leaf=self.min_leaf, max_leaf_nodes=3000, random_state=self.seed).fit(X, lab.where(lab.isin(top), "_rest"))
            else:
                t = np.log1p(y) if c in self.log_columns else y
                tree = DecisionTreeRegressor(min_samples_leaf=self.min_leaf, max_leaf_nodes=3000, random_state=self.seed).fit(X, t.fillna(t.median()))
            leaves = tree.apply(X)
            order = np.argsort(leaves, kind="stable")
            ids, start = np.unique(leaves[order], return_index=True)
            end = np.r_[start[1:], len(order)]
            a, b = np.zeros(tree.tree_.node_count, int), np.zeros(tree.tree_.node_count, int)
            a[ids], b[ids] = start, end
            self.models[c] = (prev, tree, y.to_numpy()[order], a, b)
        return self

    def sample(self, n, first=None, given=None, seed=None):
        """n synthetic rows. `given` fixes leading columns (e.g. fuel and age) to fill sparse regions; the rest is drawn conditionally on them."""
        rng = np.random.default_rng(self.seed + 1 if seed is None else seed)
        out = given.reset_index(drop=True).copy() if given is not None else pd.DataFrame({self.order[0]: rng.choice(self.first, n)})
        n = len(out)
        for c in self.order[1:]:
            if c in out:
                continue
            prev, tree, donors, a, b = self.models[c]
            leaves = tree.apply(self._x(out, prev))
            pick = lambda: donors[(a[leaves] + rng.random(n) * (b[leaves] - a[leaves])).astype(int)]
            v = pick()
            if c in self.continuous:
                v, other = v.astype(float), pick().astype(float)
                v = v + rng.random(n) * self.jitter * (other - v)
                if c in self.log_columns:
                    v = v * (1 + rng.normal(0, 0.02, n))
            out[c] = v
        out["synthetic"] = True
        return out


def fidelity(real, synth, continuous, categorical):
    """Synthetic against REAL rows the generator never saw: marginals (KS / total variation) and correlations (largest Spearman difference)."""
    ks = {c: round(float(ks_2samp(real[c].dropna().astype(float), synth[c].dropna().astype(float)).statistic), 4) for c in continuous}
    tv = {}
    for c in categorical:
        p, q = real[c].astype(str).value_counts(normalize=True), synth[c].astype(str).value_counts(normalize=True)
        tv[c] = round(float(p.sub(q, fill_value=0).abs().sum() / 2), 4)
    cr, cs = real[continuous].astype(float).corr("spearman"), synth[continuous].astype(float).corr("spearman")
    return {"ks_statistic": ks, "total_variation": tv, "largest_spearman_difference": round(float((cr - cs).abs().to_numpy().max()), 4),
            "real_spearman": cr.round(3).to_dict(), "synthetic_spearman": cs.round(3).to_dict()}
