from concurrent.futures import ThreadPoolExecutor
import math
import os
import concurrent
import cv2
import numpy as np
import mercantile
import requests
import geometry
#from resolve import *
from geometry import *
from slippytiles import *
from resolve import FusionMap


class Tile:
    def __init__(self):
        pass

class BigTile:
    def __init__(self, row, col, x, y, z, detailed = False):
        self.DetailedImageTiles = []
        self.DetailedElevationTiles = []
        self.row = row
        self.col = col
        self.x = x
        self.y = y
        self.z = z
        self.detailed = detailed
        self.status = 0
        self.outputstatus = 0
        self.elevationsource = ''
        self.imagesource = ''
        self.finishedelevationtile = ''
        self.finishedimagetile = ''
        self.finishedelevationdetailedtile = ''
        self.finishedimagedetailedtile = ''
    
    def getSize(self):

        img = cv2.imread(self.finishedimagedetailedtile)
        height, width, channels = img.shape
        return height


class DetailedTile:
    def __init__(self, row, col, x, y, z):
        self.row = row
        self.col = col
        self.x = x
        self.y = y
        self.z = z
        self.status = 0
        self.elevationsource = ''
        self.imagesource = ''


class MapBuilder:
    def __init__(self, mapname, zoom=10, minelevation=0, maxelevation=9000, margin_around_geometry_sources=1000, toplefttilex=-1, toplefttiley=-1):
        self.mapname = mapname
        self.zoom = zoom
        self.overviewzoom = 0
        self.margin_around_geometry_sources = margin_around_geometry_sources # meters
        self.minelevation = minelevation
        self.maxelevation = maxelevation
        self.toplefttilex = toplefttilex
        self.toplefttiley = toplefttiley
        self.filesources = geometry.GeometrySources()
        self.tilesources = TileSources()
        self.image_directory = os.path.join(os.path.dirname(__file__) , 'images')
        self.download_directory = os.path.join(self.image_directory, "download")
        self.addtilesarounddetailed = 0
        self.tiles = []
        self._maxtilesperimage = 0
        self.maxpixelwidthpertile = 4096
        self.scalefactor = 1
        self.forcereprocesselevation = False
        self.exagerateelevation = 1.2
        self.waypointtoroutemargin = 1 #In kilometers

    def getTileInformationForRelativeCalculations(self):

        tiles_with_details = list(filter(lambda item: item.detailed == True, self.tiles))
        first_tile = min(tiles_with_details, key=lambda tile: (tile.x, tile.y))
        first_child_tile = min(first_tile.DetailedImageTiles, key=lambda tile: (tile.x, tile.y))

        return first_tile.row, first_tile.col, first_child_tile.x, first_child_tile.y, first_child_tile.z

    def getMapDimesions(self):
        cols = max(self.tiles, key=lambda x: x.col).col+1
        rows = max(self.tiles, key=lambda x: x.row).row+1
        return rows, cols

    def calculateTiles(self):
    
        # lat1, lon1, lat2, lon2, zoom, tile_size, overview_tile_buffer

        #overview_zoom = self.zoom - int(math.log2(self.maxtilesperimage))
        
        maxlat, minlon, minlat, maxlon = self.filesources.getBounds()
        
        lat1, lon1 = translate_latlong(maxlat, minlon, self.margin_around_geometry_sources, -self.margin_around_geometry_sources)
        lat2, lon2 = translate_latlong(minlat, maxlon, -self.margin_around_geometry_sources, self.margin_around_geometry_sources)

        maxtilesperimage = self.maxpixelwidthpertile / max(self.tilesources.selectedElevationSource().tilesize, self.tilesources.selectedImageSource().tilesize) 

        overview_zoom = self.zoom - int(math.log2(maxtilesperimage))

        # Make initial map square
        tilesize_in_meters = deg2actualsize(lat1, lon1, overview_zoom)

        tiles_in_height, tiles_in_width = count_tiles(lat1, lon1, lat2, lon2, overview_zoom, self.tilesources.selectedElevationSource().tilesize)

        tl_tilex, tl_tiley = deg2num(lat1, lon1, overview_zoom)
        br_tilex, br_tiley = deg2num(lat2, lon2, overview_zoom)
        xtra_br_tilex = br_tilex
        xtra_br_tiley = br_tiley
        xtra_tl_tilex = tl_tilex
        xtra_tl_tiley = tl_tiley


        if tiles_in_height > tiles_in_width: # Need more tiles in width
            extra_tiles = tiles_in_height - tiles_in_width
            xtra_tl_tiley = tl_tiley - math.ceil(extra_tiles / 2)
            xtra_br_tiley = br_tiley + math.floor(extra_tiles / 2)

            print(f'Tiles not square - missing tiles in width. Adding {extra_tiles}')
    

        if tiles_in_width > tiles_in_height:
            extra_tiles = tiles_in_width - tiles_in_height
            xtra_tl_tilex = tl_tilex + math.ceil(extra_tiles / 2)
            xtra_br_tilex = br_tilex - math.floor(extra_tiles / 2)

            print(f'Tiles not square - missing tiles in height. Adding {extra_tiles} tiles')

        # LATITUDE -> HEIGHT -> ROWS
        # LONGITUDE -> WIDTH -> COLS

        if self.addtilesarounddetailed > 0:
            xtra_tl_tilex -= self.addtilesarounddetailed
            xtra_tl_tiley -= self.addtilesarounddetailed
            xtra_br_tilex += self.addtilesarounddetailed
            xtra_br_tiley += self.addtilesarounddetailed


        x_index = 0
        y_index = 0

        print("Building tile matrix...")

        no_off_tiles = (xtra_br_tilex - xtra_tl_tilex + 1) * (xtra_br_tiley - xtra_tl_tiley + 1)

        print(f'There are {no_off_tiles} big tiles...')
        no_off_detailedimagetiles = 0
        no_off_detailedelevationtiles = 0

        for x in range (xtra_tl_tilex, xtra_br_tilex + 1):
            for y in range(xtra_tl_tiley, xtra_br_tiley + 1):

                detailed = False
                # Is this a overview or detailed tile?
                if (x >= tl_tilex and x <= br_tilex) and (y >= tl_tiley and y <= br_tiley): 
                    detailed = True

                new_tile = BigTile(x_index, y_index, x, y, overview_zoom, detailed)

                if detailed:
                    new_tile.DetailedImageTiles = sorted(get_all_children(x, y, overview_zoom, self.tilesources.selectedImageSource().maxzoom), key=lambda tile: (tile.x, tile.y))
                    new_tile.DetailedElevationTiles = sorted(get_all_children(x, y, overview_zoom, self.tilesources.selectedElevationSource().maxzoom), key=lambda tile: (tile.x, tile.y))
                    no_off_detailedimagetiles += len(new_tile.DetailedImageTiles)
                    no_off_detailedelevationtiles += len(new_tile.DetailedElevationTiles)


                self.tiles.append(new_tile)
                y_index += 1
            y_index = 0
            x_index += 1

        print(f'There are {no_off_detailedimagetiles} detailed image tiles and {no_off_detailedelevationtiles} detailed elevation tiles...')
        self._maxtilesperimage = maxtilesperimage

    def fetchTiles(self):
   
        print(f'Finding or downloading tiles...')

        for tile in self.tiles:
            elevation_tile = os.path.join(self.download_directory, f'elevation_{self.tilesources.selectedElevationSource().prefix}_{tile.x}_{tile.y}.png')
            tile.elevationsource = elevation_tile
            if os.path.isfile(elevation_tile):
                #Found
                tile.status = 1             
                print(f'{elevation_tile} found...')
            else:
                tile.status = downloadTile(self.tilesources.selectedElevationSource().getFormattedUrl(tile.x, tile.y, tile.z), elevation_tile)
                print(f'{elevation_tile} downloaded...')

            image_tile = os.path.join(self.download_directory, f'image_{self.tilesources.selectedImageSource().prefix}_{tile.x}_{tile.y}.png')
            tile.imagesource = image_tile
            if os.path.isfile(image_tile):
                #Found
                tile.status = 1        
                print(f'{image_tile} found...')
            else:
                tile.status = downloadTile(self.tilesources.selectedImageSource().getFormattedUrl(tile.x, tile.y, tile.z), image_tile)
                print(f'{image_tile} downloaded...')

            if tile.detailed == True:
                for detailed_tile in tile.DetailedElevationTiles:
                    elevation_tile = os.path.join(self.download_directory, f'elevation_{self.tilesources.selectedElevationSource().prefix}_{detailed_tile.x}_{detailed_tile.y}.png')
                    detailed_tile.elevationsource = elevation_tile
                    if os.path.isfile(elevation_tile):
                        detailed_tile.status = 1
                        #Found
                        print(f'{elevation_tile} found...')
                    else:
                        detailed_tile.status = downloadTile(self.tilesources.selectedElevationSource().getFormattedUrl(detailed_tile.x, detailed_tile.y, detailed_tile.z), elevation_tile)
                        print(f'{elevation_tile} downloaded...')
                for detailed_tile in tile.DetailedImageTiles:
                    image_tile = os.path.join(self.download_directory, f'image_{self.tilesources.selectedImageSource().prefix}_{detailed_tile.x}_{detailed_tile.y}.png')
                    detailed_tile.imagesource = image_tile
                    if os.path.isfile(image_tile):
                        #Found
                        detailed_tile.status = 1
                        print(f'{image_tile} found...')
                    else:
                        detailed_tile.status = downloadTile(self.tilesources.selectedImageSource().getFormattedUrl(detailed_tile.x, detailed_tile.y, detailed_tile.z), image_tile)
                        print(f'{image_tile} downloaded...')
                        
    def buildOutputTiles(self):

        elevation_output_temp_tile = 0
        image_output_temp_tile = 0
        
        self.tilesources.minelevation = self.minelevation
        self.tilesources.maxelevation = self.maxelevation
        
        imagesource = self.tilesources.selectedImageSource()
        elevationsource = self.tilesources.selectedElevationSource()
        
        for tile in self.tiles:

            print(f'Generating overview tile {tile.row} - {tile.col}')
            elevation_output_temp_tile = np.zeros((elevationsource.tilesize, elevationsource.tilesize), np.uint16)
            image_output_temp_tile = np.zeros((imagesource.tilesize , imagesource.tilesize , 3), np.uint8)

            elevation_output_tile = os.path.join(self.image_directory, f'{self.mapname}_elevation_{elevationsource.prefix}_zoom{tile.z}_{tile.x}_{tile.y}_overview.png')
            image_output_tile = os.path.join(self.image_directory, f'{self.mapname}_image_{imagesource.prefix}_zoom{tile.z}_{tile.x}_{tile.y}_overview.png')

            if os.path.isfile(elevation_output_tile) and self.forcereprocesselevation == False:
                print(f'Elevationtile {tile.row} - {tile.col} found...')
                tile.outputstatus += 1
                tile.finishedelevationtile = elevation_output_tile
            else:
                tz = self.tilesources.selectedElevationSource().tilesize
                elevation_output_temp_tile[0:tz,0:tz], dummy1, dummy2 = makeGrayscale(cv2.imread(tile.elevationsource), self.tilesources, 0, 0)
                cv2.imwrite(elevation_output_tile, elevation_output_temp_tile)
                print("")
                print(f'Saving finished overview elevation tile as {elevation_output_tile}')
                tile.outputstatus += 1
                tile.finishedelevationtile = elevation_output_tile

            if os.path.isfile(image_output_tile):
                print(f'Imagetile {tile.row} - {tile.col} found...')
                tile.outputstatus += 1
                tile.finishedimagetile = image_output_tile
            else:
                tz = self.tilesources.selectedImageSource().tilesize
                image_output_temp_tile[0:tz,0:tz] = cv2.imread(tile.imagesource)
                cv2.imwrite(image_output_tile, image_output_temp_tile)
                print("")
                print(f'Saving finished image overview tile as {image_output_tile}')
                tile.outputstatus += 1
                tile.finishedimagetile = image_output_tile


            if tile.detailed:

                elevation_output_tile = os.path.join(self.image_directory, f'{self.mapname}_elevation_{elevationsource.prefix}_zoom{tile.z}_{tile.x}_{tile.y}_detailed.png')
                image_output_tile = os.path.join(self.image_directory, f'{self.mapname}_image_{imagesource.prefix}_zoom{tile.z}_{tile.x}_{tile.y}_detailed.png')
                
                print(f'Generating detailed tile {tile.row} - {tile.col}')
                no_detailed_elevation_tiles = int(math.sqrt(len(tile.DetailedElevationTiles)))
                no_detailed_image_tiles = int(math.sqrt(len(tile.DetailedImageTiles)))
                elevation_tile_size = no_detailed_elevation_tiles * elevationsource.tilesize
                image_tile_size = no_detailed_image_tiles * imagesource.tilesize 
                elevation_output_temp_tile = np.zeros((elevation_tile_size, elevation_tile_size), np.uint16)
                image_output_temp_tile = np.zeros((image_tile_size, image_tile_size, 3), np.uint8)
           
            
                if os.path.isfile(elevation_output_tile) and self.forcereprocesselevation == False:
                    print(f'Detailed elevationtile for {tile.row} - {tile.col} found...')
                    tile.outputstatus += 1
                    tile.finishedelevationdetailedtile = elevation_output_tile
                else:                  
                    row_min = min(tile.DetailedElevationTiles, key=lambda x: x.x)
                    col_min = min(tile.DetailedElevationTiles, key=lambda x: x.y)
                    no_detailed_tiles = len(tile.DetailedElevationTiles)
                    tiles_per_side = int(math.sqrt(no_detailed_tiles))
                    print(f'Stitching {no_detailed_tiles} greyscale tiles... ({tiles_per_side}*{tiles_per_side})')
                    tz = self.tilesources.selectedElevationSource().tilesize

                    current_tile = 0
                    completed_tiles = 0

                    futures = []
                    results = []

                    with ThreadPoolExecutor(max_workers=6) as executor:
                        for detailed_tile in tile.DetailedElevationTiles:
                            print(f'\rProcessing grayscale values - Started {current_tile} of {no_detailed_tiles} - {completed_tiles} completed', end='', flush=True)
                            row = detailed_tile.x - row_min.x
                            col = detailed_tile.y - col_min.y

                            row_pos = row * tz
                            col_pos = col * tz

                            future = executor.submit(makeGrayscale, cv2.imread(detailed_tile.elevationsource), self.tilesources, row_pos, col_pos)
                            futures.append(future)
                            #grey_source = makeGrayscale(cv2.imread(detailed_tile.elevationsource), tilesources)
                            current_tile += 1

                        for future in concurrent.futures.as_completed(futures):
                            completed_tiles += 1
                            print(f'\rProcessing grayscale values - Started {current_tile} of {no_detailed_tiles} - {completed_tiles} completed', end='', flush=True)
                            grey_source, row_pos, col_pos = future.result()
                            elevation_output_temp_tile[col_pos:(col_pos)+tz, row_pos:(row_pos)+tz] = grey_source
            
                    cv2.imwrite(elevation_output_tile, elevation_output_temp_tile)
                    print("")
                    print(f'Saving finished tile as {elevation_output_tile}')
                    tile.outputstatus += 1
                    tile.finishedelevationdetailedtile = elevation_output_tile

                if os.path.isfile(image_output_tile):
                    print(f'Detailed imagetile {tile.row} - {tile.col} found...')
                    tile.outputstatus += 1
                    tile.finishedimagedetailedtile = image_output_tile
                else:

                    row_min = min(tile.DetailedImageTiles, key=lambda x: x.x)
                    col_min = min(tile.DetailedImageTiles, key=lambda x: x.y)
                    no_detailed_tiles = len(tile.DetailedImageTiles)
                    tiles_per_side = int(math.sqrt(no_detailed_tiles))
                    print(f'Stitching {no_detailed_tiles} image tiles... ({tiles_per_side}*{tiles_per_side})')
                    tz = self.tilesources.selectedImageSource().tilesize

                    current_tile = 1
                    completed_tiles = 0
                    
                    for detailed_tile in tile.DetailedImageTiles:
                        print(f'\rProcessing images - {completed_tiles} completed', end='', flush=True)
                        row = detailed_tile.x - row_min.x
                        col = detailed_tile.y - col_min.y

                        row_pos = row * tz
                        col_pos = col * tz

                        image_source = cv2.imread(detailed_tile.imagesource)
                        completed_tiles += 1
                        current_tile += 1

                        image_output_temp_tile[col_pos:(col_pos)+tz, row_pos:(row_pos)+tz] = image_source

                    cv2.imwrite(image_output_tile, image_output_temp_tile)
                    print("")
                    print(f'Saving finished tile as {image_output_tile}')
                    tile.outputstatus += 1
                    tile.finishedimagedetailedtile = image_output_tile

        if self.tilesources.maxelevation < self.tilesources.calculatedmaxelevation:
            print(f'The elevation found was higher than the maximum set. Consider changing this value and run again - Max: {elevationsource.maxelevation} - Found: {elevationsource.calculatedmaxelevation}')
            input("Press Enter to continue...")
        if self.tilesources.minelevation > self.tilesources.calculatedminelevation:
            print(f'The elevation found was lower than the minimum set. Consider changing this value and run again - Min: {self.tilesources.minelevation} - Found: {self.tilesources.calculatedminelevation}')
            input("Press Enter to continue...")

    def processAndAddFileSources(self):


        offset_row, offset_col, x, y, z = self.getTileInformationForRelativeCalculations()

        for source in self.filesources.sources:
            self.scalefactor = source.process(self.minelevation, self.maxelevation, self.zoom, x, y, self._maxtilesperimage, self.waypointtoroutemargin, offset_row, offset_col)

    def buildFusionMap(self, startanimation = 10, endanimation = 5):

        fusionMap = FusionMap(startanimation=startanimation, endanimation=endanimation)
        fusionMap.checkFusionInstance()
        #fusionMap.buildSettingsComponent(self.filesources.sources[0].route, self.scalefactor)
        fusionMap.buildMainComponents(self.scalefactor, self.tilesources.selectedElevationSource().attribution)

        for tile in self.tiles:

            fusionMap.buildOverviewTile(tile.finishedelevationtile, tile.finishedimagetile, tile.row, tile.col, tile.detailed)
            
            if tile.detailed == True:
                fusionMap.buildDetailedTile(tile.finishedelevationdetailedtile, tile.finishedimagedetailedtile, tile.row, tile.col)
            
            
            
            for source in self.filesources.sources:
                parts = list(filter(lambda part: part.col == tile.col and part.row == tile.row, source.route.parts))
                if len(parts) > 0:
                    
                    fusionMap.buildGeometry(source.route, parts, tile.getSize())             
                
        for source in self.filesources.sources:
            if source.addwaypointsasmarkers == True:
                    fusionMap.buildMarkers(source.route)
            if source.animate == True:
                rows, cols = self.getMapDimesions()
                fusionMap.animateCamera(source.route, rows, cols)

        fusionMap.unlockComp()

