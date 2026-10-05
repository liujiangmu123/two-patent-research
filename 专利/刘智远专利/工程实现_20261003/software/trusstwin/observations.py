"""Calibrated CPU projection and geometry residuals with declared association.

Occlusion, return intensity, multi-path and automatic image feature extraction
are not implemented. The input must identify usable, visible member features.
"""
from __future__ import annotations
import math
import numpy as np
from .geometry import cross_section_world, member_mesh, section_polygon


def positive(value, name):
    v = float(value)
    if not math.isfinite(v) or v <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return v


def camera_matrices(measurement):
    K = np.asarray(measurement["K"],float)
    R = np.asarray(measurement["R"],float)
    t = np.asarray(measurement["t_m"],float)
    if K.shape != (3,3) or R.shape != (3,3) or t.shape != (3,):
        raise ValueError("camera requires K(3x3), R(3x3), t_m(3); world-to-camera Xc=R X+t")
    if not all(np.isfinite(v).all() for v in (K,R,t)):
        raise ValueError("camera matrices must be finite")
    if K[0,0] <= 0 or K[1,1] <= 0 or not np.allclose(K[2],[0,0,1]):
        raise ValueError("camera K requires positive focal lengths and last row [0,0,1]")
    if not np.allclose(R@R.T,np.eye(3),atol=1e-6) or not np.isclose(np.linalg.det(R),1.,atol=1e-6):
        raise ValueError("camera R must be a proper orthonormal rotation")
    return K,R,t


def project(points, measurement):
    K,R,t = camera_matrices(measurement)
    cam = np.asarray(points,float)@R.T+t
    if np.any(cam[:,2] <= 1e-8):
        raise ValueError("usable image feature is behind or on the camera plane")
    homogeneous = cam@K.T
    return homogeneous[:,:2]/homogeneous[:,2,None]


def point_segment_distances(points, starts, ends):
    points, starts, ends = np.asarray(points),np.asarray(starts),np.asarray(ends)
    d = ends-starts
    n = np.sum(d*d,axis=1)
    alpha = np.sum((points[:,None,:]-starts[None,:,:])*d[None,:,:],axis=2)/np.maximum(n,1e-30)
    closest = starts[None,:,:]+np.clip(alpha,0,1)[:,:,None]*d[None,:,:]
    return np.linalg.norm(points[:,None,:]-closest,axis=2)


def point_surface_distances(points, mesh):
    """Exact Euclidean distance to the finite triangular surface union."""
    pts = np.asarray(points,float)
    if pts.ndim != 2 or pts.shape[1] != 3 or not np.isfinite(pts).all() or len(pts) == 0:
        raise ValueError("lidar_points points_m must be a nonempty finite Nx3 array")
    v = np.asarray(mesh["vertices_m"],float)
    triangles = v[np.asarray(mesh["triangles"],int)]
    a,b,c = triangles[:,0],triangles[:,1],triangles[:,2]
    ab,ac = b-a,c-a
    normal = np.cross(ab,ac); normal /= np.linalg.norm(normal,axis=1)[:,None]
    signed = np.einsum("ptj,tj->pt",pts[:,None,:]-a[None,:,:],normal)
    projected = pts[:,None,:]-signed[:,:,None]*normal[None,:,:]
    ap = projected-a[None,:,:]
    d00,d01,d11 = np.sum(ab*ab,axis=1),np.sum(ab*ac,axis=1),np.sum(ac*ac,axis=1)
    d20,d21 = np.einsum("ptj,tj->pt",ap,ab),np.einsum("ptj,tj->pt",ap,ac)
    denom = d00*d11-d01*d01
    u = (d11*d20-d01*d21)/denom
    w = (d00*d21-d01*d20)/denom
    inside = (u>=-1e-10)&(w>=-1e-10)&(u+w<=1+1e-10)
    plane = np.where(inside,np.abs(signed),np.inf)
    edges = np.minimum(point_segment_distances(pts,a,b),point_segment_distances(pts,b,c))
    edges = np.minimum(edges,point_segment_distances(pts,c,a))
    return np.min(np.minimum(plane,edges),axis=1)


