"""CARS Auto Center - carro 3D para o pré-diagnóstico do site.

Gera um hatch estilizado com cada sistema mecânico como objeto separado
(motor, correia, câmbio, bateria, arrefecimento, escapamento, suspensão,
freios, pneus, iluminação), exporta GLB para o three.js e renderiza a
imagem do hero com Cycles.

Uso:  blender -b --factory-startup -P 3d/carro.py            (tudo)
      blender -b --factory-startup -P 3d/carro.py -- glb     (só o GLB)
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ONLY_GLB = "glb" in ARGS

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
col = scene.collection

# ------------------------------------------------------------------ util
def smooth_curve(pts, x):
    """Catmull-Rom 1D sobre pontos (x, v) ordenados por x."""
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for i in range(len(pts) - 1):
        x0, v0 = pts[i]
        x1, v1 = pts[i + 1]
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            vm = pts[i - 1][1] if i > 0 else v0
            vp = pts[i + 2][1] if i + 2 < len(pts) else v1
            m0 = (v1 - vm) / 2
            m1 = (vp - v0) / 2
            t2, t3 = t * t, t * t * t
            return (2*t3 - 3*t2 + 1)*v0 + (t3 - 2*t2 + t)*m0 + (-2*t3 + 3*t2)*v1 + (t3 - t2)*m1
    return pts[-1][1]

def sgnpow(v, p):
    return math.copysign(abs(v) ** p, v)

def mesh_obj(name, bm, mats, smooth=True, angle=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    for m in mats:
        me.materials.append(m)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    if angle is not None:
        bpy.context.view_layer.objects.active = ob
        for o in bpy.context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))
        ob.select_set(False)
    return ob

def set_origin(ob, point):
    """Move a origem do objeto para `point` sem mover a geometria."""
    p = Vector(point)
    ob.data.transform(Matrix.Translation(-p))
    ob.location = p

# ------------------------------------------------------------------ materiais
def mat(name, color, metal=0.0, rough=0.5, coat=0.0, emit=None, emit_str=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.05
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = emit_str
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            pass
    return m

def srgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)

M = {
    "paint":   mat("Pintura", srgb("#c4161c"), metal=0.35, rough=0.28, coat=1.0),
    "roof":    mat("Teto", srgb("#0d0d0f"), rough=0.12, coat=1.0),
    "trim":    mat("Acabamento", srgb("#101012"), rough=0.35),
    "glass":   mat("Vidro", srgb("#0c1116"), rough=0.04, coat=1.0),
    "tire":    mat("Pneu", srgb("#161617"), rough=0.86),
    "rim":     mat("Roda", srgb("#c9ccd2"), metal=1.0, rough=0.22),
    "disc":    mat("Disco", srgb("#8b8e94"), metal=1.0, rough=0.42),
    "caliper": mat("Pinca", srgb("#e1251b"), rough=0.35, coat=0.6),
    "alu":     mat("Aluminio", srgb("#a4a8ae"), metal=1.0, rough=0.38),
    "cover":   mat("Tampa", srgb("#1b1b1e"), rough=0.3, coat=0.5),
    "red":     mat("Vermelho", srgb("#d42a20"), rough=0.4),
    "rubber":  mat("Borracha", srgb("#202022"), rough=0.7),
    "spring":  mat("Mola", srgb("#e1251b"), rough=0.35, metal=0.3),
    "steel":   mat("Aco", srgb("#6d7077"), metal=1.0, rough=0.35),
    "chrome":  mat("Cromo", srgb("#d9dadd"), metal=1.0, rough=0.12),
    "battery": mat("Bateria", srgb("#1f2329"), rough=0.5),
    "tank":    mat("Reservatorio", srgb("#e8e6df"), rough=0.3),
    "radiator":mat("Radiador", srgb("#2b2d31"), metal=0.7, rough=0.45),
    "head":    mat("Farol", srgb("#f4f1ea"), rough=0.08, emit=srgb("#fff4de"), emit_str=2.0),
    "tail":    mat("Lanterna", srgb("#7a0d0d"), rough=0.1, emit=srgb("#ff2a1f"), emit_str=1.6),
    "grille":  mat("Grade", srgb("#0b0b0c"), rough=0.55),
}

# ------------------------------------------------------------------ geometria base
L = 2.07          # meio comprimento
W = 0.86          # meia largura
WX = 1.30         # posição dos eixos (+-)
WR = 0.33         # raio do pneu
WZ = 0.33         # altura do centro da roda
WY = 0.765        # bitola (meia)
ARCH = 0.385      # raio da caixa de roda

TOP = [(-2.07, 0.82), (-2.02, 0.93), (-1.85, 0.975), (-1.2, 0.985), (0.85, 0.975),
       (1.25, 0.945), (1.65, 0.895), (1.90, 0.845), (2.01, 0.78), (2.07, 0.60)]
BOT = [(-2.07, 0.42), (-2.0, 0.31), (-1.85, 0.255), (-1.5, 0.245), (1.5, 0.245),
       (1.88, 0.26), (2.0, 0.30), (2.07, 0.40)]

def bottom_at(x):
    b = smooth_curve(BOT, x)
    for wx in (-WX, WX):
        d = x - wx
        if abs(d) < ARCH:
            b = max(b, WZ + math.sqrt(ARCH * ARCH - d * d))
    return b

def xs_cos(n, a, b):
    return [a + (b - a) * (0.5 - 0.5 * math.cos(math.pi * i / (n - 1))) for i in range(n)]

def loft(name, xs, ring, m_count, mats, assign=None):
    bm = bmesh.new()
    rings = []
    for x in xs:
        rings.append([bm.verts.new(v) for v in ring(x, m_count)])
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(m_count):
            k = (j + 1) % m_count
            bm.faces.new((a[j], a[k], b[k], b[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # o anel quase sem largura nas pontas confunde o recalc: confere pelo volume com sinal
    bm.normal_update()
    vol = sum(f.calc_center_median().dot(f.normal) * f.calc_area() for f in bm.faces) / 3
    if vol < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    print("LOFT", name, round(vol, 3))
    if assign:
        bm.normal_update()
        for f in bm.faces:
            f.material_index = assign(f)
    return mesh_obj(name, bm, mats)

# carroceria inferior
def body_ring(x, m):
    top = smooth_curve(TOP, x)
    bot = bottom_at(x)
    zc, h = (top + bot) / 2, (top - bot) / 2
    w = W * max(1e-4, 1 - abs(x / L) ** 5) ** 0.2
    pts = []
    for j in range(m):
        t = 2 * math.pi * j / m
        c, s = math.cos(t), math.sin(t)
        y = w * sgnpow(c, 2 / 6.5)
        zn = sgnpow(s, 2 / 5.5)
        y *= 1 - 0.075 * max(0, zn) ** 2 - 0.035 * max(0, -zn) ** 2
        pts.append((x, y, zc + h * zn))
    return pts

body = loft("carroceria", xs_cos(170, -L * 0.9995, L * 0.9995), body_ring, 56, [M["paint"], M["trim"]],
            assign=lambda f: 1 if f.calc_center_median().z < 0.33 else 0)

# cabine (vidros + teto + colunas)
ROOF = [(-1.80, 0.93), (-1.72, 1.15), (-1.58, 1.34), (-1.30, 1.415), (-0.4, 1.43),
        (0.02, 1.41), (0.28, 1.30), (0.62, 1.11), (0.98, 0.93)]
CB = 0.90

def cabin_ring(x, m):
    top = smooth_curve(ROOF, x)
    top = max(top, CB + 0.012)
    zc, h = (top + CB) / 2, (top - CB) / 2
    w = 0.745 - 0.03 * max(0, x) / 0.98
    pts = []
    for j in range(m):
        t = 2 * math.pi * j / m
        c, s = math.cos(t), math.sin(t)
        y = w * sgnpow(c, 2 / 7)
        zn = sgnpow(s, 2 / 7)
        tt = (zn + 1) / 2
        y *= 1 - 0.19 * tt ** 1.4
        pts.append((x, y, zc + h * zn))
    return pts

def cabin_assign(f):
    c = f.calc_center_median()
    n = f.normal
    if n.z > 0.94 and -1.50 < c.x < 0.08:
        return 0                     # teto pintado
    if c.z < 1.0:
        return 1                     # borracha da janela
    if -0.60 < c.x < -0.47 and abs(n.y) > 0.5:
        return 1                     # coluna B
    if abs(n.y) > 0.5 and c.x > 0.16 and c.z > 1.0:
        return 2
    return 2

cabin = loft("cabine", xs_cos(130, -1.80, 0.98), cabin_ring, 64, [M["roof"], M["trim"], M["glass"]],
             assign=cabin_assign)

# ------------------------------------------------------------------ primitivas
def lathe(name, prof, center, side=1, segs=48, mats=(), axis_y=True, closed=True, angle=40):
    """Revolve perfil [(r, y)] em torno do eixo Y passando por `center`."""
    bm = bmesh.new()
    rings = []
    cx, cy, cz = center
    for i in range(segs):
        a = 2 * math.pi * i / segs
        rings.append([bm.verts.new((cx + r * math.cos(a), cy + y * side, cz + r * math.sin(a))) for r, y in prof])
    n = len(prof)
    for i in range(segs):
        a, b = rings[i], rings[(i + 1) % segs]
        rng = n if closed else n - 1
        for j in range(rng):
            k = (j + 1) % n
            try:
                bm.faces.new((a[j], a[k], b[k], b[j]))
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return mesh_obj(name, bm, list(mats), angle=angle)

def box(name, center, size, mat_, bevel=0.01, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    if bevel:
        bmesh.ops.bevel(bm, geom=bm.verts[:] + bm.edges[:], offset=bevel, segments=3, affect='EDGES')
    ob = mesh_obj(name, bm, [mat_], angle=35)
    ob.rotation_euler = rot
    ob.location = center
    return ob

def ellipsoid(name, center, scale, mat_, rot=(0, 0, 0), seg=32):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2]))
    ob = mesh_obj(name, bm, [mat_])
    ob.rotation_euler = rot
    ob.location = center
    return ob

def cyl_between(name, p0, p1, r, mat_, segs=20):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=d.length)
    ob = mesh_obj(name, bm, [mat_], angle=40)
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    ob.location = (p0 + p1) / 2
    return ob

def tube(name, pts, r, mat_, cyclic=False, res=6, shape=None):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = r
    cu.bevel_resolution = 3
    cu.use_fill_caps = True
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for p, co in zip(sp.points, pts):
        p.co = (*co, 1)
    sp.use_cyclic_u = cyclic
    ob = bpy.data.objects.new(name, cu)
    col.objects.link(ob)
    ob.data.materials.append(mat_)
    for o in bpy.context.selected_objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.convert(target='MESH')
    ob = bpy.context.view_layer.objects.active
    ob.select_set(False)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob

def join(name, objs):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    ob.select_set(False)
    return ob

# ------------------------------------------------------------------ rodas, freios, suspensão
TIRE = []
for a in range(13):
    t = a / 12 * math.pi
    TIRE.append((0.30 + 0.03 * math.sin(t), 0.112 * math.cos(t)))      # banda de rodagem arredondada
TIRE += [(0.218, -0.10), (0.214, -0.06), (0.214, 0.06), (0.218, 0.10)]
TIRE = [(r, y) for r, y in TIRE]

RIM = [(0.214, -0.085), (0.214, 0.075), (0.205, 0.092), (0.195, 0.082), (0.195, -0.06), (0.06, -0.06), (0.04, 0.05), (0.03, 0.09)]

for tag, wx, side in (("DE", WX, 1), ("DD", WX, -1), ("TE", -WX, 1), ("TD", -WX, -1)):
    cy = WY * side
    hub = (wx, cy, WZ)
    tire = lathe(f"pneu_{tag}", TIRE, hub, side, 64, [M["tire"]], angle=50)
    rim = lathe(f"roda_{tag}", RIM, hub, side, 64, [M["rim"]], closed=False, angle=40)
    spokes = []
    for k in range(5):
        a = 2 * math.pi * k / 5 + 0.3
        r0 = 0.12
        c = (wx + r0 * math.cos(a), cy + 0.074 * side, WZ + r0 * math.sin(a))
        sp = box(f"raio_{tag}_{k}", c, (0.17, 0.028, 0.042), M["rim"], bevel=0.008, rot=(0, -a, 0))
        spokes.append(sp)
    cap = lathe(f"cubo_{tag}", [(0.0, 0.10), (0.045, 0.095), (0.055, 0.07), (0.05, 0.05), (0.0, 0.05)], hub, side, 32, [M["chrome"]], closed=False)
    rim = join(f"roda_{tag}", [rim] + spokes + [cap])
    set_origin(rim, hub)
    set_origin(tire, hub)

    disc = lathe(f"freio_disco_{tag}", [(0.05, -0.012), (0.172, -0.012), (0.172, 0.012), (0.05, 0.012)], (wx, cy - 0.03 * side, WZ), side, 48, [M["disc"]], angle=30)
    set_origin(disc, hub)
    ca = 2.35 if wx > 0 else 0.79  # pinça atrás do eixo, em cima
    cc = (wx + 0.15 * math.cos(ca), cy - 0.025 * side, WZ + 0.15 * math.sin(ca))
    box(f"freio_pinca_{tag}", cc, (0.075, 0.07, 0.13), M["caliper"], bevel=0.02, rot=(0, -(ca - math.pi / 2), 0))

    # suspensão McPherson estilizada
    sy = cy - 0.20 * side
    hel = []
    turns, z0, z1, rr = 5.5, 0.47, 0.86, 0.062
    for i in range(int(turns * 24) + 1):
        t = i / 24 * 2 * math.pi
        hel.append((wx + rr * math.cos(t), sy + rr * math.sin(t), z0 + (z1 - z0) * i / (turns * 24)))
    tube(f"susp_mola_{tag}", hel, 0.011, M["spring"])
    cyl_between(f"susp_amortecedor_{tag}", (wx, sy, WZ + 0.02), (wx, sy, 0.92), 0.026, M["steel"])
    cyl_between(f"susp_bandeja_{tag}", (wx, sy + 0.02 * side, WZ - 0.04), (wx, sy - 0.32 * side, WZ - 0.06), 0.022, M["steel"])

# ------------------------------------------------------------------ motor e cofre
EX, EY = 1.43, 0.04
box("motor_bloco", (EX, EY, 0.55), (0.40, 0.60, 0.34), M["alu"], bevel=0.03)
box("motor_cabecote", (EX + 0.02, EY, 0.755), (0.34, 0.56, 0.08), M["cover"], bevel=0.03)
box("motor_tampa", (EX + 0.02, EY, 0.81), (0.26, 0.50, 0.035), M["red"], bevel=0.015)
coils = [cyl_between(f"motor_bobina_{i}", (EX + 0.02, EY - 0.18 + 0.12 * i, 0.82), (EX + 0.02, EY - 0.18 + 0.12 * i, 0.865), 0.022, M["rubber"]) for i in range(4)]
join("motor_bobinas", coils)
cyl_between("motor_coletor", (EX - 0.22, EY - 0.26, 0.66), (EX - 0.22, EY + 0.26, 0.66), 0.045, M["cover"])
box("motor_filtro_ar", (EX - 0.36, EY - 0.18, 0.76), (0.18, 0.26, 0.11), M["cover"], bevel=0.03)

# correia dentada (lado direito do motor)
BY = EY + 0.33
p1 = lathe("correia_polia_virabrequim", [(0, -0.02), (0.075, -0.02), (0.075, 0.02), (0, 0.02)], (EX - 0.04, BY, 0.43), 1, 32, [M["chrome"]], closed=False)
p2 = lathe("correia_polia_comando", [(0, -0.02), (0.065, -0.02), (0.065, 0.02), (0, 0.02)], (EX + 0.05, BY, 0.74), 1, 32, [M["chrome"]], closed=False)
p3 = lathe("correia_tensor", [(0, -0.02), (0.035, -0.02), (0.035, 0.02), (0, 0.02)], (EX + 0.13, BY, 0.56), 1, 24, [M["chrome"]], closed=False)
join("correia_polias", [p1, p2, p3])
belt = []
for i in range(73):
    t = i / 72 * 2 * math.pi
    # contorno das três polias aproximado por uma elipse inclinada
    cx = EX + 0.005 + 0.09 * math.cos(t) + 0.03 * math.sin(t)
    cz = 0.585 + 0.205 * math.sin(t)
    belt.append((cx, BY + 0.025, cz))
tube("correia_dentada", belt, 0.012, M["red"], cyclic=True)

# câmbio e semieixos
gb = lathe("cambio_caixa", [(0.0, 0.0), (0.17, 0.0), (0.17, 0.08), (0.13, 0.26), (0.08, 0.32), (0.0, 0.32)], (EX - 0.05, EY - 0.30, 0.47), -1, 40, [M["alu"]], closed=False, angle=35)
s1 = cyl_between("cambio_semieixo_e", (EX - 0.05, EY - 0.55, 0.42), (WX, -WY + 0.12, WZ), 0.022, M["steel"])
s2 = cyl_between("cambio_semieixo_d", (EX - 0.05, EY + 0.25, 0.42), (WX, WY - 0.12, WZ), 0.022, M["steel"])
join("cambio_semieixos", [s1, s2])

# bateria
box("bateria_caixa", (1.13, 0.50, 0.72), (0.24, 0.17, 0.19), M["battery"], bevel=0.012)
box("bateria_tampa", (1.13, 0.50, 0.822), (0.245, 0.175, 0.02), M["red"], bevel=0.006)
t1 = cyl_between("bateria_polo_pos", (1.06, 0.46, 0.83), (1.06, 0.46, 0.86), 0.016, M["red"])
t2 = cyl_between("bateria_polo_neg", (1.20, 0.46, 0.83), (1.20, 0.46, 0.86), 0.016, M["rubber"])
join("bateria_polos", [t1, t2])
tube("bateria_cabo", [(1.06, 0.46, 0.86), (1.08, 0.36, 0.90), (1.25, 0.25, 0.86), (1.38, 0.2, 0.80)], 0.011, M["red"])

# arrefecimento
box("arrefecimento_radiador", (1.86, 0.0, 0.50), (0.05, 1.08, 0.34), M["radiator"], bevel=0.008)
box("arrefecimento_ventoinha", (1.80, 0.0, 0.50), (0.03, 0.52, 0.30), M["cover"], bevel=0.01)
box("arrefecimento_reservatorio", (1.60, -0.56, 0.76), (0.12, 0.12, 0.13), M["tank"], bevel=0.02)
tube("arrefecimento_mangueira", [(1.83, 0.42, 0.62), (1.72, 0.36, 0.70), (1.58, 0.30, 0.66)], 0.022, M["rubber"])

# escapamento
pipe = [(EX + 0.1, EY + 0.05, 0.40), (EX + 0.05, EY + 0.12, 0.29), (1.05, 0.16, 0.272), (-1.3, 0.28, 0.272), (-1.52, 0.30, 0.28)]
tube("escape_tubo", pipe, 0.03, M["steel"])
box("escape_silencioso", (-1.75, 0.30, 0.29), (0.42, 0.26, 0.13), M["steel"], bevel=0.04)
cyl_between("escape_ponteira", (-1.95, 0.30, 0.28), (-2.13, 0.30, 0.275), 0.034, M["chrome"])

# iluminação e detalhes da carroceria
for side in (1, -1):
    ellipsoid(f"luz_farol_{'e' if side > 0 else 'd'}", (1.955, 0.55 * side, 0.725), (0.05, 0.15, 0.04), M["head"], rot=(0, 0.18, 0.62 * side))
    ellipsoid(f"luz_lanterna_{'e' if side > 0 else 'd'}", (-2.005, 0.58 * side, 0.865), (0.04, 0.15, 0.042), M["tail"], rot=(0, 0, -0.55 * side))
    ellipsoid(f"espelho_{'e' if side > 0 else 'd'}", (0.78, 0.835 * side, 1.03), (0.07, 0.10, 0.055), M["roof"])
    cyl_between(f"espelho_haste_{'e' if side > 0 else 'd'}", (0.80, 0.70 * side, 0.99), (0.79, 0.80 * side, 1.02), 0.015, M["trim"])
    box(f"maçaneta_{'e' if side > 0 else 'd'}", (-0.25, 0.79 * side, 0.90), (0.12, 0.03, 0.025), M["trim"], bevel=0.01)
box("grade", (2.07, 0, 0.47), (0.06, 0.70, 0.14), M["grille"], bevel=0.03)
box("grade_superior", (2.06, 0, 0.585), (0.05, 0.50, 0.035), M["grille"], bevel=0.015)
box("placa_traseira", (-2.065, 0, 0.62), (0.02, 0.36, 0.12), M["trim"], bevel=0.008)

# ------------------------------------------------------------------ export GLB
os.makedirs(os.path.join(ROOT, "models"), exist_ok=True)
for o in bpy.context.selected_objects:
    o.select_set(False)
for o in col.objects:
    if o.type == 'MESH':
        o.select_set(True)
glb = os.path.join(ROOT, "models", "carro.glb")
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_apply=True,
                          export_yup=True, export_cameras=False, export_lights=False)
print("GLB", glb, os.path.getsize(glb))
tri = sum(len(p.vertices) - 2 for o in col.objects if o.type == 'MESH' for p in o.data.polygons)
print("TRIS", tri)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "carro.blend"))
if ONLY_GLB:
    sys.exit(0)

# ------------------------------------------------------------------ render do hero (Cycles)
for o in bpy.context.selected_objects:
    o.select_set(False)
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
floor = bpy.context.active_object
floor.name = "chao_sombra"
floor.is_shadow_catcher = True

def light(name, kind, loc, energy, color=(1, 1, 1), size=2.0, rot=None, target=(0, 0, 0.6)):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == 'AREA':
        ld.size = size
    ob = bpy.data.objects.new(name, ld)
    col.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob

light("topo", 'AREA', (0, 0, 6), 650, size=7)
light("chave", 'AREA', (5.5, -4.5, 3.0), 900, size=3)
light("recorte", 'AREA', (-5, 3.5, 2.2), 1300, color=(1.0, 0.25, 0.2), size=3)
light("lateral", 'AREA', (-1.0, -6, 1.2), 380, size=4)

world = bpy.data.worlds.new("mundo")
scene.world = world
try:
    world.use_nodes = True
except Exception:
    pass
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.035, 0.035, 0.04, 1)
bg.inputs[1].default_value = 0.6

cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 60
cam = bpy.data.objects.new("cam", cam_d)
col.objects.link(cam)
cam.location = (6.6, -4.7, 1.35)
d = Vector((0.05, 0, 0.62)) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = int(os.environ.get("SAMPLES", "96"))
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.render.resolution_x = 1800
scene.render.resolution_y = 1100
scene.render.resolution_percentage = 100
try:
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
except Exception:
    pass

img = scene.render.image_settings
try:
    img.media_type = 'IMAGE'
except Exception:
    pass
bpy.ops.render.render()
res = bpy.data.images["Render Result"]
for fmt, ext, path in (('PNG', 'png', os.path.join(HERE, "render_hero.png")),
                       ('WEBP', 'webp', os.path.join(ROOT, "img", "carro-hero.webp"))):
    img.file_format = fmt
    img.color_mode = 'RGBA'
    if fmt == 'WEBP':
        img.quality = 86
    res.save_render(filepath=path, scene=scene)
    print("RENDER", path, os.path.getsize(path))
# versão de celular, menor
scene.render.resolution_percentage = 50
bpy.ops.render.render()
res = bpy.data.images["Render Result"]
img.file_format = 'WEBP'
res.save_render(filepath=os.path.join(ROOT, "img", "carro-hero-900.webp"), scene=scene)
print("RENDER small")
