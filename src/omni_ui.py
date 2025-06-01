import gradio as gr
from pathlib import Path
from PIL import Image
import cv2
import time
from .omni_processor import OmniVideoProcessor


class OmniConverterUI:
    def __init__(self):
        self.processor = OmniVideoProcessor()
        self.default_params = self.processor.params.copy()
        self.max_gallery_items = 20

    def create_interface(self):
        """Create Gradio interface"""
        with gr.Blocks(
            title="Omnidirectional Video to Pinhole Converter"
        ) as demo:
            gr.Markdown("## Omnidirectional Video to Pinhole Converter")

            with gr.Row():
                with gr.Column():
                    # Video input
                    video_input = gr.File(label="Upload Video", type="filepath")

                    # Submit button
                    submit_btn = gr.Button("Convert", variant="primary")

                    # Frame extraction settings
                    with gr.Accordion("Frame Extraction", open=True):
                        frame_interval = gr.Slider(
                            1,
                            100,
                            value=self.default_params["frame_interval"],
                            label="Frame Interval",
                            interactive=True,
                        )

                    # Pinhole camera settings
                    with gr.Accordion("Pinhole Parameters", open=True):
                        with gr.Row():
                            image_width = gr.Slider(
                                100,
                                2000,
                                value=self.default_params["width"],
                                label="Image Width",
                                interactive=True,
                            )
                            image_height = gr.Slider(
                                100,
                                2000,
                                value=self.default_params["height"],
                                label="Image Height",
                                interactive=True,
                            )
                        with gr.Row():
                            cx = gr.Slider(
                                50,
                                1000,
                                value=self.default_params["cx"],
                                label="Principal Point X",
                                interactive=True,
                            )
                            cy = gr.Slider(
                                50,
                                1000,
                                value=self.default_params["cy"],
                                label="Principal Point Y",
                                interactive=True,
                            )
                        with gr.Row():
                            fov_h = gr.Slider(
                                30,
                                180,
                                value=self.default_params["fov_h"],
                                label="Horizontal FOV (deg)",
                                interactive=True,
                            )
                            fov_v = gr.Slider(
                                30,
                                180,
                                value=self.default_params["fov_v"],
                                label="Vertical FOV (deg)",
                                interactive=True,
                            )
                        with gr.Row():
                            fx = gr.Slider(
                                50,
                                1000,
                                value=self.default_params["fx"],
                                label="Focal Length X",
                                interactive=True,
                            )
                            fy = gr.Slider(
                                50,
                                1000,
                                value=self.default_params["fy"],
                                label="Focal Length Y",
                                interactive=True,
                            )

                    # View selection
                    with gr.Accordion("Custom View editions", open=False):
                        with gr.Row():
                            custom_pitch = gr.Slider(
                                -90, 90, value=0, label="Custom Pitch"
                            )
                            custom_yaw = gr.Slider(
                                -180, 180, value=0, label="Custom Yaw"
                            )
                        add_custom = gr.Button("Add Custom View")

                with gr.Column():
                    # Results display
                    output_gallery = gr.Gallery(
                        label="Generated Pinhole Images",
                        columns=len(
                            self.default_params["views"]
                        ),  # Use initial value
                        object_fit="contain",
                        height="auto",
                    )
                    view_state_display = gr.JSON(
                        label="Current Views",
                        value=self.default_params["views"].copy(),
                    )

            # Initialize views state
            views_state = gr.State(self.default_params["views"].copy())

            # Event handlers
            add_custom.click(
                fn=self._update_views,
                inputs=[custom_pitch, custom_yaw, views_state],
                outputs=[views_state, view_state_display],
            )

            submit_btn.click(
                fn=self._run_conversion,
                inputs=[
                    video_input,
                    frame_interval,
                    fx,
                    fy,
                    cx,
                    cy,
                    image_width,
                    image_height,
                    fov_h,
                    fov_v,
                    views_state,
                ],
                outputs=output_gallery,
            )

        return demo

    def _update_views(self, pitch, yaw, current_views):
        """Update views state with new custom view"""
        new_views = {**current_views, f"pitch_{pitch}_yaw_{yaw}": (pitch, yaw)}
        return new_views, new_views

    def _run_conversion(self, video_file, *params):
        """Run conversion with progress tracking"""
        param_names = [
            "frame_interval",
            "fx",
            "fy",
            "cx",
            "cy",
            "width",
            "height",
            "fov_h",
            "fov_v",
            "views",
        ]
        params_dict = dict(zip(param_names, params))

        self.processor.set_params(params_dict)

        output_dir = Path.cwd() / "outputs" / time.strftime("%Y%m%d%H%M%S")
        output_dir.mkdir(parents=True, exist_ok=True)
        pinhole_images = self.processor.process_video(
            video_file.name, output_dir
        )

        image_list_for_gallery = [
            (
                Image.fromarray(cv2.cvtColor(img[2], cv2.COLOR_BGR2RGB)),
                f"Frame {img[0]}, View: {img[1]}",
            )
            for img in pinhole_images
        ][: self.max_gallery_items]
        if not image_list_for_gallery:
            return gr.update(value=[], visible=False)
        return gr.update(
            columns=len(params_dict["views"]), value=image_list_for_gallery
        )
