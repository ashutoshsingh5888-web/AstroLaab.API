use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::sync::Arc;

use xalen_ephemeris::ayanamsa::Ayanamsa;
use xalen_ephemeris::ephem::{Almanac, Body, De440Provider, De440Reader};
use xalen_ephemeris::time::{DeltaTModel, JdUT1};

#[derive(Debug, Deserialize)]
struct InputCase {
    id: String,
    jd_ut: f64,
}

#[derive(Debug, Serialize)]
struct OutputCase {
    id: String,
    planets: std::collections::BTreeMap<String, f64>,
    ayanamsa: f64,
    delta_t_seconds: f64,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    let input = arg_value(&args, "--input")?;
    let output = arg_value(&args, "--output")?;
    let kernel = arg_value(&args, "--kernel")?;

    let cases: Vec<InputCase> = serde_json::from_str(&fs::read_to_string(&input)?)?;
    // Use a real JPL DE440 NAIF kernel supplied by CI for the strongest
    // independent ephemeris cross-check. The production Worker is not
    // modified by this reference harness.
    let reader = De440Reader::from_file(std::path::Path::new(&kernel))?;
    if reader.kernel_id() != Some("DE440") {
        return Err("supplied kernel did not identify as DE440".into());
    }
    let provider = De440Provider::with_reader(reader);
    let almanac = Almanac::default_vedic().with_provider(Arc::new(provider));
    let dt = DeltaTModel::StephensonMorrisonHohenkerk2016;

    let mut out = Vec::with_capacity(cases.len());

    for case in cases {
        let jd_ut = JdUT1(case.jd_ut);
        let jd_tt = jd_ut.to_tt(&dt).0;
        let delta_t_seconds = (jd_tt - jd_ut.0) * 86400.0;
        let ayanamsa = Ayanamsa::Lahiri.compute_deg(jd_tt);

        let mut planets = std::collections::BTreeMap::new();
        for (name, body) in [
            ("Sun", Body::Sun),
            ("Moon", Body::Moon),
            ("Mercury", Body::Mercury),
            ("Venus", Body::Venus),
            ("Mars", Body::Mars),
            ("Jupiter", Body::Jupiter),
            ("Saturn", Body::Saturn),
            ("Rahu", Body::MeanNode),
        ] {
            let pos = almanac.geocentric_ecliptic(body, jd_ut)?;
            let sid = (pos.longitude.to_degrees() - ayanamsa).rem_euclid(360.0);
            planets.insert(name.to_string(), sid);
        }

        let rahu = *planets.get("Rahu").ok_or("Rahu missing")?;
        planets.insert("Ketu".to_string(), (rahu + 180.0).rem_euclid(360.0));

        out.push(OutputCase { id: case.id, planets, ayanamsa, delta_t_seconds });
    }

    let path = PathBuf::from(output);
    fs::write(path, serde_json::to_string_pretty(&out)?)?;
    Ok(())
}

fn arg_value(args: &[String], key: &str) -> Result<String, Box<dyn std::error::Error>> {
    args.windows(2)
        .find(|pair| pair[0] == key)
        .map(|pair| pair[1].clone())
        .ok_or_else(|| format!("missing {key}").into())
}
