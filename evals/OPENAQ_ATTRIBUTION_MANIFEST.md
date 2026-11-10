# Air-quality provider and license audit

This manifest covers the nine fitted, scientist-led reanalyses. It distinguishes
the organization that produced or published the observations from OpenAQ, which
distributed many of them through its API or public S3 archive. We identified
providers only from preserved station IDs, traces, and source manifests. We did
not assign providers from study geography.

We checked OpenAQ location metadata and the `/v3/licenses` endpoint on
2026-09-26. `UNVERIFIED` means that the preserved record or current OpenAQ
metadata did not establish an exact license. It does not mean that reuse is
prohibited.

| Study | Original monitoring provider | Dataset or source used | OpenAQ route | License | Verification URL |
|---|---|---|---|---|---|
| France COVID-19 (PMID 34488764) | **UNVERIFIED.** The aggregate department output did not retain contributing location or provider IDs. | 2019 PM2.5 department monitor means | OpenAQ v3 daily records, with historical S3 fallback | **UNVERIFIED:** station-specific provider and license cannot be recovered from the preserved output. | [OpenAQ locations](https://docs.openaq.org/resources/locations) |
| Italian cities COVID-19 (PMID 33398753) | Arpae Emilia-Romagna, EEA, and ARPA Lazio. Preserved OpenAQ location IDs: Arpae 7631, 7626, 7623, 7604, 7498, 7608, 7611, 7601, 7622; EEA 7599, 7236, 7527; ARPA Lazio 7539, 7541. | 2018 daily PM10 from 14 unique assigned locations | OpenAQ v3 and historical S3 | Arpae: **CC BY 4.0**, verified against its air-monitoring dataset. EEA: **ODC-BY 1.0**, OpenAQ license 10. ARPA Lazio: **UNVERIFIED**; the location records return `licenses: null`. | [Arpae dataset](https://dati.arpae.it/eu/dataset/arpa_aria_qualita_retemon_qualita_17_09); [OpenAQ license 10](https://api.openaq.org/v3/licenses/10); [provider 151](https://api.openaq.org/v3/providers/151) |
| Sao Jose admissions (PMID 36383802) | Sao Paulo CETESB, verified from OpenAQ location 5220 (Jacarei) | 2020--2021 PM10, NO2, and O3 from the Jacarei regulatory station | OpenAQ v3 and historical S3 | **UNVERIFIED:** OpenAQ location 5220 returns `licenses: null`, and no explicit license was found on the CETESB historical-data pages. | [OpenAQ location 5220](https://api.openaq.org/v3/locations/5220); [CETESB air data](https://sistemasinter.cetesb.sp.gov.br/Ar/php/mapa_qualidade_interior.php) |
| Sao Paulo AMI (PMID 33227571) | CETESB | CETESB historical daily record selected after the OpenAQ request returned no usable 2012--2015 observations | OpenAQ v3/S3 for discovery and coverage audit; fitted observations came from CETESB directly | **UNVERIFIED:** no explicit data license was found on the CETESB historical-data interface. | [CETESB historical interface](https://sistemasinter.cetesb.sp.gov.br/Ar/php/ar_dados_horarios_resultado.php) |
| UK COVID-19 (PMID 38182658) | **UNVERIFIED.** The aggregate nation-day output did not retain contributing OpenAQ location or provider IDs. | 2020 daily PM2.5 within four UK nation polygons | OpenAQ v3 boundary aggregation and historical S3 | **UNVERIFIED:** the preserved output cannot establish which provider-specific OpenAQ licenses apply. | [OpenAQ locations](https://docs.openaq.org/resources/locations) |
| US stroke mortality (PMID 39377000) | AirNow, OpenAQ provider 119. All preserved assigned location IDs resolve to AirNow. | 2019 daily PM2.5; 51 assigned locations, of which 47 met the analysis coverage rule | OpenAQ v3 daily records | **US Public Domain**, OpenAQ license 33, effective for these records from 2016-01-30. | [OpenAQ provider 119](https://api.openaq.org/v3/providers/119); [OpenAQ license 33](https://api.openaq.org/v3/licenses/33) |
| Brazil cancer mortality (PMID 38788590) | IEMA distributed standardized archives from state monitoring networks. The retained manifest does not identify the original agency for each observation. | 2015--2019 PM2.5 archives for CE, ES, MG, RJ, and SP | OpenAQ v3/S3 coverage audit; fitted observations came from IEMA archives | **UNVERIFIED:** IEMA invites users to download and work with the data, but the retained files and public landing page do not state an exact license for each underlying network. | [IEMA air-quality platform](https://energiaeambiente.org.br/qualidadedoar/) |
| Northern Italy COVID-19 (PMID 34004167) | EEA, identified in the preserved source record; contributing OpenAQ location IDs were not retained | May 2020 daily NO2 for Lombardia and Veneto | OpenAQ v3 and historical S3 | **ODC-BY 1.0**, OpenAQ license 10, at provider level. **PARTIAL:** station-specific license records cannot be rechecked without the omitted location IDs. | [OpenAQ provider 70](https://api.openaq.org/v3/providers/70); [OpenAQ license 10](https://api.openaq.org/v3/licenses/10) |
| OECD COVID-19 (PMID 33484722) | **UNVERIFIED.** The country-level output retained station counts but not all contributing location and provider IDs. | 2017 PM2.5 monitor means for countries with adequate coverage | OpenAQ v3 country-boundary aggregation and historical S3 | **UNVERIFIED:** the multi-country record may combine provider-specific licenses, which cannot be assigned exactly from the retained aggregate. | [OpenAQ locations](https://docs.openaq.org/resources/locations); [OpenAQ licenses](https://api.openaq.org/v3/licenses) |

## License records used

- **ODC-BY 1.0:** attribution required; commercial use, modification, and
  redistribution allowed.
  <https://opendatacommons.org/licenses/by/odc_by_1.0_public_text.txt>
- **US Public Domain:** OpenAQ marks attribution as unnecessary and commercial
  use, modification, and redistribution as allowed.
  <http://www.usa.gov/publicdomain/label/1.0/>
- **CC BY 4.0:** attribution required; sharing and adaptation allowed.
  <https://creativecommons.org/licenses/by/4.0/>

The corresponding machine-readable table is
`OPENAQ_ATTRIBUTION_MANIFEST.csv`.