def makeGrayscale(image, tilesource, row_pos, col_pos):
    tilesize = tilesource.selectedElevationSource().tilesize
    grayscale_tile = np.random.randint(255, size=(tilesize, tilesize))

    minr = image[..., 2].min()
    maxr = image[..., 2].max()
    h, w, c = image.shape

    elevationerrors = 0
    

    for i in range (0, h):
        for j in range(0, w):
            pixelcolor = image[i, j]
            elevation = tilesource.selectedElevationSource().GetElevation(pixelcolor)

            if elevation > tilesource.maxelevation:
                if elevation > tilesource.calculatedmaxelevation:
                    tilesource.calculatedmaxelevation = elevation
                elevationerrors += 1
            if elevation < tilesource.minelevation:
                if elevation < tilesource.calculatedminelevation:
                    tilesource.calculatedminelevation = elevation
                elevationerrors += 1
            if elevationerrors == 1:   
                print(f"Elevation error on this tile... ")
                elevationerrors += 1
            
            grayscale = int(round((math.ceil(elevation) - tilesource.minelevation) / (tilesource.maxelevation-tilesource.minelevation) * (65536), 0))
            
            if grayscale < 1: grayscale = 1 # Set lowest value to 1
            if grayscale > 255: grayscale = 255 # Set highest value to 255
            grayscale_tile[i, j] = grayscale
            
    return grayscale_tile, row_pos, col_pos

