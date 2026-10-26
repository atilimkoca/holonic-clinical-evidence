# §3.5 — Active Inference: Holon Temporal Evolution

- Holons evolved: **12** over 5 evidence steps each (seed 42).
- Total `holon:terminates` events (verdict flips): **7**.
- Surprise = KL(posterior || prior) per Bayesian update; spikes mark high-information (often contradicting) evidence.

| Holon | drug→disease | initial | final | flips |
|-------|--------------|---------|-------|-------|
| q_acute_kidney_injury_treatment | furosemide→acute_kidney_injury | 0.92 | 0.30 | 1 |
| q_addison_disease_efficacy | prednisone→addison_disease | 0.38 | 0.68 | 1 |
| q_alzheimer_disease_treatment | donepezil→alzheimer_disease | 0.53 | 0.84 | 0 |
| q_angina_pectoris_treatment | metoprolol→angina_pectoris | 0.93 | 0.46 | 1 |
| q_ankylosing_spondylitis_efficacy | adalimumab→ankylosing_spondylitis | 0.91 | 0.74 | 0 |
| q_ankylosing_spondylitis_treatment | adalimumab→ankylosing_spondylitis | 0.94 | 0.79 | 0 |
| q_aortic_stenosis_efficacy | furosemide→aortic_stenosis | 0.56 | 0.44 | 3 |
| q_asthma_efficacy | salbutamol→asthma | 0.93 | 0.74 | 0 |
| q_asthma_treatment | salbutamol→asthma | 0.88 | 0.88 | 0 |
| q_atrial_fibrillation_efficacy | apixaban→atrial_fibrillation | 0.92 | 0.37 | 1 |
| q_atrial_fibrillation_treatment | apixaban→atrial_fibrillation | 0.91 | 0.81 | 0 |
| q_bipolar_disorder_efficacy | lithium→bipolar_disorder | 0.97 | 0.90 | 0 |

A termination fires when new evidence moves the posterior mean across the 0.5 effective/ineffective boundary; the superseded assertion is closed with `holon:terminates` (see terminations.ttl).