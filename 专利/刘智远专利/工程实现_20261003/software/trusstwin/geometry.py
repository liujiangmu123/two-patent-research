"""Finite-thickness, non-overlapping L sections and deterministic surface surfels.

Coordinates and all linear parameters are metres. The member line joins section
centroids. Surface Gaussians are a geometric engineering representation, not the
result of a photometric 3DGS training pipeline.
"""
from __future__ import annotations

import math
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation


def section_properties(width: float, thickness: float) -> dict:
    b, t = float(width), float(thickness)
    if not math.isfinite(b + t) or not 0 < t < b:
        raise ValueError("L section requires finite 0 < thickness_m < width_m")
    # Two disjoint rectangles: horizontal leg and the remainder of vertical leg.
    rectangles = [(0.0, b, 0.0, t), (0.0, t, t, b)]
    area = sx = sy = qx = qy = qxy = 0.0
    for x0, x1, y0, y1 in rectangles:
        a = (x1-x0)*(y1-y0)
        area += a
        sx += a*(x0+x1)/2
        sy += a*(y0+y1)/2
        qx += (y1-y0)*(x1**3-x0**3)/3
        qy += (x1-x0)*(y1**3-y0**3)/3
        qxy += (x1*x1-x0*x0)*(y1*y1-y0*y0)/4
    cx, cy = sx/area, sy/area
    ix, iy, ixy = qy-area*cy*cy, qx-area*cx*cx, qxy-area*cx*cy
    principal = np.linalg.eigvalsh([[ix, -ixy], [-ixy, iy]])
    return {"area_m2": area, "centroid_m": [cx, cy], "Ixx_m4": ix,
            "Iyy_m4": iy, "Ixy_m4": ixy,
            "I_min_m4": float(principal[0]), "I_max_m4": float(principal[1])}


def section_polygon(width: float, thickness: float) -> np.ndarray:
    section_properties(width, thickness)
    b, t = width, thickness
    return np.array([[0, 0], [b, 0], [b, t], [t, t], [t, b], [0, b]], dtype=float)