def downloadTile(url, savepath):

    header = {
            'cache-control': 'max-age=0',
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="99", "Google Chrome";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.82 Safari/537.36'
        }

    response = requests.get(url, headers=header)
    if response.status_code == 200:
        with open(savepath, "wb") as f:
            f.write(response.content)
            return 1
    else:
        print(f"Failed while downloading {url}")
        return -1

def calculate_tiles(lat1, lon1, lat2, lon2, zoom, tile_size, max_tiles_per_image):
    
    width, height = image_size(lat1, lon1, lat2, lon2, zoom, tile_size)
    smalltiles_in_height = math.ceil(height/tile_size)
    smalltiles_in_width = math.ceil(width/tile_size)
    rows = (math.ceil(smalltiles_in_height / max_tiles_per_image))
    tiles_per_row = math.ceil(smalltiles_in_height/rows)
    cols = (math.ceil(smalltiles_in_width / max_tiles_per_image))
    tiles_per_col = math.ceil(smalltiles_in_width/cols)
    return rows, cols, tiles_per_row, tiles_per_col, smalltiles_in_width, smalltiles_in_height

def image_size(lat1: float, lon1: float, lat2: float, lon2: float, zoom: int, tile_size: int = 256):
    """ Calculates the size of an image without downloading it. Returns the width and height in pixels as a tuple. """

    scale = 1 << zoom
    tl_proj_x, tl_proj_y = project_with_scale(lat1, lon1, scale)
    br_proj_x, br_proj_y = project_with_scale(lat2, lon2, scale)

    tl_pixel_x = int(math.floor(tl_proj_x) * tile_size)
    tl_pixel_y = int(math.floor(tl_proj_y) * tile_size)
    br_pixel_x = int((math.floor(br_proj_x)+1) * tile_size)
    br_pixel_y = int((math.floor(br_proj_y)+1) * tile_size)

    return abs(tl_pixel_x - br_pixel_x), br_pixel_y - tl_pixel_y

