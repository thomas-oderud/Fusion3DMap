import os
import sys
import time


# Set these paths according to your DaVinci Resolve installation
RESOLVE_SCRIPT_API = "C:\\ProgramData\\Blackmagic Design\\DaVinci Resolve\\Support\\Developer\\Scripting\\"
RESOLVE_SCRIPT_LIB = "C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\fusionscript.dll"


COMP_MAPSETTINGS_NAME = "MapSettings"
COMP_ROUTESETTINGS_NAME = "RouteSettings"
COMP_MAINMAPMERGE_NAME = "MainMapMerge"
COMP_RENDER_NAME = "Render_Main"
COMP_MAINCAMERA_NAME = "MainCamera"
COMP_CAMERALOCATOR_NAME = "CameraLocator"
COMP_ATTRIBUTION_NAME = "Attribution"
COMP_MEDIAOUT_SAVER_NAME = "MediaOut"
COMP_ELEVATION_IMAGE_NAME = "Elevation"
COMP_IMAGESOURCE_NAME = "Satelite"
COMP_MARKERSMERGE_NAME = "MarkersMerge"
COMP_OVERVIEW_TILE_PREFIX = "Overview"
COMP_DETAILED_TILE_PREFIX = "Detailed"



class FusionInstance:
    def __init__(self):
        pass

    def tryGetInstance(self):
    
        if os.path.exists(RESOLVE_SCRIPT_API):
            sys.path.append(os.path.join(RESOLVE_SCRIPT_API, "Modules"))
            os.environ["RESOLVE_SCRIPT_API"] = RESOLVE_SCRIPT_API
            os.environ["RESOLVE_SCRIPT_LIB"] = RESOLVE_SCRIPT_LIB
        else:
            print("DaVinci Resolve Scripting API path not found.")
            sys.exit()

        try:
            import DaVinciResolveScript as dvr
        except ImportError:
            print("Could not import DaVinciResolveScript. Ensure environment variables are set correctly.")

        resolve = dvr.scriptapp("Resolve")

        if resolve:
            
            projectManager = resolve.GetProjectManager()
            currentProject = projectManager.GetCurrentProject()
            if currentProject:
                fusion = resolve.Fusion().GetCurrentComp() # Get the current Fusion composition
                if fusion:
                    print("Fusion composition found and ready for scripting.")
                    useresolve = 1
                else:
                    print("Found Resolve instance, but no active Fusion composition.")
                    False, None
            else:
                print("Found Resolve instance, but no project open in Resolve.")
                False, None
        else:
            print("Could not get DaVinci Resolve instance. Trying Fusion...")
            fusion = dvr.scriptapp("Fusion")
            if fusion:
                # You can now interact with Resolve and Fusion
                    comp = fusion.GetCurrentComp() # Get the current Fusion composition
                    if comp:
                        print("Fusion composition found and ready for scripting.")
                        useresolve = 2
                    else:
                        print("Found Fusion instance, but no active Fusion composition.")
                        sys.exit()
            else:
                print("Could not get DaVinci Fusion instance.")
                return False, None

        if useresolve == 1: 
            return True, resolve.Fusion(), 1
        if useresolve == 2:
            return True, fusion, 2

    def readString(self, string):
        try:
            import DaVinciResolveScript as dvr
            return dvr.readstring(string)
        except ImportError:
            print("Could not import DaVinciResolveScript. Ensure environment variables are set correctly.")



