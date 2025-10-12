# Mapalyst

A simple geospatial analysis tool with dedicated ML Backend running [Grounding Dino](https://huggingface.co/IDEA-Research/grounding-dino-base) to analyze objects from satellite imagery that we fetch from a hidden Google Maps API.

> [!WARNING] 
> The undocumented Google Maps API endpoint this project uses has changed in the meantime and doesn't allow anymore to get older satellite images sadly. Hence, the images shown in the tool, even if more than one, will be (most probably) the same ones. So please forgive us on that one, a proper satellite imagery source [is just really expensive](https://app.skyfi.com/tasking?s=DAY&r=VERY+HIGH&aoi=POLYGON+%28%28-97.71707461991977+30.28934572636869%2C+-97.71708649530422+30.244242480134297%2C+-97.76903510469577+30.244242480134297%2C+-97.76904698008022+30.28934572636869%2C+-97.71707461991977+30.28934572636869%29%29)

## Good Examples to use
-> Most other examples probably will have problems with the coordinates as the LLM will not have accurate data on that; Mistral's Conversation/Agent API sadly [errored out while developing this](https://github.com/mistralai/client-ts/issues/141), so adding a tool wasn't possible.

* JFK Airport - "Can you analyze the current amount and trend of airplanes at JFK Airport?"
* Chrysler Car Factory Detroit - "Please analyze the current trend and amount of cars at the GM Chrysler Factory"
* Amsterdam Airport Schiphol - "Analyze the amount of airplanes at Amsterdam Schiphol Airport"

## Setup