def addExtraPointToLastPart(lastRelativeX, relativeX, lastRelativeY, relativeY):
    
    returnX = relativeX
    returnY = relativeY
    isOutside = False
    xDifference = abs(lastRelativeX - relativeX)
    yDifference = abs(lastRelativeY - relativeY)

    if lastRelativeX < 0 and relativeX > 0 and xDifference > 0.5:
         returnX = -1+relativeX
         isOutside = True
    if lastRelativeX > 0 and relativeX < 0 and xDifference > 0.5:
         returnX = 1 + relativeX
         isOutside = True
    if lastRelativeY < 0 and relativeY > 0 and yDifference > 0.5:
         returnY = -1+relativeY
         isOutside = True
    if lastRelativeY > 0 and relativeY < 0 and yDifference > 0.5:
         returnY = 1 + relativeY
         isOutside = True

    return isOutside, returnX, returnY

def addExtraPointToNextPart(lastRelativeX, relativeX, lastRelativeY, relativeY):
    
    returnX = lastRelativeX
    returnY = lastRelativeY
    isOutside = False
    xDifference = abs(lastRelativeX - relativeX)
    yDifference = abs(lastRelativeY - relativeY)

    if lastRelativeX < 0 and relativeX > 0 and xDifference > 0.5:
         returnX = 1+lastRelativeX
         isOutside = True
    if lastRelativeX > 0 and relativeX < 0 and xDifference > 0.5:
         returnX = -1 + lastRelativeX
         isOutside = True
    if lastRelativeY < 0 and relativeY > 0 and yDifference > 0.5:
         returnY = 1+lastRelativeY
         isOutside = True
    if lastRelativeY > 0 and relativeY < 0 and yDifference > 0.5:
         returnY = -1 + lastRelativeY
         isOutside = True

    return isOutside, returnX, returnY

    
