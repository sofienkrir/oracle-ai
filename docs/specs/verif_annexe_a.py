"""Oracle indépendant de la spécification de l'étape 3 (v4).

Implémentation volontairement différente de celle de l'application : calcul ligne par ligne,
`Decimal`, sans pandas, avec un **registre** qui attribue à chaque ligne une seule catégorie,
son montant saisi `m` et sa contribution `c` au CA produits net.

Usage : python docs/specs/verif_annexe_a.py
Ce script n'est pas un test de l'application : il produit les valeurs attendues que les tests
de l'annexe B compareront au code (à écrire après validation de la spécification).
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal as D

# ----------------------------------------------------------------------------- données

Row = tuple[str, str, int | None, D | None, str | None]  # facture, code, Q, prix, client

ROWS: list[Row] = [
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

BILLED = {  # sous-catégorie R3 -> incluse dans la facturation client indicative
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
    o1_include_duplicates: bool = False
    o2_show_cana: bool = False  # v4 : indicateur distinct, ne modifie jamais le CAN
    o3_incoherent_c_as_return: bool = False
    o4_r9_as_return: bool = False


def is_standard(code: str) -> bool:
    return re.fullmatch(r"\d{5}[A-Za-z]{0,2}", code) is not None


# ----------------------------------------------------------------------------- registre


@dataclass
class Entry:
    line: int
    category: str
    sub: str | None
    m: D | None  # montant saisi (None si non calculable)
    c: D  # contribution au CA produits net
    bucket: str  # ligne du pont financier


def ledger(rows: list[Row], rules: Rules) -> list[Entry]:
    validated = dict(rules.validated)
    seen: set[tuple] = set()
    out: list[Entry] = []
    for n, (inv, code, q, p, cust) in enumerate(rows, start=1):
        key = (inv, code, q, p, cust)
        dup = key in seen
        seen.add(key)
        m = q * p if q is not None and p is not None else None
        sub = None
        if dup and not rules.o1_include_duplicates:
            cat = "R0"
        elif m is None:
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

        # contribution au CAN et ligne du pont : UNE seule par ligne
        if cat == "R10":
            c, bucket = m, "Ventes valides (R10)"
        elif cat == "R5":
            c, bucket = m, "Retours produits (R5)"
        elif cat == "R4" and rules.o3_incoherent_c_as_return:
            c, bucket = -abs(m), "Annulations incohérentes traitées en retours (O3)"
        elif cat == "R9" and rules.o4_r9_as_return:
            c, bucket = m, "Retours hors facture C traités en retours (O4)"
        else:
            c, bucket = D(0), f"Exclu : {cat}"
        out.append(Entry(n, cat, sub, m, c, bucket))
    return out


def kpis(rows: list[Row], rules: Rules) -> dict[str, object]:
    led = ledger(rows, rules)
    validated = dict(rules.validated)
    in_cat = lambda *cats: [(e, rows[e.line - 1]) for e in led if e.category in cats]  # noqa: E731

    m_brut = sum((e.m for e in led if e.m is not None), D(0))
    vb = sum((e.m for e, _ in in_cat("R10")), D(0))
    # Retours signés = contributions négatives entrant dans le CAN hors ventes valides
    rs = sum((e.c for e in led if e.category != "R10"), D(0))
    can_direct = vb + rs
    can_ledger = sum((e.c for e in led), D(0))
    bridge = m_brut + sum(((e.c - e.m) for e in led if e.m is not None), D(0))

    s_r2 = sum((e.m for e, _ in in_cat("R2")), D(0))
    orders = {r[0] for _, r in in_cat("R10")}
    invoices = {r[0] for r in rows}
    up = sum(r[2] for _, r in in_cat("R10"))
    ug = sum(r[2] for _, r in in_cat("R7"))
    vb_anonyme = sum((e.m for e, r in in_cat("R10") if not r[4]), D(0))
    vb_id = vb - vb_anonyme
    sub_sum: dict[str, D] = {}
    for e in led:
        if e.category == "R3":
            sub_sum[e.sub] = sub_sum.get(e.sub, D(0)) + e.m
    billed = sum((v for k, v in sub_sum.items() if BILLED[k]), D(0))
    unvalidated = [
        e.m for e, r in in_cat("R10", "R5") if not is_standard(r[1]) and r[1] not in validated
    ]
    buckets = {}
    for e in led:
        buckets.setdefault(e.bucket, []).append(e.line)
    return {
        "lignes": len(led),
        "chaque_ligne_une_fois": sorted(x for v in buckets.values() for x in v)
        == list(range(1, len(rows) + 1)),
        "M_brut": m_brut,
        "integrite_montants": sum((e.m for e in led if e.m is not None), D(0)) == m_brut,
        "pont": bridge,
        "CAN_registre": can_ledger,
        "pont_ok": bridge == can_direct == can_ledger,
        "VB": vb,
        "R": -rs,
        "CAN": can_direct,
        "CANA": can_direct + s_r2 if rules.o2_show_cana else None,
        "TR": (-rs / vb) if vb else None,
        "C": len(orders),
        "PM": (vb / len(orders)) if orders else None,
        "UP": up,
        "UG": ug,
        "PU": (vb / up) if up else None,
        "factures_sans_vente": len(invoices - orders),
        "clients": len({r[4] for _, r in in_cat("R10") if r[4]}),
        "VB_identifie": vb_id,
        "VB_anonyme": vb_anonyme,
        "part_ventes_sans_client": (vb_anonyme / vb) if vb else None,
        "lignes_vente_sans_client": sum(1 for _, r in in_cat("R10") if not r[4]),
        "RM": sub_sum.get("Remise", D(0)),
        "FP": sub_sum.get("Frais de port", D(0)),
        "BC": sub_sum.get("Bon cadeau", D(0)),
        "CA_net_apres_remises": can_direct + sub_sum.get("Remise", D(0)),
        "FCI": can_direct + billed,
        "non_valide_montant": sum(unvalidated, D(0)),
        "non_valide_lignes": len(unvalidated),
        "_buckets": buckets,
        "_ledger": led,
    }


SCENARIOS = {
    "S0 défaut": Rules(),
    "S1 doublons inclus": Rules(o1_include_duplicates=True),
    "S2 CA y c. ajustements": Rules(o2_show_cana=True),
    "S3 C incohérentes = retours": Rules(o3_incoherent_c_as_return=True),
    "S4 retours hors C = retours": Rules(o4_r9_as_return=True),
    "S5 GIFTX1 = Bon cadeau": Rules(
        validated=(("POST", "Frais de port"), ("D", "Remise"), ("GIFTX1", "Bon cadeau"))
    ),
}

# Table de l'annexe A (v4) telle qu'écrite dans la spécification.
TABLE_V4 = {
    "VB": [80, 100, 80, 80, 80, 60],
    "R": [10, 10, 10, 30, 30, 10],
    "CAN": [70, 90, 70, 50, 50, 50],
    "CANA": [None, None, 20, None, None, None],
    "TR": ["0.125", "0.1", "0.125", "0.375", "0.375", "0.1667"],
    "C": [4, 4, 4, 4, 4, 3],
    "PM": [20, 25, 20, 20, 20, 20],
    "UP": [7, 9, 7, 7, 7, 6],
    "UG": [5, 5, 5, 5, 5, 5],
    "PU": ["11.43", "11.11", "11.43", "11.43", "11.43", "10.00"],
    "factures_sans_vente": [9, 9, 9, 9, 9, 10],
    "clients": [2, 2, 2, 2, 2, 2],
    "VB_identifie": [50, 70, 50, 50, 50, 30],
    "VB_anonyme": [30, 30, 30, 30, 30, 30],
    "part_ventes_sans_client": ["0.375", "0.3", "0.375", "0.375", "0.375", "0.5"],
    "lignes_vente_sans_client": [1, 1, 1, 1, 1, 1],
    "CA_net_apres_remises": [67, 87, 67, 47, 47, 47],
    "FCI": [72, 92, 72, 52, 52, 72],
    "BC": [0, 0, 0, 0, 0, 20],
    "non_valide_montant": [20, 20, 20, 20, 20, 0],
    "non_valide_lignes": [1, 1, 1, 1, 1, 0],
}


def same(exp: object, got: object) -> bool:
    if exp is None or got is None:
        return exp is got
    if isinstance(exp, str):
        places = len(exp.split(".")[1])
        return round(D(got), places) == D(exp)
    return got == exp


def fmt(v: object) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "✓" if v else "✗"
    if isinstance(v, D):
        if v == 0:
            return "0"
        return f"{v:.0f}" if v == v.to_integral() else f"{v:.4f}".rstrip("0")
    return str(v)


# ----------------------------------------------------------------------------- couverture


def coverage(
    days_with_data: set[date],
    gap_min: int = 7,
    closed_weekdays: set[int] | None = None,
) -> dict[str, object]:
    """Position dans la fenêtre, couverture en jours, interruptions, et — seulement si un
    calendrier d'activité est déclaré — vérification de la couverture attendue."""
    j_min, j_max = min(days_with_data), max(days_with_data)
    months = {}
    d = date(j_min.year, j_min.month, 1)
    while d <= j_max:
        nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        end = nxt - timedelta(days=1)
        all_days = [d + timedelta(i) for i in range((end - d).days + 1)]
        in_win = [x for x in all_days if j_min <= x <= j_max]
        with_data = [x for x in in_win if x in days_with_data]
        if closed_weekdays is None:
            verified = "non vérifiée (aucun calendrier déclaré)"
        else:
            expected = [x for x in in_win if x.weekday() not in closed_weekdays]
            missing = [x for x in expected if x not in days_with_data]
            verified = (
                "conforme au calendrier déclaré"
                if not missing
                else f"écart : {len(missing)} jour(s) attendu(s) sans données"
            )
        months[(d.year, d.month)] = {
            "position": "intérieure" if d >= j_min and end <= j_max else "bord (partielle)",
            "jours_dans_fenetre": f"{len(in_win)}/{len(all_days)}",
            "jours_avec_donnees": f"{len(with_data)}/{len(in_win)}",
            "couverture_verifiee": verified,
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
    by_wd: dict[int, tuple[int, int]] = {}
    x = j_min
    while x <= j_max:
        tot, empty = by_wd.get(x.weekday(), (0, 0))
        by_wd[x.weekday()] = (tot + 1, empty + (x not in days_with_data))
        x += timedelta(days=1)
    weeks = {}
    w = j_min - timedelta(days=j_min.weekday())
    while w <= j_max:
        iso = w.isocalendar()
        inside = w >= j_min and w + timedelta(days=6) <= j_max
        weeks[f"{iso[0]}-W{iso[1]:02d}"] = (
            "intérieure" if inside else "bord (partielle)",
            f"{sum(1 for i in range(7) if j_min <= w + timedelta(i) <= j_max)}/7",
        )
        w += timedelta(days=7)
    return {
        "fenetre": (j_min, j_max),
        "mois": months,
        "semaines": weeks,
        "interruptions": gaps,
        "par_jour_semaine": by_wd,
    }


def coverage_fixture() -> set[date]:
    days, x = set(), date(2024, 1, 1)
    while x <= date(2024, 3, 15):
        if not (
            x.weekday() == 5
            or date(2024, 1, 15) <= x <= date(2024, 1, 17)
            or date(2024, 2, 10) <= x <= date(2024, 2, 20)
        ):
            days.add(x)
        x += timedelta(days=1)
    return days


# ----------------------------------------------------------------------------- main

if __name__ == "__main__":
    res = {name: kpis(ROWS, r) for name, r in SCENARIOS.items()}

    print("1) Registre S0 (ligne → catégorie, m saisi, contribution c au CAN)")
    for e in res["S0 défaut"]["_ledger"]:
        print(f"   #{e.line:<2} {e.category:4} m={fmt(e.m):>5} c={fmt(e.c):>4}  {e.bucket}")

    print("\n2) Pont financier S0 (une ligne du pont par groupe, chaque ligne une seule fois)")
    led0 = res["S0 défaut"]["_ledger"]
    for b, lines in res["S0 défaut"]["_buckets"].items():
        es = [led0[i - 1] for i in lines]
        sm = sum((e.m for e in es if e.m is not None), D(0))
        sm_txt = "n.c." if all(e.m is None for e in es) else fmt(sm)
        sc = sum((e.c for e in es), D(0))
        print(
            f"   {b:52} lignes={lines!s:22} Σm={sm_txt:>4} Σc={fmt(sc):>4} écart={fmt(sc - sm):>4}"
        )
    print(
        f"   M_brut {fmt(res['S0 défaut']['M_brut'])} + Σ écarts = pont "
        f"{fmt(res['S0 défaut']['pont'])} ; CAN direct {fmt(res['S0 défaut']['CAN'])}"
    )

    print("\n3) Les 16 combinaisons O1–O4 (O2 n'affecte jamais le CAN : il ajoute la CANA)")
    print("   O1 O2 O3 O4 |  CAN direct  Σ c registre  pont  | 1 fois  pont=CAN | CANA")
    all_ok = True
    for o1, o2, o3, o4 in itertools.product([False, True], repeat=4):
        k = kpis(
            ROWS,
            Rules(
                o1_include_duplicates=o1,
                o2_show_cana=o2,
                o3_incoherent_c_as_return=o3,
                o4_r9_as_return=o4,
            ),
        )
        ok = k["pont_ok"] and k["chaque_ligne_une_fois"] and k["integrite_montants"]
        all_ok &= ok
        flags = " ".join("x " if f else ". " for f in (o1, o2, o3, o4))
        print(
            f"   {flags} |  {fmt(k['CAN']):>6}  {fmt(k['CAN_registre']):>10}  {fmt(k['pont']):>6} "
            f"|   {fmt(k['chaque_ligne_une_fois'])}      {fmt(k['pont_ok'])}   | {fmt(k['CANA'])}"
        )
    print(f"   → 16/16 cohérentes : {all_ok}")

    print("\n4) Table de l'annexe A (v4) : écrit dans la spécification vs recalculé")
    cols = list(SCENARIOS)
    n_ok = n_tot = 0
    bad = []
    for key, vals in TABLE_V4.items():
        for sc, exp in zip(cols, vals, strict=True):
            n_tot += 1
            if same(exp, res[sc][key]):
                n_ok += 1
            else:
                bad.append((sc, key, exp, res[sc][key]))
    print(f"   {n_ok}/{n_tot} cellules concordantes", bad or "")

    print("\n5) Part des ventes sans client quand VB = 0 (fixture : uniquement un retour)")
    only_return = [("C9", "22423", -1, D("5.00"), None)]
    k = kpis(only_return, Rules())
    print(
        f"   VB={fmt(k['VB'])} part_ventes_sans_client={fmt(k['part_ventes_sans_client'])} "
        f"(attendu : non calculable) TR={fmt(k['TR'])} PM={fmt(k['PM'])}"
    )

    print("\n6) Couverture (fixture annexe C)")
    for label, cal in (("sans calendrier", None), ("calendrier déclaré : fermé le samedi", {5})):
        cov = coverage(coverage_fixture(), closed_weekdays=cal)
        print(f"   [{label}]")
        for mo, v in cov["mois"].items():
            print(f"     {mo}: {v}")
    print("   interruptions ≥ 7 j :", cov["interruptions"])
    s = cov["semaines"]
    print(
        "   semaines :",
        "2024-W01",
        s["2024-W01"],
        "| 2024-W06",
        s["2024-W06"],
        "| 2024-W11",
        s["2024-W11"],
    )
    names = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
    print(
        "   jours sans données / total :",
        {names[k]: f"{v[1]}/{v[0]}" for k, v in sorted(cov["par_jour_semaine"].items())},
    )
    days = {date(2024, 1, d) for d in range(2, 31)} | {date(2024, 3, d) for d in range(1, 20)}
    cov2 = coverage(days)
    print(
        "   mois vide dans la fenêtre :",
        cov2["mois"][(2024, 2)],
        "| interruptions :",
        cov2["interruptions"],
    )

    # ------------------------------------------------------------------ lecture de la spec
    from pathlib import Path

    spec = (Path(__file__).parent / "etape3_explorer_kpi.md").read_text(encoding="utf-8")

    def table_after(header_start: str) -> list[list[str]]:
        lines = spec.splitlines()
        i = next(k for k, ln in enumerate(lines) if ln.startswith(header_start))
        rows = []
        for ln in lines[i + 2 :]:
            if not ln.startswith("|"):
                break
            rows.append([c.strip().strip("*") for c in ln.strip("|").split("|")])
        return rows

    def num(s: str) -> D | None:
        s = s.replace("**", "").replace(" ", "").replace(",", ".").replace("−", "-")
        if s in ("—", ""):
            return None
        if s.endswith("%"):
            return D(s[:-1]) / 100
        return D(s)

    LABELS = {
        "Ventes brutes VB": "VB",
        "Retours R": "R",
        "CA produits net": "CAN",
        "CA net y c. ajustements (CANA)": "CANA",
        "Taux de retour": "TR",
        "Commandes C": "C",
        "Panier moyen": "PM",
        "Unités payantes": "UP",
        "Unités gratuites": "UG",
        "Prix moyen unitaire": "PU",
        "Factures sans vente payante": "factures_sans_vente",
        "Clients actifs": "clients",
        "VB clients identifiés": "VB_identifie",
        "VB non rattachées à un client": "VB_anonyme",
        "Lignes de vente sans identifiant": "lignes_vente_sans_client",
        "Part des ventes brutes non rattachées": "part_ventes_sans_client",
        "CA net après remises": "CA_net_apres_remises",
        "Facturation client indicative": "FCI",
    }
    checked = mism = 0
    for row in table_after("| KPI | S0 défaut"):
        key = LABELS.get(row[0])
        if key is None:
            continue
        for sc, cell in zip(cols, row[1:], strict=True):
            exp, got = num(cell), res[sc][key]
            checked += 1
            if exp is None or got is None:
                ok = exp is got
            else:
                places = len(cell.split(",")[1].rstrip(" %")) if "," in cell else 0
                q = D(got) * (100 if cell.strip().endswith("%") else 1)
                e = exp * (100 if cell.strip().endswith("%") else 1)
                ok = round(q, places) == e
            if not ok:
                mism += 1
                print("   ✗ spec", sc, key, cell, "recalcul", got)
    print(
        f"\n7) Lecture automatique de la table de l'annexe A dans le .md : {checked - mism}/{checked}"
    )

    combos_ok = 0
    combo_rows = table_after("| O1 | O2 | O3 | O4 |")
    for row in combo_rows:
        o = [c == "x" for c in row[:4]]
        k = kpis(
            ROWS,
            Rules(
                o1_include_duplicates=o[0],
                o2_show_cana=o[1],
                o3_incoherent_c_as_return=o[2],
                o4_r9_as_return=o[3],
            ),
        )
        exp = [num(c) for c in row[4:7]] + [row[7] == "✓", num(row[8])]
        got = [
            k["CAN"],
            k["CAN_registre"],
            k["pont"],
            k["chaque_ligne_une_fois"] and k["pont_ok"],
            k["CANA"],
        ]
        combos_ok += exp == got
    print(f"   Lecture automatique de la table des 16 combinaisons : {combos_ok}/{len(combo_rows)}")
