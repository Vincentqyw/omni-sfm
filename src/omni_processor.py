import cv2
import json
from pathlib import Path
from tqdm import tqdm
import py360convert
from loguru import logger


class OmniVideoProcessor:
    def __init__(self, params=None):
        self.params = params or {
            "focal_length_x": 500.0,
            "focal_length_y": 500.0,
            "principal_point_x": 320.0,
            "principal_point_y": 240.0,
            "height": 480,
            "width": 640,
            "fov_h": 120,
            "fov_v": 120,
            "frame_interval": 24,
            "views": {
                "pitch_0_yaw_0": (0, 0),
                "pitch_0_yaw_60": (0, 60),
                "pitch_0_yaw_300": (0, 300),
            },
        }

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
        fps = video.get(cv2.CAP_PROP_FPS)
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

        for pano_idx, pano_image in enumerate(pano_images):
            for view_name, (pitch, yaw) in self.params["views"].items():
                pinhole_image = self._convert_to_pinhole(pano_image, pitch, yaw)
                save_path = (
                    output_pinhole_dir / f"pinhole_{pano_idx:04d}_{view_name}.jpg"
                )
                cv2.imwrite(str(save_path), pinhole_image)

                pinhole_images.append((pano_idx, view_name, pinhole_image))
                pinhole_camera_params.append(
                    self._create_camera_params(
                        save_path, pano_idx, view_name, pitch, yaw
                    )
                )

        self._save_camera_params(pinhole_camera_params, output_pinhole_parameters_file)
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

    def _create_camera_params(self, save_path: Path, pano_idx, view_name, pitch, yaw):
        """Create camera parameters dictionary"""
        return {
            "image_name": save_path.name,
            "focal_length_x": self.params["focal_length_x"],
            "focal_length_y": self.params["focal_length_y"],
            "cx": self.params["principal_point_x"],
            "cy": self.params["principal_point_y"],
            "height": self.params["height"],
            "width": self.params["width"],
            "fov_h": self.params["fov_h"],
            "fov_v": self.params["fov_v"],
            "view_name": view_name,
            "yaw": yaw,
            "pitch": pitch,
            "pano_index": pano_idx,
        }

    def _save_camera_params(self, params, output_file):
        """Save camera parameters to JSON file"""
        with open(output_file, "w") as f:
            json.dump(params, f, indent=4)