def project_with_scale(lat, lon, scale):
    siny = np.sin(lat * np.pi / 180)
    siny = min(max(siny, -0.9999), 0.9999)
    x = scale * (0.5 + lon / 360)
    y = scale * (0.5 - np.log((1 + siny) / (1 - siny)) / (4 * np.pi))
    return x, y

def deg2num(lat, lon, zoom):
      lat_rad = math.radians(lat)
      n = 2.0 ** zoom
      xtile = int((lon + 180.0) / 360.0 * n)
      ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
      return (xtile, ytile)

def deg2actualsize(lat, lon, zoom):
    circ = 40075
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    width = circ * np.cos(lat_rad) / n
    return width * 1000

def count_tiles(lat1, lon1, lat2, lon2, zoom, tile_size):
    width, height = image_size(lat1, lon1, lat2, lon2, zoom, tile_size)
    tiles_in_height = math.ceil(height/tile_size)
    tiles_in_width = math.ceil(width/tile_size)
    return tiles_in_height, tiles_in_width

def translate_latlong(lat,long,lat_translation_meters,long_translation_meters):
    ''' method to move any lat,long point by provided meters in lat and long direction.
    params :
        lat,long: lattitude and longitude in degrees as decimal values, e.g. 37.43609517497065, -122.17226450150885
        lat_translation_meters: movement of point in meters in lattitude direction.
                                positive value: up move, negative value: down move
        long_translation_meters: movement of point in meters in longitude direction.
                                positive value: left move, negative value: right move
        '''
    earth_radius = 6378.137

    #Calculate top, which is lat_translation_meters above
    m_lat = (1 / ((2 * math.pi / 360) * earth_radius)) / 1000;  
    lat_new = lat + (lat_translation_meters * m_lat)

    #Calculate right, which is long_translation_meters right
    m_long = (1 / ((2 * math.pi / 360) * earth_radius)) / 1000;  # 1 meter in degree
    long_new = long + (long_translation_meters * m_long) / math.cos(lat * (math.pi / 180));
    
    return lat_new,long_new

