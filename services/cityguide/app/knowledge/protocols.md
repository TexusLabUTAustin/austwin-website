# Heat response protocol

When forecast heat index enters the Danger band (103F or above) for populated tracts, operators should consider opening cooling centers, prioritizing high population-density and low tree-canopy tracts. Extreme Danger (125F or above) warrants escalation: extend cooling-center hours, issue public alerts, and coordinate wellness checks for vulnerable residents. These are decision-support guidelines, not automatic actions.

# Cooling centers

Cooling centers are air-conditioned public sites (libraries, recreation centers) opened during extreme heat. Placement should target tracts that are both hot (high forecast heat index or anomaly severity) and vulnerable (high population density, low canopy). CityCommand can recommend which tracts to prioritize based on forecast and anomaly outputs.

# Anomaly severity response

Severity levels map to operator posture: watch means monitor and prepare; alert means pre-position resources and notify the relevant division; extreme means activate response (cooling centers, escalation). Every recommended action is meant to be auditable and reversible, logged with a timestamp and the agent state that informed it.

# Flood and grid context

Beyond heat, AusTwin tracks live flood risk (USGS gauges + recent precip, modulated by impervious/drainage) and grid stress (ERCOT demand/capacity plus heat and density). During compound events — heat plus grid strain — cooling-center siting must account for power availability. Rising stream stress with heavy rain warrants monitoring low-drainage, high-impervious tracts even when heat is moderate.
