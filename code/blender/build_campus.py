"""Build a first-pass, metric 3D map of the BaselHack challenge area in Blender.

Run inside Blender: exec(compile(open(__file__).read(), __file__, 'exec'))
The OSM extract is a source of footprints and street geometry, not surveyed heights.
"""
from pathlib import Path
from collections import Counter
import json, math, random, xml.etree.ElementTree as ET
import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'assets/campus-map/source.osm'
ROOF_COLORS = ROOT / 'assets/campus-map/roof-colors.json'
OUT = ROOT / 'assets/campus-map/scene.blend'
PREVIEW = ROOT / 'assets/campus-map/overview.png'
TOPDOWN = ROOT / 'assets/campus-map/topdown.png'
DETAIL = ROOT / 'assets/campus-map/ring-detail.png'
SOUTH = ROOT / 'assets/campus-map/south-detail.png'
LON0, LAT0 = 7.59825, 47.48785
LON_MIN, LON_MAX = 7.5944, 7.6021
LAT_MIN, LAT_MAX = 47.4854, 47.4903
SX = 111320 * math.cos(math.radians(LAT0))
SY = 111132

def xy(lon, lat): return ((lon-LON0)*SX, (lat-LAT0)*SY)
XMIN,YMIN = xy(LON_MIN,LAT_MIN)
XMAX,YMAX = xy(LON_MAX,LAT_MAX)

tree = ET.parse(SOURCE).getroot()
nodes = {el.attrib['id']:(float(el.attrib['lon']),float(el.attrib['lat']),{t.attrib['k']:t.attrib['v'] for t in el.findall('tag')}) for el in tree.findall('node')}
ways=[]
for el in tree.findall('way'):
    refs=[n.attrib['ref'] for n in el.findall('nd')]
    tags={t.attrib['k']:t.attrib['v'] for t in el.findall('tag')}
    ways.append((el.attrib['id'],refs,tags))
roof_rgb_by_way=json.loads(ROOF_COLORS.read_text())['rgb_by_osm_way']

# Keep the earlier study scene intact in the running Blender session.
scene=bpy.data.scenes.new('Christoph-Merian-Ring Campus')
for window in bpy.context.window_manager.windows: window.scene=scene
scene.unit_settings.system='METRIC'
scene.render.engine='BLENDER_EEVEE'
scene.render.image_settings.file_format='PNG'
scene.render.film_transparent=False
scene.render.resolution_percentage=100
scene.render.resolution_x=1600
scene.render.resolution_y=1200
scene.world=bpy.data.worlds.new('Cloudy Basel daylight')
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(0.72,0.78,0.83,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=0.65

def coll(name):
    c=bpy.data.collections.new(name); scene.collection.children.link(c); return c
ground_c=coll('01 Ground and green space')
road_c=coll('02 Streets and paths')
build_c=coll('03 OSM building footprints')
detail_c=coll('04 Christoph-Merian-Ring detail')
parking_c=coll('05 Bicycle parking prototypes')
tree_c=coll('06 Trees')
annot_c=coll('07 Wayfinding and source notes')
light_c=coll('08 Lighting and cameras')

def mat(name,color,metal=0,rough=0.8,alpha=1):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,alpha); m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Metallic'].default_value=metal; bs.inputs['Roughness'].default_value=rough
    bs.inputs['Alpha'].default_value=alpha
    if alpha<1:
        try:m.surface_render_method='DITHERED'
        except:pass
    return m
asphalt=mat('Asphalt charcoal',(0.21,0.22,0.23))
ring_asphalt=mat('Christoph Merian Ring asphalt',(0.18,0.19,0.20))
sidewalk=mat('Concrete sidewalks',(0.38,0.39,0.40))
base=mat('Campus ground',(0.37,0.40,0.37))
grass=mat('Lawn',(0.26,0.31,0.25))
stripe=mat('Road markings',(0.85,0.84,0.72))
facades=[mat('Facade %02d'%i,c) for i,c in enumerate([(0.64,0.67,0.68),(0.73,0.73,0.69),(0.50,0.56,0.59),(0.68,0.66,0.62),(0.54,0.57,0.55)])]
silver_facade=mat('South Ring silver panel facade',(0.70,0.72,0.73),0.15,0.6)
roofs=[mat('Roof %02d'%i,c) for i,c in enumerate([(0.23,0.27,0.29),(0.39,0.43,0.45),(0.51,0.52,0.49),(0.32,0.36,0.38)])]
def srgb_to_linear(value):
    c=value/255
    return c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4
