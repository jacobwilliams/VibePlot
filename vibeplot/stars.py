import os
import csv
import math

from direct.showbase.ShowBase import ShowBase
from direct.task import Task

from panda3d.core import (TextNode,
                          LineSegs,
                          Geom,
                          GeomVertexFormat,
                          GeomVertexWriter,
                          GeomPoints,
                          GeomNode,
                          GeomVertexArrayFormat)

from .utilities import create_sphere


CONSTELLATIONS = {
    "orion": [
        "betelgeuse", "bellatrix", "mintaka", "alnilam", "alnitak", "saiph", "rigel"
    ],
    "big_dipper": [
        "dubhe", "merak", "phecda", "megrez", "alioth", "mizar", "alkaid"
    ],
    "cassiopeia": [
        "schedar", "caph", "gamma cassiopeiae", "rho cassiopeiae", "segin"
    ],
    "cygnus": [
        "deneb", "sadr", "gienah", "delta cygni", "albireo"
    ],
    "lyra": [
        "vega", "sheliak", "sulafat"
    ],
    "taurus": [
        "aldebaran", "ain", "alnath"
    ],
    "scorpius": [
        "antareS", "shaula", "sargas", "dschubba"
    ],
    "leo": [
        "regulus", "denebola", "algieba", "zeta leonis", "adhafera"
    ],
    "gemini": [
        "castor", "pollux", "alhena", "wasat"
    ],
    "canis_major": [
        "sirius", "mirzam", "adhara", "wezen", "aludra"
    ],
    "canis_minor": [
        "procyon", "gomeisa"
    ],
    "aquila": [
        "altair", "tarazed", "alshain"
    ],
    "perseus": [
        "mirfak", "algol", "atiks"
    ],
    "crux": [
        "acrux", "mimosa", "gacrux", "delta crucis"
    ],
    "centaurus": [
        "rigil kentaurus", "hadar", "menkent"
    ],
    "aries": [
        "hamal", "sheratan", "mesarthim"
    ],
    "andromeda": [
        "almach", "mirach", "alpheratz"
    ],
    "corona_borealis": [
        "alphecca", "nusakan"
    ],
    "ursa_minor": [
        "polaris", "kochab", "pherkad"
    ],
    "pegasus": [
        "markab", "scheat", "algenib", "enif"
    ],
    "summer_triangle": [
        "vega", "deneb", "altair"
    ],
    # Add more as desired!
}


