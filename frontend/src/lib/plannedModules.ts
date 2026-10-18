import type { IconName } from '../components/Icon'

export interface PlannedModule {
  module: string
  title: string
  icon: IconName
  summary: string
  deliverables: string[]
  safeguards: string[]
}

export const PLANNED: Record<string, PlannedModule> = {
  explorer: {
    module: 'explorer_kpi',
    title: 'Explorer & KPI',
    icon: 'explore',
    summary: 'Statistiques descriptives, distributions, corrélations descriptives et KPI adaptés au schéma.',
    deliverables: [
      'KPI génériques + Retail (CA, unités, commandes, panier moyen) + Maintenance (taux de panne)',
      'Dénominateur, période et filtres affichés pour chaque KPI',
      'Tendances temporelles si une colonne date est confirmée',
    ],
    safeguards: ['Signalement explicite quand les données sont insuffisantes pour un KPI fiable'],
  },
  anomalies: {
    module: 'anomalies',
    title: "Détection d'anomalies",
    icon: 'anomaly',
    summary: 'Baselines robustes (médiane/MAD, IQR) et Isolation Forest, avec paramètres exposés.',
    deliverables: [
      "Score d'anomalie, niveau relatif et variables contributrices (descriptif)",
      'Precision, Recall, F1, PR-AUC uniquement si un label vérifié existe',
      'Seed et configuration enregistrés pour la reproductibilité',
    ],
    safeguards: [
      'Aucune observation qualifiée de « fraude » ou « panne certaine » sans label',
      "Sans label : exploration non supervisée, pas d'accuracy annoncée",
    ],
  },
  forecasting: {
    module: 'forecasting',
    title: 'Prévision',
    icon: 'forecast',
    summary: 'Split chronologique train/validation/test, baseline naïve vs modèle plus élaboré.',
    deliverables: ['MAE, RMSE, MASE ; horizon et intervalles affichés', 'Contrôle fréquence, doublons et trous temporels'],
    safeguards: ['Prévision refusée si l’historique est insuffisant, plutôt que fabriquée'],
  },
  'root-cause': {
    module: 'root_cause',
    title: 'Hypothèses de causes',
    icon: 'cause',
    summary: 'Facteurs associés à un événement, puis estimation causale seulement si identifiable.',
    deliverables: ['Traitement, résultat et covariables explicites', 'Graphe causal et test de robustesse (DoWhy) si applicable'],
    safeguards: ['SHAP et corrélations jamais présentés comme preuve causale', 'Sinon : liste d’hypothèses à vérifier'],
  },
  scenarios: {
    module: 'scenario_lab',
    title: 'Scenario Lab',
    icon: 'scenario',
    summary: 'Variables de décision, objectif, coûts, contraintes et hypothèses modifiables.',
    deliverables: ['Formules, unités et provenance des paramètres visibles', 'Comparaison de 3 stratégies de classement sur simulations synthétiques'],
    safeguards: ['Pas de simulation sur une variable non modélisée', 'Validation humaine obligatoire, aucune action automatique'],
  },
  report: {
    module: 'decision_report',
    title: 'Decision Report',
    icon: 'report',
    summary: 'Recommandations classées, preuves, incertitude et avertissements, exportables.',
    deliverables: ['Rapport HTML séparant faits, associations, prédictions et hypothèses', 'Explications LLM optionnelles à partir de résultats déjà calculés'],
    safeguards: ['Chaque recommandation traçable à un calcul ou une règle', 'Mode déterministe disponible sans clé API'],
  },
}