sampled_roofs={wid:mat('Aerial sampled roof OSM '+wid,tuple(srgb_to_linear(c) for c in rgb)) for wid,rgb in roof_rgb_by_way.items()}
glass=mat('Tinted office glazing',(0.12,0.23,0.29),0.1,0.24)
dark_band=mat('South Ring dark horizontal glazing',(0.10,0.14,0.17),0.08,0.3)
steel=mat('Galvanized steel',(0.45,0.49,0.50),0.6,0.45)
dark_steel=mat('Shelter frame',(0.22,0.26,0.29),0.6,0.45)
translucent=mat('Frosted canopy',(0.57,0.70,0.72),0,0.35,0.62)
orange=mat('Approximate parking zone markers',(0.95,0.38,0.06),0.1,0.35)
leaf=mat('Autumn foliage',(0.32,0.38,0.18))
trunk=mat('Tree bark',(0.23,0.18,0.14))

def mesh(name,verts,faces,ma,co):
    me=bpy.data.meshes.new(name+' mesh'); me.from_pydata(verts,[],faces); me.materials.append(ma); me.update()
    ob=bpy.data.objects.new(name,me); co.objects.link(ob); return ob
def box(name,x,y,z,dx,dy,dz,ma,co,angle=0):
    hx,hy,hz=dx/2,dy/2,dz/2
    v=[(-hx,-hy,-hz),(hx,-hy,-hz),(hx,hy,-hz),(-hx,hy,-hz),(-hx,-hy,hz),(hx,-hy,hz),(hx,hy,hz),(-hx,hy,hz)]
    f=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    ob=mesh(name,v,f,ma,co); ob.location=(x,y,z); ob.rotation_euler[2]=angle; return ob
def segment(name,a,b,width,z,ma,co):
    ax,ay=a; bx,by=b; dx,dy=bx-ax,by-ay; ln=math.hypot(dx,dy)
    if ln<0.05:return None
    return box(name,(ax+bx)/2,(ay+by)/2,z,ln,width,0.045,ma,co,math.atan2(dy,dx))
def path(name,pts,width,z,ma,co):
    # One joined strip per mapped way avoids rectangular spikes at road bends.
    clean=[pts[0]]
    for p in pts[1:]:
        if math.hypot(p[0]-clean[-1][0],p[1]-clean[-1][1])>0.03:clean.append(p)
    if len(clean)<2:return None
    left=[];right=[]
    for i,p in enumerate(clean):
        a=clean[max(0,i-1)];b=clean[min(len(clean)-1,i+1)]
        tx,ty=b[0]-a[0],b[1]-a[1];length=math.hypot(tx,ty)
        if length<0.01:continue
        nx,ny=-ty/length,tx/length
        if 0<i<len(clean)-1:
            pa=clean[i-1];pb=clean[i+1]
            ax,ay=p[0]-pa[0],p[1]-pa[1];bx,by=pb[0]-p[0],pb[1]-p[1]
            al,bl=math.hypot(ax,ay),math.hypot(bx,by)
            if al>0 and bl>0:
                n0=(-ay/al,ax/al);dot=max(0.55,nx*n0[0]+ny*n0[1])
                width_factor=min(1.8,1/dot)
            else:width_factor=1
        else:width_factor=1
        d=width*0.5*width_factor
        left.append((p[0]+nx*d,p[1]+ny*d,z));right.append((p[0]-nx*d,p[1]-ny*d,z))
    verts=left+right;n=len(left)
    return mesh(name,verts,[(i,i+1,n+i+1,n+i) for i in range(n-1)],ma,co)
def cylinder(name,center,radius,depth,ma,co,vertices=8):
    x,y,z=center; v=[]
    for h in [-depth/2,depth/2]:
        for i in range(vertices):
            t=2*math.pi*i/vertices;v.append((x+radius*math.cos(t),y+radius*math.sin(t),z+h))
    f=[tuple(range(vertices-1,-1,-1)),tuple(range(vertices,2*vertices))]
    f += [(i,(i+1)%vertices,(i+1)%vertices+vertices,i+vertices) for i in range(vertices)]
    return mesh(name,v,f,ma,co)
