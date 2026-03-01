from enum import Enum
import math
import re
import gpxpy
import mercantile

from utils import *
from utils import haversine
from utils import deg2actualsize
from utils import deg2num


class GeometrySources:
    def __init__(self):
        self.sources = [] 

    def addSource(self, source):
        self.sources.append(source)

    def getBounds(self):

        minlat, maxlat, minlon, maxlon = 90,-90,90,-90

        for s in self.sources:
            s.preprocess()       
            curminlat, curmaxlat, curminlon, curmaxlon = s.getBounds()
            minlat = curminlat if curminlat < minlat else minlat
            maxlat = curmaxlat if curmaxlat > maxlat else maxlat
            minlon = curminlon if curminlon < minlon else minlon
            maxlon = curmaxlon if curmaxlon > maxlon else maxlon

        return maxlat, minlon, minlat, maxlon



class GeometrySource:
    def __init__(self, filepath):
        self.filepath = filepath
        self.animate = False
        self.addwaypointsasmarkers = False



class GpxSource(GeometrySource):
    def __init__(self, filepath, gpx = None, animate = False, addwaypointsasmarkers = False):
        super().__init__(filepath)
        self.gpx = gpx
        self.waypoints = []
        self.route = Route(0, 0, 0)
        self.animate = animate
        self.addwaypointsasmarkers = addwaypointsasmarkers
       
    def preprocess(self):
        
        gpx_file = open(self.filepath, "r")
        gpx = gpxpy.parse(gpx_file)
       
        # LATITUDE -> HEIGHT -> ROWS
        # LONGITUDE -> WIDTH -> COLS

        minlat, maxlat, minlon, maxlon = gpx.get_bounds()

        if not gpx.routes:
            print("No routes in gpx. Checking to see if there are a track that can be converted and used.")
            if not gpx.tracks:
                print("No tracks in gpx. Unusable gpx.")
                return False
            else:
                route_gpx = gpxpy.gpx.GPX()
                gpx_route = gpxpy.gpx.GPXRoute()

                # Iterate through the track points and add them as route points
                for track in gpx.tracks:
                    for segment in track.segments:
                        for point in segment.points:
                            route_point = gpxpy.gpx.GPXRoutePoint(
                                latitude=point.latitude,
                                longitude=point.longitude,
                                elevation=point.elevation,
                                time=point.time
                            )
                            gpx_route.points.append(route_point)

                route_gpx.routes.append(gpx_route)      
            gpx.routes = route_gpx.routes

        self.gpx = gpx
        return True
   
    def getBounds(self):
        return self.gpx.get_bounds()
    
    def process(self, minelevation, maxelevation, zoom, tl_tilex, tl_tiley, tiles_per_side, wp_route_margin, offset_row, offset_col):
        distance_points = self.gpx.get_points_data()
        self.gpx.add_missing_elevations()
        self.route = Route(length=self.gpx.length_3d(), minelevation=minelevation, maxelevation=maxelevation)
        center = self.gpx.tracks[0].get_center()


        tilewidthinmeters = deg2actualsize(center.latitude, center.longitude, zoom) * tiles_per_side
        elevation_span = maxelevation-minelevation
        scalefactor = elevation_span / tilewidthinmeters

        print(f'Processing gpx...')

        print(f'Finding tracks...')
        for track in self.gpx.tracks:
            point_tracker = 0
            firstpoint = 1
            index = 1
            totallength = track.length_3d()
            currentlength = 0.0
            lasttarget = 0
            added_camera_start_wp = 0
    
            self.route.name = track.name

            for segment in track.segments:
                print(f'Total points {len(segment.points)}')
                p_counter = 0
                last_part_was_empty = False
                total_points = len(segment.points)
                part = RoutePart(1, 0, 0, 0, 0.0)
                partsegment = gpxpy.gpx.GPXTrackSegment()

                for point in segment.points:
                    p_counter += 1
                    #print(f'Point at ({point.latitude},{point.longitude}) -> {point.elevation}')
                    point_row, point_col, relx, rely = point2rowcol(point.latitude, point.longitude, zoom, tl_tilex, tl_tiley, tiles_per_side)
                    point_row += offset_row
                    point_col += offset_col
                    # First point
                    if firstpoint:                       
                        waypointrelativeelevation = (point.elevation - minelevation) / (elevation_span) 
                        waypointylocation = (waypointrelativeelevation)*scalefactor 
                        wp_new = Waypoint('Start', '', WaypointType.Start, 0, point.elevation, point_row+relx, point_col-rely, waypointylocation)             
                        self.waypoints.append(wp_new)
                    
                        part.row = point_row
                        part.col = point_col
                        part.start = currentlength
                        part.points.append(XYPoint(relx, rely))
                        partsegment.points.append(gpxpy.gpx.GPXTrackPoint(point.latitude, point.longitude, point.elevation))
                        firstpoint = 0
                        continue

                    # New point in same part
                    if part.row == point_row and part.col == point_col:
                        part.points.append(XYPoint(relx, rely))
                        partsegment.points.append(gpxpy.gpx.GPXTrackPoint(point.latitude, point.longitude, point.elevation))


                    # TODO: Try and add previous point and next point to parts to overlap better on map
                    else:
                        part.length = partsegment.length_3d()
                        currentlength = currentlength + part.length
                        if part.length > 0:
                            
                            if last_part_was_empty == False:
                                isoutside, x, y = addExtraPointToLastPart(lastrelx, relx, lastrely, rely)
                                if isoutside:
                                     part.points.append(XYPoint(x, y))
                                #if (lastrelx < 0 and relx > 0):            
                                #    part.points.append(XYPoint(-1+relx, rely))
                                #if (lastrelx > 0 and relx < 0):
                                #   part.points.append(XYPoint(1+relx, rely))
                                #if (lastrely < 0 and rely > 0):
                                #  part.points.append(XYPoint(relx, -1+rely))
                                #if (lastrely > 0 and rely < 0):
                                #    part.points.append(XYPoint(relx, 1+rely))
                                
                            self.route.parts.append(part)
                            print(f"Added route part in tile {part.row}, {part.col}")
                            index += 1
                            part = RoutePart(index, point_row, point_col, 0, currentlength)
                            partsegment = gpxpy.gpx.GPXTrackSegment()
                            partsegment.points.append(gpxpy.gpx.GPXTrackPoint(point.latitude, point.longitude, point.elevation))
                            isoutside, x, y = addExtraPointToNextPart(lastrelx, relx, lastrely, rely)
                            if isoutside:
                                part.points.append(XYPoint(x, y))
                            #if (lastrelx < 0 and relx > 0):
                            #    part.points.append(XYPoint(1+lastrelx, lastrely))
                            #if (lastrelx > 0 and relx < 0):
                            #    part.points.append(XYPoint(-1+lastrelx, lastrely))
                            #if (lastrely < 0 and rely > 0):
                            #    part.points.append(XYPoint(lastrelx, 1+lastrely))
                            #if (lastrely > 0 and rely < 0):
                            #    part.points.append(XYPoint(lastrelx, -1+lastrely))
                            part.points.append(XYPoint(relx, rely))
                            last_part_was_empty = False
                        else:
                            part = RoutePart(index, point_row, point_col, 0, currentlength)
                            partsegment = gpxpy.gpx.GPXTrackSegment()
                            last_part_was_empty = True
                            continue

                    # Add camera target if over threshold distance

                    current_distance_from_start = distance_points[point_tracker].distance_from_start / 1000 

                    if current_distance_from_start - lasttarget > 3: #camera_target_every_nth_km:
                        waypointrelativeelevation = (point.elevation - minelevation) / (elevation_span) 
                        waypointylocation = (waypointrelativeelevation)*scalefactor 
                        wp_new = Waypoint('CameraTarget', '', WaypointType.CameraTracker, current_distance_from_start*1000, point.elevation, point_row+relx, point_col-rely, waypointylocation)             
                        self.waypoints.append(wp_new)                   
                        lasttarget = current_distance_from_start


                    # Add waypoint to calculate camera placement at start off animation

                    if current_distance_from_start > (totallength / 10) and added_camera_start_wp == 0:
                        waypointrelativeelevation = (point.elevation - minelevation) / (elevation_span) 
                        waypointylocation = (waypointrelativeelevation)*scalefactor 
                        wp_new = Waypoint('CameraStartTarget', '', WaypointType.StartCameraDirection, current_distance_from_start*1000, point.elevation, point_row+relx, point_col-rely, waypointylocation)             
                        self.waypoints.append(wp_new)
                        added_camera_start_wp = 1


                    point_tracker += 1

                    # Last point
                    if p_counter == total_points:
                        part.length = partsegment.length_3d()
                        self.route.parts.append(part)
                        waypointrelativeelevation = (point.elevation - minelevation) / (elevation_span) 
                        waypointylocation = (waypointrelativeelevation)*scalefactor 
                        wp_new = Waypoint('Finish', '', WaypointType.Finish, self.route.length, point.elevation, point_row+relx, point_col-rely, waypointylocation)
                        self.waypoints.append(wp_new)

                    lastrelx = relx
                    lastrely = rely

            print(f'Processing waypoints...')

            # Add waypoint in center off track
            point_row, point_col, relx, rely = point2rowcol(center.latitude, center.longitude, zoom, tl_tilex, tl_tiley, tiles_per_side)            
            point_row += offset_row
            point_col += offset_col
            self.waypoints.append(Waypoint("Route center",'',WaypointType.Center, -1, elevation_span/2, point_row+relx, point_col-rely, 0))

            lat1, lat2, lon1, lon2 = self.gpx.get_bounds()

            for wp in self.gpx.waypoints:

                print(f"Prosessing - {wp.name}", end='')

                if wp.latitude < lat2 and wp.latitude > lat1:
                    
                    if wp.longitude > lon1 and wp.longitude < lon2:
                    
                        dfs = 0.0
                        wpelevation = 0

                        loc, track_no, segment_no, point_no =  self.gpx.get_nearest_location(wp)
                        for i  in distance_points:
                            if track_no == i[2]:
                                if segment_no == i[3]:
                                    if point_no == i[4]:
                                        dfs = i.distance_from_start
                                        wpelevation = i.point.elevation
                                        break 

                        distance_from_route = haversine(wp.latitude, wp.longitude, loc.latitude, loc.longitude)
                        print(f" - Distance from route: {distance_from_route:.2f} km", end='')

                        if distance_from_route < wp_route_margin:

                            print(f" - Distance from start: {dfs/1000:.2f} km - Adding to output")
                            point_row, point_col, relx, rely = point2rowcol(wp.latitude, wp.longitude, zoom, tl_tilex, tl_tiley, tiles_per_side)
                            point_row += offset_row
                            point_col += offset_col
                            waypointrelativeelevation = (point.elevation - minelevation) / (elevation_span) 
                            waypointylocation = (waypointrelativeelevation)*scalefactor 
                            wp_new = Waypoint(wp.name, wp.comment, WaypointType.Normal, dfs, wpelevation, point_row+relx, point_col-rely, waypointylocation)
                        
                            self.waypoints.append(wp_new)
                        else:
                            print(" - Ignored (to far away from route)")
                    else:
                        print(" - Ignored (not on any tile)")
                else:
                    print(" - Ignored (not on any tile)")

            print('Sorting waypoints..."')
            self.waypoints.sort(key=lambda x: x.distancefromstart)
            self.route.waypoints = self.waypoints


        return scalefactor



