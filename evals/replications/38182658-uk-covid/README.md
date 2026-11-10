# UK COVID-19: post-optimization run

This is a fresh exposure reconstruction following AERIS retrieval changes in
commit `bcca784`. It does not modify or reinterpret the earlier baseline run.

The run requests OpenAQ server-side daily PM2.5 aggregates within each named UK
country boundary. `boundaries.geojson` is the pinned geoBoundaries release
artifact `9469f09` (2021 representation, CC-BY 4.0), downloaded from
`https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/GBR/ADM1/geoBoundaries-GBR-ADM1.geojson`.
Its SHA-256 is `22b69feadc23622a05d273479ab1915cace89355f6918157a1bc480cb80c3dcd`.
It uses the public UKHSA outcome artifact in
`../../data-acquisition/38182658-uk-covid/` only after panel completeness is
checked. It does not read the article's pollution data.
