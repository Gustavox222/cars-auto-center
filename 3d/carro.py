"""CARS Auto Center - carro 3D para o pré-diagnóstico do site.

Gera um hatch compacto com cada sistema mecânico como objeto separado
(motor, correia, câmbio, bateria, arrefecimento, escapamento, suspensão,
freios, pneus, iluminação), exporta GLB para o three.js e renderiza a
imagem do hero e a sombra de contato com Cycles.

Lataria: loft de seções transversais (cintura, vinco do ombro, caixas de
roda com parede interna). Frisos de porta e capô saem da própria malha.
Faróis, lanternas, grade e placas são "decalques": malhas projetadas na
lataria por raycast, com espessura, para encaixar na superfície.

Uso:  blender -b --factory-startup -P 3d/carro.py            (tudo)
      blender -b --factory-startup -P 3d/carro.py -- glb     (só o GLB)
Depois: npx @gltf-transform/cli quantize models/carro.glb models/carro.glb
        npx esbuild js/car3d.js --bundle --format=esm --minify --target=es2020 --tsconfig=3d/build.json --outfile=js/car3d.min.js
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

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
            # tangentes em x (não em índice): evita ondas onde os pontos são desiguais
            xm = pts[i - 1][0] if i > 0 else x0 - (x1 - x0)
            xp = pts[i + 2][0] if i + 2 < len(pts) else x1 + (x1 - x0)
            m0 = (v1 - vm) / (x1 - xm) * (x1 - x0)
            m1 = (vp - v0) / (xp - x0) * (x1 - x0)
            t2, t3 = t * t, t * t * t
            return (2*t3 - 3*t2 + 1)*v0 + (t3 - 2*t2 + t)*m0 + (-2*t3 + 3*t2)*v1 + (t3 - t2)*m1
    return pts[-1][1]

def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))

def lerp(a, b, t):
    return a + (b - a) * t

def sstep(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)

def cr_pt(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return tuple(0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3)
                 for a, b, c, d in zip(p0, p1, p2, p3))

def cr_path(pts, samples):
    """Spline Catmull-Rom 2D. samples[i] = lista de t em [0,1) do segmento i. Devolve [(pt, seg, t)]."""
    out = []
    n = len(pts)
    for i in range(n - 1):
        p0 = pts[i - 1] if i > 0 else tuple(2 * a - b for a, b in zip(pts[0], pts[1]))
        p3 = pts[i + 2] if i + 2 < n else tuple(2 * a - b for a, b in zip(pts[-1], pts[-2]))
        for t in samples[i]:
            out.append((cr_pt(p0, pts[i], pts[i + 1], p3, t), i, t))
    out.append((pts[-1], n - 1, 0.0))
    return out

def uni(n):
    return [k / n for k in range(n)]

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

def fix_normals(bm, name=""):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    vol = sum(f.calc_center_median().dot(f.normal) * f.calc_area() for f in bm.faces) / 3
    if vol < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.normal_update()
    return vol

def set_origin(ob, point):
    """Move a origem do objeto para `point` sem mover a geometria."""
    p = Vector(point)
    ob.data.transform(Matrix.Translation(-p))
    ob.location = p

# ------------------------------------------------------------------ materiais
def mat(name, color, metal=0.0, rough=0.5, coat=0.0, coat_rough=0.04, emit=None, emit_str=0.0):
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
    b.inputs["Coat Roughness"].default_value = coat_rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = emit_str
    return m

def srgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)

M = {
    "paint":   mat("Pintura", srgb("#b3121b"), metal=0.55, rough=0.34, coat=1.0, coat_rough=0.03),
    "trim":    mat("Preto brilhante", srgb("#08080a"), rough=0.16, coat=0.6),
    "plastic": mat("Plastico", srgb("#141416"), rough=0.72),
    "glass":   mat("Vidro", srgb("#06080b"), rough=0.03, coat=1.0, coat_rough=0.0),
    "tire":    mat("Pneu", srgb("#19191a"), rough=0.88),
    "rim":     mat("Roda", srgb("#a9adb4"), metal=1.0, rough=0.26),
    "rimdark": mat("Roda grafite", srgb("#2c2e33"), metal=0.9, rough=0.32),
    "disc":    mat("Disco", srgb("#7d8087"), metal=1.0, rough=0.45),
    "caliper": mat("Pinca", srgb("#e1251b"), rough=0.3, coat=0.8),
    "alu":     mat("Aluminio", srgb("#a4a8ae"), metal=1.0, rough=0.38),
    "cover":   mat("Tampa", srgb("#1b1b1e"), rough=0.3, coat=0.5),
    "red":     mat("Vermelho", srgb("#d42a20"), rough=0.4),
    "rubber":  mat("Borracha", srgb("#202022"), rough=0.7),
    "spring":  mat("Mola", srgb("#e1251b"), rough=0.35, metal=0.3),
    "steel":   mat("Aco", srgb("#6d7077"), metal=1.0, rough=0.35),
    "chrome":  mat("Cromo", srgb("#dcdde0"), metal=1.0, rough=0.08),
    "battery": mat("Bateria", srgb("#1f2329"), rough=0.5),
    "tank":    mat("Reservatorio", srgb("#e8e6df"), rough=0.3),
    "radiator":mat("Radiador", srgb("#2b2d31"), metal=0.7, rough=0.45),
    "lens":    mat("Farol", srgb("#1a1d23"), metal=0.85, rough=0.07, coat=1.0, coat_rough=0.0),
    "drl":     mat("LED", srgb("#ffffff"), rough=0.2, emit=srgb("#f3f6ff"), emit_str=6.0),
    "amber":   mat("Seta", srgb("#7a4200"), rough=0.15, emit=srgb("#ff9a1f"), emit_str=0.8),
    "tail":    mat("Lanterna", srgb("#3d0405"), rough=0.08, coat=1.0, emit=srgb("#ff1a12"), emit_str=0.35),
    "tailled": mat("Lanterna LED", srgb("#ff2a1f"), rough=0.2, emit=srgb("#ff1f14"), emit_str=4.0),
    "plate":   mat("Placa", srgb("#efefea"), rough=0.35),
    "plateb":  mat("Placa faixa", srgb("#1f4fa8"), rough=0.35),
}
PA, TR, GL, PL = 0, 1, 2, 3   # índices de material da lataria e da cabine
SHELL_MATS = [M["paint"], M["trim"], M["glass"], M["plastic"]]

# ------------------------------------------------------------------ medidas (m)
L = 2.04          # meio comprimento (4,08 m)
W = 0.875         # meia largura (1,75 m)
WX = 1.27         # eixos em +-WX (entre-eixos 2,54 m)
WR = 0.315        # raio do pneu (195/55 R17)
WZ = 0.315        # altura do centro da roda
WY = 0.762        # meia bitola
TW = 0.1025       # meia largura do pneu
ARCH = 0.358      # raio da caixa de roda
RF, RR = 0.44, 0.36           # raio dos cantos em planta (frente, traseira)
GAPS = (0.84, -0.22, -0.98)   # frisos das portas
GW = 0.007

TOP = [(-2.04, 0.95), (-2.036, 0.985), (-2.0, 1.0), (-1.8, 1.003), (-1.0, 0.99), (0.0, 0.975),
       (0.84, 0.950), (1.10, 0.912), (1.45, 0.872), (1.75, 0.825), (1.93, 0.775), (2.01, 0.725), (2.04, 0.665)]
BOT = [(-2.04, 0.42), (-2.0, 0.30), (-1.85, 0.22), (-1.5, 0.19), (1.5, 0.19), (1.85, 0.22),
       (2.0, 0.30), (2.04, 0.40)]
ROOF = [(-1.96, 0.985), (-1.91, 1.09), (-1.80, 1.22), (-1.64, 1.31), (-1.45, 1.365), (-1.10, 1.398),
        (-0.6, 1.412), (-0.2, 1.40), (0.05, 1.34), (0.35, 1.205), (0.62, 1.07), (0.84, 0.953)]

def plan_w(x):
    """Meia largura em planta: cantos em superelipse (frente quase reta, cantos arredondados)."""
    if x > L - RF:
        d = clamp((x - (L - RF)) / RF)
        return W * max(1e-4, 1 - d ** 3.2) ** (1 / 3.2)
    if x < -(L - RR):
        d = clamp((-(L - RR) - x) / RR)
        return W * max(1e-4, 1 - d ** 3.0) ** (1 / 3.0)
    return W

def arch_z(x):
    za = smooth_curve(BOT, x)
    for wx in (-WX, WX):
        d = x - wx
        if abs(d) < ARCH:
            za = max(za, WZ + math.sqrt(ARCH * ARCH - d * d))
    return za

def top_z(x):
    return smooth_curve(TOP, x)

def xs_cos(n, a, b):
    return [a + (b - a) * (0.5 - 0.5 * math.cos(math.pi * i / (n - 1))) for i in range(n)]

def with_breaks(xs, breaks, lo, hi):
    s = set(round(x, 6) for x in xs)
    for b in breaks:
        if lo < b < hi:
            s.add(round(b, 6))
    return sorted(s)

def loft(name, xs, section, mats, assign, angle=None):
    """Loft de seções fechadas. section(x) -> (pontos 3D, tag de cada aresta)."""
    bm = bmesh.new()
    rings, tags = [], None
    for x in xs:
        pts, tg = section(x)
        rings.append([bm.verts.new(p) for p in pts])
        tags = tg
    m = len(rings[0])
    meta = []
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(m):
            k = (j + 1) % m
            f = bm.faces.new((a[j], a[k], b[k], b[j]))
            meta.append((f, tags[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    vol = fix_normals(bm)
    print("LOFT", name, round(vol, 3), "aneis", len(rings), "pts", m)
    for f, tg in meta:
        f.material_index = assign(tg, f.calc_center_median())
    return mesh_obj(name, bm, mats, angle=angle)

def mirror_ring(right, rtags):
    """right: meia seção de (0,zb) a (0,zt), lado +y. Fecha a seção espelhando."""
    n = len(right)
    left = [(-y, z) for (y, z) in reversed(right[1:-1])]
    edge = list(rtags[:n - 1]) + [rtags[n - 2]] + [rtags[n - 3 - m] for m in range(n - 3)] + [rtags[0]]
    return right + left, edge

# ------------------------------------------------------------------ lataria
SHUT_T = (0.22, 0.245)    # friso do capô dentro do segmento C7-C8

def body_section(x):
    w = plan_w(x)
    zt = top_z(x)
    zin = smooth_curve(BOT, x)
    za = arch_z(x)
    zs = zt - 0.035
    ya = min(0.60, 0.70 * w)
    right, tg = [], []
    # fundo e caixa de roda (linear)
    lin = [((0.0, zin), 'under', 3), ((ya, zin), 'well', 1), ((ya + 0.004, za), 'well', 3)]
    end = (0.93 * w, za)
    for idx, (p, tag, n) in enumerate(lin):
        q = lin[idx + 1][0] if idx + 1 < len(lin) else end
        for k in range(n):
            t = k / n
            right.append((lerp(p[0], q[0], t), lerp(p[1], q[1], t)))
            tg.append(tag)
    h = zs - za
    C = [(0.93 * w, za), (0.985 * w, za + 0.10 * h), (w, za + 0.30 * h), (0.995 * w, za + 0.62 * h),
         (0.975 * w, za + 0.90 * h), (0.955 * w, zs), (0.90 * w, zs + 0.020), (0.78 * w, zt - 0.008),
         (0.45 * w, zt + 0.006), (0.0, zt + 0.011)]
    samples = [uni(2), uni(2), uni(3), uni(3), uni(3), uni(2), uni(2),
               [0.0, 0.12, SHUT_T[0], SHUT_T[1], 0.5, 0.75], uni(3)]
    for (p, seg, t) in cr_path(C, samples):
        right.append(p)
        if seg <= 4:
            tg.append('side')
        elif seg == 7 and abs(t - SHUT_T[0]) < 1e-6:
            tg.append('shut')
        else:
            tg.append('top')
    right[-1] = (0.0, right[-1][1])
    ring, edge = mirror_ring(right, tg)
    return [(x, y, z) for (y, z) in ring], edge

def body_assign(tag, c):
    x, y, z = c
    ay = abs(y)
    w = plan_w(x)
    if tag in ('under', 'well'):
        return PL
    if tag == 'shut':
        return PL if 0.90 < x < 1.975 else PA
    if tag == 'top':
        if 0.84 < x < 0.90 and ay < 0.86 * w:
            return PL                                   # grade do para-brisa
        if 1.975 < x < 1.983 and ay < 0.70 * w:
            return PL                                   # friso dianteiro do capô
        return PA
    if z < 0.275:
        return PL                                       # saia lateral
    for g in GAPS:
        if abs(x - g) < GW / 2 + 1e-4 and arch_z(x) + 0.05 < z < top_z(x) - 0.047:
            return PL                                   # friso de porta
    return PA

xb = [b + s * GW / 2 for b in GAPS for s in (-1, 1)]
xb += [0.84, 0.90, 1.975, 1.983]
for wx in (-WX, WX):
    xb += [wx + s * (ARCH + e) for s in (-1, 1) for e in (-0.0015, 0.0015)]
XS_BODY = with_breaks(xs_cos(230, -L * 0.9995, L * 0.9995), xb, -L, L)
body = loft("carroceria", XS_BODY, body_section, SHELL_MATS, body_assign, angle=55)

# ------------------------------------------------------------------ cabine (vidros, colunas, teto)
GX0, GX1 = -1.96, 0.84

def roof_z(x):
    return smooth_curve(ROOF, x)

def cabin_section(x):
    cb = top_z(x) - 0.03
    zr = max(roof_z(x), cb + 0.015)
    hg = zr - cb
    wb = 0.89 * plan_w(x)
    wr = wb - 0.17 * clamp(hg / 0.45)
    ek = clamp(hg / 0.14, 0.12, 1.0)
    g0 = (wb - 0.002, cb + 0.028 * ek)
    f0 = (wr + 0.008, zr - 0.062 * ek)
    right, tg = [(0.0, cb), (wb, cb)], ['base', 'seal']
    for t in (0.0, 0.33, 0.66):
        bow = 0.012 * ek * math.sin(math.pi * t)
        right.append((lerp(g0[0], f0[0], t) + bow, lerp(g0[1], f0[1], t)))
        tg.append('glass')
    right += [f0, (wr + 0.002, zr - 0.040 * ek), (wr - 0.012, zr - 0.016 * ek), (wr - 0.045, zr - 0.003 * ek),
              (wr - 0.09, zr), (wr * 0.5, zr + 0.006 * ek), (0.0, zr + 0.008 * ek)]
    tg += ['frame', 'edge', 'edge', 'edge', 'top', 'top', 'top']
    ring, edge = mirror_ring(right, tg)
    return [(x, y, z) for (y, z) in ring], edge

def cabin_assign(tag, c):
    if tag == 'base':
        return PL
    if tag == 'seal':
        return TR
    return PA                                           # vidros: decalques mais abaixo

XS_CAB = xs_cos(170, GX0, GX1)
cabin = loft("cabine", XS_CAB, cabin_section, SHELL_MATS, cabin_assign, angle=50)

# ------------------------------------------------------------------ primitivas
def lathe(name, prof, center, side=1, segs=48, mats=(), closed=True, angle=40):
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

def tube(name, pts, r, mat_, cyclic=False):
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

def sweep(name, sections, mat_, angle=35):
    """Tubo de seção quadrilateral passando por `sections` (listas de 4 pontos), com tampas."""
    bm = bmesh.new()
    rings = [[bm.verts.new(p) for p in s] for s in sections]
    for a, b in zip(rings, rings[1:]):
        for j in range(4):
            k = (j + 1) % 4
            bm.faces.new((a[j], a[k], b[k], b[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    fix_normals(bm)
    return mesh_obj(name, bm, [mat_], angle=angle)

# ------------------------------------------------------------------ decalques projetados na lataria
dg = bpy.context.evaluated_depsgraph_get()
BVH = BVHTree.FromObject(body, dg)

def surf(o, d, bvh=None):
    d = Vector(d).normalized()
    loc, nor, _, _ = (bvh or BVH).ray_cast(Vector(o), d, 30.0)
    if loc is None:
        raise RuntimeError("raio sem acerto %s %s" % (o, d))
    if nor.dot(d) > 0:
        nor = -nor
    return loc, nor

def decal(name, ray_fn, nu, nv, off, mat_, depth=0.012, angle=45, bvh=None):
    """Malha fina sobre a lataria: grade nu x nv de raios ray_fn(u, v) -> (origem, direção)."""
    bm = bmesh.new()
    top, bot = [], []
    for i in range(nu + 1):
        tr, br = [], []
        for k in range(nv + 1):
            o, d = ray_fn(i / nu, k / nv)
            p, n = surf(o, d, bvh)
            tr.append(bm.verts.new(p + n * off))
            br.append(bm.verts.new(p - n * depth))
        top.append(tr)
        bot.append(br)
    for i in range(nu):
        for k in range(nv):
            bm.faces.new((top[i][k], top[i + 1][k], top[i + 1][k + 1], top[i][k + 1]))
            bm.faces.new((bot[i][k], bot[i][k + 1], bot[i + 1][k + 1], bot[i + 1][k]))
    for i in range(nu):
        for k in (0, nv):
            bm.faces.new((top[i][k], bot[i][k], bot[i + 1][k], top[i + 1][k]))
    for k in range(nv):
        for i in (0, nu):
            bm.faces.new((top[i][k], top[i][k + 1], bot[i][k + 1], bot[i][k]))
    fix_normals(bm)
    return mesh_obj(name, bm, [mat_], angle=angle)

def corner_ray(s, z, xc, yc, R, sx, side):
    """Raio horizontal em volta do canto: s<0 lateral, 0..arco canto, depois frente/traseira."""
    arc = R * math.pi / 2
    if s <= 0:
        return (xc + sx * s, side * 6.0, z), (0, -side, 0)
    if s < arc:
        phi = s / R
        nx, ny = math.sin(phi) * sx, math.cos(phi) * side
        return (xc + nx * 6, side * yc + ny * 6, z), (-nx, -ny, 0)
    return (sx * 6.0, side * (yc - (s - arc)), z), (-sx, 0, 0)

def front_ray(y, z):
    return (6.0, y, z), (-1, 0, 0)

def rear_ray(y, z):
    return (-6.0, y, z), (1, 0, 0)

def side_ray(x, z, side):
    return (x, side * 6.0, z), (0, -side, 0)

def tip(u, a=0.12, b=0.05, lo=0.25):
    return max(lo, min(1.0, u / a, (1 - u) / b)) ** 0.5

FC = (L - RF, W - RF)     # centro do canto dianteiro em planta
RC = (-(L - RR), W - RR)  # centro do canto traseiro

for side in (1, -1):
    sfx = 'e' if side > 0 else 'd'
    # ---- farol: carcaça cromada escura + LED diurno + seta + projetor
    s0, s1 = -0.02, RF * math.pi / 2 + 0.02
    def hl_band(u):
        e = sstep(u)
        return lerp(0.782, 0.615, e), lerp(0.815, 0.695, e)
    def hl(u, v, side=side, inset=(0.0, 0.0), trim=(0.0, 1.0)):
        uu = lerp(trim[0], trim[1], u)
        lo, hi = hl_band(uu)
        lo, hi = lo + inset[0] * (hi - lo), hi - inset[1] * (hi - lo)
        mid, half = (lo + hi) / 2, (hi - lo) / 2 * tip(uu, 0.18, 0.04)
        return corner_ray(lerp(s0, s1, uu), mid + (v - 0.5) * 2 * half, FC[0], FC[1], RF, 1, side)
    decal(f"luz_farol_{sfx}", hl, 40, 6, 0.004, M["lens"])
    decal(f"luz_drl_{sfx}", lambda u, v, hl=hl: hl(u, v, inset=(0.72, 0.10), trim=(0.03, 0.97)), 40, 2, 0.0068, M["drl"])
    decal(f"luz_seta_{sfx}", lambda u, v, hl=hl: hl(u, v, inset=(0.08, 0.72), trim=(0.55, 0.95)), 16, 2, 0.0062, M["amber"])
    for k, uu in enumerate((0.66, 0.82)):
        lo, hi = hl_band(uu)
        p, n = surf(*corner_ray(lerp(s0, s1, uu), (lo + hi) / 2 - 0.004, FC[0], FC[1], RF, 1, side))
        ob = ellipsoid(f"luz_projetor_{sfx}_{k}", p + n * 0.002, (0.024, 0.024, 0.024), M["chrome"], seg=24)

    # ---- lanterna traseira envolvendo o canto
    t0, t1 = -0.06, RR * math.pi / 2 + 0.035
    def tl_band(u):
        e = sstep(u)
        return lerp(0.875, 0.83, e), lerp(0.935, 0.925, e)
    def tl(u, v, side=side, inset=(0.0, 0.0), trim=(0.0, 1.0)):
        uu = lerp(trim[0], trim[1], u)
        lo, hi = tl_band(uu)
        lo, hi = lo + inset[0] * (hi - lo), hi - inset[1] * (hi - lo)
        mid, half = (lo + hi) / 2, (hi - lo) / 2 * tip(uu, 0.15, 0.02, 0.5)
        return corner_ray(lerp(t0, t1, uu), mid + (v - 0.5) * 2 * half, RC[0], RC[1], RR, -1, side)
    decal(f"luz_lanterna_{sfx}", tl, 34, 6, 0.004, M["tail"])
    decal(f"luz_lanterna_led_{sfx}", lambda u, v, tl=tl: tl(u, v, inset=(0.62, 0.18), trim=(0.04, 1.0)), 34, 2, 0.0062, M["tailled"])
    decal(f"luz_refletor_{sfx}", lambda u, v, side=side: rear_ray(side * lerp(0.56, 0.68, u), lerp(0.448, 0.466, v)), 8, 2, 0.004, M["tail"])

    # ---- maçanetas (rebaixo preto + puxador na cor do carro)
    for k, hx in enumerate((-0.12, -0.86)):
        zc = top_z(hx) - 0.088
        decal(f"maçaneta_rebaixo_{sfx}_{k}", lambda u, v, hx=hx, zc=zc, side=side: side_ray(hx + (u - 0.5) * 0.17, zc + (v - 0.5) * 0.045, side), 10, 3, 0.0015, M["plastic"])
        decal(f"maçaneta_{sfx}_{k}", lambda u, v, hx=hx, zc=zc, side=side: side_ray(hx + (u - 0.5) * 0.14 * tip(v, 0.5, 0.5, 0.6), zc + (v - 0.5) * 0.022, side), 10, 3, 0.010, M["paint"])

    # ---- retrovisor
    ellipsoid(f"espelho_{sfx}", (0.60, side * 0.905, 1.035), (0.068, 0.105, 0.058), M["paint"], rot=(0, 0, -0.10 * side))
    ellipsoid(f"espelho_vidro_{sfx}", (0.546, side * 0.912, 1.035), (0.012, 0.088, 0.046), M["glass"], rot=(0, 0, -0.10 * side))
    box(f"espelho_base_{sfx}", (0.625, side * 0.815, 0.985), (0.11, 0.10, 0.045), M["trim"], bevel=0.015)

# ---- frente: grade, tomada de ar, placa Mercosul, faróis de neblina
decal("grade_superior", lambda u, v: front_ray(lerp(-0.405, 0.405, u), lerp(0.598, 0.652, v) - 0.010 * (1 - abs(u - 0.5) * 2) ** 2), 34, 4, 0.0035, M["trim"])
decal("grade_superior_friso", lambda u, v: front_ray(lerp(-0.40, 0.40, u), lerp(0.592, 0.597, v) - 0.010 * (1 - abs(u - 0.5) * 2) ** 2), 34, 1, 0.0045, M["chrome"])
def intake(u, v):
    z = lerp(0.27, 0.50, v)
    hw = lerp(0.56, 0.46, v)
    return front_ray(lerp(-hw, hw, u), z)
decal("grade_inferior", intake, 36, 8, 0.004, M["plastic"])
for k, zz in enumerate((0.33, 0.39)):
    decal(f"grade_friso_{k}", lambda u, v, zz=zz: front_ray(lerp(-0.50, 0.50, u), zz + (v - 0.5) * 0.010), 30, 1, 0.0065, M["trim"])
def lip(u, v, side):
    arc = RF * math.pi / 2
    s = lerp(-0.22, arc + FC[1], u)
    z = lerp(0.235, 0.29, v)
    return corner_ray(s, z, FC[0], FC[1], RF, 1, side)
for side in (1, -1):
    decal(f"carroceria_labio_{'e' if side > 0 else 'd'}", lambda u, v, side=side: lip(u, v, side), 40, 3, 0.003, M["plastic"])
decal("placa_dianteira", lambda u, v: front_ray(lerp(-0.20, 0.20, u), lerp(0.375, 0.48, v)), 12, 4, 0.012, M["plate"])
decal("placa_dianteira_faixa", lambda u, v: front_ray(lerp(-0.20, 0.20, u), lerp(0.462, 0.48, v)), 12, 1, 0.0135, M["plateb"])
for side in (1, -1):
    p, n = surf(*front_ray(side * 0.475, 0.305))
    ellipsoid(f"luz_milha_{'e' if side > 0 else 'd'}", p + n * 0.001, (0.028, 0.028, 0.028), M["lens"], seg=24)
    ellipsoid(f"luz_milha_led_{'e' if side > 0 else 'd'}", p + n * 0.012, (0.012, 0.012, 0.012), M["drl"], seg=16)

# ---- traseira: faixa preta com barra de LED, placa
decal("carroceria_faixa_traseira", lambda u, v: rear_ray(lerp(-0.50, 0.50, u), lerp(0.862, 0.905, v)), 30, 2, 0.0035, M["trim"])
decal("luz_barra_traseira", lambda u, v: rear_ray(lerp(-0.49, 0.49, u), lerp(0.879, 0.889, v)), 30, 1, 0.0058, M["tailled"])
def diffuser(u, v, side):
    # do lado (s<0) até o centro da traseira, faixa baixa preta
    arc = RR * math.pi / 2
    s = lerp(-0.30, arc + RC[1], u)
    z = lerp(0.24, lerp(0.465, 0.445, sstep(u)), v)
    return corner_ray(s, z, RC[0], RC[1], RR, -1, side)
for side in (1, -1):
    decal(f"carroceria_difusor_{'e' if side > 0 else 'd'}", lambda u, v, side=side: diffuser(u, v, side), 40, 6, 0.003, M["plastic"])
# frisos da tampa traseira
decal("carroceria_friso_tampa_h", lambda u, v: rear_ray(lerp(-0.64, 0.64, u), lerp(0.503, 0.509, v)), 40, 1, 0.0015, M["plastic"])
for side in (1, -1):
    decal(f"carroceria_friso_tampa_{'e' if side > 0 else 'd'}", lambda u, v, side=side: rear_ray(side * lerp(0.637, 0.643, v), lerp(0.503, 0.93, u)), 30, 1, 0.0015, M["plastic"])
decal("placa_traseira", lambda u, v: rear_ray(lerp(-0.20, 0.20, u), lerp(0.615, 0.725, v)), 12, 4, 0.006, M["plate"])
decal("placa_traseira_faixa", lambda u, v: rear_ray(lerp(-0.20, 0.20, u), lerp(0.707, 0.725, v)), 12, 1, 0.0075, M["plateb"])

# ---- vidros (decalques sobre a cabine): moldura preta + vidro
BVH_C = BVHTree.FromObject(cabin, dg)

def cab_dims(x):
    cb = top_z(x) - 0.03
    zr = max(roof_z(x), cb + 0.015)
    hg = zr - cb
    wb = 0.89 * plan_w(x)
    wr = wb - 0.17 * clamp(hg / 0.45)
    return cb, zr, wb, wr, clamp(hg / 0.14, 0.12, 1.0)

def belt(x):
    cb, zr, wb, wr, ek = cab_dims(x)
    return cb + 0.028 * ek + 0.006

def rail(x):
    cb, zr, wb, wr, ek = cab_dims(x)
    return zr - 0.062 * ek - 0.010

XF = next(x / 1000 for x in range(840, 0, -2) if rail(x / 1000) - belt(x / 1000) > 0.035)
XRB, XRT = -1.40, -1.20

def dlo(u, v):
    """Contorno da janela lateral em vista de lado (Coons): base na cintura, topo na calha do teto."""
    def B(t):
        x = lerp(XF, XRB, t)
        return Vector((x, belt(x)))
    def T(t):
        x = lerp(XF, XRT, t)
        return Vector((x, rail(x)))
    F = lambda t: B(0).lerp(T(0), t)
    R = lambda t: B(1).lerp(T(1), t)
    p = (1 - v) * B(u) + v * T(u) + (1 - u) * F(v) + u * R(v)
    p -= (1 - u) * (1 - v) * B(0) + u * (1 - v) * B(1) + (1 - u) * v * T(0) + u * v * T(1)
    return p

def u_at(x, v):
    a, b = 0.0, 1.0
    for _ in range(30):
        m = (a + b) / 2
        if dlo(m, v).x > x:
            a = m
        else:
            b = m
    return (a + b) / 2

for side in (1, -1):
    sfx = 'e' if side > 0 else 'd'
    def win(u, v, side=side):
        p = dlo(u, v)
        return side_ray(p.x, p.y, side)
    decal(f"cabine_moldura_{sfx}", win, 70, 8, 0.0018, M["trim"], bvh=BVH_C)
    for k, (xa, xb) in enumerate(((None, -0.168), (-0.272, None))):
        def pane(u, v, xa=xa, xb=xb, side=side):
            vv = lerp(0.045, 0.94, v)
            ua = 0.012 if xa is None else u_at(xa, vv)
            ub = 0.985 if xb is None else u_at(xb, vv)
            p = dlo(lerp(ua, ub, u), vv)
            return side_ray(p.x, p.y, side)
        decal(f"cabine_vidro_{sfx}_{k}", pane, 36, 8, 0.0034, M["glass"], bvh=BVH_C)

def top_ray(x, y):
    return (x, y, 5.0), (0, 0, -1)

def screen(x0, x1, inset):
    def fn(u, v):
        x = lerp(x0, x1, v)
        cb, zr, wb, wr, ek = cab_dims(x)
        hw = max(0.05, wr - 0.05) - inset
        return top_ray(x, lerp(-hw, hw, u))
    return fn
decal("cabine_parabrisa_moldura", screen(0.83, -0.13, 0.0), 30, 24, 0.0018, M["trim"], bvh=BVH_C)
decal("cabine_parabrisa", screen(0.815, -0.085, 0.03), 30, 24, 0.0034, M["glass"], bvh=BVH_C)
decal("cabine_vidro_traseiro_moldura", screen(-1.47, -1.935, 0.0), 30, 16, 0.0018, M["trim"], bvh=BVH_C)
decal("cabine_vidro_traseiro", screen(-1.50, -1.90, 0.035), 30, 16, 0.0034, M["glass"], bvh=BVH_C)

# ---- teto: aerofólio, luz de freio, antena; limpadores
box("carroceria_aerofolio", (-1.50, 0, roof_z(-1.50) + 0.004), (0.11, 1.10, 0.018), M["paint"], bevel=0.008, rot=(0, -0.30, 0))
box("luz_freio_alto", (-1.565, 0, roof_z(-1.47) - 0.004), (0.012, 0.30, 0.012), M["tailled"], bevel=0.004)
ellipsoid("carroceria_antena", (-1.30, 0, 1.438), (0.085, 0.022, 0.04), M["trim"], seg=24)
for k, (ya, yb) in enumerate(((-0.60, -0.04), (0.02, 0.50))):
    tube(f"carroceria_limpador_{k}", [(0.885, ya, top_z(0.885) + 0.004), (0.835, (ya + yb) / 2, 0.972), (0.80, yb, 0.985)], 0.0065, M["trim"])

# ------------------------------------------------------------------ rodas, freios, suspensão
TIRE = [(0.216, -0.092), (0.240, -0.100), (0.275, -0.1035), (0.300, -0.098), (0.311, -0.087), (0.315, -0.072),
        (0.315, -0.050), (0.307, -0.050), (0.307, -0.040), (0.315, -0.040),
        (0.315, -0.006), (0.307, -0.006), (0.307, 0.006), (0.315, 0.006),
        (0.315, 0.040), (0.307, 0.040), (0.307, 0.050), (0.315, 0.050),
        (0.315, 0.072), (0.311, 0.087), (0.300, 0.098), (0.275, 0.1035), (0.240, 0.100), (0.216, 0.092)]
RIM = [(0.205, -0.090), (0.214, -0.088), (0.214, 0.070), (0.222, 0.083), (0.226, 0.093), (0.216, 0.098),
       (0.204, 0.090), (0.199, 0.078), (0.199, -0.075)]
HUB = [(0.0, 0.062), (0.030, 0.062), (0.060, 0.056), (0.074, 0.044), (0.076, 0.030), (0.070, 0.018), (0.0, 0.018)]

def spoke(name, hub, a, side):
    rv = Vector((math.cos(a), 0, math.sin(a)))
    tv = Vector((-math.sin(a), 0, math.cos(a)))
    av = Vector((0, side, 0))
    secs = []
    for r, yo, wd, th in ((0.064, 0.050, 0.019, 0.020), (0.135, 0.066, 0.021, 0.018), (0.204, 0.084, 0.029, 0.016)):
        c = hub + rv * r + av * yo
        secs.append([c + tv * (su * wd / 2) + av * (sv * th / 2) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    return sweep(name, secs, M["rim"])

for tag, wx, side in (("DE", WX, 1), ("DD", WX, -1), ("TE", -WX, 1), ("TD", -WX, -1)):
    cy = WY * side
    hub = Vector((wx, cy, WZ))
    tire = lathe(f"pneu_{tag}", TIRE, hub, side, 72, [M["tire"]], angle=40)
    parts = [lathe(f"roda_{tag}", RIM, hub, side, 72, [M["rim"]], closed=False, angle=40)]
    for k in range(5):
        for d in (-0.13, 0.13):
            parts.append(spoke(f"raio_{tag}_{k}_{d}", hub, 2 * math.pi * k / 5 + 0.3 + d, side))
    parts.append(lathe(f"cubo_{tag}", HUB, hub, side, 40, [M["rimdark"]], closed=False))
    for k in range(5):
        a = 2 * math.pi * k / 5 + 0.3 + math.pi / 5
        c = hub + Vector((0.042 * math.cos(a), 0, 0.042 * math.sin(a)))
        parts.append(cyl_between(f"porca_{tag}_{k}", c + Vector((0, 0.054 * side, 0)), c + Vector((0, 0.068 * side, 0)), 0.0085, M["chrome"], segs=6))
    parts.append(lathe(f"calota_{tag}", [(0.0, 0.066), (0.018, 0.065), (0.024, 0.060), (0.024, 0.055), (0.0, 0.055)], hub, side, 32, [M["chrome"]], closed=False))
    rim = join(f"roda_{tag}", parts)
    set_origin(rim, hub)
    set_origin(tire, hub)

    disc = lathe(f"freio_disco_{tag}", [(0.075, -0.035), (0.165, -0.035), (0.165, -0.013), (0.075, -0.013)], hub, side, 56, [M["disc"]], angle=30)
    hat = lathe(f"freio_disco_cubo_{tag}", [(0.0, -0.005), (0.08, -0.005), (0.08, -0.036), (0.0, -0.036)], hub, side, 40, [M["rimdark"]], closed=False)
    disc = join(f"freio_disco_{tag}", [disc, hat])
    set_origin(disc, hub)
    ca = 2.35 if wx > 0 else 0.79  # pinça atrás do eixo, em cima
    cc = (wx + 0.152 * math.cos(ca), cy - 0.024 * side, WZ + 0.152 * math.sin(ca))
    box(f"freio_pinca_{tag}", cc, (0.07, 0.07, 0.15), M["caliper"], bevel=0.022, rot=(0, -(ca - math.pi / 2), 0))

    # suspensão McPherson estilizada
    sy = cy - 0.20 * side
    hel = []
    turns, z0, z1, rr = 5.5, 0.47, 0.83, 0.062
    for i in range(int(turns * 24) + 1):
        t = i / 24 * 2 * math.pi
        hel.append((wx + rr * math.cos(t), sy + rr * math.sin(t), z0 + (z1 - z0) * i / (turns * 24)))
    tube(f"susp_mola_{tag}", hel, 0.011, M["spring"])
    cyl_between(f"susp_amortecedor_{tag}", (wx, sy, WZ + 0.02), (wx, sy, 0.86), 0.026, M["steel"])
    cyl_between(f"susp_bandeja_{tag}", (wx, sy + 0.02 * side, WZ - 0.04), (wx, sy - 0.32 * side, WZ - 0.06), 0.022, M["steel"])

# ------------------------------------------------------------------ motor e cofre
EX, EY = 1.43, 0.04
box("motor_bloco", (EX, EY, 0.55), (0.40, 0.60, 0.34), M["alu"], bevel=0.03)
box("motor_cabecote", (EX + 0.02, EY, 0.735), (0.34, 0.56, 0.08), M["cover"], bevel=0.03)
box("motor_tampa", (EX + 0.02, EY, 0.79), (0.26, 0.50, 0.035), M["red"], bevel=0.015)
coils = [cyl_between(f"motor_bobina_{i}", (EX + 0.02, EY - 0.18 + 0.12 * i, 0.80), (EX + 0.02, EY - 0.18 + 0.12 * i, 0.84), 0.022, M["rubber"]) for i in range(4)]
join("motor_bobinas", coils)
cyl_between("motor_coletor", (EX - 0.22, EY - 0.26, 0.66), (EX - 0.22, EY + 0.26, 0.66), 0.045, M["cover"])
box("motor_filtro_ar", (EX - 0.36, EY - 0.18, 0.74), (0.18, 0.26, 0.11), M["cover"], bevel=0.03)

# correia dentada (lado direito do motor)
BY = EY + 0.33
p1 = lathe("correia_polia_virabrequim", [(0, -0.02), (0.075, -0.02), (0.075, 0.02), (0, 0.02)], (EX - 0.04, BY, 0.43), 1, 32, [M["chrome"]], closed=False)
p2 = lathe("correia_polia_comando", [(0, -0.02), (0.065, -0.02), (0.065, 0.02), (0, 0.02)], (EX + 0.05, BY, 0.74), 1, 32, [M["chrome"]], closed=False)
p3 = lathe("correia_tensor", [(0, -0.02), (0.035, -0.02), (0.035, 0.02), (0, 0.02)], (EX + 0.13, BY, 0.56), 1, 24, [M["chrome"]], closed=False)
join("correia_polias", [p1, p2, p3])
belt = []
for i in range(73):
    t = i / 72 * 2 * math.pi
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
tube("bateria_cabo", [(1.06, 0.46, 0.86), (1.08, 0.36, 0.88), (1.25, 0.25, 0.85), (1.38, 0.2, 0.80)], 0.011, M["red"])

# arrefecimento
box("arrefecimento_radiador", (1.86, 0.0, 0.50), (0.05, 1.04, 0.34), M["radiator"], bevel=0.008)
box("arrefecimento_ventoinha", (1.80, 0.0, 0.50), (0.03, 0.52, 0.30), M["cover"], bevel=0.01)
box("arrefecimento_reservatorio", (1.60, -0.56, 0.74), (0.12, 0.12, 0.13), M["tank"], bevel=0.02)
tube("arrefecimento_mangueira", [(1.83, 0.42, 0.62), (1.72, 0.36, 0.70), (1.58, 0.30, 0.66)], 0.022, M["rubber"])

# escapamento
pipe = [(EX + 0.1, EY + 0.05, 0.40), (EX + 0.05, EY + 0.12, 0.29), (1.05, 0.16, 0.25), (-1.3, 0.28, 0.25), (-1.52, 0.30, 0.27)]
tube("escape_tubo", pipe, 0.03, M["steel"])
box("escape_silencioso", (-1.75, 0.30, 0.29), (0.40, 0.26, 0.13), M["steel"], bevel=0.04)
cyl_between("escape_ponteira", (-1.93, 0.30, 0.285), (-2.08, 0.30, 0.282), 0.036, M["chrome"])

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
CAR = [o for o in col.objects if o.type == 'MESH']
for o in bpy.context.selected_objects:
    o.select_set(False)
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
floor = bpy.context.active_object
floor.name = "chao_sombra"
floor.is_shadow_catcher = True

def light(name, kind, loc, energy, color=(1, 1, 1), size=2.0, size_y=None, target=(0, 0, 0.6)):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == 'AREA':
        if size_y:
            ld.shape = 'RECTANGLE'
            ld.size, ld.size_y = size, size_y
        else:
            ld.size = size
    ob = bpy.data.objects.new(name, ld)
    col.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob

LIGHTS = [
    light("topo", 'AREA', (0, 0, 5.5), 700, size=7.0, size_y=1.4),
    light("chave", 'AREA', (5.5, -4.5, 3.0), 850, size=3),
    light("faixa", 'AREA', (2.0, -5.5, 1.6), 260, size=6.0, size_y=0.35, target=(0, 0, 0.75)),
    light("recorte", 'AREA', (-5, 3.5, 2.2), 1300, color=(1.0, 0.25, 0.2), size=3),
    light("lateral", 'AREA', (-1.0, -6, 1.2), 300, size=4),
]

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
d = Vector((0.05, 0, 0.66)) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = int(os.environ.get("SAMPLES", "128"))
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

def save(path, fmt='WEBP', q=86):
    res = bpy.data.images["Render Result"]
    img.file_format = fmt
    img.color_mode = 'RGBA'
    if fmt == 'WEBP':
        img.quality = q
    res.save_render(filepath=path, scene=scene)
    print("RENDER", path, os.path.getsize(path))

if "nohero" not in ARGS:
    bpy.ops.render.render()
    save(os.path.join(HERE, "render_hero.png"), 'PNG')
    save(os.path.join(ROOT, "img", "carro-hero.webp"))
    scene.render.resolution_percentage = 50
    bpy.ops.render.render()
    save(os.path.join(ROOT, "img", "carro-hero-900.webp"))

# ------------------------------------------------------------------ sombra de contato (vista de cima) para o three.js
for o in CAR:
    o.visible_camera = False
for lo in LIGHTS:
    lo.hide_render = True
light("sombra_topo", 'AREA', (0, 0, 4.0), 900, size=5.0, size_y=2.6, target=(0, 0, 0))
bg.inputs[1].default_value = 0.9
top_d = bpy.data.cameras.new("cam_topo")
top_d.type = 'ORTHO'
top_d.ortho_scale = 6.0
topc = bpy.data.objects.new("cam_topo", top_d)
col.objects.link(topc)
topc.location = (0, 0, 8)
topc.rotation_euler = (0, 0, 0)
scene.camera = topc
scene.render.resolution_x = 768
scene.render.resolution_y = 384
scene.render.resolution_percentage = 100
scene.cycles.samples = 96
try:
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
except Exception:
    pass
bpy.ops.render.render()
save(os.path.join(ROOT, "models", "sombra.png"), 'PNG')