def poly(name,pts,z0,z1,wall,roof,co):
    if len(pts)<3:return None
    if pts[0]==pts[-1]:pts=pts[:-1]
    if len(pts)<3:return None
    n=len(pts); v=[(x,y,z0) for x,y in pts]+[(x,y,z1) for x,y in pts]
    f=[]
    try:
        for tri in tessellate_polygon([[Vector((x,y,z1)) for x,y in pts]]):
            ids=[]
            for p in tri:ids.append(min(range(n),key=lambda i:(pts[i][0]-p.x)**2+(pts[i][1]-p.y)**2)+n)
            f.append(tuple(ids))
    except: f.append(tuple(range(n,2*n)))
    f += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    ob=mesh(name,v,f,wall,co)
    ob.data.materials.append(roof)
    for face in ob.data.polygons[:len(f)-n]:face.material_index=1
    return ob

# A complete, neutral base; mapped ways below supply all blocks in the screenshot.
box('Ground',0,0,-0.18,XMAX-XMIN+35,YMAX-YMIN+35,0.35,base,ground_c)
counts=Counter()
building_records=[]
for wid,refs,tags in ways:
    pts=[xy(*nodes[r][:2]) for r in refs if r in nodes]
    if len(pts)<2:continue
    if 'landuse' in tags and tags['landuse'] in ('grass','meadow','forest') and refs[0]==refs[-1]:
        ob=poly('Green space '+wid,pts,0.02,0.045,grass,grass,ground_c); counts['green']+=bool(ob)
    if 'building' in tags and tags['building'] not in ('no','roof') and refs[0]==refs[-1]:
        cx=sum(x for x,y in pts[:-1])/(len(pts)-1);cy=sum(y for x,y in pts[:-1])/(len(pts)-1)
        if not (XMIN-30<cx<XMAX+30 and YMIN-30<cy<YMAX+30):continue
        area=abs(sum(pts[i][0]*pts[i+1][1]-pts[i+1][0]*pts[i][1] for i in range(len(pts)-1)))/2
        try:h=float(tags.get('height','').replace('m',''))
        except:
            try:h=float(tags.get('building:levels',''))*3.4
            except:h=7.5+min(16,math.sqrt(max(area,1))*0.18)
        h=max(3,min(42,h))
        k=int(wid)%len(facades)
        roof_material=sampled_roofs.get(wid,roofs[int(wid)%len(roofs)])
        wall_material=silver_facade if wid=='238805703' else facades[k]
        ob=poly('Building OSM '+wid,pts,0.12,h,wall_material,roof_material,build_c)
        if ob:
            ob['osm_id']=wid;ob['height_source']='OSM' if 'height' in tags or 'building:levels' in tags else 'estimated from footprint'
            ob['roof_color_source']='user supplied aerial screenshot' if wid in sampled_roofs else 'fallback palette'
            ob['height_m']=round(h,1);building_records.append((wid,cx,cy,h,area,pts));counts['buildings']+=1
    elif tags.get('building')=='roof' and refs[0]==refs[-1] and tags.get('amenity')!='bicycle_parking':
        ob=poly('Mapped roof '+wid,pts,3.6,3.86,steel,roofs[int(wid)%len(roofs)],build_c)
        if ob:ob['osm_id']=wid;ob['height_source']='illustrative roof clearance';counts['mapped_roofs']+=1
    if 'highway' in tags:
        hw=tags['highway'];name=tags.get('name','')
        w={'motorway':18,'primary':10,'secondary':8,'tertiary':7,'residential':5.8,'service':4.8,'living_street':4.8,'footway':2.0,'cycleway':2.2,'path':1.8,'pedestrian':4.0}.get(hw,4.5)
        isring='Christoph Merian' in name
        ma=ring_asphalt if isring else (sidewalk if hw in ('footway','path','pedestrian','cycleway') else asphalt)
        if hw not in ('motorway','footway','path','cycleway','pedestrian'):
            path((name or hw)+' sidewalks '+wid,pts,w+3,0.07,sidewalk,road_c)
        path((name or hw)+' road '+wid,pts,w,0.12,ma,detail_c if isring else road_c)
        counts['road_ways']+=1
        if isring:
            counts['ring_ways']+=1
            # Sparse centre dashes expose street alignment at both map and detail scale.
            for a,b in zip(pts,pts[1:]):
                d=Vector((b[0]-a[0],b[1]-a[1]));length=d.length
                if length<6:continue
                u=d.normalized();steps=int(length//12)
                for j in range(steps):
                    t=5+j*12; p=(a[0]+u.x*t,a[1]+u.y*t);q=(p[0]+u.x*3,p[1]+u.y*3)
                    segment('Ring centre dash',p,q,0.17,0.17,stripe,detail_c)

# Legible block faces and rooftop equipment around the bike parking corridor.
rng=random.Random(18)
for wid,cx,cy,h,area,pts in building_records:
    if not (abs(cx)<195 and abs(cy)<175 and area>120):continue
    if abs(cx-xy(7.6003,LAT0)[0])>85 and abs(cx-xy(7.5988,LAT0)[0])>95:continue
    if wid=='238805703':
        # Street View (September 2023): pale panel frontage with long, dark
        # horizontal glazing beside the south stretch of the Ring.
        south_edge_y=min(p[1] for p in pts)
        for edge_index,(a,b) in enumerate(zip(pts,pts[1:])):
            length=math.dist(a,b)
            if length<10 or (a[1]+b[1])/2>south_edge_y+10:continue
            dx,dy=(b[0]-a[0])/length,(b[1]-a[1])/length
            angle=math.atan2(dy,dx)
            for z in (4.1,8.2,12.3,16.4):
                if z+0.7>=h:continue
                box('South Ring glazing band '+str(edge_index),
                    (a[0]+b[0])/2,(a[1]+b[1])/2,z,
                    length-0.8,0.11,0.9,dark_band,detail_c,angle)
        counts['detailed_buildings']+=1
        continue
    # Place glazing on actual footprint edges, rather than across a bounding box.
    n=min(5,max(1,int(h/4)))
    for edge_index,(a,b) in enumerate(zip(pts,pts[1:])):
        length=math.dist(a,b)
        if length<12:continue
        dx,dy=(b[0]-a[0])/length,(b[1]-a[1])/length
        angle=math.atan2(dy,dx)
        bays=min(18,int(length/5.5))
        for floor in range(n):
            z=3.1+floor*3.3
            if z+1.15>=h:break
            for bay in range(bays):
                t=(bay+0.5)*length/bays
                x,y=a[0]+dx*t,a[1]+dy*t
                box('Facade glazing '+wid+' '+str(edge_index),x,y,z,2.7,0.10,1.05,glass,detail_c,angle)
    if area>800:
        for i in range(min(3,int(area/1300)+1)):
            x=cx+(i-1)*min(9,math.sqrt(area)/5);y=cy
            box('Roof service unit '+wid,x,y,h+0.7,3.5,2.4,1.3,steel,detail_c)
    counts['detailed_buildings']+=1

# Mapped shelter geometry and two user-marked wayfinding anchors.
def tube(name,a,b,r,ma,co):
    av,bv=Vector(a),Vector(b); d=bv-av; mid=(av+bv)/2
    ob=cylinder(name,(0,0,0),r,d.length,ma,co,8); ob.location=mid
    ob.rotation_euler=d.to_track_quat('Z','Y').to_euler();return ob
def rack(name,x,y,z=0.2,theta=0):
    ux,uy=math.cos(theta),math.sin(theta);vx,vy=-uy,ux
    points=[]
    for i in range(9):
        t=math.pi*i/8
        points.append((x+ux*(0.38*math.cos(t)),y+uy*(0.38*math.cos(t)),z+0.8*math.sin(t)))
    for i,(a,b) in enumerate(zip(points,points[1:])):tube(name+' arc '+str(i),a,b,0.026,steel,parking_c)

roof_way=next((refs for wid,refs,tags in ways if wid=='1463536691'),None)
if roof_way is None:raise RuntimeError('Mapped bicycle shelter OSM way 1463536691 is missing')
roof_pts=[xy(*nodes[r][:2]) for r in roof_way if r in nodes]
flat_x=sum(p[0] for p in roof_pts[:-1])/(len(roof_pts)-1)
flat_y=sum(p[1] for p in roof_pts[:-1])/(len(roof_pts)-1)
flat=poly('ParkingZone.NorthMappedBicycleRoof',roof_pts,3.0,3.16,steel,steel,parking_c)
flat['zone_id']='CMR_NORTH_01'
flat['osm_id']='1463536691'
flat['footprint_source']='OpenStreetMap bicycle_parking roof'
flat['capacity']='unverified'
flat['anchor_source']='north user heart, near Foodtruck Charlie Brown'
flat['physical_dimensions']='mapped roof footprint approximately 2.7 m x 53 m'
flat_min_y=min(y for x,y in roof_pts);flat_max_y=max(y for x,y in roof_pts)
for y in [flat_min_y+1.5+i*6.5 for i in range(8)]:
    for x in (flat_x-1.2,flat_x+1.2):
        box('North shelter steel post',x,y,1.51,0.12,0.12,2.95,dark_steel,parking_c)
    box('North roof transverse rib',flat_x,y,3.24,2.8,0.11,0.08,dark_steel,parking_c)
for i in range(29):
    y=flat_min_y+1.3+i*1.75
    rack('North covered bicycle rack',flat_x,y,0.17,math.pi/2)
counts['mapped_bicycle_roofs']=1

# A separate short glass-and-steel shelter is visible at 35 Christoph
# Merian-Ring in September 2023 Street View. Its purpose and dimensions
# cannot be confirmed from the imagery, so keep it distinct from the
# mapped 53 m bicycle roof and mark its measurements as approximate.
sx,sy=xy(7.60004,47.486835)
short_roof=box('South Ring short street shelter roof',sx,sy,2.73,7.2,2.55,0.16,steel,parking_c)
short_roof['source']='Google Maps Street View, September 2023'
short_roof['purpose']='unverified'
short_roof['dimensions']='approximate from street imagery'
for ox in (-3.35,3.35):
    for oy in (-1.12,1.12):
        box('South short shelter post',sx+ox,sy+oy,1.38,0.11,0.11,2.72,dark_steel,parking_c)
for ox in (-1.72,1.72):
    box('South short shelter glass panel',sx+ox,sy+1.17,1.38,3.3,0.055,2.55,translucent,parking_c)
box('South short shelter bench',sx,sy+0.57,0.53,3.9,0.43,0.11,dark_steel,parking_c)
for ox in (-1.7,1.7):
    box('South short shelter bench support',sx+ox,sy+0.57,0.27,0.08,0.35,0.54,dark_steel,parking_c)
counts['street_view_shelters']=1

# The hearts are virtual wayfinding icons, not surveyed physical structures.
north_lonlat=(7.60032,47.48815)
south_lonlat=(7.59984,47.48678)
marker_points=[('NORTH',north_lonlat,'CMR_NORTH_01'),('SOUTH',south_lonlat,'CMR_SOUTH_02')]
pink=mat('Heart markers',(0.91,0.03,0.29),0.05,0.42)
white=mat('Marker white',(0.94,0.95,0.90),0,0.45)

def heart_marker(label,lonlat,zone_id):
    x,y=xy(*lonlat)
    anchor=cylinder('WayfindingHeart.'+label,(x,y,0.26),5.0,0.10,pink,annot_c,32)
    anchor['zone_id']=zone_id;anchor['longitude']=lonlat[0];anchor['latitude']=lonlat[1]
    anchor['marker_type']='user supplied map heart';anchor['is_physical_structure']=False
    if label=='NORTH':anchor['screenshot_heart_approx_lonlat']='7.60054,47.48815; snapped to mapped Ring centreline'
    cylinder('Heart marker stem '+label,(x,y,6.0),0.24,11.6,pink,annot_c,12)
    cylinder('Heart marker face '+label,(x,y,12.1),5.5,0.35,white,annot_c,32)
    v=[]
    for i in range(65):
        t=2*math.pi*i/64
        hx=16*math.sin(t)**3/17
        hy=(13*math.cos(t)-5*math.cos(2*t)-2*math.cos(3*t)-math.cos(4*t))/17
        v.append(Vector((x+hx*3.8,y+hy*3.8,12.32)))
    tris=tessellate_polygon([v[:-1]])
    heart_verts=[tuple(p) for p in v[:-1]]
    heart_faces=[]
    for tri in tris:
        heart_faces.append(tuple(q if isinstance(q,int) else min(range(64),key=lambda j:(v[j]-q).length_squared) for q in tri))
    mesh('Heart symbol '+label,heart_verts,heart_faces,pink,annot_c)
    txt=bpy.data.curves.new('Zone label '+label,'FONT');txt.body=label+'  /  '+zone_id;txt.size=4.0;txt.align_x='CENTER'
    ob=bpy.data.objects.new('Zone label '+label,txt);annot_c.objects.link(ob)
    ob.location=(x,y-9.5,12.45);txt.materials.append(white)
    return (x,y)

north_marker=heart_marker(*marker_points[0])
south_marker=heart_marker(*marker_points[1])
counts['heart_anchors']=2

# A thin orange overlay follows the mapped main street between the two hearts.
route=[north_marker,xy(7.60033,47.4877),xy(7.60033,47.4870),xy(7.60026,47.48684),xy(7.60010,47.48678),south_marker]
for a,b in zip(route,route[1:]):
    dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
    if length<0.01:continue
    ux,uy=dx/length,dy/length
    for j in range(int(length/8)+1):
        start=j*8+0.8;end=min(start+3.2,length)
        if end<=start:continue
        p=(a[0]+ux*start,a[1]+uy*start);q=(a[0]+ux*end,a[1]+uy*end)
        ob=segment('Virtual route between hearts',p,q,0.42,0.23,orange,annot_c)
        if ob:ob['is_physical_road_marking']=False

# Trees from mapped points, plus a restrained planted edge visible in the aerial.
for nid,(lon,lat,tags) in nodes.items():
    if tags.get('natural')!='tree':continue
    x,y=xy(lon,lat)
    if not (XMIN<x<XMAX and YMIN<y<YMAX):continue
    h=5.5+(int(nid)%4)
    cylinder('OSM tree trunk '+nid,(x,y,h/2),0.22,h,trunk,tree_c)
    cylinder('OSM tree crown '+nid,(x,y,h+1.1),2.2,3.4,leaf,tree_c,12)
    counts['trees']+=1

def text_label(label,x,y,size=3.1):
    cu=bpy.data.curves.new(label,'FONT');cu.body=label;cu.size=size;cu.align_x='CENTER'
    ob=bpy.data.objects.new('Label '+label,cu);annot_c.objects.link(ob)
    ob.location=(x,y,0.30);cu.materials.append(stripe);return ob
text_label('CHRISTOPH MERIAN RING',*xy(7.59898,47.48870),5)
text_label('KAEGENSTRASSE',*xy(7.59778,47.48755),3)
text_label('BRUGGSTRASSE',*xy(7.59820,47.49002),3)
text_label('MAPPED BICYCLE ROOF',flat_x,flat_y,2)

def camera(name,location,target,ortho):
    data=bpy.data.cameras.new(name);ob=bpy.data.objects.new(name,data);light_c.objects.link(ob)
    ob.location=location;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()
    data.type='ORTHO';data.ortho_scale=ortho;return ob
overview=camera('Oblique campus overview',(360,-440,680),(0,0,0),585)
plan=camera('North-up campus plan',(0,0,790),(0,0,0),660)
detail=camera('North bicycle shelter detail',(270,-145,160),(*north_marker,0),145)
south_detail=camera('South heart detail',(240,-250,150),(*south_marker,0),145)
sun_data=bpy.data.lights.new('Soft daylight','AREA');sun=bpy.data.objects.new('Soft daylight',sun_data);light_c.objects.link(sun)
sun.location=(-250,-150,420);sun_data.energy=12000;sun_data.shape='DISK';sun_data.size=450
sun.rotation_euler=(Vector((0,0,0))-sun.location).to_track_quat('-Z','Y').to_euler()
scene.camera=overview
scene.render.filepath=str(PREVIEW)
scene.view_settings.view_transform='Standard'
scene.view_settings.look='Medium High Contrast'
scene.view_settings.exposure=0.35
scene.render.image_settings.color_mode='RGBA'
scene['source']='OpenStreetMap building and street geometry, extract 2026-10-30'
scene['height_accuracy']='Approximate; no surveyed height data for most buildings'
scene['parking_accuracy']='North roof footprint from OSM way 1463536691; posts/racks/height illustrative. Two heart positions interpreted from user screenshot; south physical facility unverified.'
scene['scale']='1 Blender unit = 1 metre; horizontal locations from OSM projected locally'
scene['map_bounds']='7.5944,47.4854,7.6021,47.4903'

# Save first, so even a render error leaves a usable editable model.
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
bpy.ops.render.render(write_still=True,scene=scene.name)
scene.camera=detail;scene.render.resolution_x=1600;scene.render.resolution_y=1000
scene.render.filepath=str(DETAIL)
bpy.ops.render.render(write_still=True,scene=scene.name)
scene.camera=south_detail;scene.render.resolution_x=1600;scene.render.resolution_y=1000
scene.render.filepath=str(SOUTH)
bpy.ops.render.render(write_still=True,scene=scene.name)
scene.camera=plan;scene.render.resolution_x=1400;scene.render.resolution_y=1400
scene.render.filepath=str(TOPDOWN)
bpy.ops.render.render(write_still=True,scene=scene.name)
scene.camera=overview;scene.render.resolution_x=1600;scene.render.resolution_y=1200
scene.render.filepath='//overview.png'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
result={'scene':scene.name,'objects':len(scene.objects),'counts':dict(counts),'blend':str(OUT),'overview':str(PREVIEW),'topdown':str(TOPDOWN),'north_detail':str(DETAIL),'south_detail':str(SOUTH)}
