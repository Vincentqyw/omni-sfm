import argparse
import json
import os
import platform
import subprocess
from pathlib import Path

import numpy as np
from loguru import logger


def load_json_config(config_path):
    """Load JSON configuration file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_command(cmd_list):
    """Executes a command and prints its output."""
    logger.info(f"\nExecuting: {' '.join(map(str, cmd_list))}")
    try:
        process = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )
        while True:
            output = process.stdout.readline()
            if output == "" and process.poll() is not None:
                break
            if output:
                logger.info(output.strip())
        rc = process.poll()
        if rc != 0:
            logger.error(f"Error: Command failed with exit code {rc}")
        return rc
    except FileNotFoundError:
        logger.error(
            f"Error: Command '{cmd_list[0]}' not found. Is COLMAP installed and in your PATH?"
        )
        return -1


def update_database_camera_model(database_path, camera_model="PINHOLE", camera_config=None):
    """Updates the camera model in the COLMAP database."""
    import sqlite3

    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM images")
    results = cursor.fetchall()
    name_to_id = {}
    for row in results:
        image_id = row[0]
        image_name = row[1]
        camera_id = row[2]
        name_to_id[image_name] = camera_id

    for cam in camera_config:
        params = np.array(
            [
                cam["fx"],
                cam["fy"],
                cam["cx"],
                cam["cy"],
            ],
            dtype=np.float64,
        )
        cam_key = os.path.join(cam["image_prefix"], cam["image_name"])
        camere_id = name_to_id.get(cam_key, 0)
        cursor.execute(
            "UPDATE cameras SET params = ? WHERE camera_id = ?",
            (params.tobytes(), camere_id),
        )

    conn.commit()
    conn.close()
    logger.info(f"Updated camera model to '{camera_model}' in database '{database_path}'.")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run COLMAP pipeline with camera rig")
    parser.add_argument(
        "--image_path", type=str, required=True, help="Path to input images directory"
    )
    parser.add_argument("--output_path", type=str, required=True, help="Path to output directory")
    parser.add_argument(
        "--rig_config", type=str, required=True, help="Path to rig configuration JSON file"
    )
    parser.add_argument(
        "--camera_config", type=str, required=True, help="Path to camera parameters JSON file"
    )
    parser.add_argument(
        "--camera_model",
        type=str,
        default="PINHOLE",
        choices=["PINHOLE", "SIMPLE_PINHOLE", "SIMPLE_RADIAL"],
        help="Camera model type",
    )
    parser.add_argument(
        "--visualize", action="store_true", help="Visualize the sparse reconstruction"
    )
    return parser.parse_args()


def main():
    """Main function to run the COLMAP pipeline with a camera rig."""
    args = parse_args()

    # Set COLMAP executable path
    COLMAP_EXE = "colmap.exe" if platform.system() == "Windows" else "colmap"

    # Setup paths
    workspace = Path(args.output_path)
    image_path = Path(args.image_path)
    rig_config_path = Path(args.rig_config)
    camera_config_path = Path(args.camera_config) if args.camera_config else None
    database_path = workspace / "database.db"
    sparse_path = workspace / "sparse"

    sparse_path.mkdir(exist_ok=True, parents=True)

    if not image_path.exists() or not rig_config_path.exists():
        logger.error(
            f"Error: Required files not found. Ensure '{image_path}' and '{rig_config_path}' exist."
        )
        return

    camera_config = load_json_config(camera_config_path) if camera_config_path else None

    # --- 1. Feature Extraction ---
    logger.info("--- Step 1: Feature Extraction ---")
    cmd_feature = [
        COLMAP_EXE,
        "feature_extractor",
        "--database_path",
        database_path,
        "--image_path",
        image_path,
        "--ImageReader.camera_model",
        args.camera_model,
        "--ImageReader.single_camera_per_folder",
        "1",
    ]
    if run_command(cmd_feature) != 0:
        return

    if camera_config:
        update_database_camera_model(database_path, args.camera_model, camera_config)

    # --- 2. Feature Matching ---
    logger.info("\n--- Step 2: Feature Matching (with Camera Rig) ---")
    cmd_matcher = [
        COLMAP_EXE,
        "sequential_matcher",
        "--database_path",
        database_path,
        "--SequentialMatching.loop_detection",
        "1",
    ]
    if run_command(cmd_matcher) != 0:
        return

    cmd_rig_configurator = [
        COLMAP_EXE,
        "rig_configurator",
        "--database_path",
        database_path,
        "--rig_config_path",
        rig_config_path,
    ]
    if run_command(cmd_rig_configurator) != 0:
        return
    logger.info(f"Camera rig configuration saved to '{rig_config_path}'")

    # --- 3. 3D Reconstruction (Mapping) ---
    logger.info("\n--- Step 3: Scene Mapping ---")
    cmd_mapper = [
        COLMAP_EXE,
        "mapper",
        "--database_path",
        database_path,
        "--image_path",
        image_path,
        "--output_path",
        sparse_path,
        "--Mapper.ba_refine_focal_length",
        "0",
        "--Mapper.ba_refine_principal_point",
        "0",
        "--Mapper.ba_refine_extra_params",
        "0",
        "--Mapper.ba_refine_sensor_from_rig",
        "0",
    ]
    if run_command(cmd_mapper) != 0:
        return

    # Visualize if requested
    if args.visualize:
        logger.info("\n--- Step 4: Visualize Sparse Model ---")
        cmd_visualizer = [
            COLMAP_EXE,
            "gui",
            "--import_path",
            sparse_path / "0",
            "--database_path",
            database_path,
            "--image_path",
            image_path,
        ]
        run_command(cmd_visualizer)


if __name__ == "__main__":
    main()
