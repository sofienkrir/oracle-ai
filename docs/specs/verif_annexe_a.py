"""Vérification indépendante de l'annexe A de la spécification de l'étape 3.

Implémentation volontairement différente de celle de l'application (ligne par ligne, Decimal,
sans pandas) : elle sert d'oracle. Usage : python docs/specs/verif_annexe_a.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal as D

# ----------------------------------------------------------------------------- données

ROWS = [  # facture, code, Q, prix, client
    ("1001", "22423", 2, D("10.00"), "17001"),
    ("1001", "22423", 2, D("10.00"), "17001"),
    ("1001", "85123A", 1, D("0.00"), "17001"),
    ("1001", "POST", 1, D("5.00"), "17001"),
    ("1002", "22423", 3, D("10.00"), None),
    ("1003", "85123A", 4, D("0.00"), "17002"),
    ("C1004", "22423", -1, D("10.00"), "17001"),
    ("C1005", "D", -1, D("3.00"), "17001"),
    ("C1006", "22423", 2, D("10.00"), "17002"),
    ("A1007", "B", 1, D("-50.00"), None),
    ("1008", "22423", -5, D("0.00"), None),
    ("1009", "22423", -2, D("10.00"), "17002"),
    ("1010", "22423", 0, D("10.00"), "17002"),
    ("1011", "22423", 1, D("10.00"), "17003"),
    ("1012", "22423", 1, None, "17003"),
    ("1013", "GIFTX1", 1, D("20.00"), "17003"),
]

# sous-catégorie -> incluse dans la facturation client indicative ?
BILLED = {
    "Frais de port": True,
    "Remise": True,
    "Bon cadeau": True,
    "Échantillon": True,
    "Frais & commissions": False,
    "Ajustement manuel": False,
    "Test": False,
    "Autre": False,
}


@dataclass(frozen=True)
class Rules:
    validated: tuple[tuple[str, str], ...] = (("POST", "Frais de port"), ("D", "Remise"))
    include_duplicates: bool = False
    adjustments_in_net: bool = False
    incoherent_c_as_return: bool = False
    r9_as_return: bool = False


def is_standard(code: str) -> bool:
    return re.fullmatch(r"\d{5}[A-Za-z]{0,2}", code) is not None


def classify(rules: Rules) -> list[tuple[int, str, str | None]]:
    validated = dict(rules.validated)
    seen: set[tuple] = set()
    out = []
    for n, (inv, code, q, p, cust) in enumerate(ROWS, start=1):
        key = (inv, code, q, p, cust)
        dup = key in seen
        seen.add(key)
        sub = None
        if dup and not rules.include_duplicates:
            cat = "R0"
        elif q is None or p is None:
            cat = "R1"
        elif inv.startswith("A") or p < 0:
            cat = "R2"
        elif code in validated and validated[code] != "Produit":
            cat, sub = "R3", validated[code]
        elif inv.startswith("C") and q > 0:
            cat = "R4"
        elif inv.startswith("C") and q < 0:
            cat = "R5"
        elif q == 0:
            cat = "R6"
        elif p == 0 and q > 0:
            cat = "R7"
        elif p == 0 and q < 0:
            cat = "R8"
        elif p > 0 and q < 0:
            cat = "R9"
        else:
            cat = "R10"
        out.append((n, cat, sub))
    return out


def kpis(rules: Rules) -> dict[str, object]:
    cls = classify(rules)
    validated = dict(rules.validated)
    S: dict[str, D] = {}
    N: dict[str, int] = {}
    for (n, cat, _sub), (_inv, _code, q, p, _c) in zip(cls, ROWS, strict=True):
        N[cat] = N.get(cat, 0) + 1
        if q is not None and p is not None:
            S[cat] = S.get(cat, D(0)) + q * p
    m = [(q * p if q is not None and p is not None else None) for (_i, _c, q, p, _cu) in ROWS]
    m_brut = sum((x for x in m if x is not None), D(0))

    def rows_in(*cats):
        return [(i, ROWS[i]) for i, (_, c, _) in enumerate(cls) if c in cats]

    vb = sum((q * p for _, (_, _, q, p, _) in rows_in("R10")), D(0))
    rs = sum((q * p for _, (_, _, q, p, _) in rows_in("R5")), D(0))
    if rules.incoherent_c_as_return:
        rs -= sum((abs(q * p) for _, (_, _, q, p, _) in rows_in("R4")), D(0))
    if rules.r9_as_return:
        rs += sum((q * p for _, (_, _, q, p, _) in rows_in("R9")), D(0))
    can = vb + rs
    if rules.adjustments_in_net:
        can += S.get("R2", D(0))
    orders = {inv for _, (inv, *_r) in rows_in("R10")}
    invoices = {r[0] for r in ROWS}
    up = sum(q for _, (_, _, q, _, _) in rows_in("R10"))
    ug = sum(q for _, (_, _, q, _, _) in rows_in("R7"))
    ident = [(c, q * p) for _, (_, _, q, p, c) in rows_in("R10") if c]
    vb_id = sum((x for _, x in ident), D(0))
    sub_sum: dict[str, D] = {}
    for (n, cat, sub), (_i, _c, q, p, _cu) in zip(cls, ROWS, strict=True):
        if cat == "R3":
            sub_sum[sub] = sub_sum.get(sub, D(0)) + q * p
    billed = sum((v for k, v in sub_sum.items() if BILLED[k]), D(0))
    fci = (
        vb + rs + billed
    )  # facturation client indicative (ventes + retours produits + R3 facturés)
    unvalidated = [
        (q * p)
        for (n, cat, _), (_i, code, q, p, _c) in zip(cls, ROWS, strict=True)
        if cat in ("R10", "R5") and not is_standard(code) and code not in validated
    ]
    excluded_for_bridge = sum((v for k, v in S.items() if k not in ("R5", "R10")), D(0))
    # Pont pour la configuration ACTIVE : on retire chaque catégorie exclue, puis on réintègre
    # ce que les options font entrer dans le CA net (avec le signe défini par l'option).
    reintegration = D(0)
    if rules.adjustments_in_net:
        reintegration += S.get("R2", D(0))
    if rules.incoherent_c_as_return:
        reintegration -= sum((abs(q * p) for _, (_, _, q, p, _) in rows_in("R4")), D(0))
    if rules.r9_as_return:
        reintegration += S.get("R9", D(0))
    pont_actif = m_brut - excluded_for_bridge + reintegration
    return {
        "lignes": sum(N.values()),
        "N": dict(sorted(N.items(), key=lambda kv: int(kv[0][1:]))),
        "M_brut": m_brut,
        "integrite_montants": sum(S.values(), D(0)) == m_brut,
        "pont_v2": m_brut - excluded_for_bridge,
        "pont_actif": pont_actif,
        "pont_ok": pont_actif == can,
        "VB": vb,
        "R": -rs,
        "CAN": can,
        "TR": (-rs / vb) if vb else None,
        "C": len(orders),
        "PM": (vb / len(orders)) if orders else None,
        "UP": up,
        "UG": ug,
        "PU": (vb / up) if up else None,
        "factures_sans_vente": len(invoices - orders),
        "clients": len({c for c, _ in ident}),
        "VB_identifie": vb_id,
        "part_sans_client": 1 - vb_id / vb if vb else None,
        "RM": sub_sum.get("Remise", D(0)),
        "FP": sub_sum.get("Frais de port", D(0)),
        "BC": sub_sum.get("Bon cadeau", D(0)),
        "CA_net_apres_remises": vb + rs + sub_sum.get("Remise", D(0)),
        "FCI": fci,
        "FCI_formule_v2": vb
        + rs
        + sub_sum.get("Remise", D(0))
        + sub_sum.get("Frais de port", D(0)),
        "non_valide_montant": sum(unvalidated, D(0)),
        "non_valide_lignes": len(unvalidated),
    }


SCENARIOS = {
    "S0 défaut": Rules(),
    "S1 doublons inclus": Rules(include_duplicates=True),
    "S2 ajustements dans CA net": Rules(adjustments_in_net=True),
    "S3 C incohérentes = retours": Rules(incoherent_c_as_return=True),
    "S4 retours hors C = retours": Rules(r9_as_return=True),
    "S5 GIFTX1 = Bon cadeau": Rules(
        validated=(("POST", "Frais de port"), ("D", "Remise"), ("GIFTX1", "Bon cadeau"))
    ),
}

# Valeurs écrites dans la spécification v2 (annexe A et §3), à comparer.
SPEC_V2 = {
    ("S0 défaut", "lignes"): 16,
    ("S0 défaut", "M_brut"): D(42),
    ("S0 défaut", "pont_v2"): D(70),
    ("S0 défaut", "VB"): D(80),
    ("S0 défaut", "R"): D(10),
    ("S0 défaut", "CAN"): D(70),
    ("S0 défaut", "TR"): D("0.125"),
    ("S0 défaut", "C"): 4,
    ("S0 défaut", "PM"): D(20),
    ("S0 défaut", "UP"): 7,
    ("S0 défaut", "UG"): 5,
    ("S0 défaut", "CA_net_apres_remises"): D(67),
    ("S0 défaut", "FCI_formule_v2"): D(72),
    ("S0 défaut", "clients"): 2,
    ("S0 défaut", "part_sans_client"): D("0.375"),
    ("S0 défaut", "non_valide_montant"): D(20),
    ("S0 défaut", "non_valide_lignes"): 1,
    ("S1 doublons inclus", "VB"): D(100),
    ("S1 doublons inclus", "CAN"): D(90),
    ("S2 ajustements dans CA net", "CAN"): D(20),
    ("S3 C incohérentes = retours", "CAN"): D(50),
    ("S5 GIFTX1 = Bon cadeau", "VB"): D(60),
    ("S5 GIFTX1 = Bon cadeau", "CAN"): D(50),
    ("S5 GIFTX1 = Bon cadeau", "C"): 3,
}


def fmt(v: object) -> str:
    if isinstance(v, D):
        return f"{v:.4f}".rstrip("0").rstrip(".") if v != v.to_integral() else f"{v:.0f}"
    return str(v)


# ----------------------------------------------------------------------------- couverture


def coverage(days_with_data: set[date], gap_min: int = 7) -> dict[str, object]:
    j_min, j_max = min(days_with_data), max(days_with_data)
    months: dict[tuple[int, int], dict] = {}
    d = date(j_min.year, j_min.month, 1)
    while d <= j_max:
        nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        end = nxt - timedelta(days=1)
        in_win = [
            d + timedelta(i)
            for i in range((end - d).days + 1)
            if j_min <= d + timedelta(i) <= j_max
        ]
        status = "complète" if d >= j_min and end <= j_max else "partielle"
        empty = [x for x in in_win if x not in days_with_data]
        months[(d.year, d.month)] = {
            "statut": status,
            "couverture": f"{len(in_win)}/{(end - d).days + 1}",
            "jours_sans_donnees": len(empty),
        }
        d = nxt
    gaps, run = [], []
    x = j_min
    while x <= j_max:
        if x not in days_with_data:
            run.append(x)
        else:
            if len(run) >= gap_min:
                gaps.append((run[0], run[-1], len(run)))
            run = []
        x += timedelta(days=1)
    by_wd = {}
    x = j_min
    while x <= j_max:
        tot, empty = by_wd.get(x.weekday(), (0, 0))
        by_wd[x.weekday()] = (tot + 1, empty + (x not in days_with_data))
        x += timedelta(days=1)
    weeks = {}
    w = j_min - timedelta(days=j_min.weekday())
    while w <= j_max:
        end = w + timedelta(days=6)
        in_win = sum(1 for i in range(7) if j_min <= w + timedelta(i) <= j_max)
        iso = w.isocalendar()
        weeks[f"{iso[0]}-W{iso[1]:02d}"] = (
            "complète" if w >= j_min and end <= j_max else "partielle",
            f"{in_win}/7",
        )
        w += timedelta(days=7)
    return {
        "fenetre": (j_min, j_max),
        "mois": months,
        "semaines": weeks,
        "trous": gaps,
        "par_jour_semaine": by_wd,
    }


def coverage_fixture() -> set[date]:
    days = set()
    x = date(2024, 1, 1)
    while x <= date(2024, 3, 15):
        saturday = x.weekday() == 5
        short_gap = date(2024, 1, 15) <= x <= date(2024, 1, 17)
        long_gap = date(2024, 2, 10) <= x <= date(2024, 2, 20)
        if not (saturday or short_gap or long_gap):
            days.add(x)
        x += timedelta(days=1)
    return days


if __name__ == "__main__":
    results = {name: kpis(r) for name, r in SCENARIOS.items()}
    keys = [k for k in results["S0 défaut"] if k != "N"]
    print("Catégories (S0) :", results["S0 défaut"]["N"])
    print()
    print(f"{'KPI':24}" + "".join(f"{n.split(' ', 1)[0]:>9}" for n in SCENARIOS))
    for k in keys:
        print(f"{k:24}" + "".join(f"{fmt(results[n][k]):>9}" for n in SCENARIOS))
    print()
    print("Comparaison avec la spécification v2 :")
    ok = 0
    for (sc, k), expected in SPEC_V2.items():
        got = results[sc][k]
        same = got == expected
        ok += same
        print(
            f"  {'✓' if same else '✗'} {sc:30} {k:22} spec={fmt(expected):>7} recalcul={fmt(got):>7}"
        )
    print(f"  {ok}/{len(SPEC_V2)} valeurs concordantes")
    print()
    cov = coverage(coverage_fixture())
    print("Couverture — fenêtre", cov["fenetre"])
    for m, v in cov["mois"].items():
        print("  ", m, v)
    print("   trous ≥ 7 jours :", cov["trous"])
    sem = cov["semaines"]
    print(
        "   semaines : 2024-W01",
        sem["2024-W01"],
        "| 2024-W06",
        sem["2024-W06"],
        "| 2024-W11",
        sem["2024-W11"],
        "| nb",
        len(sem),
    )
    names = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
    print(
        "   jours vides / total par jour de semaine :",
        {names[k]: f"{v[1]}/{v[0]}" for k, v in sorted(cov["par_jour_semaine"].items())},
    )

    # Mois entier sans données à l'intérieur de la fenêtre : complet, signalé comme trou.
    days = {date(2024, 1, d) for d in range(2, 31)} | {date(2024, 3, d) for d in range(1, 20)}
    cov2 = coverage(days)
    print("Mois vide dans la fenêtre :", cov2["mois"][(2024, 2)], "| trous :", cov2["trous"])

    # ------------------------------------------------------------------ table v3 de l'annexe A
    V3_COLS = list(SCENARIOS)
    V3 = {  # valeurs telles qu'écrites dans la table de l'annexe A (v3)
        "VB": [80, 100, 80, 80, 80, 60],
        "R": [10, 10, 10, 30, 30, 10],
        "CAN": [70, 90, 20, 50, 50, 50],
        "TR": ["0.125", "0.1", "0.125", "0.375", "0.375", "0.1667"],
        "C": [4, 4, 4, 4, 4, 3],
        "PM": [20, 25, 20, 20, 20, 20],
        "UP": [7, 9, 7, 7, 7, 6],
        "UG": [5, 5, 5, 5, 5, 5],
        "PU": ["11.43", "11.11", "11.43", "11.43", "11.43", "10.00"],
        "factures_sans_vente": [9, 9, 9, 9, 9, 10],
        "clients": [2, 2, 2, 2, 2, 2],
        "VB_identifie": [50, 70, 50, 50, 50, 30],
        "part_sans_client": ["0.375", "0.3", "0.375", "0.375", "0.375", "0.5"],
        "CA_net_apres_remises": [67, 87, 67, 47, 47, 47],
        "FCI": [72, 92, 72, 52, 52, 72],
        "non_valide_montant": [20, 20, 20, 20, 20, 0],
        "non_valide_lignes": [1, 1, 1, 1, 1, 0],
        "BC": [0, 0, 0, 0, 0, 20],
    }
    bad = []
    n = 0
    for k, vals in V3.items():
        for sc, exp in zip(V3_COLS, vals, strict=True):
            got = results[sc][k]
            n += 1
            if isinstance(exp, str):  # valeur affichée arrondie
                places = len(exp.split(".")[1])
                ok = round(D(got), places) == D(exp)
            else:
                ok = got == exp
            if not ok:
                bad.append((sc, k, exp, got))
    print(f"\nTable v3 de l'annexe A : {n - len(bad)}/{n} cellules concordantes", bad or "")

    # ------------------------------------------------------------------ 16 combinaisons O1–O4
    import itertools

    ok_all = all(
        kpis(
            Rules(
                include_duplicates=a, adjustments_in_net=b, incoherent_c_as_return=c, r9_as_return=d
            )
        )["pont_ok"]
        for a, b, c, d in itertools.product([False, True], repeat=4)
    )
    print("Pont actif = CAN pour les 16 combinaisons O1–O4 :", ok_all)