class FusionMap:
    def __init__(self, component_settings_name = 'Map', component_marker_name = 'SimpleMarker', startanimation=10, endanimation=5):
        self.componentdirectory = os.path.join(os.path.dirname(__file__) , 'components')
        self.markerdirectory = os.path.join(self.componentdirectory, "markers")     
        self.settings = None
        self.component_settings_name = component_settings_name
        self.component_marker_name = component_marker_name
        self.animatecamera = 1
        self.startanimation = startanimation
        self.endanimation = endanimation
        self.cameralag = 3
        self.camerayoffset = 0.15
        self._useresolve = 0
        self._tilecounter = 3
         
        self._fusion = None
        self._comp = None
        self._mainmapmerge = None
        self._settings = None
        self._maincamera = None
        self._iscomplocked = False


    def checkFusionInstance(self):
        instance = FusionInstance()
        result, fusion, useresolve = instance.tryGetInstance()

        if result == True:
            self._fusion = fusion
            self._comp = self._fusion.CurrentComp
            self._useresolve = useresolve


    def unlockComp(self):
        comp = self._comp
        time.sleep(2)
        comp.Unlock()
        flow = comp.CurrentFrame.FlowView
        flow.FrameAll()

    def buildGeometry(self, route, parts, size):

        partsintile = 0
        comp = self._comp
        flow = comp.CurrentFrame.FlowView

        print(f'Adding geometry... ')

        # Add route settings control
        route_settings_name = f"{COMP_ROUTESETTINGS_NAME}_"+route.getName()
        route_settings = comp.FindTool(route_settings_name)
        if not route_settings:
            route_settings_control_file = os.path.join(self.componentdirectory, "route.settings").replace("\\", chr(47)) 
            comp.Execute("comp:Paste(bmd.readfile('"+route_settings_control_file+"'))")
            time.sleep(1)
            route_settings = comp.FindTool("Route")
            route_settings.SetAttrs({"TOOLS_Name": f"{route_settings_name}"})
            route_settings.BorderWidth = 0.0025
            route_settings.RouteActualLength = round(route.length/1000, 3)

        for part in parts:
            partsintile += 1
            partname = f"Route_{part.index}_{part.row}_{part.col}"
            routepolygon = buildpolygon(partname, part.points, size, size)

            cont = FusionInstance().readString(routepolygon)            
            comp.Paste(cont) 

            routepart = comp.FindTool(partname)
            if part.length > 0:
                routepart.WriteLength.SetExpression(f"(({route.length}*"+route_settings_name+f".Progress)-{part.start})/(({part.length}+{part.start})-{part.start})") 
            routepart.WritePosition.SetExpression("iif(WriteLength>0,0,-0.01)")
            routepart.BorderWidth.SetExpression(route_settings_name+".BorderWidth")   

            routeBackground = comp.Background()
            routeBackground.SetAttrs({"TOOLS_Name": f"RouteBackground_"+partname})
            routeBackground.UseFrameFormatSettings = 0
            routeBackground.Width = size
            routeBackground.Height = size
            routeBackground.TopLeftRed.SetExpression(route_settings_name+".routeRED") 
            routeBackground.TopLeftGreen.SetExpression(route_settings_name+".routeGREEN") 
            routeBackground.TopLeftBlue.SetExpression(route_settings_name+".routeBLUE")
            routeBackground.TopLeftAlpha.SetExpression(route_settings_name+".routeALPHA")     
            routeBackground.EffectMask = routepart

            softglow = comp.SoftGlow()
            softglow.SetAttrs({"TOOLS_Name": f"SoftGlow_"+partname})
            softglow.Gain.SetExpression(route_settings_name+".GlowGain")
            softglow.Input = routeBackground

            planemerge = comp.FindTool(f"{COMP_DETAILED_TILE_PREFIX}_MergeTile_{part.row}_{part.col}")
            planemerge[f"Layer{partsintile}"].Foreground = softglow

            # Copy plane, make displace and merge with merge
            flow.SetPos(routepart, 1 + partsintile, 5*(self._tilecounter)-2)
            flow.SetPos(routeBackground, 1 + partsintile, 5*(self._tilecounter)-1)
            flow.SetPos(softglow, 1 + partsintile, 5*(self._tilecounter))
            flow.Select() # Deselect all
            #print(f'{part.col}')

    def buildMarkers(self, route):

        currentwp = 0
        self._component_marker = os.path.join(self.markerdirectory, self.component_marker_name+".settings").replace("\\", chr(47)) 
        comp = self._comp
        flow = comp.CurrentFrame.FlowView

        markermerge = comp.Merge3D()
        markermerge.SetAttrs({"TOOLS_Name": f"{COMP_MARKERSMERGE_NAME}"})
        flow.SetPos(markermerge, 15, 9)
        #mapmerge = comp.FindTool({COMP_MAINMAPMERGE_NAME})
        self._mainmapmerge[f"SceneInput{self._tilecounter}"] = markermerge 

        comp_start_frame = comp.GetAttrs("COMPN_GlobalStart")
        comp_end_frame = comp.GetAttrs("COMPN_GlobalEnd")

   
        frames_to_animate_over = comp_end_frame - self.startanimation - self.endanimation

        for wp in route.waypoints:
            if wp.type.value == 1 or wp.type.value == 3 or wp.type.value == 4:
                currentwp += 1
                frame = round((wp.distancefromstart/route.length)*frames_to_animate_over+self.startanimation)
                comp.CurrentTime = frame
                time.sleep(0.5)
                comp.Execute("comp:Paste(bmd.readfile('"+self._component_marker+"'))")
                time.sleep(0.5)
                print(f"Adding marker: {wp.name}")
                placeMarker = comp.FindTool(self.component_marker_name)    
                placeMarker.SetAttrs({"TOOLS_Name": f"Marker_{wp.name}"})
                placeMarker.PlaceText = wp.name
                placeMarker.InfoText = f"{wp.distancefromstart/1000:.1f} km"
                placeMarker.Size = comp.BezierSpline("{}")
                placeMarker.Size[frame] = 0.1
                placeMarker.Size[frame-10] = 0
                flow.SetPos(placeMarker, 19, 7+currentwp)
                
                placeMarker.TranslationX = wp.relx
                placeMarker.TranslationY = wp.relz
                placeMarker.TranslationZ = wp.rely
                placeMarker.TargetX.SetExpression('CameraLocator:GetValue("Transform3DOp.Translate.X", time - 6)')
                placeMarker.TargetY.SetExpression('CameraLocator:GetValue("Transform3DOp.Translate.Y", time - 6)')
                placeMarker.TargetZ.SetExpression('CameraLocator:GetValue("Transform3DOp.Translate.Z", time - 6)')

                markermerge[f"SceneInput{currentwp}"] = placeMarker
                flow.Select()

    def animateCamera(self, route, rows, cols):

        print("Adding camera animation...")
        currentwp = 0
        camera_wp_index = 0
        comp = self._comp
        flow = comp.CurrentFrame.FlowView
        route_settings_name = f"{COMP_ROUTESETTINGS_NAME}_"+route.getName()
        route_settings = comp.FindTool(route_settings_name)
        comp.CurrentTime = 0

        comp_start_frame = comp.GetAttrs("COMPN_GlobalStart")
        comp_end_frame = comp.GetAttrs("COMPN_GlobalEnd")

        frames_to_animate_over = comp_end_frame - self.startanimation - self.endanimation
        print(f"Animating from frame {self.startanimation} over {frames_to_animate_over} frames and ending at frame {comp_end_frame-self.endanimation}")

        
        route_settings.Progress = comp.BezierSpline("{}")
        route_settings.Progress.InterpolateBetweenFrames = 0
        route_settings.Progress[0] = 0
        route_settings.Progress[self.startanimation] = 0
        route_settings.Progress[self.startanimation+frames_to_animate_over] = 1

        #maincamera = comp.FindTool({COMP_MAINCAMERA_NAME})
        self._maincamera.Transform3DOp.Translate.X = comp.BezierSpline("{}")
        self._maincamera.Transform3DOp.Translate.Y = comp.BezierSpline("{}")
        self._maincamera.Transform3DOp.Translate.Z = comp.BezierSpline("{}")

        self._maincamera.Transform3DOp.Target.X = comp.BezierSpline("{}")
        self._maincamera.Transform3DOp.Target.Y = comp.BezierSpline("{}")
        self._maincamera.Transform3DOp.Target.Z = comp.BezierSpline("{}")

        self._maincamera.Transform3DOp.UseTarget = 1
        self._maincamera.Transform3DOp.Translate.X[0] = (cols-0.5)/2
        self._maincamera.Transform3DOp.Translate.Z[0] = (rows-0.5)/2
        self._maincamera.Transform3DOp.Translate.Y[0] = 0.5
        self._maincamera.PerspNearClip = 0.05
        self._maincamera.FLength = 18
        self._maincamera.FilmGate = "Canon_7D"

        for wp in route.waypoints:
            camera_wp_index += 1

            # Animate camera
            if currentwp == 1:
                self._maincamera.Transform3DOp.Target.X[0] = wp.relx
                self._maincamera.Transform3DOp.Target.Y[0] = wp.relz
                self._maincamera.Transform3DOp.Target.Z[0] = wp.rely 

                if len(route.waypoints) > self.cameralag:
                    camerastartx = wp.relx - (route.waypoints[self.cameralag].relx - wp.relx)
                    camerastarty = wp.rely - (route.waypoints[self.cameralag].rely - wp.rely)
                    self._maincamera.Transform3DOp.Translate.X[self.startanimation] = camerastartx
                    self._maincamera.Transform3DOp.Translate.Z[self.startanimation] = camerastarty


            frame = round((wp.distancefromstart/route.length)*frames_to_animate_over+self.startanimation)
            comp.CurrentTime = frame
            self._maincamera.Transform3DOp.Target.X[frame] = wp.relx
            self._maincamera.Transform3DOp.Target.Y[frame] = wp.relz
            self._maincamera.Transform3DOp.Target.Z[frame] = wp.rely

            if camera_wp_index >= self.cameralag:
                self._maincamera.Transform3DOp.Translate.X[frame] = route.waypoints[camera_wp_index-self.cameralag].relx
                self._maincamera.Transform3DOp.Translate.Y[frame] = route.waypoints[camera_wp_index-self.cameralag].relz + self.camerayoffset
                self._maincamera.Transform3DOp.Translate.Z[frame] = route.waypoints[camera_wp_index-self.cameralag].rely

            if wp.type.value == 1 or wp.type.value == 3 or wp.type.value == 4:
                currentwp += 1
      
    def buildMainComponents(self, scalefactor, attributiontext):


        print("Adding main components")
        
        comp = self._comp
        flow = comp.CurrentFrame.FlowView

        comp.Lock()
        
        # Map settings
        component_map_settings = os.path.join(self.componentdirectory, self.component_settings_name+".settings").replace("\\", chr(47)) 
        self.settings = comp.FindTool({COMP_MAPSETTINGS_NAME})
        if not self.settings:
            comp.Execute("comp:Paste(bmd.readfile('"+component_map_settings+"'))")
            time.sleep(1)
            settings = comp.FindTool(self.component_settings_name)
            settings.SetAttrs({"TOOLS_Name": f"{COMP_MAPSETTINGS_NAME}"})
            settings.mapDisplace = scalefactor       
            self.settings = settings


        mapmerge = comp.Merge3D()
        mapmerge.SetAttrs({"TOOLS_Name": f"{COMP_MAINMAPMERGE_NAME}"})
        self._mainmapmerge = mapmerge

        render = comp.Renderer3D()
        render.SetAttrs({"TOOLS_Name": f"{COMP_RENDER_NAME}"})
        render.SceneInput = mapmerge

        maincamera = comp.Camera3D()
        maincamera.SetAttrs({"TOOLS_Name": f"{COMP_MAINCAMERA_NAME}"})
        maincamera.InterpolateBetweenFrames = 0
        mapmerge.SceneInput1 = maincamera
        self._maincamera = maincamera

        cameralocator = comp.Locator3D()
        cameralocator.SetAttrs({"TOOLS_Name": f"{COMP_CAMERALOCATOR_NAME}"})
        cameralocator.Transform3DOp.Translate.X.SetExpression("MainCamera.Transform3DOp.Translate.X")
        cameralocator.Transform3DOp.Translate.Y.SetExpression(f"MainCamera.Transform3DOp.Translate.Y-{self.camerayoffset/2}")
        cameralocator.Transform3DOp.Translate.Z.SetExpression("MainCamera.Transform3DOp.Translate.Z")
        mapmerge.SceneInput2 = cameralocator

        attribution = comp.TextPlus()
        attribution.SetAttrs({"TOOLS_Name": f"{COMP_ATTRIBUTION_NAME}"})
        attribution.StyledText = attributiontext
        attribution.Size = 0.012
        attribution.HorizontalLeftCenterRight = 1
        attribution.Font = "Arial"
        attribution.Style = "Regular"

        mergeattribution = comp.Merge()
        mergeattribution.SetAttrs({"TOOLS_Name": f"Merge_{COMP_ATTRIBUTION_NAME}"})
        mergeattribution.Background = render
        mergeattribution.Foreground = attribution
        mergeattribution.Center = (0.99, 0.02) # Portrait mode is different

        mediaout = comp.FindToolByID(f"{COMP_MEDIAOUT_SAVER_NAME}")
        if mediaout == None:
            if self._useresolve == 1:
                mediaout = comp.MediaOut()
            if self._useresolve == 2:
                mediaout = comp.Saver()

        mediaout.Input = mergeattribution
        
        flow.SetPos(settings, 13, 5)
        flow.SetPos(mapmerge, 15, 7)
        flow.SetPos(maincamera, 15, 5)
        flow.SetPos(cameralocator, 16, 5)
        flow.SetPos(render, 17, 7)
        flow.SetPos(attribution, 19, 5)
        flow.SetPos(mergeattribution, 19, 7)
        flow.SetPos(mediaout, 21, 7)

    def buildOverviewTile(self, elevationsource, imagesource, tile_x, tile_y, hasdetailed = False):

        print("Adding overview tile")
        
        position_x = 2
        position_y = 5 *(self._tilecounter)

        comp = self._comp
        flow = comp.CurrentFrame.FlowView
        comp.Lock()
            
        sat = comp.Loader()
        sat.Clip[0] = imagesource #"F:\\Python\\FusionMap\\images\\TOR_sat_0_0_.png"
        time.sleep(0.5)
        sat.SetAttrs({"TOOLS_Name": f"{COMP_OVERVIEW_TILE_PREFIX}_Image_{tile_x}_{tile_y}"})
        flow.SetPos(sat, position_x-1, position_y+2)

        dem = comp.Loader()
        dem.Clip[0] = elevationsource #"F:\\Python\\FusionMap\\images\\TOR_dem_0_0_.png"
        time.sleep(0.5)
        dem.SetAttrs({"TOOLS_Name": f"{COMP_OVERVIEW_TILE_PREFIX}_Elevation_{tile_x}_{tile_y}"})
        flow.SetPos(dem, position_x+4, position_y)

        tilemerge = comp.MultiMerge()
        tilemerge.SetAttrs({f"TOOLS_Name": f"{COMP_OVERVIEW_TILE_PREFIX}_MergeTile_{tile_x}_{tile_y}"})
        tilemerge.Background = sat
        flow.SetPos(tilemerge, position_x, position_y+2)

        plane = comp.ImagePlane3D()
        plane.MaterialInput = tilemerge
        plane.Transform3DOp.Rotate.X[0] = -90.0
        plane.Transform3DOp.Translate.X[0] = tile_x
        plane.Transform3DOp.Translate.Z[0] = tile_y
        plane.SetAttrs({"TOOLS_Name": f"{COMP_OVERVIEW_TILE_PREFIX}_ImagePlane_{tile_x}_{tile_y}"})
        flow.SetPos(plane, position_x+2.5, position_y+2)

        displace = comp.Displace3D()
        displace.SceneInput = plane
        displace.Input = dem
        displace.SetAttrs({"TOOLS_Name": f"{COMP_OVERVIEW_TILE_PREFIX}_Displace_{tile_x}_{tile_y}"})
        flow.SetPos(displace, position_x+4, position_y+2)

        merge = comp.Merge3D()
        merge.SetAttrs({"TOOLS_Name": f"{COMP_OVERVIEW_TILE_PREFIX}_Merge_{tile_x}_{tile_y}"})
        merge.SceneInput1= displace
        flow.SetPos(merge, position_x+7, position_y+2)

        time.sleep(2)

        #mainmapmerge = comp.FindTool({COMP_MAINMAPMERGE_NAME})
        self._mainmapmerge[f"SceneInput{self._tilecounter}"] = merge
        displace.Scale.SetExpression(f"{COMP_MAPSETTINGS_NAME}.mapDisplace")
        plane["SurfacePlaneInputs"].SubdivisionWidth.SetExpression(f"{COMP_MAPSETTINGS_NAME}.MapSubdivisions")
        if hasdetailed:
            plane["MtlStdInputs"].Diffuse.Opacity.SetExpression(f"{COMP_MAPSETTINGS_NAME}.OverviewWithDetailedVisibility")
        else:
            plane["MtlStdInputs"].Diffuse.Opacity.SetExpression(f"{COMP_MAPSETTINGS_NAME}.OverviewVisibility")

        self._tilecounter += 1

    def buildDetailedTile(self, elevationsource, imagesource, tile_x, tile_y):

        print("Adding detailed tile")
        
        position_x = 2
        position_y = 5 *(self._tilecounter)

        comp = self._comp
        flow = comp.CurrentFrame.FlowView
        comp.Lock()
            
        sat = comp.Loader()
        sat.Clip[0] = imagesource #"F:\\Python\\FusionMap\\images\\TOR_sat_0_0_.png"
        time.sleep(0.5)
        sat.SetAttrs({"TOOLS_Name": f"{COMP_DETAILED_TILE_PREFIX}_Image_{tile_x}_{tile_y}"})
        flow.SetPos(sat, position_x-1, position_y+2)

        dem = comp.Loader()
        dem.Clip[0] = elevationsource #"F:\\Python\\FusionMap\\images\\TOR_dem_0_0_.png"
        time.sleep(0.5)
        dem.SetAttrs({"TOOLS_Name": f"{COMP_DETAILED_TILE_PREFIX}_Elevation_{tile_x}_{tile_y}"})
        flow.SetPos(dem, position_x+4, position_y)

        tilemerge = comp.MultiMerge()
        tilemerge.SetAttrs({f"TOOLS_Name": f"{COMP_DETAILED_TILE_PREFIX}_MergeTile_{tile_x}_{tile_y}"})
        tilemerge.Background = sat
        flow.SetPos(tilemerge, position_x, position_y+2)

        plane = comp.ImagePlane3D()
        plane.MaterialInput = tilemerge
        plane.Transform3DOp.Rotate.X[0] = -90.0
        plane.Transform3DOp.Translate.X[0] = tile_x
        plane.Transform3DOp.Translate.Z[0] = tile_y
        plane.SetAttrs({"TOOLS_Name": f"{COMP_DETAILED_TILE_PREFIX}_ImagePlane_{tile_x}_{tile_y}"})
        flow.SetPos(plane, position_x+2.5, position_y+2)

        displace = comp.Displace3D()
        displace.SceneInput = plane
        displace.Input = dem
        displace.SetAttrs({"TOOLS_Name": f"{COMP_DETAILED_TILE_PREFIX}_Displace_{tile_x}_{tile_y}"})
        flow.SetPos(displace, position_x+4, position_y+2)

        merge = comp.Merge3D()
        merge.SetAttrs({"TOOLS_Name": f"{COMP_DETAILED_TILE_PREFIX}_Merge_{tile_x}_{tile_y}"})
        merge.SceneInput1= displace
        flow.SetPos(merge, position_x+7, position_y+2)

        time.sleep(2)

        #mainmapmerge = comp.FindTool({COMP_MAINMAPMERGE_NAME})
        self._mainmapmerge[f"SceneInput{self._tilecounter}"] = merge
        displace.Scale.SetExpression(f"{COMP_MAPSETTINGS_NAME}.mapDisplace")
        plane["SurfacePlaneInputs"].SubdivisionWidth.SetExpression(f"{COMP_MAPSETTINGS_NAME}.MapSubdivisions")
        plane["MtlStdInputs"].Diffuse.Opacity.SetExpression(f"{COMP_MAPSETTINGS_NAME}.DetailedVisibility")
        self._tilecounter += 1

        
