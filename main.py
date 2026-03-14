from resolve import *
from geometry import *
from slippytiles import *
from utils import *
from dotenv import load_dotenv


gpxdirectory, imagedirectory, downloaddirectory = checkDirectories()

mapbuilder = MapBuilder(mapname='krsultra', zoom=15, minelevation=0, maxelevation=750)
#mapbuilder.forcereprocesselevation = True
gpxfile = os.path.join(gpxdirectory, 'KRSUltra60.gpx')
mapbuilder.filesources.addSource(GpxSource(gpxfile, animate=True, addwaypointsasmarkers=True))

mapbuilder.tilesources.setElevationSource(1) #
mapbuilder.tilesources.setImageSource(2) # 

# Add .env file and add an entry for you api-key if the source requires it
MAPTILER_API_KEY = os.getenv("MAPTILER_API_KEY")
mapbuilder.tilesources.ImageSources[2].apikey = MAPTILER_API_KEY
mapbuilder.tilesources.ElevationSources[1].apikey = MAPTILER_API_KEY

mapbuilder.addtilesarounddetailed = 2

mapbuilder.calculateTiles()
mapbuilder.fetchTiles()
mapbuilder.buildOutputTiles()

mapbuilder.processAndAddFileSources()

mapbuilder.buildFusionMap(startanimation=300, endanimation=100)


print("Done!")


