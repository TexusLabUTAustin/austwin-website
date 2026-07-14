# AusTwin overview

AusTwin is an open-source digital twin of Austin, Texas, extended with an intelligence layer of cooperating agents. It converts open climate and infrastructure data into real-time, actionable city decisions. The platform focuses on heat, flood, and grid stress across Austin census tracts.

# The four agents

AusTwin is a four-agent neurosymbolic copilot:
- UrbanSense — real-time anomaly detection (heat spikes, flood precursors, grid overload) with ontology-grounded explanations.
- CityForesight — 1 to 6 hour multi-hazard forecasting per census tract (heat, flood risk, grid stress), refreshed every 15 minutes.
- CityGuide — operator question-and-answer. Grounded, cited, and refuses to answer when it lacks evidence.
- CityCommand — a reinforcement-learning coordination agent that observes the other three and selects interventions (open cooling centers, pre-position resources).

# Data sources

Weather comes from the ASOS mesonet station KAUS (Austin-Bergstrom International Airport), fetched from the Iowa Environmental Mesonet, plus Open-Meteo precip. Geography uses US Census tracts for Travis County. Land cover comes from NLCD (National Land Cover Database). Flood context uses USGS NWIS instantaneous stream gauges around Austin. Grid context uses the public ERCOT supply-demand dashboard (system demand and capacity). The system also references event calendars and satellite imagery (MODIS/Landsat).

# What CityGuide can answer

CityGuide answers operator questions about: live heat, flood, and grid scores and which tracts rank highest; live ERCOT utilization and USGS gauge stages; active heat anomalies and alert counts; morphology metric definitions; how the forecasting and anomaly models work; and Austin heat-response protocols. It only answers from live system data and this knowledge base, and it declines questions outside that scope rather than guessing.
