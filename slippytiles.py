import mercantile

class TileSources:
    def __init__(self, selectedImageSource = 0, selectedElevationSource = 0, minelevation = 0, maxelevation = 9000):
        self.ImageSources = []
        self.ElevationSources = []

        self.ImageSources.append(ImageTileSource('ArcGis Online - World Imagery', 'http://services.arcgisonline.com/ArcGis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}.png', 'XYZ', 256, 'Esri, DigitalGlobe, GeoEye, i-cubed, USDA FSA, USGS, AEX, Getmapping, Aerogrid, IGN, IGP, swisstopo, and the GIS User Community', 'arcgis', 15 ))
        self.ImageSources.append(ImageTileSource('Google - Satellite', 'https://mt.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', 'XYZ', 256, '', 'google', 18 ))
        self.ImageSources.append(ImageTileSource('Maptiler - Satellite V2', 'https://api.maptiler.com/tiles/satellite-v2/{z}/{x}/{y}.jpg?key={apikey}', 'XYZ', 512, '© MapTiler © OpenStreetMap contributors', 'maptiler_satellite_v2', '',15 ))
        self.ImageSources.append(ImageTileSource('Bing - Satellite', "http://ecn.t3.tiles.virtualearth.net/tiles/a{q}.jpeg?g=0&dir=dir_n'", 'QUADKEY', 256, '', 'bing', 18))

        self.ElevationSources.append(ElevationTileSource('Terrarium', 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png', 'XYZ', 256,'', 'terrarium', 15, None, 1 ))
        self.ElevationSources.append(ElevationTileSource('Maptiler - Terrain RGB', 'https://api.maptiler.com/tiles/terrain-rgb-v2/{z}/{x}/{y}.webp?key={apikey}', 'XYZ', 512, '© MapTiler © OpenStreetMap contributors', 'maptiler_terrain_rgb', 14, '', 2 ))

        self._selectedImageSource = selectedImageSource
        self._selectedElevationSource = selectedElevationSource
        self.maxelevation = maxelevation
        self.minelevation = minelevation
        self.calculatedmaxelevation = 0
        self.calculatedminelevation = 9000

    def setElevationSource(self, index):
        self._selectedElevationSource = index

    def setImageSource(self, index):
        self._selectedImageSource = index


    def selectedElevationSource(self):
        return self.ElevationSources[self._selectedElevationSource]

    def selectedImageSource(self): 
        return self.ImageSources[self._selectedImageSource]


class TileSource:
    def __init__(self, name, url, type, tilesize, attribution, prefix, maxzoom, apikey = None):
        self.name = name
        self.url = url
        self.type = type
        self.tilesize = tilesize
        self.attribution = attribution
        self.prefix = prefix
        self.apikey = apikey
        self.maxzoom = maxzoom
        

    def getFormattedUrl(self, x, y, z):
        if self.type == 'XYZ':
            return self.url.format(x=x, y=y, z=z, apikey = self.apikey)
        if self.type == 'QUADKEY':
            return self.url.format(q=mercantile.quadkey(x, y, z))

class ImageTileSource(TileSource):
        pass

class ElevationTileSource(TileSource):
    def __init__(self, name, url, type, tilesize, attribution, prefix, maxzoom, apikey = None, calculationmethod = 1):
        super().__init__(name, url, type, tilesize, attribution, prefix, maxzoom, apikey)
        self.calculationmethod = calculationmethod

    def GetElevation(self, pixelcolor):
        red = pixelcolor[2]
        green = pixelcolor[1]
        blue = pixelcolor[0]
        if self.calculationmethod == 1:
            return ((red * 256.0) + green + (blue / 256.0)) - 32768.0
        if self.calculationmethod == 2:
            return  -10000 + ((red * 256 * 256 + green * 256 + blue) * 0.1)
        

