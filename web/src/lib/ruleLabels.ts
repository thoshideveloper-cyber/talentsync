/**
 * Single source of truth for turning machine rule IDs (e.g. "filter.gender_preference")
 * into human-readable labels for recruiters. Used by the compliance panel, the dashboard
 * "top triggered rules" list, and bulk-audit views — so the UI never shows raw IDs.
 */

export const TIER_LABEL: Record<string, string> = {
  high_risk: 'High-Risk Filter',
  advisory: 'Advisory',
}

const RULE_LABEL: Record<string, string> = {
  'filter.age_cap': 'Age cap / age range',
  'filter.gender_preference': 'Gender preference',
  'filter.marital_status': 'Marital status filter',
  'filter.community_caste': 'Caste / community / category',
  'filter.disability_exclusion': 'Disability exclusion',
  'filter.maternity_status': 'Pregnancy / maternity filter',
  'filter.freshers_only': 'Freshers-only restriction',
  'pay.disclosure_absent': 'No pay disclosed',
  'quality.leveling_mismatch': 'Seniority leveling mismatch',
  'quality.unverified_seniority': 'Unverified seniority',
  'language.inclusive': 'Non-inclusive language',
}

/** Human-readable label for a rule ID, including dynamic language.inclusive.<term> sub-rules. */
export function ruleLabel(ruleId: string): string {
  if (ruleId in RULE_LABEL) return RULE_LABEL[ruleId]
  if (ruleId.startsWith('language.inclusive.')) {
    const term = ruleId.replace('language.inclusive.', '').replace(/_/g, ' ')
    return `Non-inclusive term: "${term}"`
  }
  return ruleId
}