class Stars():

    def __init__(self, parent : ShowBase,
                 star_image: str = None,
                 star_database: str = "models/hygdata_v41.csv",
                 constellation_lines: bool = True,
                 sky_grid: bool = True,
                 star_sphere_radius: float = 100):
        """
        Initialize the Stars class, which creates a celestial star sphere, draws stars,
        constellation lines, and an optional sky grid.

        Args:
            parent (ShowBase): The parent ShowBase instance (typically your main app).
            star_image (str, optional): Path to a background image for the star sphere.
                If provided, a textured sphere is rendered around the scene. If None,
                the background is set to black. Defaults to None.
                Examples: 'models/2k_stars.jpg' or 'models/epsilon_nebulae_texture_by_amras_arfeiniel.jpg'
            star_database (str, optional): Path to a CSV or TXT file containing star data
                (e.g., HYG database). If provided, stars are drawn using this data.
                Defaults to "models/hygdata_v41.csv".
            constellation_lines (bool, optional): If True, draws lines connecting stars
                in well-known constellations. Defaults to True.
            sky_grid (bool, optional): If True, draws a right ascension/declination grid
                on the celestial sphere. Defaults to True.
            star_sphere_radius (float, optional): Radius of the star sphere in Panda3D units.
                Defaults to 100.

        Side Effects:
            - Creates a NodePath for the star sphere and attaches it to the scene.
            - Loads and draws stars as small spheres.
            - Optionally draws constellation lines and a sky grid.
            - Adds a task to keep the star sphere centered on the camera.
        """

        self.parent = parent
        self.star_sphere_np = self.parent.render.attachNewNode("star_sphere")
        self.star_sphere_radius = star_sphere_radius

        # Star sphere
        if star_image:
            # Star background (sky sphere)
            self.stars = self.parent.loader.loadModel("models/planet_sphere")
            self.stars.reparentTo(self.parent.camera)
            self.stars.setPos(0, 0, 0)
            self.stars.setScale(1000, 1000, 1000)
            self.stars.setTwoSided(True)  # Render inside of sphere
            self.stars.setCompass()
            self.stars.setBin('background', 0)
            self.stars.setDepthWrite(False)
            self.stars.setLightOff()
            self.stars.setCompass()  # Keep stars stationary relative to camera
            star_tex = self.parent.loader.loadTexture(star_image)
            self.stars.setTexture(star_tex, 1)
        else:
            self.parent.win.setClearColor((0, 0, 0, 1))  # black background

        if star_database:
            self.add_stars(star_database, num_stars=500)
            #self.add_stars_as_points(star_database, num_stars=200)
            if constellation_lines:
                self.draw_constellations()

        if sky_grid:
            self.draw_sky_grid(sphere_radius=self.star_sphere_radius)

        self.parent.add_task(self.update_star_sphere, "UpdateStarSphere")

    def add_stars(self, filename="models/Stars_HYGv3.txt", num_stars=100):
        """this one draws stars as spheres. this is not as efficient, but
        seems to work."""
        # Read the star data
        stars = []
        if os.path.splitext(filename)[1] == '.txt':
            delimiter = '\t'
        else:
            delimiter = ','
        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            for row in reader:
                try:
                    ra = float(row['ra'])
                    dec = float(row['dec'])
                    mag = float(row['mag'])
                    ci = float(row.get('ci', 0.0))  # Color index, default to 0.0 if missing
                    name = row.get('proper', '')
                    if name.lower().strip() == 'sol':  # skip the Sun
                        continue
                    stars.append({'ra': ra, 'dec': dec, 'mag': mag, 'ci': ci, 'name': name})
                except Exception:
                    continue  # skip malformed lines

        # Sort by magnitude (lower is brighter)
        stars = sorted(stars, key=lambda s: s['mag'])
        stars = stars[:num_stars]

        # Place each star on a celestial sphere of large radius
        self.star_positions = {}
        for star in stars:
            ra = star['ra'] * 15  # convert hours to degrees
            dec = star['dec']
            mag = star['mag']
            ci = star['ci']
            # Color mapping by color index (ci)
            if ci <= 0.0:
                color = (0.6, 0.8, 1.0, 1)  # blue-white
            elif ci <= 0.3:
                color = (0.7, 0.85, 1.0, 1)  # white-blue
            elif ci <= 0.6:
                color = (1.0, 1.0, 1.0, 1)   # white
            elif ci <= 1.0:
                color = (1.0, 1.0, 0.7, 1)   # yellow-white
            elif ci <= 1.5:
                color = (1.0, 0.8, 0.6, 1)   # orange
            else:
                color = (1.0, 0.6, 0.6, 1)   # red
            # Convert to radians
            ra_rad = math.radians(ra)
            dec_rad = math.radians(dec)
            # Spherical to Cartesian
            x = self.star_sphere_radius * math.cos(dec_rad) * math.cos(ra_rad)
            y = self.star_sphere_radius * math.cos(dec_rad) * math.sin(ra_rad)
            z = self.star_sphere_radius * math.sin(dec_rad)
            self.star_positions[star['name'].strip().lower()] = (x, y, z)
            # Scale star size by magnitude (smaller mag = bigger)
            size = max(0.05, 0.25 - 0.04 * (mag + 1.5))
            #color = (1, 0, 0, 1)  # white, or use color index if desired
            star_np = create_sphere(radius=size, num_lat=6, num_lon=12, color=color)
            star_np.setPos(x, y, z)
            # star_np.reparentTo(self.render)
            star_np.reparentTo(self.star_sphere_np)
            star_np.setLightOff()
            star_np.setTransparency(True)
            if mag < 100.0 and star['name']:
                text_node = TextNode('star_label')
                text_node.setText(star['name'])
                text_node.setTextColor(color)
                text_node.setAlign(TextNode.ACenter)
                text_np = star_np.attachNewNode(text_node)
                text_np.setScale(0.9)  # Adjust size as needed
                text_np.setPos(0, 0, size * 2.5)  # Offset above the star
                text_np.setBillboardAxis()  # Make label always face the camera

    def draw_constellations(self):
        for name, star_list in CONSTELLATIONS.items():
            segs = LineSegs()
            segs.setThickness(1.0)
            segs.setColor(1, 1, 0.5, 0.3)  # Light yellow
            for i in range(len(star_list) - 1):
                s1 = star_list[i].strip().lower()
                s2 = star_list[i + 1].strip().lower()
                if s1 in self.star_positions and s2 in self.star_positions:
                    segs.moveTo(*self.star_positions[s1])
                    segs.drawTo(*self.star_positions[s2])
            constellation_np = self.star_sphere_np.attachNewNode(segs.create())
            constellation_np.setLightOff()
            constellation_np.setTransparency(True)

    def update_star_sphere(self, task):
        # Always center the star sphere on the camera, in the star sphere's parent space
        self.star_sphere_np.setPos(self.star_sphere_np.getParent(), self.parent.camera.getPos(self.star_sphere_np.getParent()))
        return Task.cont

    def add_stars_as_points(self, filename : str = "models/Stars_HYGv3.txt", num_stars : int = 100):
        """this one draws stars as points, but they are squares on mac since
        i can't get the shader thing to work right."""
        # --- Custom vertex format with per-point size ---
        array = GeomVertexArrayFormat()
        array.addColumn("vertex", 3, Geom.NTFloat32, Geom.CPoint)
        array.addColumn("color", 4, Geom.NTFloat32, Geom.CColor)
        array.addColumn("size", 1, Geom.NTFloat32, Geom.COther)
        format = GeomVertexFormat()
        format.addArray(array)
        format = GeomVertexFormat.registerFormat(format)
        vdata = GeomVertexData('stars', format, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, 'vertex')
        color_writer = GeomVertexWriter(vdata, 'color')
        size_writer = GeomVertexWriter(vdata, 'size')

        # --- Read and sort stars ---
        stars = []
        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile, delimiter='\t')
            for row in reader:
                try:
                    ra = float(row['ra'])
                    dec = float(row['dec'])
                    mag = float(row['mag'])
                    ci = float(row['ci'])
                    stars.append({'ra': ra, 'dec': dec, 'mag': mag, 'ci': ci})
                except Exception:
                    continue
        stars = sorted(stars, key=lambda s: s['mag'])[:num_stars]

        # --- Write star data ---
        for star in stars:
            ra = star['ra'] * 15
            dec = star['dec']
            mag = star['mag']
            ci = star['ci']
            size = max(4.0, 16.0 - 2.5 * (mag + 1.5)) / 4.0
            if ci <= 0.0:
                color = (0.6, 0.8, 1.0, 1)
            elif ci <= 0.3:
                color = (0.7, 0.85, 1.0, 1)
            elif ci <= 0.6:
                color = (1.0, 1.0, 1.0, 1)
            elif ci <= 1.0:
                color = (1.0, 1.0, 0.7, 1)
            elif ci <= 1.5:
                color = (1.0, 0.8, 0.6, 1)
            else:
                color = (1.0, 0.6, 0.6, 1)
            ra_rad = math.radians(ra)
            dec_rad = math.radians(dec)
            x = self.star_sphere_radius * math.cos(dec_rad) * math.cos(ra_rad)
            y = self.star_sphere_radius * math.cos(dec_rad) * math.sin(ra_rad)
            z = self.star_sphere_radius * math.sin(dec_rad)
            vertex.addData3(x, y, z)
            color_writer.addData4f(*color)
            size_writer.addData1f(size)

        points = GeomPoints(Geom.UHStatic)
        for i in range(len(stars)):
            points.addVertex(i)
        points.closePrimitive()

        geom = Geom(vdata)
        geom.addPrimitive(points)
        node = GeomNode('star_points')
        node.addGeom(geom)

        stars_np = self.parent.camera.attachNewNode(node)
        stars_np.setBin('background', 0)
        stars_np.setDepthWrite(False)
        stars_np.setLightOff()
        stars_np.setCompass()
        stars_np.setTransparency(True)

        # this doesn't work on the mac:
        #stars_np.setShader(Shader.load(Shader.SL_GLSL, "models/star_point.vert", "models/star_point.frag"))

    def draw_sky_grid(self, sphere_radius=100, ra_lines=24, dec_lines=12):
        """Draws a right ascension/declination grid on the celestial sphere."""
        grid = LineSegs()
        grid.setThickness(1.0)
        grid.setColor(0.4, 0.7, 1, 0.3)  # Light blue, semi-transparent

        # Declination lines (horizontal circles)
        for i in range(1, dec_lines):
            dec = -90 + 180 * i / dec_lines  # from -90 to +90
            dec_rad = math.radians(dec)
            z = sphere_radius * math.sin(dec_rad)
            r_xy = sphere_radius * math.cos(dec_rad)
            segments = 120
            for j in range(segments + 1):
                ra = 360 * j / segments
                ra_rad = math.radians(ra)
                x = r_xy * math.cos(ra_rad)
                y = r_xy * math.sin(ra_rad)
                if j == 0:
                    grid.moveTo(x, y, z)
                else:
                    grid.drawTo(x, y, z)

        # Right Ascension lines (vertical half-circles)
        for i in range(ra_lines):
            ra = 360 * i / ra_lines
            ra_rad = math.radians(ra)
            segments = 120
            for j in range(segments + 1):
                dec = -90 + 180 * j / segments
                dec_rad = math.radians(dec)
                x = sphere_radius * math.cos(dec_rad) * math.cos(ra_rad)
                y = sphere_radius * math.cos(dec_rad) * math.sin(ra_rad)
                z = sphere_radius * math.sin(dec_rad)
                if j == 0:
                    grid.moveTo(x, y, z)
                else:
                    grid.drawTo(x, y, z)

        sky_grid_np = self.star_sphere_np.attachNewNode(grid.create())
        sky_grid_np.setLightOff()
        sky_grid_np.setTransparency(True)
        sky_grid_np.setTwoSided(True)
