from resolve import *
from geometry import *
from slippytiles import *
from utils import *
from dotenv import load_dotenv


checkDirectories()

mapbuilder = MapBuilder(mapname='krsultra', zoom=14, minelevation=0, maxelevation=750)
#mapbuilder.forcereprocesselevation = True
mapbuilder.filesources.addSource(GpxSource("F://Python//FUSIONMAP//GPX//KRSUltra60.gpx", animate=True, addwaypointsasmarkers=True))

mapbuilder.tilesources.setElevationSource(1) #
mapbuilder.tilesources.setImageSource(1) # 

# Add .env file and add an entry for you api-key if the source requires it
MAPTILER_API_KEY = os.getenv("MAPTILER_API_KEY")
mapbuilder.tilesources.ImageSources[2].apikey = MAPTILER_API_KEY
mapbuilder.tilesources.ElevationSources[1].apikey = MAPTILER_API_KEY

mapbuilder.addtilesarounddetailed = 1

mapbuilder.calculateTiles()
mapbuilder.fetchTiles()
mapbuilder.buildOutputTiles()

mapbuilder.processAndAddFileSources()

mapbuilder.buildFusionMap()


print("Done!")