def buildpolygon(name, points, height, width, closed = 0):

    returnstring = '{'
    returnstring += '   Tools = ordereddict() {'
    returnstring += f'      {name}' + ' = PolylineMask {'
    returnstring += '           DrawMode = "ClickAppend",'
    returnstring += '           DrawMode2 = "InsertAndModify",'
    returnstring += '           CtrlWZoom = false,'
    returnstring += '           Inputs = {'
    returnstring += '               Filter = Input { Value = FuID { "Fast Gaussian" }, },'
    returnstring += '               OutputSize = Input { Value = FuID { "Custom" }, },'
    returnstring += '               CapStyle = Input { Value = 2, },'
    returnstring += '               MaskWidth = Input { Value = ' f'{width}' + ', },'
    returnstring += '               MaskHeight = Input { Value = ' + f'{height}' + ', },'
    returnstring += '               PixelAspect = Input { Value = {1, 1 }, },'
    returnstring += '               ClippingMode = Input { Value = FuID { "None" }, },'
    returnstring += '               Polyline = Input {'
    returnstring += '                   Value = Polyline {'
    if closed == 1:
        returnstring += '                       Closed = true,'
    returnstring += '                       Points = {'

    #Points
    for point in points:
        returnstring += '                           { Linear = true, X = ' + f'{point.X}' + ', Y = ' + f'{point.Y}' + ' },'
    
    returnstring += '                       }'
    returnstring += '                   },'
    returnstring += '               },'
    returnstring += '               Polyline2 = Input {'
    returnstring += '                   Value = Polyline {'
    returnstring += '                   },'
    returnstring += '                   Disabled = true,'
    returnstring += '               }'
    returnstring += '           },'
    returnstring += '           ViewInfo = OperatorInfo { Pos = { 4600.94, 3072.32 } },'
    returnstring += '       }'
    returnstring += '   },'
    returnstring += '   ActiveTool = "' + name + '"'
    returnstring += '}'

    return returnstring