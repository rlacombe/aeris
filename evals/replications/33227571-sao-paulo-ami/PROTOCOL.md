# Protocol

## Question

Can public DATASUS admissions, AERIS ambient exposure reconstruction, and public weather data reproduce the published daily environmental-cluster analysis for acute myocardial-infarction admissions in metropolitan São Paulo?

## Primary reconstruction

1. Download the 48 public monthly SIH/SUS `RDSP` files for 2012-15.
2. Retain admissions with an admission date in the study window, principal diagnosis beginning `I21`, and residence in the 39-municipality São Paulo metropolitan region.
3. Create one daily count, including zero-admission days.
4. Build the union of the 39 public IBGE municipal polygons.
5. Request daily PM2.5, PM10, and NO2 boundary exposure records through AERIS for the full period.
6. Retrieve daily mean temperature, mean relative humidity, and precipitation from the public Open-Meteo archive at the boundary centroid.
7. Standardize the six daily environmental inputs, apply hierarchical clustering with three clusters, and compare daily admissions between clusters.

## Result scale

The article reports a cluster-level difference in daily admissions rather than a pollutant coefficient. The comparable result is the percentage increase in mean daily admissions for the high-pollution cluster relative to the lower-admission clusters.

## Predefined departures

The original paper used CETESB and BDMEP inputs. This reconstruction substitutes AERIS-generated ambient exposure records and the documented Open-Meteo archive. The cluster labels are derived anew from the reconstructed panel.
