import math
import random
from panda3d.core import (GeomVertexFormat,
                          GeomVertexData,
                          GeomVertexWriter,
                          Geom, GeomNode,
                          GeomTriangles,
                          GeomLinestrips,
                          GeomLines,
                          NodePath,
                          Vec3,
                          LineSegs,
                          Point3)


# lines styles are defined as (length, gap *[,length, gap])
LINE_STYLES = [(1.0),                 # solid
               (1.0, 1.0),            # dashed
               (0.5, 0.5),            # short dashed
               (0.2, 0.3, 1.0, 0.3),  # dot-dash
               (0.2, 1.0),            # dot
               (2.0, 1.0)]            # long dash

def lonlat_to_xyz(lon, lat, radius):
    lon_rad = math.radians(lon)
    lat_rad = math.radians(lat)
    x = radius * math.cos(lat_rad) * math.cos(lon_rad)
    y = radius * math.cos(lat_rad) * math.sin(lon_rad)
    z = radius * math.sin(lat_rad)
    return x, y, z

def create_body_fixed_arrow(body_radius: float, color=(1, 1, 1, 1)):
    shaft_length = body_radius * 2.0
    shaft_radius = body_radius * 0.05
    head_length = body_radius * 0.3
    head_radius = body_radius * 0.1
    return create_arrow(shaft_length, shaft_radius, head_length, head_radius, color=color)

def create_arrow(shaft_length=4.0, shaft_radius=0.1, head_length=0.6, head_radius=0.3, color=(1, 1, 1, 1)):
    """Create an arrow NodePath pointing along +Y."""
    # Shaft (cylinder)
    format = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData('arrow', format, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, 'vertex')
    normal = GeomVertexWriter(vdata, 'normal')
    color_writer = GeomVertexWriter(vdata, 'color')
    tris = GeomTriangles(Geom.UHStatic)
    segments = 24

    # Cylinder shaft
    for i in range(segments + 1):
        theta = 2 * math.pi * i / segments
        x = shaft_radius * math.cos(theta)
        z = shaft_radius * math.sin(theta)
        # Bottom
        vertex.addData3(x, 0, z)
        normal.addData3(x, 0, z)
        color_writer.addData4(*color)
        # Top
        vertex.addData3(x, shaft_length, z)
        normal.addData3(x, 0, z)
        color_writer.addData4(*color)
    for i in range(segments):
        a = i * 2
        b = a + 1
        c = ((i + 1) % segments) * 2
        d = c + 1
        tris.addVertices(a, b, d)
        tris.addVertices(a, d, c)

    # Cone head
    base_idx = (segments + 1) * 2
    tip = Vec3(0, shaft_length + head_length, 0)
    for i in range(segments + 1):
        theta = 2 * math.pi * i / segments
        x = head_radius * math.cos(theta)
        z = head_radius * math.sin(theta)
        vertex.addData3(x, shaft_length, z)
        normal_vec = Vec3(x, head_length * 0.5, z).normalized()
        normal.addData3(normal_vec)
        color_writer.addData4(*color)
    vertex.addData3(tip)
    normal.addData3(0, 1, 0)
    color_writer.addData4(*color)
    tip_idx = vertex.getWriteRow() - 1
    for i in range(segments):
        a = base_idx + i
        b = base_idx + (i + 1) % segments
        tris.addVertices(a, b, tip_idx)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode('arrow')
    node.addGeom(geom)
    arrow_np = NodePath(node)
    arrow_np.setTwoSided(True)
    # arrow_np.setBin('opaque', 10)
    arrow_np.setPos(0, 0, 0)  # by default, center at origin

    return arrow_np

def create_sphere(radius=1.0, num_lat=16, num_lon=32, color=(1, 1, 1, 1)):
    """Create a sphere NodePath with specified radius, latitude and longitude divisions, and color."""

    format = GeomVertexFormat.getV3n3c4t2()
    vdata = GeomVertexData('sphere', format, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, 'vertex')
    normal = GeomVertexWriter(vdata, 'normal')
    color_writer = GeomVertexWriter(vdata, 'color')
    texcoord = GeomVertexWriter(vdata, 'texcoord')
    tris = GeomTriangles(Geom.UHStatic)

    for i in range(num_lat + 1):
        theta = math.pi * i / num_lat
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        v = i / num_lat  # V coordinate
        for j in range(num_lon + 1):
            phi = 2 * math.pi * j / num_lon
            sin_phi = math.sin(phi)
            cos_phi = math.cos(phi)
            x = radius * sin_theta * cos_phi
            y = radius * sin_theta * sin_phi
            z = radius * cos_theta
            u = j / num_lon  # U coordinate
            vertex.addData3(x, y, z)
            normal.addData3(Vec3(x, y, z).normalized())
            color_writer.addData4(*color)
            texcoord.addData2(u, 1 - v)

    for i in range(num_lat):
        for j in range(num_lon):
            first = i * (num_lon + 1) + j
            second = first + num_lon + 1
            tris.addVertices(first, second, first + 1)
            tris.addVertices(second, second + 1, first + 1)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode('sphere')
    node.addGeom(geom)
    sphere_np = NodePath(node)
    return sphere_np

