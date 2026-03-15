from resolve import *
from geometry import *
from slippytiles import *
from utils import *
from dotenv import load_dotenv


# Add .env file and add an entry for you api-key if the source requires it
MAPTILER_API_KEY = os.getenv("MAPTILER_API_KEY")
gpxdirectory, imagedirectory, downloaddirectory = checkDirectories()


###### Change to your prefences #########

mapbuilder = MapBuilder(mapname='krsultra', zoom=15, minelevation=0, maxelevation=750, margin_around_geometry_sources=1000)
gpxfile = os.path.join(gpxdirectory, 'KRSUltra60.gpx')
mapbuilder.filesources.addSource(GpxSource(gpxfile, animate=True, addwaypointsasmarkers=True))
mapbuilder.tilesources.setElevationSource(1) # See slippytiles for options
mapbuilder.tilesources.setImageSource(2) # See slippytiles for options
mapbuilder.addtilesarounddetailed = 2 # How many extra non-detailed tiles to add around the detailed area?

#########################################

mapbuilder.tilesources.ImageSources[2].apikey = MAPTILER_API_KEY
mapbuilder.tilesources.ElevationSources[1].apikey = MAPTILER_API_KEY

mapbuilder.calculateTiles()
mapbuilder.fetchTiles()
mapbuilder.buildOutputTiles()

mapbuilder.processAndAddFileSources()

mapbuilder.buildFusionMap(startanimation=300, endanimation=100)


print("Done!")


