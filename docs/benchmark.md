---
hide:
  - navigation
---

# Source-Substitution Reanalysis Benchmark

The **AERIS Source-Substitution Reanalysis Benchmark** evaluates whether a research agent can independently reconstruct ambient air-pollution exposures from public sources, link them to public health-outcome records, and reproduce published epidemiological analyses without access to the original authors' pollution datasets.

- **Interactive Dataset & Agent Trajectories**: [huggingface.co/datasets/rlacombe/aeris](https://huggingface.co/datasets/rlacombe/aeris)
- **Executable Reanalysis Code & Manifests**: [`evals/` on GitHub](https://github.com/rlacombe/aeris/tree/main/evals)

---

## 1. Two-Route Study-Identification Pipeline (18,919 &rarr; 9 Studies)

We began with a frozen, deduplicated corpus of **18,919 PubMed and OpenAlex records** published between August 2020 and August 2026 and screened it through two complementary discovery routes:

- **Route 1 (Scientific Scope First)**: Screened titles and abstracts for ambient criteria pollutants ($\text{PM}_{2.5}$, $\text{PM}_{10}$, $\text{NO}_2$, $\text{O}_3$, $\text{SO}_2$, $\text{CO}$), wildfire smoke, or desert dust paired with human health outcomes and recoverable spatial/temporal keys, yielding **9 candidate studies**.
- **Route 2 (Public-Outcome Access First)**: Identified **203 articles** citing a named reusable public health-outcome system, audited their full text and data portals (finding 45 direct downloads and 47 public portals), and retained **13 unauthenticated ambient-exposure studies**.

The two routes shared one article, producing **21 unique candidate studies**. An agent feasibility audit confirmed **14 runnable candidates**, of which **9 produced fitted same-pollutant reanalyses** and **5 encountered documented public-data blockers**.

<div class="aeris-figure">
  <img src="../assets/study_pipeline_funnel.svg" alt="Study-Identification Funnel">
  <div class="aeris-figcaption">
    <strong>Figure 2 — Study-Selection Funnel.</strong> Two parallel screening routes across 18,919 PubMed and OpenAlex records converge on 21 unique candidates, 14 runnable studies, and 9 completed same-pollutant reanalyses.
  </div>
</div>

### Five Documented Execution Blockers

| Candidate Study | Target Geography & Window | Blocker Category | Observed Public-Source Limitation |
| :--- | :--- | :--- | :--- |
| **China COVID-19** (`33585383`) | 287 prefectures, 2014–2016 | Historical monitor coverage | OpenAQ v3 and S3 archive yielded only 2 usable prefecture panels for 2014–2016 vs. 287 in the published study. |
| **Israel COVID-19** (`34260961`) | Municipalities, 2017–2019 | Spatial variation collapse | Available public $\text{PM}_{2.5}$ monitors lacked spatial variation across municipalities for the study window. |
| **Argentina COVID-19** (`39689648`) | Provinces, 2020 | Monitor coverage density | Completed boundary retrieval did not return enough $\text{PM}_{2.5}$ station observations to fit the multi-province panel. |
| **Taubaté COVID Admissions** (`36197352`) | Municipality, 2020–2021 | Outcome export recovery | The required daily municipal SIH/SUS hospitalization export could not be recovered from the public portal. |
| **Alaska Wildfire Asthma** (`38249516`) | Regional health areas, 2015–2019 | Restricted outcome table | The regional emergency-department asthma outcome table is not available for unauthenticated public download. |

---

## 2. Contrast-Level Calibration Results (9 Studies, 14 Contrasts)

Across the nine completed reanalyses, AERIS processed **1,847,519 monitor observations** across **705 monitor-study associations** into **20,568 area-time exposure estimates**.

<div class="aeris-figure">
  <img src="../assets/effect_calibration.svg" alt="Effect Calibration Plot">
  <div class="aeris-figcaption">
    <strong>Figure 3 — Effect-Size Calibration.</strong> Published vs. AERIS-reconstructed odds ratios (OR) and rate ratios (RR) across 14 contrasts on log<sub>2</sub> axes (study-level Pearson <em>r</em> = 0.834, median |&Delta; log R| = 0.040, geometric mean ratio 0.998).
  </div>
</div>

| Study & Contrast | Published Setting | AERIS Setting | Published OR / RR (95% CI) | AERIS OR / RR (95% CI) | Replication Directory |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **France COVID-19**<br>RR / 1 &mu;g/m<sup>3</sup> $\text{PM}_{2.5}$ | 96 departments, 1999–2016 | 63 departments, 2019 | **1.24** (1.08–1.43) | **1.05** (0.95–1.15) | [`34488764-france-covid`](https://github.com/rlacombe/aeris/tree/main/evals/replications/34488764-france-covid) |
| **Italy COVID-19**<br>OR / doubling $\text{PM}_{10}$ days | 55 cities, 2018 | 8 cities, 2018 | **1.76**<sup>&ddagger;</sup> | **1.74** (1.13–2.69) | [`33398753-italy-cities`](https://github.com/rlacombe/aeris/tree/main/evals/replications/33398753-italy-cities) |
| **São José Admissions**<br>$\text{O}_3$ lag 2 RR / IQR<br>$\text{NO}_2$ lag 3 RR / IQR | SIH/SUS, 2020–2021 | SIVEP-Gripe, 89 days in 2021 | **1.061** (1.016–1.108)<br>**1.125** (1.050–1.205) | **1.003** (0.981–1.026)<br>**1.034** (0.876–1.220) | [`36383802-sao-jose-covid`](https://github.com/rlacombe/aeris/tree/main/evals/replications/36383802-sao-jose-covid) |
| **São Paulo AMI**<br>High-pollution RR | 39 municipalities, 2012–2015 | 39 municipalities, 193 days | **1.090** | **1.069** (1.006–1.135) | [`33227571-sao-paulo-ami`](https://github.com/rlacombe/aeris/tree/main/evals/replications/33227571-sao-paulo-ami) |
| **UK COVID-19**<br>OR / 10 &mu;g/m<sup>3</sup> $\text{PM}_{2.5}$ | 4 nations, 696 days | 4 nations, 635 nation-days | **1.13** (1.09–1.16) | **1.46** (1.21–1.76) | [`38182658-uk-covid`](https://github.com/rlacombe/aeris/tree/main/evals/replications/38182658-uk-covid) |
| **US Stroke Mortality**<br>RR / 10 &mu;g/m<sup>3</sup> $\text{PM}_{2.5}$<sup>&dagger;</sup> | US counties, 2016–2020 | 46 counties, 2019 | **1.132** | **1.111** (0.628–1.594) | [`39377000-us-stroke`](https://github.com/rlacombe/aeris/tree/main/evals/replications/39377000-us-stroke) |
| **Brazil Cancer Mortality**<br>OR / 10 &mu;g/m<sup>3</sup> $\text{PM}_{2.5}$ | Brazil, 2015–2019 | 5 states, 1,824 days; 929,790 deaths | **1.010** (1.00–1.02) | **1.060** (1.052–1.069) | [`38788590-brazil-cancer`](https://github.com/rlacombe/aeris/tree/main/evals/replications/38788590-brazil-cancer) |
| **Italy $\text{NO}_2$ COVID-19**<br>Incidence RR / 1 &mu;g/m<sup>3</sup><br>Mortality RR / 1 &mu;g/m<sup>3</sup> | 2 regions, Feb–May 2020 | 2 regions, 14 days | **1.00**<sup>*</sup><br>**1.00**<sup>*</sup> | **1.051** (1.042–1.060)<br>**0.988** (0.987–0.990) | [`34004167-northern-italy-covid`](https://github.com/rlacombe/aeris/tree/main/evals/replications/34004167-northern-italy-covid) |
| **OECD COVID-19**<br>Day 60 cases<br>Day 60 deaths<br>Day 80 cases<br>Day 80 deaths | 36 countries | 11 countries, 2017 | **1.020**<br>**1.030**<br>**1.020**<br>**1.009** | **0.998** (0.853–1.168)<br>**1.016** (0.806–1.279)<br>**0.971** (0.926–1.018)<br>**0.971** (0.873–1.079) | [`33484722-oecd-covid`](https://github.com/rlacombe/aeris/tree/main/evals/replications/33484722-oecd-covid) |

<small>
<sup>*</sup> The article reports a null effect rounded to two decimals.<br>
<sup>&dagger;</sup> Stroke ratios use the reported linear-model coefficient and mean outcome rate.<br>
<sup>&ddagger;</sup> For the published estimate, the article reports the underlying log-log coefficient without a confidence interval or <em>p</em>-value.
</small>

---

## 3. Autonomous & Harness Ablation Controls

To separate the contribution of the AERIS harness from researcher review, we executed three independent zero-intervention campaigns (`C1`, `C2`, `C3`; 27 study attempts) for **Self-Driving AERIS** and three matched campaigns (27 study attempts) for the **Raw Agent Control** without AERIS tools or instructions.

<div class="aeris-figure">
  <img src="../assets/autonomy_comparison.svg" alt="Autonomy and Harness Ablation Comparison">
  <div class="aeris-figcaption">
    <strong>Figure 4 — Autonomy &amp; Harness Ablation Comparison Across Campaigns.</strong> <strong>(a)</strong> Fitted studies completed per nine-study campaign across AERIS with researcher review (9/9), self-driving AERIS (7.7 &plusmn; 1.5; campaigns C1–C3: 8, 9, 6), and the raw-agent ablation without AERIS (2.3 &plusmn; 1.2; campaigns C1–C3: 3, 3, 1). <strong>(b)</strong> Pooled median study-level absolute log-effect error |&Delta; log R| among comparable fits (left) and study-level Pearson correlation <em>r</em> by campaign (right).
  </div>
</div>

---

## 4. Repository & Dataset Map

| Resource | Location | Contents |
| :--- | :--- | :--- |
| **Hugging Face Dataset** | [`huggingface.co/datasets/rlacombe/aeris`](https://huggingface.co/datasets/rlacombe/aeris) | Interactive Dataset Viewer for all 10 benchmark & screening tables (`18,919` records) + full clean-room agent trajectories. |
| **Scientist-Led Reanalyses** | [`evals/replications/`](https://github.com/rlacombe/aeris/tree/main/evals/replications) | Per-study executable retrieval, AERIS exposure, and statistical fitting code + `README.md` / `RESULT.md`. |
| **Self-Driving AERIS Controls** | [`evals/controls/self-driving/`](https://github.com/rlacombe/aeris/tree/main/evals/controls/self-driving) | Three zero-intervention autonomous campaigns (`r8404`, `r8406`, `r8407`), manifests, and non-interactive JSONL traces. |
| **Raw-Agent Ablation Controls** | [`evals/controls/raw-agents/`](https://github.com/rlacombe/aeris/tree/main/evals/controls/raw-agents) | Three matched raw-agent campaigns (`r1`, `r2`, `r3`) run without AERIS across all 9 studies (27 attempts). |
| **OpenAQ Attribution Audit** | [`evals/OPENAQ_ATTRIBUTION_MANIFEST.md`](https://github.com/rlacombe/aeris/blob/main/evals/OPENAQ_ATTRIBUTION_MANIFEST.md) | Upstream monitoring agency and license verification across all nine fitted studies. |
| **Researcher Intervention Ledger** | [`evals/RESEARCHER_INTERVENTION_LEDGER.md`](https://github.com/rlacombe/aeris/blob/main/evals/RESEARCHER_INTERVENTION_LEDGER.md) | Study-by-study accounting of human review and steering decisions in the interactive condition. |