class RoutePart:
    def __init__(self, index, row, col, length, start):
        self.index = index
        self.row = row
        self.col = col
        self.length = length
        self.start = start
        self.points = []

class XYPoint:
    def __init__(self, X, Y):
        self.X = X
        self.Y = Y

class Route:
    def __init__(self, length, minelevation, maxelevation):
        self.length = length
        self.minelevation = minelevation
        self.maxelevation = maxelevation
        self.name = ''
        self.waypoints = []
        self.parts = []

    def getName(self):
        return re.sub(r'[^a-zA-Z0-9\s]', '', self.name).replace(" ", "")

class Waypoint:
    def __init__(self, name, info, type, distancefromstart, elevation, relx, rely, relz):
        self.name = name
        self.info = info
        self.type = type
        self.distancefromstart = distancefromstart
        self.elevation = elevation
        self.relx = relx
        self.rely = rely
        self.relz = relz

class WaypointType(Enum):
    Normal = 1
    CameraTracker = 2
    Start = 3
    Finish = 4
    Center = 5
    StartCameraDirection = 6



def point2rowcol(lat, lon, zoom, top_left_tilex, top_left_tiley, tiles_per_side):
    
    point_tilex, point_tiley = deg2num(lat, lon, zoom)
    point_row = math.floor((point_tilex - top_left_tilex) / tiles_per_side)
    point_col = math.floor((point_tiley - top_left_tiley) / tiles_per_side)

    rowtopxtile =  top_left_tilex +(point_row * tiles_per_side)
    rowtopytile = top_left_tiley +(point_col * tiles_per_side)

    topbbox = mercantile.bounds(rowtopxtile, rowtopytile, zoom)
    bottombbox = mercantile.bounds(rowtopxtile+tiles_per_side-1, rowtopytile+tiles_per_side-1, zoom)
    
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