def member_frame(start, end, orientation_rad=0.0):
    a, z = np.asarray(start, float), np.asarray(end, float)-np.asarray(start, float)
    length = float(np.linalg.norm(z))
    if length <= 1e-9:
        raise ValueError("member endpoints must be distinct")
    z /= length
    ref = np.eye(3)[int(np.argmin(np.abs(z)))]
    x = np.cross(ref, z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    c, s = math.cos(orientation_rad), math.sin(orientation_rad)
    basis = np.column_stack((c*x+s*y, -s*x+c*y, z))
    return a, basis, length


def cross_section_world(start, end, width, thickness, orientation_rad=0.0):
    a, basis, length = member_frame(start, end, orientation_rad)
    polygon = section_polygon(width, thickness)
    centroid = np.asarray(section_properties(width, thickness)["centroid_m"])
    local = np.column_stack((polygon-centroid, np.full(6, length/2)))
    return a + local @ basis.T


def member_mesh(start, end, width, thickness, orientation_rad=0.0) -> dict:
    a, basis, length = member_frame(start, end, orientation_rad)
    p = section_polygon(width, thickness)
    centroid = np.asarray(section_properties(width, thickness)["centroid_m"])
    local = np.vstack([np.column_stack((p-centroid, np.zeros(6))),
                       np.column_stack((p-centroid, np.full(6, length)))])
    # Side faces follow the concave polygon. Ends use the two disjoint rectangles.
    faces = []
    for k in range(6):
        j = (k+1) % 6
        faces.extend([[k,j,j+6], [k,j+6,k+6]])
    # Additional corners (0,t) let the cap be tessellated without filling the void.
    for z in (0.0, length):
        cap = np.array([[0,0],[width,0],[width,thickness],[0,thickness],
                        [thickness,thickness],[thickness,width],[0,width]], float)
        offset = len(local)
        local = np.vstack([local, np.column_stack((cap-centroid, np.full(7,z)))])
        triangles = [[0,1,2],[0,2,3],[3,4,5],[3,5,6]]
        for tri in triangles:
            if z == 0:
                tri = list(reversed(tri))
            faces.append([offset+i for i in tri])
    return {"vertices_m": (a+local@basis.T).tolist(), "triangles": faces,
            "section_polygon_m": p.tolist(), "section_properties": section_properties(width, thickness)}


def surface_gaussians(start, end, width, thickness, orientation_rad=0.0,
                      spacing_m=0.10) -> list[dict]:
    """Sample six lateral faces and both finite-thickness end caps."""
    if not 0 < spacing_m <= 1:
        raise ValueError("surface Gaussian spacing_m must be in (0,1]")
    a, basis, length = member_frame(start, end, orientation_rad)
    p = section_polygon(width, thickness)
    cent = np.asarray(section_properties(width, thickness)["centroid_m"])
    surfels = []
    def add(center, tangent1, tangent2, normal, s1, s2, label):
        rot = basis @ np.column_stack((tangent1, tangent2, normal))
        quat_xyzw = Rotation.from_matrix(rot).as_quat()
        surfels.append({"center_m": (a+basis@np.asarray(center)).tolist(),
                        "normal": (basis@normal).tolist(),
                        "scales_m": [max(s1,1e-6),max(s2,1e-6),1e-5],
                        "quaternion_wxyz": np.roll(quat_xyzw,1).tolist(),
                        "surface": label})
    labels = ["outer_leg_y", "end_edge_x", "inner_leg_y",
              "inner_leg_x", "end_edge_y", "outer_leg_x"]
    for k in range(6):
        q, r = p[k], p[(k+1)%6]
        tangent = (r-q)/np.linalg.norm(r-q)
        u = np.r_[tangent,0.0]; v = np.array([0.,0.,1.])
        normal = np.cross(u,v)
        n1, n2 = max(1,math.ceil(np.linalg.norm(r-q)/spacing_m)), max(1,math.ceil(length/spacing_m))
        for i in range(n1):
            xy = q+(r-q)*(i+.5)/n1-cent
            for j in range(n2):
                add([*xy,length*(j+.5)/n2],u,v,normal,
                    np.linalg.norm(r-q)/(2*n1),length/(2*n2),labels[k])
    for z, sign in ((0.,-1.),(length,1.)):
        for x0,x1,y0,y1 in ((0,width,0,thickness),(0,thickness,thickness,width)):
            nx, ny = max(1,math.ceil((x1-x0)/spacing_m)),max(1,math.ceil((y1-y0)/spacing_m))
            for i in range(nx):
                for j in range(ny):
                    center = [x0+(x1-x0)*(i+.5)/nx-cent[0],
                              y0+(y1-y0)*(j+.5)/ny-cent[1],z]
                    add(center,np.array([1.,0.,0.]),np.array([0.,sign,0.]),
                        np.array([0.,0.,sign]),(x1-x0)/(2*nx),(y1-y0)/(2*ny),"end_cap")
    return surfels


def export_gaussian_ply(path: Path, surfels: list[dict]):
    """Standard Gaussian-property names; no learned colour or opacity."""
    names = ["x","y","z","nx","ny","nz","f_dc_0","f_dc_1","f_dc_2",
             "opacity","scale_0","scale_1","scale_2","rot_0","rot_1","rot_2","rot_3"]
    with Path(path).open("w",encoding="ascii",newline="\n") as f:
        f.write("ply\nformat ascii 1.0\ncomment engineering surface Gaussians; no scene training\n")
        f.write(f"element vertex {len(surfels)}\n")
        f.writelines(f"property float {name}\n" for name in names)
        f.write("end_header\n")
        for s in surfels:
            values = s["center_m"]+s["normal"]+[(.65-.5)/.28209479177387814]*3
            values += [math.log(.95/.05)]+np.log(s["scales_m"]).tolist()+s["quaternion_wxyz"]
            f.write(" ".join(f"{v:.9g}" for v in values)+"\n")
