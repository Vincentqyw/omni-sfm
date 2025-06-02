import cv2
import json
from pathlib import Path
from tqdm import tqdm
import py360convert
import numpy as np
import torch
from scipy.spatial.transform import Rotation as R


def compute_focal_length(image_size, fov_deg):
    return (image_size / 2) / np.tan(np.deg2rad(fov_deg) / 2)


class OmniVideoProcessor:
    default_params = {
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
    def __init__(self, params = {}):
        self.params = params if params else self.default_params.copy()
        self.ref_sensor = list(self.params["views"].keys())[0]

    def set_params(self, params):
        self.params = params

    def process_video(self, video_or_path, output_dir):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if isinstance(video_or_path, str):
            video_file = Path(video_or_path)
            video = cv2.VideoCapture(str(video_file))
            if not video.isOpened():
                raise IOError(f"Cannot open video file: {video_file}")
            pano_images = self._extract_frames(video, output_dir)
            video.release()
        elif isinstance(video_or_path, torch.Tensor) or isinstance(
            video_or_path, np.ndarray
        ):
            pano_images = self._extract_frames_torch(video_or_path)
        else:
            raise ValueError("video_or_path must be a string or Path object")

        pinhole_images_data = self._generate_pinhole_images(pano_images, output_dir)
        return pano_images, pinhole_images_data

    def _extract_frames(self, video, output_dir):
        frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        pano_images = []

        for frame_idx in tqdm(range(frame_count), desc="Extracting Frames"):
            ret, frame = video.read()
            if not ret:
                break
            if frame_idx % self.params["frame_interval"] == 0:
                pano_images.append({"image": frame, "idx": frame_idx})
        return pano_images

    def _extract_frames_torch(self, video_tensor):
        if not isinstance(video_tensor, torch.Tensor):
            raise ValueError("video_tensor must be a torch.Tensor")

        pano_images = []
        num_frames = video_tensor.shape[0]

        for frame_idx in tqdm(range(num_frames), desc="Extracting Frames"):
            if frame_idx % self.params["frame_interval"] == 0:
                # Assuming video_tensor is normalized [0, 1], rgb mode
                img = video_tensor[frame_idx].numpy() * 255.0
                img = img.astype(np.uint8)  # Convert to uint8
                pano_images.append({"image": img, "idx": frame_idx})

        return pano_images

    def _generate_pinhole_images(self, pano_images, output_dir):
        output_pinhole_dir = output_dir / "pinhole_images" / "images"
        output_pinhole_dir.mkdir(parents=True, exist_ok=True)

        pinhole_data = []
        camera_params_list = []
        camera_rig_params = {}
        pinhole_views = []

        for pano_info in tqdm(pano_images, desc="Generating Pinhole Views"):
            pano_idx, pano_image = pano_info["idx"], pano_info["image"]
            for view_name, (pitch, yaw) in self.params["views"].items():
                pinhole_image = self._convert_to_pinhole(pano_image, pitch, yaw)

                save_dir = output_pinhole_dir / view_name
                save_dir.mkdir(parents=True, exist_ok=True)
                save_path = save_dir / f"{pano_idx:06d}.jpg"
                cv2.imwrite(str(save_path), pinhole_image)

                h, w = pinhole_image.shape[:2]
                pinhole_views.append(
                    {
                        "image": pinhole_image,
                        "pano_index": pano_idx,
                        "view_name": view_name,
                        "pitch": pitch,
                        "yaw": yaw,
                        "width": w,
                        "height": h,
                        "save_path": str(save_path),
                    }
                )

                pinhole_data.append(
                    (pano_idx, view_name, pinhole_image, str(save_path))
                )

                is_ref = view_name == self.ref_sensor
                cam_params = self._create_camera_params(
                    save_path, pano_idx, view_name, pitch, yaw, is_ref
                )
                camera_params_list.append(cam_params)

                if view_name not in camera_rig_params:
                    camera_rig_params[view_name] = {
                        "image_prefix": view_name,
                        "yaw": yaw,
                        "pitch": pitch,
                        "ref_sensor": is_ref,
                    }

        self._save_camera_params(
            camera_params_list,
            output_dir / "pinhole_images" / "camera_params.json",
        )
        self._save_colmap_camera_rig(
            camera_rig_params, output_dir / "pinhole_images" / "rig_config.json"
        )

        return pinhole_views

    def _convert_to_pinhole(self, pano_image, pitch, yaw):
        return py360convert.e2p(
            e_img=pano_image,
            fov_deg=(self.params["fov_h"], self.params["fov_v"]),
            u_deg=yaw,
            v_deg=pitch,
            out_hw=(self.params["height"], self.params["width"]),
            in_rot_deg=0,
            mode="bilinear",
        )

    def _create_camera_params(
        self, save_path: Path, pano_idx, view_name, pitch, yaw, ref_sensor=None
    ):
        fx = compute_focal_length(self.params["width"], self.params["fov_h"])
        fy = compute_focal_length(self.params["height"], self.params["fov_v"])
        return {
            "image_name": save_path.name,
            "image_prefix": view_name,
            "fx": fx,
            "fy": fy,
            "cx": self.params["width"] / 2,
            "cy": self.params["height"] / 2,
            "height": self.params["height"],
            "width": self.params["width"],
            "fov_h": self.params["fov_h"],
            "fov_v": self.params["fov_v"],
            "yaw": yaw,
            "pitch": pitch,
            "pano_index": pano_idx,
            "ref_sensor": ref_sensor,
        }

    def _save_camera_params(self, params, output_file):
        with open(output_file, "w") as f:
            json.dump(params, f, indent=4)

    def _save_colmap_camera_rig(self, camera_rig_params, output_file):
        if not self.params["views"]:
            return

        ref_view_name = list(self.params["views"].keys())[0]
        ref_pitch, ref_yaw = self.params["views"][ref_view_name]

        # COLMAP: X right, Y down, Z forward. Euler: yaw, pitch, roll
        R_ref_world = R.from_euler("yx", [ref_yaw, ref_pitch], degrees=True)

        rig_cameras = []
        for image_prefix, params in camera_rig_params.items():
            R_view_world = R.from_euler(
                "yx", [params["yaw"], params["pitch"]], degrees=True
            )
            R_view_ref = R_view_world.inv() * R_ref_world  # Cam from Rig

            # Scipy quat (x,y,z,w) -> COLMAP quat (w,x,y,z)
            qvec_scipy = R_view_ref.as_quat()
            qvec_colmap = [
                qvec_scipy[3],
                qvec_scipy[0],
                qvec_scipy[1],
                qvec_scipy[2],
            ]

            cam_entry = {"image_prefix": image_prefix}
            if params.get("ref_sensor"):
                cam_entry["ref_sensor"] = True
            else:
                cam_entry["cam_from_rig_rotation"] = qvec_colmap
                cam_entry["cam_from_rig_translation"] = [0.0, 0.0, 0.0]
            rig_cameras.append(cam_entry)

        colmap_rig_config = [{"cameras": rig_cameras}]
        with open(output_file, "w") as f:
            json.dump(colmap_rig_config, f, indent=4)
