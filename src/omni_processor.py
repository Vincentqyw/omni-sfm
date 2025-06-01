import cv2
import json
from pathlib import Path
from tqdm import tqdm
import py360convert
from loguru import logger
import numpy as np
from scipy.spatial.transform import Rotation as R


def compute_focal_length(image_size, fov_deg=90):
    """Create a virtual perspective camera."""
    focal = image_size / (2 * np.tan(np.deg2rad(fov_deg) / 2))
    return focal


class OmniVideoProcessor:
    def __init__(self, params=None):
        self.params = params or {
            "fx": 320.0,
            "fy": 320.0,
            "cx": 320.0,
            "cy": 320.0,
            "height": 640,
            "width": 640,
            "fov_h": 90,
            "fov_v": 90,
            "frame_interval": 24,
            "num_steps_yaw": 4,
            "pitches_deg": [-35.0, 35.0],
            "views": {
                # "pitch_0_yaw_0":   (0, 0),
                # "pitch_0_yaw_90":  (0, 60),
                # "pitch_0_yaw_-90": (0, -90),
                # "pitch_0_yaw_180": (0, 180),
                "pitch_35_yaw_0": (35, 0),
                "pitch_35_yaw_90": (35, 60),
                "pitch_35_yaw_-90": (35, -90),
                "pitch_35_yaw_180": (35, 180),
                "pitch_-35_yaw_0": (-35, 0),
                "pitch_-35_yaw_90": (-35, 60),
                "pitch_-35_yaw_-90": (-35, -90),
                "pitch_-35_yaw_180": (-35, 180),
            },
        }
        self.ref_sensor = list(self.params["views"].keys())[
            0
        ]  # Default reference sensor

    def set_params(self, params):
        self.params = params

    def process_video(self, video_file, output_dir):
        """Process video file with current parameters"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Read video
        video = cv2.VideoCapture(video_file)
        if not video.isOpened():
            raise IOError(f"Cannot open video file: {video_file}")

        frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = video.get(cv2.CAP_PROP_FPS)
        width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Extract frames
        pano_images = self._extract_frames(video, output_dir)
        video.release()

        # Generate pinhole images
        return self._generate_pinhole_images(pano_images, output_dir)

    def _extract_frames(self, video, output_dir):
        """Extract frames from video based on frame interval"""
        frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        # fps = video.get(cv2.CAP_PROP_FPS)
        output_pano_dir = output_dir / "pano_images" / "images"
        output_pano_dir.mkdir(parents=True, exist_ok=True)
        pano_images = []
        for frame_idx in tqdm(range(frame_count)):
            ret, frame = video.read()
            if not ret:
                break
            if frame_idx % self.params["frame_interval"] == 0:
                pano_images.append(frame)
                pano_image_path = output_pano_dir / f"pano_{frame_idx:04d}.jpg"
                cv2.imwrite(str(pano_image_path), frame)
        return pano_images

    def _generate_pinhole_images(self, pano_images, output_dir):
        """Generate pinhole images from panorama frames"""
        output_pinhole_dir = output_dir / "pinhole_images" / "images"
        output_pinhole_dir.mkdir(parents=True, exist_ok=True)
        output_pinhole_parameters_file = (
            output_pinhole_dir.parent / "camera_params.json"
        )

        pinhole_images = []
        pinhole_camera_params = []
        camera_rig_params = {}
        for pano_idx, pano_image in enumerate(pano_images):
            for view_name, (pitch, yaw) in self.params["views"].items():
                pinhole_image = self._convert_to_pinhole(pano_image, pitch, yaw)
                save_path = (
                    output_pinhole_dir
                    / view_name
                    / f"pinhole_{pano_idx:04d}.jpg"
                )
                save_path.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(save_path), pinhole_image)

                pinhole_images.append((pano_idx, view_name, pinhole_image))
                pinhole_camera_params.append(
                    self._create_camera_params(
                        save_path,
                        pano_idx,
                        view_name,
                        pitch,
                        yaw,
                        view_name == self.ref_sensor,
                    )
                )
                if view_name not in camera_rig_params:
                    # Store camera rig parameters for COLMAP
                    camera_rig_params[view_name] = {
                        "image_prefix": view_name,
                        "yaw": yaw,
                        "pitch": pitch,
                        "ref_sensor": view_name == self.ref_sensor,
                    }

        self._save_camera_params(
            pinhole_camera_params, output_pinhole_parameters_file
        )
        self._save_colmap_camera_rig(
            camera_rig_params, output_pinhole_dir.parent / "rig_config.json"
        )

        logger.info(
            f"Saved camera parameters to {output_pinhole_parameters_file}"
        )
        return pinhole_images

    def _convert_to_pinhole(self, pano_image, pitch, yaw):
        """Convert panorama to pinhole view"""
        return py360convert.e2p(
            e_img=pano_image,
            fov_deg=[self.params["fov_h"], self.params["fov_v"]],
            u_deg=yaw,
            v_deg=pitch,
            out_hw=(self.params["height"], self.params["width"]),
            in_rot_deg=0,
            mode="bilinear",
        )

    def _create_camera_params(
        self, save_path: Path, pano_idx, view_name, pitch, yaw, ref_sensor=None
    ):
        """Create camera parameters dictionary"""
        # compute focal length based on FOV and image dimensions
        fx = compute_focal_length(
            self.params["width"], fov_deg=self.params["fov_h"]
        )
        fy = compute_focal_length(
            self.params["height"], fov_deg=self.params["fov_v"]
        )
        return {
            "image_name": save_path.name,
            "fx": fx,
            "fy": fy,
            "cx": self.params["cx"],
            "cy": self.params["cy"],
            "height": self.params["height"],
            "width": self.params["width"],
            "fov_h": self.params["fov_h"],
            "fov_v": self.params["fov_v"],
            "image_prefix": view_name,
            "yaw": yaw,
            "pitch": pitch,
            "pano_index": pano_idx,
            "ref_sensor": ref_sensor,  # Use provided ref_sensor or default
        }

    def _save_camera_params(self, params, output_file):
        """Save camera parameters to JSON file"""
        with open(output_file, "w") as f:
            json.dump(params, f, indent=4)

    def _save_colmap_camera_rig(self, camera_rig_params, output_file):
        """Save camera rig configuration file for COLMAP describing fixed relative poses of virtual pinhole cameras."""
        if not self.params["views"]:
            return

        # Select reference camera (first one by default)
        ref_view_name = list(self.params["views"].keys())[0]
        ref_pitch, ref_yaw = self.params["views"][ref_view_name]

        # Compute reference camera's world rotation
        # COLMAP/OpenCV: X right, Y down, Z forward
        # Using 'yx' order: apply yaw first, then pitch
        R_ref_world = R.from_euler("yx", [ref_yaw, ref_pitch], degrees=True)

        rig_cameras = []
        for image_prefix, params in camera_rig_params.items():
            yaw = params["yaw"]
            pitch = params["pitch"]
            ref_sensor = params.get("ref_sensor", False)

            # Compute current camera's world rotation
            R_view_world = R.from_euler("yx", [yaw, pitch], degrees=True)

            # Compute relative rotation from current camera to reference
            R_ref_view = R_ref_world * R_view_world.inv()

            # Convert to COLMAP quaternion format (w, x, y, z), scipy as_quat() gives (x, y, z, w)
            qvec_scipy = R_ref_view.as_quat()
            qvec_colmap = [
                qvec_scipy[3],
                qvec_scipy[0],
                qvec_scipy[1],
                qvec_scipy[2],
            ]

            # All virtual cameras share optical center, so translation is zero
            tvec = [0.0, 0.0, 0.0]

            if ref_sensor:
                camera_params = {
                    "image_prefix": image_prefix,
                    "ref_sensor": ref_sensor,
                }
            else:
                camera_params = {
                    "image_prefix": image_prefix,
                    "cam_from_rig_translation": tvec,
                    "cam_from_rig_rotation": qvec_colmap,
                }
            rig_cameras.append(camera_params)

        colmap_rig_config = [{"cameras": rig_cameras}]
        with open(output_file, "w") as f:
            json.dump(colmap_rig_config, f, indent=4)
