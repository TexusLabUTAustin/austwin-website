# CityForesight forecasting model

CityForesight produces 1 to 6 hour ahead scores for every Austin census tract across three hazards: heat index (Fahrenheit), flood risk (0-100), and grid stress (0-100). Heat uses a two-layer LSTM with Knowledge-Infused Learning (KIL): morphology features (impervious ratio, tree canopy, drainage capacity, population density) are injected at the dense layer so predictions reflect each tract's built environment. Input is a 24-hour lookback window of KAUS weather. The phase gate is at least 15% RMSE improvement over a plain LSTM on held-out Austin data.

# Flood and grid live scores

Flood risk is not a FEMA floodplain map. It is built from live USGS stream gage height and discharge near each tract, recent Open-Meteo rainfall, and a mild NLCD runoff modulator (impervious and drainage). Grid stress is built from live ERCOT system demand versus capacity (utilization), then raised where heat index and population density are higher. It is not an outage map. Both scores refresh with the forecast cache.

# Forecast horizons and refresh

Forecasts cover horizons +1h through +6h. A background scheduler re-runs inference every 15 minutes against the latest observations, and the API serves the most recent cached run with a last_updated timestamp. If the trained heat model is unavailable, a heuristic fallback estimates tract heat index from current conditions and morphology; flood and grid still use live USGS/ERCOT/precip inputs when available.

# UrbanSense anomaly model

UrbanSense flags tracts whose forecast heat index is anomalous relative to the city and their own history. It combines spatial, temporal, and morphology factors into an anomaly score and assigns a severity: normal, watch, alert, or extreme. Detections are explained against an urban-climate ontology (CityGML / SOSA / SSN) so each alert names its triggering factors. It reads forecasts from CityForesight and refreshes on the same 15-minute cadence.

# CityGuide (this assistant)

CityGuide answers operator questions using retrieval-augmented generation. It retrieves from this knowledge base with neural embeddings (sentence-transformers cosine similarity) fused with symbolic Jaccard token overlap, and pulls live snapshots from the CityForesight and UrbanSense APIs when a question needs current data. A local open-source LLM (run via llama.cpp, no external API) writes the answer strictly from that grounded context. If retrieval falls below a confidence threshold and no live data applies, CityGuide refuses rather than hallucinate.
