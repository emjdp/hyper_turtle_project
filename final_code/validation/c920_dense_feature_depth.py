"""Build a dense C920-only surfel map from COLMAP tracks.

This is a fast local fallback for "not sparse" reconstruction when a neural
monocular depth model is not installed. It uses COLMAP's registered C920 poses
and 2D-3D feature tracks as sparse depth anchors, fills a smooth per-image depth
field, then back-projects a dense image grid into the COLMAP world frame.

The output is intentionally called a dense proxy: it is denser than SfM points,
but the filled regions are interpolation/hallucination, not measured MVS depth.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import struct
from typing import Any, Sequence

import cv2
import numpy as np


CAMERA_MODEL_PARAM_COUNTS = {
    0: 3,   # SIMPLE_PINHOLE
    1: 4,   # PINHOLE
    2: 4,   # SIMPLE_RADIAL
    3: 5,   # RADIAL
    4: 8,   # OPENCV
    5: 8,   # OPENCV_FISHEYE
    6: 12,  # FULL_OPENCV
    7: 5,   # FOV
    8: 4,   # SIMPLE_RADIAL_FISHEYE
    9: 5,   # RADIAL_FISHEYE
    10: 12, # THIN_PRISM_FISHEYE
}


MODEL_SPECS = (
    ("component_0_ba", "sparse/0_ba", "150628 + 150854 connected component"),
    ("component_1", "sparse/1", "second connected component"),
)


def build_dense_feature_depth_map(
    colmap_root: str | Path = "outputs/colmap_sfm",
    output_dir: str | Path = "outputs/c920_dense_feature_depth_now",
    *,
    work_width: int = 426,
    grid_stride: int = 3,
    max_images_per_component: int | None = None,
    min_track_points: int = 35,
    voxel_size: float = 0.12,
    max_points_per_component: int = 90000,
) -> dict[str, Any]:
    root = Path(colmap_root)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    image_root = root / "images"
    models: list[dict[str, Any]] = []
    combined_clouds: list[np.ndarray] = []
    for model_id, relative_model_path, label in MODEL_SPECS:
        model_path = root / relative_model_path
        if not model_path.exists():
            continue
        cameras = _read_cameras_binary(model_path / "cameras.bin")
        points_by_id = _read_points3d_binary(model_path / "points3D.bin")
        images = _read_images_binary(model_path / "images.bin")
        if max_images_per_component is not None:
            images = _pick_evenly(images, max_images_per_component)
        model_center = _model_center(points_by_id)
        component_clouds: list[np.ndarray] = []
        frame_rows: list[dict[str, Any]] = []
        for image_index, image in enumerate(images):
            camera = cameras[image["camera_id"]]
            image_path = image_root / image["name"]
            if not image_path.exists():
                continue
            rgb = _read_rgb(image_path)
            sparse = _sparse_depth_points(image, points_by_id)
            if sparse.shape[0] < min_track_points:
                frame_rows.append(
                    {
                        "name": image["name"],
                        "status": "skipped_few_tracks",
                        "track_points": int(sparse.shape[0]),
                    }
                )
                continue
            depth_map, confidence, depth_stats = _filled_depth_map(
                sparse,
                width=int(camera["width"]),
                height=int(camera["height"]),
                work_width=work_width,
            )
            cloud = _backproject_dense_grid(
                rgb,
                depth_map,
                confidence,
                camera,
                image,
                model_center,
                grid_stride=grid_stride,
            )
            if cloud.size:
                component_clouds.append(cloud)
            if image_index < 6:
                _write_depth_debug(
                    output / f"{model_id}_{image_index:03d}_depth.png",
                    depth_map,
                    confidence,
                )
            frame_rows.append(
                {
                    "name": image["name"],
                    "status": "used" if cloud.size else "empty_cloud",
                    "track_points": int(sparse.shape[0]),
                    "dense_points": int(cloud.shape[0]),
                    **depth_stats,
                }
            )

        component_cloud = _fuse_component_clouds(component_clouds)
        raw_points = int(component_cloud.shape[0])
        component_cloud = _voxel_downsample(component_cloud, voxel_size=voxel_size)
        if component_cloud.shape[0] > max_points_per_component:
            component_cloud = _deterministic_sample(component_cloud, max_points_per_component)
        combined_clouds.append(_offset_component_for_view(component_cloud, len(models)))

        component_ply = output / f"{model_id}_dense_feature_depth.ply"
        _write_colored_ply(component_ply, component_cloud)
        model = {
            "id": model_id,
            "label": label,
            "imageCount": int(sum(1 for row in frame_rows if row["status"] == "used")),
            "rawDensePoints": raw_points,
            "pointCount": int(component_cloud.shape[0]),
            "points": _pack_points(component_cloud),
            "bounds": _bounds(component_cloud[:, :3]) if component_cloud.size else {"min": [0, 0, 0], "max": [0, 0, 0]},
            "ply": component_ply.name,
            "frames": frame_rows,
        }
        models.append(model)

    if not models:
        raise RuntimeError(f"no readable COLMAP sparse models found under {root}")

    combined_cloud = _fuse_component_clouds(combined_clouds)
    combined_ply = output / "combined_dense_feature_depth_offset_for_view.ply"
    _write_colored_ply(combined_ply, combined_cloud)
    _write_summary_png(output / "summary.png", models)
    _write_viewer(output / "index.html", models)

    report = {
        "source": str(root),
        "output": str(output),
        "status": "ready",
        "method": "C920-only dense proxy: COLMAP pose + feature-track depth interpolation + dense grid back-projection",
        "important_caveat": (
            "This is not true neural monocular depth or COLMAP dense MVS. "
            "It densifies each registered image from sparse SfM track depths, so textureless areas are approximate."
        ),
        "work_width": int(work_width),
        "grid_stride": int(grid_stride),
        "voxel_size": float(voxel_size),
        "models": [
            {
                "id": model["id"],
                "label": model["label"],
                "registered_images_used": model["imageCount"],
                "raw_dense_points": model["rawDensePoints"],
                "final_points": model["pointCount"],
                "ply": model["ply"],
                "bounds": model["bounds"],
            }
            for model in models
        ],
        "combined_ply": combined_ply.name,
        "viewer": str(output / "index.html"),
        "summary": str(output / "summary.png"),
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _read_cameras_binary(path: Path) -> dict[int, dict[str, Any]]:
    data = path.read_bytes()
    offset = 0
    (count,) = struct.unpack_from("<Q", data, offset)
    offset += 8
    cameras: dict[int, dict[str, Any]] = {}
    for _ in range(count):
        camera_id, model_id, width, height = struct.unpack_from("<iiQQ", data, offset)
        offset += struct.calcsize("<iiQQ")
        param_count = CAMERA_MODEL_PARAM_COUNTS.get(model_id)
        if param_count is None:
            raise ValueError(f"unsupported COLMAP camera model id {model_id}")
        params = struct.unpack_from("<" + "d" * param_count, data, offset)
        offset += 8 * param_count
        cameras[int(camera_id)] = {
            "model_id": int(model_id),
            "width": int(width),
            "height": int(height),
            "params": list(params),
        }
    return cameras


def _read_images_binary(path: Path) -> list[dict[str, Any]]:
    data = path.read_bytes()
    offset = 0
    (count,) = struct.unpack_from("<Q", data, offset)
    offset += 8
    rows: list[dict[str, Any]] = []
    for _ in range(count):
        image_id = struct.unpack_from("<i", data, offset)[0]
        offset += 4
        qvec = np.array(struct.unpack_from("<dddd", data, offset), dtype=np.float64)
        offset += 32
        tvec = np.array(struct.unpack_from("<ddd", data, offset), dtype=np.float64)
        offset += 24
        camera_id = struct.unpack_from("<i", data, offset)[0]
        offset += 4
        end = data.index(b"\x00", offset)
        name = data[offset:end].decode("utf-8", errors="replace")
        offset = end + 1
        num_points2d = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        point_records = np.empty((int(num_points2d), 3), dtype=np.float64)
        point3d_ids = np.empty((int(num_points2d),), dtype=np.int64)
        for idx in range(int(num_points2d)):
            x, y, point3d_id = struct.unpack_from("<ddq", data, offset)
            offset += struct.calcsize("<ddq")
            point_records[idx] = (x, y, float(point3d_id))
            point3d_ids[idx] = int(point3d_id)
        rotation = _qvec_to_rotmat(qvec)
        center = -rotation.T @ tvec
        rows.append(
            {
                "image_id": int(image_id),
                "name": name,
                "camera_id": int(camera_id),
                "qvec": qvec,
                "rotation": rotation,
                "tvec": tvec,
                "center": center,
                "points2d": point_records[:, :2],
                "point3d_ids": point3d_ids,
            }
        )
    return sorted(rows, key=lambda row: row["name"])


def _read_points3d_binary(path: Path) -> dict[int, dict[str, np.ndarray]]:
    data = path.read_bytes()
    offset = 0
    (count,) = struct.unpack_from("<Q", data, offset)
    offset += 8
    points: dict[int, dict[str, np.ndarray]] = {}
    for _ in range(count):
        point_id = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        xyz = np.array(struct.unpack_from("<ddd", data, offset), dtype=np.float64)
        offset += 24
        rgb = np.array(struct.unpack_from("<BBB", data, offset), dtype=np.float64)
        offset += 3
        _error = struct.unpack_from("<d", data, offset)[0]
        offset += 8
        track_len = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        offset += int(track_len) * struct.calcsize("<ii")
        points[int(point_id)] = {"xyz": xyz, "rgb": rgb}
    return points


def _qvec_to_rotmat(qvec: np.ndarray) -> np.ndarray:
    qw, qx, qy, qz = [float(value) for value in qvec]
    return np.array(
        [
            [1 - 2 * qy * qy - 2 * qz * qz, 2 * qx * qy - 2 * qw * qz, 2 * qz * qx + 2 * qw * qy],
            [2 * qx * qy + 2 * qw * qz, 1 - 2 * qz * qz - 2 * qx * qx, 2 * qy * qz - 2 * qw * qx],
            [2 * qz * qx - 2 * qw * qy, 2 * qy * qz + 2 * qw * qx, 1 - 2 * qx * qx - 2 * qy * qy],
        ],
        dtype=np.float64,
    )


def _pick_evenly(rows: Sequence[dict[str, Any]], max_count: int) -> list[dict[str, Any]]:
    if len(rows) <= max_count:
        return list(rows)
    indices = np.linspace(0, len(rows) - 1, max_count).round().astype(int)
    return [rows[int(index)] for index in indices]


def _model_center(points_by_id: dict[int, dict[str, np.ndarray]]) -> np.ndarray:
    xyz = np.vstack([row["xyz"] for row in points_by_id.values()])
    return np.median(xyz, axis=0)


def _read_rgb(path: Path) -> np.ndarray:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise RuntimeError(f"failed to read image: {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _sparse_depth_points(image: dict[str, Any], points_by_id: dict[int, dict[str, np.ndarray]]) -> np.ndarray:
    rows = []
    rotation = image["rotation"]
    tvec = image["tvec"]
    for (u, v), point_id in zip(image["points2d"], image["point3d_ids"]):
        if int(point_id) < 0:
            continue
        point = points_by_id.get(int(point_id))
        if point is None:
            continue
        xyz_world = point["xyz"]
        xyz_camera = rotation @ xyz_world + tvec
        depth = float(xyz_camera[2])
        if not np.isfinite(depth) or depth <= 1e-6:
            continue
        rows.append((float(u), float(v), depth))
    if not rows:
        return np.empty((0, 3), dtype=np.float64)
    values = np.asarray(rows, dtype=np.float64)
    depth = values[:, 2]
    lo, hi = np.percentile(depth, [2.0, 98.0])
    keep = (depth >= lo) & (depth <= hi)
    return values[keep]


def _filled_depth_map(
    sparse_uv_depth: np.ndarray,
    *,
    width: int,
    height: int,
    work_width: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    work_height = max(1, int(round(float(height) * float(work_width) / float(width))))
    sx = float(work_width) / float(width)
    sy = float(work_height) / float(height)
    seeds = np.zeros((work_height, work_width), dtype=np.float32)
    seed_mask = np.zeros((work_height, work_width), dtype=np.uint8)

    u = np.clip(np.round(sparse_uv_depth[:, 0] * sx).astype(int), 0, work_width - 1)
    v = np.clip(np.round(sparse_uv_depth[:, 1] * sy).astype(int), 0, work_height - 1)
    depth = sparse_uv_depth[:, 2]
    inv_depth = 1.0 / np.clip(depth, 1e-6, None)
    inv_lo, inv_hi = np.percentile(inv_depth, [3.0, 97.0])
    if abs(float(inv_hi - inv_lo)) < 1e-12:
        inv_hi = inv_lo + 1e-6
    norm = np.clip((inv_depth - inv_lo) / (inv_hi - inv_lo), 0.0, 1.0)
    for px, py, value in zip(u, v, norm):
        seeds[py, px] = max(float(seeds[py, px]), float(value))
        seed_mask[py, px] = 255

    if int(np.count_nonzero(seed_mask)) < 3:
        depth_map = np.full((work_height, work_width), float(np.median(depth)), dtype=np.float32)
        confidence = np.zeros_like(depth_map)
    else:
        seed_image = np.clip(seeds * 255.0, 0, 255).astype(np.uint8)
        missing = np.where(seed_mask > 0, 0, 255).astype(np.uint8)
        filled_u8 = cv2.inpaint(seed_image, missing, 5.0, cv2.INPAINT_TELEA)
        filled = filled_u8.astype(np.float32) / 255.0
        filled = cv2.GaussianBlur(filled, (0, 0), 1.0)
        filled[seed_mask > 0] = seeds[seed_mask > 0]
        filled_inv = filled * (inv_hi - inv_lo) + inv_lo
        depth_map = (1.0 / np.clip(filled_inv, 1e-6, None)).astype(np.float32)
        missing_binary = np.where(seed_mask > 0, 0, 1).astype(np.uint8)
        distance = cv2.distanceTransform(missing_binary, cv2.DIST_L2, 3)
        confidence = np.exp(-distance / max(16.0, work_width * 0.08)).astype(np.float32)
        confidence[seed_mask > 0] = 1.0

    d_lo, d_hi = np.percentile(depth, [2.0, 98.0])
    depth_map = np.clip(depth_map, float(d_lo), float(d_hi)).astype(np.float32)
    return (
        depth_map,
        confidence,
        {
            "depth_seed_count": int(sparse_uv_depth.shape[0]),
            "seed_depth_p50": float(np.percentile(depth, 50.0)),
            "seed_depth_p10": float(np.percentile(depth, 10.0)),
            "seed_depth_p90": float(np.percentile(depth, 90.0)),
        },
    )


def _backproject_dense_grid(
    image_rgb: np.ndarray,
    depth_map: np.ndarray,
    confidence: np.ndarray,
    camera: dict[str, Any],
    image: dict[str, Any],
    model_center: np.ndarray,
    *,
    grid_stride: int,
) -> np.ndarray:
    height, width = depth_map.shape
    ys, xs = np.mgrid[0:height:grid_stride, 0:width:grid_stride]
    z = depth_map[ys, xs].reshape(-1).astype(np.float64)
    conf = confidence[ys, xs].reshape(-1).astype(np.float64)
    keep = np.isfinite(z) & (z > 0.0) & (conf > 0.045)
    if not np.any(keep):
        return np.empty((0, 6), dtype=np.float64)
    xs = xs.reshape(-1)[keep].astype(np.float64)
    ys = ys.reshape(-1)[keep].astype(np.float64)
    z = z[keep]
    scale_x = float(camera["width"]) / float(width)
    scale_y = float(camera["height"]) / float(height)
    u = (xs + 0.5) * scale_x
    v = (ys + 0.5) * scale_y
    rays = _undistorted_normalized_rays(u, v, camera)
    camera_points = rays * z[:, None]
    world_points = (image["rotation"].T @ (camera_points - image["tvec"]).T).T
    world_points -= model_center

    rgb_h, rgb_w = image_rgb.shape[:2]
    sample_u = np.clip(np.round(u).astype(int), 0, rgb_w - 1)
    sample_v = np.clip(np.round(v).astype(int), 0, rgb_h - 1)
    colors = image_rgb[sample_v, sample_u].astype(np.float64)
    return np.column_stack((world_points, colors))


def _undistorted_normalized_rays(u: np.ndarray, v: np.ndarray, camera: dict[str, Any]) -> np.ndarray:
    model_id = int(camera["model_id"])
    params = [float(value) for value in camera["params"]]
    if model_id == 0:  # SIMPLE_PINHOLE
        f, cx, cy = params[:3]
        x = (u - cx) / f
        y = (v - cy) / f
    elif model_id in {1, 2, 3, 4, 5, 6, 8, 9, 10}:  # pinhole family
        if model_id == 1:
            fx, fy, cx, cy = params[:4]
            dist = np.zeros((4, 1), dtype=np.float64)
        elif model_id == 2:
            f, cx, cy, k1 = params[:4]
            fx = fy = f
            dist = np.array([k1, 0.0, 0.0, 0.0], dtype=np.float64).reshape(-1, 1)
        elif model_id == 3:
            f, cx, cy, k1, k2 = params[:5]
            fx = fy = f
            dist = np.array([k1, k2, 0.0, 0.0], dtype=np.float64).reshape(-1, 1)
        else:
            fx, fy, cx, cy = params[:4]
            if model_id == 4:
                k1, k2, p1, p2 = params[4:8]
                dist = np.array([k1, k2, p1, p2], dtype=np.float64).reshape(-1, 1)
            else:
                dist = np.zeros((4, 1), dtype=np.float64)
        points = np.column_stack((u, v)).astype(np.float64).reshape((-1, 1, 2))
        k = np.array([[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]], dtype=np.float64)
        normalized = cv2.undistortPoints(points, k, dist).reshape((-1, 2))
        x = normalized[:, 0]
        y = normalized[:, 1]
    else:
        raise ValueError(f"unsupported COLMAP camera model id {model_id}")
    return np.column_stack((x, y, np.ones_like(x)))


def _fuse_component_clouds(clouds: Sequence[np.ndarray]) -> np.ndarray:
    non_empty = [np.asarray(cloud, dtype=np.float64).reshape((-1, 6)) for cloud in clouds if cloud.size]
    if not non_empty:
        return np.empty((0, 6), dtype=np.float64)
    return np.vstack(non_empty)


def _voxel_downsample(cloud: np.ndarray, *, voxel_size: float) -> np.ndarray:
    values = np.asarray(cloud, dtype=np.float64).reshape((-1, 6))
    if values.size == 0 or voxel_size <= 0.0:
        return values
    keys = np.floor(values[:, :3] / voxel_size).astype(np.int64)
    _, inverse = np.unique(keys, axis=0, return_inverse=True)
    counts = np.bincount(inverse).astype(np.float64)
    sums = np.zeros((counts.shape[0], 6), dtype=np.float64)
    np.add.at(sums, inverse, values)
    down = sums / counts[:, None]
    down[:, 3:6] = np.clip(np.round(down[:, 3:6]), 0, 255)
    return down


def _deterministic_sample(cloud: np.ndarray, max_count: int) -> np.ndarray:
    values = np.asarray(cloud, dtype=np.float64).reshape((-1, 6))
    if values.shape[0] <= max_count:
        return values
    indices = np.linspace(0, values.shape[0] - 1, max_count).round().astype(int)
    return values[indices]


def _offset_component_for_view(cloud: np.ndarray, component_index: int) -> np.ndarray:
    values = np.asarray(cloud, dtype=np.float64).reshape((-1, 6))
    if values.size == 0:
        return values
    shifted = values.copy()
    shifted[:, 0] += float(component_index) * 70.0
    return shifted


def _pack_points(cloud: np.ndarray) -> list[list[float | int]]:
    packed = []
    for x, y, z, r, g, b in np.asarray(cloud, dtype=np.float64).reshape((-1, 6)):
        packed.append(
            [
                round(float(x), 4),
                round(float(y), 4),
                round(float(z), 4),
                int(np.clip(round(r), 0, 255)),
                int(np.clip(round(g), 0, 255)),
                int(np.clip(round(b), 0, 255)),
            ]
        )
    return packed


def _bounds(xyz: np.ndarray) -> dict[str, list[float]]:
    values = np.asarray(xyz, dtype=np.float64).reshape((-1, 3))
    return {
        "min": [float(value) for value in np.min(values, axis=0)],
        "max": [float(value) for value in np.max(values, axis=0)],
    }


def _write_colored_ply(path: Path, cloud: np.ndarray) -> None:
    values = np.asarray(cloud, dtype=np.float64).reshape((-1, 6))
    lines = [
        "ply",
        "format ascii 1.0",
        f"element vertex {values.shape[0]}",
        "property float x",
        "property float y",
        "property float z",
        "property uchar red",
        "property uchar green",
        "property uchar blue",
        "end_header",
    ]
    for x, y, z, r, g, b in values:
        lines.append(
            f"{x:.6f} {y:.6f} {z:.6f} "
            f"{int(np.clip(round(r), 0, 255))} "
            f"{int(np.clip(round(g), 0, 255))} "
            f"{int(np.clip(round(b), 0, 255))}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_depth_debug(path: Path, depth_map: np.ndarray, confidence: np.ndarray) -> None:
    valid = np.isfinite(depth_map) & (depth_map > 0)
    if not np.any(valid):
        return
    lo, hi = np.percentile(depth_map[valid], [2.0, 98.0])
    scaled = np.clip((depth_map - lo) / max(1e-6, hi - lo) * 255.0, 0, 255).astype(np.uint8)
    colored = cv2.applyColorMap(scaled, cv2.COLORMAP_TURBO)
    alpha = np.clip(confidence, 0.15, 1.0)[:, :, None]
    faded = (colored.astype(np.float32) * alpha + 245.0 * (1.0 - alpha)).astype(np.uint8)
    cv2.imwrite(str(path), faded)


def _write_summary_png(path: Path, models: Sequence[dict[str, Any]]) -> None:
    canvas = np.full((920, 1400, 3), 248, dtype=np.uint8)
    _draw_text(canvas, "C920 dense feature-depth reconstruction", (34, 54), 0.95, (30, 30, 30), 2)
    _draw_text(
        canvas,
        "Dense proxy: each C920 image is filled from COLMAP 2D-3D feature-track depths, then back-projected.",
        (34, 92),
        0.56,
        (70, 70, 70),
        1,
    )
    x0, y0 = 34, 132
    for index, model in enumerate(models):
        y = y0 + index * 360
        preview = _render_cloud_preview(np.asarray(model["points"], dtype=np.float64), width=760, height=300)
        canvas[y : y + preview.shape[0], x0 : x0 + preview.shape[1]] = preview
        tx = 840
        _draw_text(canvas, model["id"], (tx, y + 34), 0.75, (30, 30, 30), 2)
        _draw_text(canvas, f"{model['pointCount']:,} final dense surfels", (tx, y + 76), 0.58, (60, 60, 60), 1)
        _draw_text(canvas, f"{model['rawDensePoints']:,} raw back-projected grid points", (tx, y + 108), 0.58, (60, 60, 60), 1)
        _draw_text(canvas, f"{model['imageCount']} C920 images used", (tx, y + 140), 0.58, (60, 60, 60), 1)
    _draw_text(
        canvas,
        "Caveat: filled textureless regions are approximate; true full-density needs monocular depth or dense MVS.",
        (34, 870),
        0.62,
        (35, 80, 150),
        2,
    )
    cv2.imwrite(str(path), canvas)


def _render_cloud_preview(points: np.ndarray, *, width: int, height: int) -> np.ndarray:
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    if points.size == 0:
        return canvas
    cloud = points.reshape((-1, 6))
    xy = cloud[:, [0, 2]]
    finite = np.isfinite(xy).all(axis=1)
    xy = xy[finite]
    colors = cloud[finite, 3:6]
    if xy.size == 0:
        return canvas
    lo = np.percentile(xy, 2, axis=0)
    hi = np.percentile(xy, 98, axis=0)
    center = (lo + hi) / 2.0
    span = np.maximum(hi - lo, 1.0)
    scale = min((width - 30) / span[0], (height - 30) / span[1])
    uv = (xy - center) * scale
    px = np.round(width / 2 + uv[:, 0]).astype(int)
    py = np.round(height / 2 - uv[:, 1]).astype(int)
    order = np.linspace(0, len(px) - 1, min(len(px), 60000), dtype=int)
    for idx in order:
        if 0 <= px[idx] < width and 0 <= py[idx] < height:
            cv2.circle(canvas, (int(px[idx]), int(py[idx])), 1, tuple(int(v) for v in colors[idx, ::-1]), -1)
    cv2.rectangle(canvas, (0, 0), (width - 1, height - 1), (210, 210, 210), 1)
    return canvas


def _draw_text(
    image: np.ndarray,
    text: str,
    origin: tuple[int, int],
    scale: float,
    color: tuple[int, int, int],
    thickness: int,
) -> None:
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def _write_viewer(path: Path, models: Sequence[dict[str, Any]]) -> None:
    data = json.dumps({"models": models}, ensure_ascii=False, separators=(",", ":"))
    html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>C920 Dense Feature-Depth Viewer</title>
  <style>
    html, body {{ margin: 0; height: 100%; overflow: hidden; font-family: system-ui, sans-serif; background: #111; color: #eee; }}
    canvas {{ display: block; width: 100vw; height: 100vh; }}
    .hud {{ position: fixed; left: 14px; top: 14px; width: min(460px, calc(100vw - 28px)); background: rgba(16,18,20,.84); border: 1px solid rgba(255,255,255,.14); border-radius: 8px; padding: 12px; backdrop-filter: blur(8px); }}
    .hud h1 {{ font-size: 17px; margin: 0 0 8px; }}
    .hud p {{ margin: 6px 0; color: #cfd6df; font-size: 13px; line-height: 1.35; }}
    .row {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 10px; }}
    button {{ border: 1px solid rgba(255,255,255,.2); background: #1f2933; color: #f6f7f9; border-radius: 6px; padding: 7px 10px; font-size: 13px; cursor: pointer; }}
    button.active {{ background: #2f80ed; border-color: #74a9f5; }}
    .pill {{ color: #dbeafe; background: rgba(47,128,237,.24); border: 1px solid rgba(116,169,245,.4); border-radius: 999px; padding: 4px 8px; font-size: 12px; }}
  </style>
</head>
<body>
<canvas id="view"></canvas>
<section class="hud">
  <h1>C920 dense feature-depth map</h1>
  <p id="stats"></p>
  <p>마우스 드래그 회전, 휠 줌, WASD 이동, Q/E 위아래. 이 결과는 sparse point가 아니라 이미지 grid를 depth 보간 후 역투영한 dense surfel입니다.</p>
  <div class="row" id="buttons"></div>
  <div class="row"><span class="pill">scale: COLMAP-relative</span><span class="pill">dense proxy</span><span class="pill">C920 only</span></div>
</section>
<script id="model-data" type="application/json">{data}</script>
<script>
const DATA = JSON.parse(document.getElementById('model-data').textContent);
const canvas = document.getElementById('view');
const gl = canvas.getContext('webgl', {{ antialias: true }});
if (!gl) throw new Error('WebGL unavailable');
const program = makeProgram(`
attribute vec3 position;
attribute vec3 color;
uniform mat4 mvp;
uniform float pointSize;
varying vec3 vColor;
void main() {{
  gl_Position = mvp * vec4(position, 1.0);
  gl_PointSize = pointSize;
  vColor = color;
}}`, `
precision mediump float;
varying vec3 vColor;
void main() {{
  vec2 c = gl_PointCoord - vec2(0.5);
  if (dot(c, c) > 0.25) discard;
  gl_FragColor = vec4(vColor, 1.0);
}}`);
const loc = {{
  position: gl.getAttribLocation(program, 'position'),
  color: gl.getAttribLocation(program, 'color'),
  mvp: gl.getUniformLocation(program, 'mvp'),
  pointSize: gl.getUniformLocation(program, 'pointSize')
}};
let activeIndex = 0;
const buffers = DATA.models.map(makeBuffers);
let view = {{ yaw: -0.55, pitch: -0.42, distance: 60, target: [0,0,0] }};
let dragging = false;
let last = [0,0];
const keys = new Set();
setupButtons();
resize();
requestAnimationFrame(draw);
window.addEventListener('resize', resize);
window.addEventListener('keydown', e => keys.add(e.key.toLowerCase()));
window.addEventListener('keyup', e => keys.delete(e.key.toLowerCase()));
canvas.addEventListener('mousedown', e => {{ dragging = true; last = [e.clientX, e.clientY]; }});
window.addEventListener('mouseup', () => dragging = false);
window.addEventListener('mousemove', e => {{
  if (!dragging) return;
  const dx = e.clientX - last[0], dy = e.clientY - last[1];
  last = [e.clientX, e.clientY];
  view.yaw += dx * 0.006;
  view.pitch = Math.max(-1.45, Math.min(1.45, view.pitch + dy * 0.006));
}});
canvas.addEventListener('wheel', e => {{
  e.preventDefault();
  view.distance *= Math.exp(e.deltaY * 0.001);
  view.distance = Math.max(2, Math.min(600, view.distance));
}}, {{ passive: false }});

function setupButtons() {{
  const root = document.getElementById('buttons');
  root.textContent = '';
  DATA.models.forEach((model, index) => {{
    const button = document.createElement('button');
    button.textContent = model.id;
    button.onclick = () => {{
      activeIndex = index;
      const b = model.bounds;
      view.target = [(b.min[0]+b.max[0])/2, (b.min[1]+b.max[1])/2, (b.min[2]+b.max[2])/2];
      view.distance = Math.max(20, Math.hypot(b.max[0]-b.min[0], b.max[1]-b.min[1], b.max[2]-b.min[2]) * 1.0);
      setupButtons();
    }};
    if (index === activeIndex) button.classList.add('active');
    root.appendChild(button);
  }});
}}
function makeBuffers(model) {{
  const vertices = new Float32Array(model.points.length * 3);
  const colors = new Float32Array(model.points.length * 3);
  model.points.forEach((p, i) => {{
    vertices.set([p[0], p[1], p[2]], i * 3);
    colors.set([p[3] / 255, p[4] / 255, p[5] / 255], i * 3);
  }});
  return {{ pointCount: model.points.length, vertexBuffer: buffer(vertices), colorBuffer: buffer(colors) }};
}}
function buffer(values) {{
  const b = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, b);
  gl.bufferData(gl.ARRAY_BUFFER, values, gl.STATIC_DRAW);
  return b;
}}
function draw() {{
  updateMotion();
  resize();
  const model = DATA.models[activeIndex];
  const b = buffers[activeIndex];
  document.getElementById('stats').textContent = `${{model.label}} · ${{model.pointCount.toLocaleString()}} dense surfels · ${{model.imageCount}} images`;
  gl.viewport(0, 0, canvas.width, canvas.height);
  gl.enable(gl.DEPTH_TEST);
  gl.clearColor(0.055, 0.06, 0.07, 1);
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  const aspect = canvas.width / Math.max(1, canvas.height);
  const projection = perspective(55 * Math.PI / 180, aspect, 0.05, 2000);
  const eye = eyePosition();
  const viewMat = lookAt(eye, view.target, [0,1,0]);
  const mvp = multiply(projection, viewMat);
  gl.useProgram(program);
  gl.uniformMatrix4fv(loc.mvp, false, new Float32Array(mvp));
  gl.uniform1f(loc.pointSize, Math.max(1.2, Math.min(4.0, 140 / view.distance)));
  gl.bindBuffer(gl.ARRAY_BUFFER, b.vertexBuffer);
  gl.enableVertexAttribArray(loc.position);
  gl.vertexAttribPointer(loc.position, 3, gl.FLOAT, false, 0, 0);
  gl.bindBuffer(gl.ARRAY_BUFFER, b.colorBuffer);
  gl.enableVertexAttribArray(loc.color);
  gl.vertexAttribPointer(loc.color, 3, gl.FLOAT, false, 0, 0);
  gl.drawArrays(gl.POINTS, 0, b.pointCount);
  requestAnimationFrame(draw);
}}
function updateMotion() {{
  const speed = Math.max(0.05, view.distance * 0.012);
  const forward = normalize(sub(view.target, eyePosition()));
  const right = normalize(cross(forward, [0,1,0]));
  const up = [0,1,0];
  let delta = [0,0,0];
  if (keys.has('w')) delta = add(delta, scale(forward, speed));
  if (keys.has('s')) delta = add(delta, scale(forward, -speed));
  if (keys.has('a')) delta = add(delta, scale(right, -speed));
  if (keys.has('d')) delta = add(delta, scale(right, speed));
  if (keys.has('q')) delta = add(delta, scale(up, -speed));
  if (keys.has('e')) delta = add(delta, scale(up, speed));
  view.target = add(view.target, delta);
}}
function eyePosition() {{
  const cp = Math.cos(view.pitch), sp = Math.sin(view.pitch);
  const cy = Math.cos(view.yaw), sy = Math.sin(view.yaw);
  return [view.target[0] + view.distance * cp * sy, view.target[1] + view.distance * sp, view.target[2] + view.distance * cp * cy];
}}
function resize() {{
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const w = Math.floor(canvas.clientWidth * dpr), h = Math.floor(canvas.clientHeight * dpr);
  if (canvas.width !== w || canvas.height !== h) {{ canvas.width = w; canvas.height = h; }}
}}
function makeProgram(vsSource, fsSource) {{
  const p = gl.createProgram();
  gl.attachShader(p, compile(gl.VERTEX_SHADER, vsSource));
  gl.attachShader(p, compile(gl.FRAGMENT_SHADER, fsSource));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  return p;
}}
function compile(type, source) {{
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
  return shader;
}}
function perspective(fov, aspect, near, far) {{
  const f = 1 / Math.tan(fov / 2), nf = 1 / (near - far);
  return [f/aspect,0,0,0, 0,f,0,0, 0,0,(far+near)*nf,-1, 0,0,2*far*near*nf,0];
}}
function lookAt(eye, center, up) {{
  const z = normalize(sub(eye, center));
  const x = normalize(cross(up, z));
  const y = cross(z, x);
  return [x[0],y[0],z[0],0, x[1],y[1],z[1],0, x[2],y[2],z[2],0, -dot(x,eye),-dot(y,eye),-dot(z,eye),1];
}}
function multiply(a, b) {{
  const out = new Array(16).fill(0);
  for (let c=0;c<4;c++) for (let r=0;r<4;r++) for (let k=0;k<4;k++) out[c*4+r] += a[k*4+r] * b[c*4+k];
  return out;
}}
function add(a,b) {{ return [a[0]+b[0], a[1]+b[1], a[2]+b[2]]; }}
function sub(a,b) {{ return [a[0]-b[0], a[1]-b[1], a[2]-b[2]]; }}
function scale(a,s) {{ return [a[0]*s,a[1]*s,a[2]*s]; }}
function dot(a,b) {{ return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }}
function cross(a,b) {{ return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]; }}
function normalize(a) {{ const l = Math.hypot(a[0],a[1],a[2]) || 1; return [a[0]/l,a[1]/l,a[2]/l]; }}
</script>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build dense C920-only feature-depth surfel map.")
    parser.add_argument("--colmap-root", default="outputs/colmap_sfm")
    parser.add_argument("--output", default="outputs/c920_dense_feature_depth_now")
    parser.add_argument("--work-width", type=int, default=426)
    parser.add_argument("--grid-stride", type=int, default=3)
    parser.add_argument("--max-images-per-component", type=int, default=None)
    parser.add_argument("--min-track-points", type=int, default=35)
    parser.add_argument("--voxel-size", type=float, default=0.12)
    parser.add_argument("--max-points-per-component", type=int, default=90000)
    args = parser.parse_args(argv)
    report = build_dense_feature_depth_map(
        args.colmap_root,
        args.output,
        work_width=args.work_width,
        grid_stride=args.grid_stride,
        max_images_per_component=args.max_images_per_component,
        min_track_points=args.min_track_points,
        voxel_size=args.voxel_size,
        max_points_per_component=args.max_points_per_component,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
