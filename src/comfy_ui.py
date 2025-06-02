import os
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

try:
    from .omni_processor import OmniVideoProcessor
except ImportError:
    print(
        "Warning: omni_processor not found, some functionality may be limited",
        file=sys.stderr,
    )
try:
    from .read_write_model import read_model
except ImportError:
    print(
        "Warning: read_write_model not found, some functionality may be limited",
        file=sys.stderr,
    )


class OmniParameterControls:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "frame_interval": (
                    "INT",
                    {"default": 24, "min": 1, "max": 100},
                ),
                "width": ("INT", {"default": 640, "min": 100, "max": 2000}),
                "height": ("INT", {"default": 640, "min": 100, "max": 2000}),
                "cx": ("FLOAT", {"default": 320.0, "min": 0.0, "max": 2000.0}),
                "cy": ("FLOAT", {"default": 320.0, "min": 0.0, "max": 2000.0}),
                "fov_h": (
                    "FLOAT",
                    {"default": 90.0, "min": 30.0, "max": 180.0},
                ),
                "fov_v": (
                    "FLOAT",
                    {"default": 90.0, "min": 30.0, "max": 180.0},
                ),
                "base_pitch": (
                    "FLOAT",
                    {"default": 35.0, "min": -90.0, "max": 90.0},
                ),
                "yaw_steps": ("INT", {"default": 4, "min": 1, "max": 12}),
                "yaw_offset": (
                    "FLOAT",
                    {"default": 0.0, "min": -180.0, "max": 180.0},
                ),
            },
            "optional": {
                "pano_projection": (
                    ["equirectangular", "cubemap"],
                    {"default": "equirectangular"},
                ),
                "pano_quality": (
                    ["low", "medium", "high"],
                    {"default": "medium"},
                ),
                "stabilize": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("OMNI_PARAMS",)
    FUNCTION = "get_params"
    CATEGORY = "Omnidirectional Video"

    def get_params(
        self,
        frame_interval,
        width,
        height,
        fov_h,
        fov_v,
        base_pitch,
        yaw_steps,
        yaw_offset,
        **kwargs,
    ):
        # Generate views based on parameters
        views = {}
        yaw_step = 360.0 / yaw_steps

        # Add positive pitch views
        for i in range(yaw_steps):
            yaw = (i * yaw_step + yaw_offset) % 360
            if yaw > 180:
                yaw -= 360
            views[f"pitch_{base_pitch}_yaw_{round(yaw,1)}"] = (base_pitch, yaw)

        # Add negative pitch views
        for i in range(yaw_steps):
            yaw = (i * yaw_step + yaw_offset) % 360
            if yaw > 180:
                yaw -= 360
            views[f"pitch_{-base_pitch}_yaw_{round(yaw,1)}"] = (
                -base_pitch,
                yaw,
            )

        params = {
            "frame_interval": frame_interval,
            "width": width,
            "height": height,
            "fov_h": fov_h,
            "fov_v": fov_v,
            "views": views,
        }
        params.update(kwargs)
        return (params,)


class OmniVideoProcessorNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "omni_video": ("IMAGE",),
                "omni_params": ("OMNI_PARAMS",),
            }
        }

    RETURN_TYPES = ("OMNI_PROCESSED",)
    FUNCTION = "process_video"
    CATEGORY = "Omnidirectional Video"

    def process_video(self, omni_video, omni_params):
        import tempfile
        import time
        from tempfile import gettempdir

        # VideoFromFile

        run_timestamp = time.strftime("%Y%m%d-%H%M%S")
        output_dir = Path(gettempdir()) / f"omni_output_{run_timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        processor = OmniVideoProcessor(omni_params)
        panoramic_frames, pinhole_images_data = processor.process_video(omni_video, output_dir)
        result = {
            "output_dir": str(output_dir),
            "panoramic_frames": panoramic_frames,
            "pinhole_views": pinhole_images_data,
        }

        return (result,)


class OmniReconstructionNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "omni_processed": ("OMNI_PROCESSED",),
                "colmap_path": ("STRING", {"default": "colmap"}),
                "quality": (
                    ["low", "medium", "high", "extreme"],
                    {"default": "medium"},
                ),
            }
        }

    RETURN_TYPES = ("RECONSTRUCTION", "model_file")
    RETURN_NAMES = ("reconstruction", "model_file")
    FUNCTION = "run_reconstruction"
    CATEGORY = "Omnidirectional Video"

    def run_reconstruction(self, omni_processed, colmap_path, quality):
        output_dir = Path(omni_processed["output_dir"])
        image_dir = output_dir / "pinhole_images" / "images"
        db_path = output_dir / "database.db"
        rig_config_path = output_dir / "pinhole_images" / "rig_config.json"
        sparse_dir = output_dir / "sparse"
        dense_dir = output_dir / "dense"

        # Create necessary directories
        sparse_dir.mkdir(exist_ok=True)
        dense_dir.mkdir(exist_ok=True)

        cmds = [
            f'"{colmap_path}" feature_extractor --database_path "{db_path}" --image_path "{image_dir}" --ImageReader.camera_model PINHOLE --ImageReader.single_camera_per_folder 1',
            f'"{colmap_path}" sequential_matcher --database_path "{db_path}" --SequentialMatching.loop_detection 1',
            f'"{colmap_path}" mapper --database_path "{db_path}" --image_path "{image_dir}" --output_path "{sparse_dir}" --Mapper.ba_refine_focal_length 0 --Mapper.ba_refine_principal_point 0 --Mapper.ba_refine_extra_params 0',
        ]

        for cmd in cmds:
            print(f"Executing: {cmd}")
            ret = os.system(cmd)
            if ret != 0:
                raise RuntimeError(f"Command failed with exit code {ret}: {cmd}")
        # generate mesh and point cloud
        cameras, images, points3D = read_model(sparse_dir / "0")
        sparse_ply_path = sparse_dir / "0" / "sparse.ply"
        # points3d_data = []
        # for pts in points3D.values():
        #     # pts.rgb = pts.rgb.astype(np.float32) / 255.0
        #     points3d_data.append(
        #         (
        #             pts.xyz[0],
        #             pts.xyz[1],
        #             pts.xyz[2],
        #             pts.rgb[0],
        #             pts.rgb[1],
        #             pts.rgb[2],
        #         )
        #     )

        # with open(sparse_ply_path, "w") as f:
        #     f.write("ply\n")
        #     f.write("format ascii 1.0\n")
        #     f.write(f"element vertex {len(points3d_data)}\n")
        #     f.write("property float x\n")
        #     f.write("property float y\n")
        #     f.write("property float z\n")
        #     f.write("property uchar red\n")
        #     f.write("property uchar green\n")
        #     f.write("property uchar blue\n")
        #     f.write("end_header\n")
        #     for p in points3d_data:
        #         f.write(f"{p[0]} {p[1]} {p[2]} {int(p[3])} {int(p[4])} {int(p[5])}\n")
        print(f"Generated sparse point cloud at: {sparse_ply_path}")
        return (
            str(sparse_dir / "0"),
            str(sparse_ply_path),
        )


class OmniPreviewNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "reconstruction": ("RECONSTRUCTION",),
                "model_file": ("model_file",),
            },
            "optional": {
                "show_type": (
                    ["input_frame", "reconstruction", "mesh", "model_file"],
                    {"default": "input_frame"},
                ),
                "view_yaw": (
                    "FLOAT",
                    {"default": 0.0, "min": -180.0, "max": 180.0},
                ),
                "view_pitch": (
                    "FLOAT",
                    {"default": 0.0, "min": -90.0, "max": 90.0},
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "generate_preview"
    CATEGORY = "Omnidirectional Video"

    def _create_placeholder_preview(self, text):
        img = Image.new("RGB", (640, 480), (30, 30, 50))
        try:
            from PIL import ImageDraw, ImageFont

            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("Arial.ttf", 40)
            except:
                font = ImageFont.load_default()
            text_width = draw.textlength(text, font=font)
            position = ((640 - text_width) // 2, 220)
            draw.text(position, text, fill=(200, 200, 255), font=font)
        except ImportError:
            pass
        return img

    def generate_preview(self, show_type="input_frame", view_yaw=0.0, view_pitch=0.0, **kwargs):
        blank_image = self._create_placeholder_preview("No Preview Available")

        def to_tensor(img):
            img = img.convert("RGB").resize((640, 480))
            return torch.from_numpy(np.array(img).astype(np.float32) / 255.0)[None,]

        if show_type in ["reconstruction", "mesh", "model_file"]:
            file_path = kwargs.get(show_type)
            if file_path and Path(file_path).exists():
                text = f"{show_type.replace('_', ' ').title()} Ready"
                image = self._create_placeholder_preview(text)
                return (to_tensor(image),)

        return (to_tensor(blank_image),)


# NEW NODE FOR ADVANCED VISUALIZATION
class OmniAdvancedPreviewNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "omni_processed": ("OMNI_PROCESSED",),
                "show_type": (["Pinhole Images", "Panoramic Frames"],),
                "max_items_to_show": (
                    "INT",
                    {"default": 8, "min": 1, "max": 64},
                ),
                "start_index": ("INT", {"default": 0, "min": 0}),
                "enable_annotation": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "generate_preview_batch"
    CATEGORY = "Omnidirectional Video"

    def generate_preview_batch(
        self,
        omni_processed,
        show_type,
        max_items_to_show,
        start_index,
        enable_annotation,
    ):
        images_to_process = []
        if show_type == "Pinhole Images" and "pinhole_views" in omni_processed:
            images_to_process = omni_processed["pinhole_views"]
        elif show_type == "Panoramic Frames" and "panoramic_frames" in omni_processed:
            images_to_process = omni_processed["panoramic_frames"]

        if not images_to_process:
            blank_image = Image.new("RGB", (256, 256), "black")
            return (torch.from_numpy(np.array(blank_image).astype(np.float32) / 255.0)[None,],)

        # 分页逻辑
        end_index = start_index + max_items_to_show
        subset = images_to_process[start_index:end_index]

        output_images = []
        for item in subset:
            if isinstance(item, dict) and "image" in item:
                img_data = item["image"]
            if isinstance(item, dict) and "frame" in item:
                img_data = item["frame"]
            if isinstance(img_data, str):
                img_data = cv2.imread(img_data)
                img_data = cv2.cvtColor(img_data, cv2.COLOR_BGR2RGB)
            if img_data is None:
                print(f"Warning: Image data is None for item {item}")
                continue
            pil_img = Image.fromarray(img_data)

            if show_type == "Pinhole Images" and enable_annotation:
                from PIL import ImageDraw, ImageFont

                draw = ImageDraw.Draw(pil_img)
                try:
                    font = ImageFont.truetype("arial.ttf", 20)
                except IOError:
                    font = ImageFont.load_default()

                text = (
                    f"P: {item['pitch']:.1f}, Y: {item['yaw']:.1f}\n"
                    f"Size: {item['width']}x{item['height']}\n"
                    f"Pano Idx: {item['pano_index']}"
                )

                draw.text((10, 10), text, font=font, fill="yellow")

            img_tensor = torch.from_numpy(np.array(pil_img).astype(np.float32) / 255.0)
            output_images.append(img_tensor)

        if not output_images:
            blank_image = Image.new("RGB", (256, 256), "black")
            return (torch.from_numpy(np.array(blank_image).astype(np.float32) / 255.0)[None,],)

        return (torch.stack(output_images),)


# UPDATE THE NODE MAPPINGS
NODE_CLASS_MAPPINGS = {
    # "OmniLoadVideoUpload": OmniLoadVideoUpload,
    "OmniParameterControls": OmniParameterControls,
    "OmniVideoProcessor": OmniVideoProcessorNode,
    "OmniReconstruction": OmniReconstructionNode,
    "OmniPreview": OmniPreviewNode,  # Keeping the old one for simple previews
    "OmniAdvancedPreview": OmniAdvancedPreviewNode,  # Adding the new one
}

NODE_DISPLAY_NAME_MAPPINGS = {
    # "OmniLoadVideoUpload": "Load Omni Video Upload",
    "OmniParameterControls": "Omnidirectional Parameters",
    "OmniVideoProcessor": "Process Omnidirectional Video",
    "OmniReconstruction": "Run COLMAP Reconstruction",
    "OmniPreview": "Omni Model Preview",  # Renamed for clarity
    "OmniAdvancedPreview": "Omni Advanced Preview",  # New node's display name
}
