"""Original illustrative machining cell. Run with Blender --background --python.

Geometry is authored here, not imported from the organizer or a manufacturer.
The three named assemblies are evidence navigation targets, not fault diagnoses.
"""
import bpy
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets'
OUT.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

def material(name, color, metallic=0, rough=.4):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = rough
    return m

ivory = material('Ceramic | warm ivory', (.64,.66,.62), .3)
dark = material('Frame | graphite', (.045,.065,.075), .65)
steel = material('Machined | brushed steel', (.3,.38,.4), .85,.26)
copper = material('Signal | copper', (.8,.3,.12), .65,.28)
rubber = material('Isolation | rubber', (.017,.025,.028), 0,.8)
glass = material('Inspection | blue graphite', (.035,.12,.15), .6,.19)

groups = {}
for name in ['drive','process_chamber','tool_head','structure']:
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    groups[name] = obj

def finish(obj, name, mat, group, bevel=.025):
    obj.name = name
    obj.data.materials.append(mat)
    obj.parent = groups[group]
    if bevel:
        mod = obj.modifiers.new('Machined edge', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return obj

def box(name, loc, scale, mat=dark, group='structure', bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(o,name,mat,group,bevel)

def cyl(name,loc,radius,depth,mat=steel,group='structure',axis='Z',vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=loc)
    o=bpy.context.object
    if axis=='X': o.rotation_euler[1]=math.pi/2
    if axis=='Y': o.rotation_euler[0]=math.pi/2
    return finish(o,name,mat,group,.012)

# Shared machine bed and isolated feet.
box('Monolithic bed',(0,0,.35),(5.8,2.5,.55))
box('Bed inset',(0,-1.26,.4),(5.3,.035,.17),steel)
box('Copper datum',(0,-1.285,.49),(4.9,.025,.035),copper)
for x in [-2.35,2.35]:
    for y in [-.88,.88]:
        cyl('Isolation foot',(x,y,.05),.23,.2,rubber)
        cyl('Leveling bolt',(x,y,.19),.1,.14)
for y in [-.7,.7]:
    box('Precision rail',(0,y,.73),(5.3,.17,.15),steel)
    for x in [-2,-1,0,1,2]: cyl('Rail fastener',(x,y,.815),.037,.014,dark,vertices=12)

# Finned drive assembly on the left, with exposed shaft and coupling.
box('Motor pedestal',(-1.85,0,.99),(1.35,1.55,.42),ivory,'drive')
cyl('Motor casing',(-1.95,0,1.63),.6,1.15,dark,'drive','X')
for x in [-2.48+i*.12 for i in range(9)]:
    cyl('Cooling fin',(x,0,1.63),.65,.035,steel,'drive','X')
cyl('Drive cover',(-2.57,0,1.63),.55,.1,ivory,'drive','X')
cyl('Spindle shaft',(-1.08,0,1.63),.15,.7,steel,'drive','X')
cyl('Flexible coupling',(-.95,0,1.63),.27,.22,copper,'drive','X')
box('Terminal housing',(-1.94,0,2.27),(.46,.5,.24),ivory,'drive')
for y in [-.35,.35]:
    cyl('Pedestal bolt',(-1.8,y,1.22),.07,.035,dark,'drive',vertices=6)

# Enclosed process chamber with deliberate open inspection face.
box('Chamber tray',(.48,0,1.02),(1.9,1.72,.42),ivory,'process_chamber')
box('Rear enclosure',(.48,.78,1.9),(1.9,.16,1.45),ivory,'process_chamber')
box('Roof',(.48,0,2.64),(1.9,1.72,.14),ivory,'process_chamber')
for x in [-.43,1.39]:
    box('Enclosure column',(x,-.76,1.9),(.13,.17,1.5),ivory,'process_chamber')
box('Inspection header',(.48,-.84,2.39),(1.68,.08,.18),glass,'process_chamber')
box('Chamber working plate',(.48,0,1.29),(1.6,1.42,.12),steel,'process_chamber')
for x in [-.1,.2,.5,.8,1.1]:
    box('T slot',(x,0,1.355),(.035,1.3,.012),dark,'process_chamber',0)
cyl('Workpiece',(.48,0,1.52),.32,.3,copper,'process_chamber')
box('Rear service strip',(.48,.677,2.27),(1.3,.03,.035),copper,'process_chamber')

# Tool tower, carriage, spindle and cutting tool.
box('Tool tower',(2.05,.35,1.73),(.72,1.1,1.95),ivory,'tool_head')
for x in [1.85,2.25]: box('Vertical guide',(x,-.24,1.9),(.08,.09,1.55),steel,'tool_head')
box('Tool carriage',(2.05,-.36,2.08),(.84,.32,.65),dark,'tool_head')
box('Spindle arm',(1.45,-.3,2.12),(1.1,.42,.33),steel,'tool_head')
cyl('Tool spindle',(1.08,-.3,1.93),.18,.5,dark,'tool_head')
cyl('Collet',(1.08,-.3,1.62),.12,.17,copper,'tool_head')
cyl('Cutting tool',(1.08,-.3,1.4),.045,.3,steel,'tool_head',vertices=12)
for z in [1.3,1.6,1.9,2.2,2.5]:
    box('Tower vent',(2.42,.35,z),(.025,.62,.035),dark,'tool_head',0)

# Identifiable control panel and fasteners, all original geometry.
box('Control arm',(2.57,-.64,1.45),(.13,.65,.1),steel)
box('Operator panel',(2.57,-.99,1.8),(.55,.16,.65),dark)
box('Display',(2.57,-1.08,1.9),(.42,.02,.31),glass)
for x,mat in [(2.42,copper),(2.57,ivory),(2.72,steel)]:
    cyl('Control button',(x,-1.09,1.62),.045,.03,mat,axis='Y')
for x in [-2.7,2.7]:
    for y in [-1.08,1.08]: cyl('Bed bolt',(x,y,.64),.065,.03,steel,vertices=6)

bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'machining-cell.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'machining-cell.glb'),export_format='GLB',export_apply=True)
print('Original machine exported:', OUT/'machining-cell.glb')
