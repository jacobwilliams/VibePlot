import json
import math
import numpy as np

EARTH_MU = 398600.4418  # km^3/s^2 (Earth)


def kepler_E(M, e, tol=1e-10, max_iter=100):
    """Solve Kepler's equation for E given mean anomaly M and eccentricity e."""
    E = M if e < 0.8 else np.pi
    for _ in range(max_iter):
        dE = (M - (E - e * np.sin(E))) / (1 - e * np.cos(E))
        E += dE
        if abs(dE) < tol:
            break
    return E

def cartesian_to_elements(r_vec, v_vec, mu):
    """
    Convert position and velocity vectors to classical orbital elements.
    Args:
        r_vec: position vector (km), shape (3,)
        v_vec: velocity vector (km/s), shape (3,)
        mu: gravitational parameter (km^3/s^2)
    Returns:
        a: semi-major axis (km)
        e: eccentricity (scalar)
        i: inclination (rad)
        raan: right ascension of ascending node (rad)
        argp: argument of periapsis (rad)
        M: mean anomaly (rad)
    """
    r = np.array(r_vec)
    v = np.array(v_vec)
    R = np.linalg.norm(r)
    V = np.linalg.norm(v)

    # Specific angular momentum
    h = np.cross(r, v)
    h_norm = np.linalg.norm(h)

    # Eccentricity vector
    e_vec = (np.cross(v, h) / mu) - (r / R)
    e = np.linalg.norm(e_vec)

    # Semi-major axis
    energy = V**2 / 2 - mu / R
    a = -mu / (2 * energy)

    # Inclination
    i = np.arccos(h[2] / h_norm)

    # Node vector
    K = np.array([0, 0, 1])
    n = np.cross(K, h)
    n_norm = np.linalg.norm(n)

    # Right ascension of ascending node (RAAN)
    if n_norm != 0:
        raan = np.arccos(n[0] / n_norm)
        if n[1] < 0:
            raan = 2 * np.pi - raan
    else:
        raan = 0.0

    # Argument of periapsis
    if n_norm != 0 and e > 1e-8:
        argp = np.arccos(np.dot(n, e_vec) / (n_norm * e))
        if e_vec[2] < 0:
            argp = 2 * np.pi - argp
    else:
        argp = 0.0

    # True anomaly
    if e > 1e-8:
        nu = np.arccos(np.dot(e_vec, r) / (e * R))
        if np.dot(r, v) < 0:
            nu = 2 * np.pi - nu
    else:
        nu = 0.0

    # Eccentric anomaly
    E = 2 * np.arctan2(np.tan(nu / 2), np.sqrt((1 + e) / (1 - e)))
    # Mean anomaly
    M = E - e * np.sin(E)
    M = np.mod(M, 2 * np.pi)

    return a, e, i, raan, argp, M

def propagate_kepler(a, e, i, raan, argp, M0, mu, t, t0=0.0):
    """
    Propagate a Keplerian orbit to time t.
    Returns position (x, y, z) in inertial frame (km).
    All angles in radians.
    """
    n = np.sqrt(mu / a**3)  # mean motion
    M = M0 + n * (t - t0)   # mean anomaly at time t
    M = np.mod(M, 2*np.pi)
    E = kepler_E(M, e)
    # True anomaly
    nu = 2 * np.arctan2(np.sqrt(1+e)*np.sin(E/2), np.sqrt(1-e)*np.cos(E/2))
    # Distance
    r = a * (1 - e * np.cos(E))
    # Perifocal coordinates
    x_p = r * np.cos(nu)
    y_p = r * np.sin(nu)
    z_p = 0.0
    # Rotation matrix to inertial frame
    cosO = np.cos(raan)
    sinO = np.sin(raan)
    cosi = np.cos(i)
    sini = np.sin(i)
    cosw = np.cos(argp)
    sinw = np.sin(argp)
    R = np.array([
        [cosO*cosw - sinO*sinw*cosi, -cosO*sinw - sinO*cosw*cosi, sinO*sini],
        [sinO*cosw + cosO*sinw*cosi, -sinO*sinw + cosO*cosw*cosi, -cosO*sini],
        [sinw*sini, cosw*sini, cosi]
    ])
    r_vec = np.dot(R, np.array([x_p, y_p, z_p]))
    return r_vec  # (x, y, z) in inertial frame



