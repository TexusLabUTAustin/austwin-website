# AusTwin overview

AusTwin is an open-source digital twin of Austin, Texas, extended with an intelligence layer of cooperating agents. It converts open climate and infrastructure data into real-time, actionable city decisions. The platform focuses on heat, flood, and grid stress across Austin census tracts.

# The four agents

AusTwin is a four-agent neurosymbolic copilot:
- UrbanSense — real-time anomaly detection (heat spikes, flood precursors, grid overload) with ontology-grounded explanations.
- CityForesight — 1 to 6 hour heat-index forecasting per census tract, refreshed every 15 minutes.
- CityGuide — operator question-and-answer. Grounded, cited, and refuses to answer when it lacks evidence.
- CityCommand — a reinforcement-learning coordination agent that observes the other three and selects interventions (open cooling centers, pre-position resources).

# Data sources

Weather comes from the ASOS mesonet station KAUS (Austin-Bergstrom International Airport), fetched from the Iowa Environmental Mesonet. Geography uses US Census tracts for Travis County. Land cover comes from NLCD (National Land Cover Database). The system also references ERCOT grid load, event calendars, and satellite imagery (MODIS/Landsat).

# What CityGuide can answer

CityGuide answers operator questions about: current heat-index forecasts and which tracts are hottest, active heat anomalies and alert counts, the meaning of morphology metrics, how the forecasting and anomaly models work, and Austin heat-response protocols. It only answers from live system data and this knowledge base, and it declines questions outside that scope rather than guessing.