def mesh_edges(mesh):
    # Physical extrusion edges; cap tessellation diagonals are excluded.
    v = np.asarray(mesh["vertices_m"])
    pairs = [(k,(k+1)%6) for k in range(6)]
    pairs += [(k+6,(k+1)%6+6) for k in range(6)]+[(k,k+6) for k in range(6)]
    return v[[a for a,b in pairs]],v[[b for a,b in pairs]]


def effective_sigma(measurement):
    kind = measurement["kind"]
    sigma = positive(measurement.get("sigma_px") if kind.startswith("image") or kind=="edge_pixels"
                     else measurement.get("sigma_m"),"measurement noise sigma")
    if kind.startswith("lidar"):
        beam = float(measurement.get("beam_diameter_m",0.0))
        if beam < 0 or not math.isfinite(beam):
            raise ValueError("beam_diameter_m must be finite and nonnegative")
        # Conservative scalar footprint uncertainty approximation, not a full return renderer.
        sigma = math.sqrt(sigma*sigma+beam*beam/12)
    return sigma


def feature_prediction(measurement, start, end, width, thickness, orientation):
    kind = measurement["kind"]
    if kind == "thickness":
        return np.array([thickness])
    section = cross_section_world(start,end,width,thickness,orientation)
    if kind == "image_points":
        feature = measurement.get("feature","section_vertices")
        points = np.array([start,end]) if feature=="endpoints" else section
        if feature not in ("endpoints","section_vertices"):
            raise ValueError("image_points feature must be endpoints or section_vertices")
        indices = measurement.get("indices",list(range(len(points))))
        if not indices or not all(isinstance(i,int) and 0<=i<len(points) for i in indices):
            raise ValueError("image_points indices must be nonempty and inside associated features")
        return project(points[indices],measurement).reshape(-1)
    if kind == "image_width":
        pixels = project(section,measurement)
        return np.array([np.ptp(pixels[:,0])])
    if kind == "image_edge_gap":
        return np.array([np.linalg.norm(project(section[[0,3]],measurement)[1]-project(section[[0,3]],measurement)[0])])
    if kind == "lidar_edge_gap":
        # Explicitly associated outer/inner corner difference, in scan direction.
        direction = np.asarray(measurement.get("scan_direction",[1,1,0]),float)
        if direction.shape!=(3,) or not np.isfinite(direction).all() or np.linalg.norm(direction)==0:
            raise ValueError("scan_direction must be a finite nonzero 3-vector")
        direction /= np.linalg.norm(direction)
        return np.array([abs(float((section[3]-section[0])@direction))])
    raise ValueError(f"feature prediction unsupported for kind {kind}")


def residuals(measurement, start, end, width, thickness, orientation):
    sigma = effective_sigma(measurement)
    kind = measurement["kind"]
    if measurement.get("visible",True) is not True:
        raise ValueError("observations must be associated with explicitly usable visible features")
    if kind == "lidar_points":
        mesh = member_mesh(start,end,width,thickness,orientation)
        return point_surface_distances(measurement["points_m"],mesh)/sigma
    if kind == "edge_pixels":
        pixels = np.asarray(measurement["pixels"],float)
        if pixels.ndim!=2 or pixels.shape[1]!=2 or len(pixels)==0 or not np.isfinite(pixels).all():
            raise ValueError("edge_pixels pixels must be nonempty finite Nx2")
        a,b = mesh_edges(member_mesh(start,end,width,thickness,orientation))
        return np.min(point_segment_distances(pixels,project(a,measurement),project(b,measurement)),axis=1)/sigma
    predicted = feature_prediction(measurement,start,end,width,thickness,orientation)
    if kind == "image_points":
        pixels = np.asarray(measurement["pixels"],float)
        if pixels.ndim!=2 or pixels.shape[1]!=2 or len(pixels)==0:
            raise ValueError("image_points pixels must be nonempty Nx2")
        observed = pixels.reshape(-1)
    else:
        key = "value_px" if kind.startswith("image") else "value_m"
        observed = np.asarray([measurement[key]],float)
    if observed.shape != predicted.shape or not np.isfinite(observed).all():
        raise ValueError("measurement feature dimensions do not match the prediction")
    return (predicted-observed)/sigma