num_rings = 17  # time steps
num_points = 20  # points per ring
rings = []
for t in range(num_rings):
    z = 0.0 + t * 1.0  # spiral upward
    radius = 1.0 + t * 0.25
    angle_offset = t * 0.2  # spiral twist
    ring = []
    for i in range(num_points):
        theta = 2 * math.pi * i / num_points + angle_offset
        x = 3.0 + radius * math.cos(theta)
        y = radius * math.sin(theta)
        ring.append([x, y, z])
    rings.append(ring)
# Optionally, add a single-point start:
rings.insert(0, [[3.0, 0.0, 0.0]] * num_points)
with open("manifold2.json", "w") as f:
    json.dump(rings, f, indent=2)


# if __name__ == "__main__":

#     num_rings = 17  # time steps
#     num_points = 20  # points per ring
#     rings = []
#     for t in range(num_rings):
#         z = 0.0 + t * 1.0  # spiral upward
#         radius = 3.0 + t * 0.25
#         angle_offset = t * 0.2  # spiral twist
#         ring = []
#         for i in range(num_points):
#             theta = 2 * math.pi * i / num_points + angle_offset
#             x = radius * math.cos(theta)
#             y = radius * math.sin(theta)
#             ring.append([x, y, z])
#         rings.append(ring)
#     # Optionally, add a single-point start:
#     rings.insert(0, [[3.0, 0.0, 0.0]] * num_points)
#     with open("models/manifold3.json", "w") as f:
#         json.dump(rings, f, indent=2)

# --- Main manifold generation ---

if __name__ == "__main__":
    # Initial state (example: circular LEO)
    r0 = np.array([7000, 0, 0])  # km
    v0 = np.array([0, 7.5, 1.0]) # km/s

    mu = EARTH_MU
    num_rings = 10  # time steps
    num_points = 10  # points per ring (delta-v directions)
    dt = 100.0  # seconds between rings
    dv_mag = 0.7  # km/s, magnitude of delta-v

    # Angles for delta-v directions
    ras = np.linspace(-np.pi/2, np.pi/2, num_points, endpoint=False)  # right ascension (azimuth)
    decs = np.linspace(-np.pi/6, np.pi/6, num_points)         # declination (elevation), can be fixed or varied

    # For each delta-v direction, create a new orbit and propagate
    manifold = []
    for t_idx in range(num_rings):
        t = t_idx * dt
        ring = []
        for i in range(num_points):
            ra = ras[i]
            #dec = 0.0  # or decs[i] for a spiral in declination
            dec = decs[i]
            # Delta-v direction in local velocity frame
            # Build a local frame: x along v0, y perpendicular in orbit plane, z out of plane
            v_hat = v0 / np.linalg.norm(v0)
            h = np.cross(r0, v0)
            h_hat = h / np.linalg.norm(h)
            y_hat = np.cross(h_hat, v_hat)
            # Spherical coordinates for delta-v
            dv_dir = (
                np.cos(dec) * np.cos(ra) * v_hat +
                np.cos(dec) * np.sin(ra) * y_hat +
                np.sin(dec) * h_hat
            )
            v_new = v0 + dv_mag * dv_dir
            # Get new elements
            a, e, inc, raan, argp, M = cartesian_to_elements(r0, v_new, mu)
            # Propagate to time t
            r_t = propagate_kepler(a, e, inc, raan, argp, M, mu, t)
            r_t = np.array([r/1000 for r in r_t] ) #FIXME scale to plotting scale
            ring.append(r_t.tolist())
        manifold.append(ring)

    # Optionally, add a single-point start
    manifold.insert(0, [r0.tolist()] * num_points)

    with open("models/manifold_dv.json", "w") as f:
        json.dump(manifold, f, indent=2)