def get_all_children(x, y, z, detailedzoom):


    all_children = []

    first_level = mercantile.children(x, y, z)
    for tile in first_level:
        second_level = mercantile.children(tile.x, tile.y, tile.z)
        if detailedzoom == z+2:
            all_children.extend(second_level)
        else:
            for child_tile in second_level:
                third_level = mercantile.children(child_tile.x, child_tile.y, child_tile.z)
                all_children.extend(third_level)

    return all_children

def point2rowcol(lat, lon, zoom, top_left_tilex, top_left_tiley, tiles_per_row, tiles_per_col):
    
    point_tilex, point_tiley = deg2num(lat, lon, zoom)
    point_row = math.floor((point_tilex - top_left_tilex) / tiles_per_row)
    point_col = math.floor((point_tiley - top_left_tiley) / tiles_per_col)

    rowtopxtile =  top_left_tilex +(point_row * tiles_per_row)
    rowtopytile = top_left_tiley +(point_col * tiles_per_col)

    topbbox = mercantile.bounds(rowtopxtile, rowtopytile, zoom)
    bottombbox = mercantile.bounds(rowtopxtile+tiles_per_row-1, rowtopytile+tiles_per_col-1, zoom)
    
    bigtiletl = mercantile.LngLat(topbbox.north, topbbox.west)
    bigtilebr = mercantile.LngLat(bottombbox.south, bottombbox.east)

    # X
    tilewidth = bottombbox.east-topbbox.west
    pointxplacement = bottombbox.east-lon
    pointxrel = pointxplacement/tilewidth
    pointrelx = (pointxrel*-1)-(-0.5) 

    # Y
    tileheight = topbbox.north-bottombbox.south
    pointyplacement = topbbox.north-lat
    pointyrel = pointyplacement/tileheight
    pointrely = (pointyrel*-1) - (-0.5)

    return point_row, point_col, pointrelx, pointrely

def deg2actualsize(lat, lon, zoom):

    circ = 40075
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    width = circ * np.cos(lat_rad) / n
    return width * 1000

def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    # Radius of earth in kilometers is 6371
    km = 6371* c
    return km

def checkDirectories():
    gpxdirectory = os.path.join(os.path.dirname(__file__) , 'gpx')
    os.makedirs(gpxdirectory, exist_ok=True)

    imagedirectory = os.path.join(os.path.dirname(__file__) , 'images')
    os.makedirs(imagedirectory, exist_ok=True)

    downloaddirectory = os.path.join(imagedirectory, 'download')
    os.makedirs(downloaddirectory, exist_ok=True)
    return gpxdirectory, imagedirectory, downloaddirectory