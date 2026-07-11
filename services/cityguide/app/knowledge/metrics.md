# Heat index

Heat index is the "feels-like" temperature in degrees Fahrenheit, combining air temperature and humidity (dewpoint). AusTwin computes it with the NOAA heat-index formula. It is the primary quantity CityForesight forecasts per tract.

# Heat-index risk bands

The National Weather Service bands are: 80 to 90F Caution, 90 to 103F Extreme Caution, 103 to 124F Danger, and 125F or above Extreme Danger. Higher bands mean higher risk of heat cramps, exhaustion, and stroke, especially for vulnerable populations.

# Impervious ratio

Impervious ratio is the fraction (0 to 1) of a census tract covered by surfaces water cannot pass through — roads, parking lots, rooftops. High impervious ratio traps heat and worsens the urban heat-island effect, so those tracts tend to run hotter and drain more slowly.

# Tree canopy cover

Tree canopy cover is the fraction (0 to 1) of a tract shaded by tree canopy. Canopy cools through shade and evapotranspiration, so higher canopy generally lowers local heat index. It is one of the morphology features injected into the forecasting model.

# Drainage capacity

Drainage capacity is a normalized (0 to 1) measure of how well a tract's drainage network can move stormwater. Low drainage capacity combined with high impervious ratio raises flood risk during heavy rain.

# Population density

Population density is residents per unit area in a tract, used as a vulnerability signal. Dense tracts concentrate heat exposure and shape where interventions like cooling centers have the most impact.

# Morphology features

"Morphology" refers to the physical land-cover features of a tract: impervious ratio, tree canopy cover, drainage capacity, and population density. These are the Knowledge-Infused Learning (KIL) features injected into CityForesight's model so forecasts reflect the built environment, not just weather.