def random_rgba(alpha=1.0):
    """
    Generate a random (r, g, b, a) tuple.
    Args:
        alpha (float): Alpha value to use (default 1.0).
    Returns:
        tuple: (r, g, b, a) with r, g, b in [0, 1] and a as specified.
    """
    return (random.random(), random.random(), random.random(), alpha)

def draw_path(parent, pts, linestyle: int = 0, colors=None):
    """
    Draw a path with optional per-point colors and line styles.

    Args:
        parent (NodePath): NodePath to attach the line geometry to.
        pts (list): List of Point3 or Vec3 points to connect.
        linestyle (int, optional): See `LINE_STYLES` for options. Defaults to 0 (solid).
        colors (list, optional): List of (r, g, b, a) tuples, one per point. If provided, enables per-vertex color.
    Returns:
        NodePath: The created line NodePath.
    """
    if not pts or len(pts) < 2:
        return None
    if colors is not None and len(colors) != len(pts):
        raise ValueError("colors must be the same length as pts")

    format = GeomVertexFormat.getV3cp()
    vdata = GeomVertexData('line', format, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, 'vertex')
    color_writer = GeomVertexWriter(vdata, 'color')

    geom = Geom(vdata)
    node = GeomNode('line_path')

    if linestyle == 0:
        # Solid line (as a single linestrip)
        for pt, col in zip(pts, colors if colors else [None]*len(pts)):
            vertex.addData3(pt)
            if colors:
                color_writer.addData4f(*col)
            else:
                color_writer.addData4f(1, 1, 1, 1)
        linestrip = GeomLinestrips(Geom.UHStatic)
        for i in range(len(pts)):
            linestrip.addVertex(i)
        linestrip.closePrimitive()
        geom.addPrimitive(linestrip)
    else:
        # Dashed or patterned lines: draw as individual segments
        s = LINE_STYLES[linestyle]
        pattern_len = len(s)
        pattern_idx = 0
        remaining = s[pattern_idx]
        drawing = True

        vtx_idx = 0
        i = 0
        while i < len(pts) - 1:
            p0 = pts[i]
            p1 = pts[i+1]
            c0 = colors[i] if colors else (1, 1, 1, 1)
            c1 = colors[i+1] if colors else (1, 1, 1, 1)
            seg_vec = p1 - p0
            seg_len = seg_vec.length()
            seg_dir = seg_vec.normalized() if seg_len > 0 else Point3(0,0,0)
            seg_pos = 0.0
            while seg_pos < seg_len:
                step = min(remaining, seg_len - seg_pos)
                p_start = p0 + seg_dir * seg_pos
                p_end = p0 + seg_dir * (seg_pos + step)
                # Interpolate color for the segment ends
                t0 = seg_pos / seg_len if seg_len > 0 else 0
                t1 = (seg_pos + step) / seg_len if seg_len > 0 else 1
                col_start = tuple(c0[j] + (c1[j] - c0[j]) * t0 for j in range(4))
                col_end = tuple(c0[j] + (c1[j] - c0[j]) * t1 for j in range(4))
                if drawing:
                    vertex.addData3(p_start)
                    color_writer.addData4f(*col_start)
                    vertex.addData3(p_end)
                    color_writer.addData4f(*col_end)
                    line = GeomLines(Geom.UHStatic)
                    line.addVertices(vtx_idx, vtx_idx + 1)
                    geom.addPrimitive(line)
                    vtx_idx += 2
                seg_pos += step
                remaining -= step
                if remaining <= 1e-8:
                    pattern_idx = (pattern_idx + 1) % pattern_len
                    remaining = s[pattern_idx]
                    drawing = not drawing
            i += 1

    node.addGeom(geom)
    np = parent.attachNewNode(node)
    np.setTransparency(True)
    np.setLightOff()
    np.setTwoSided(True)
    return np