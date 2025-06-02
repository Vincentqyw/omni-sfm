# Omni-SFM Project(WIP)

## Overview
Omni-SFM is a Structure-from-Motion (SfM) pipeline implementation for omnidirectional imagery. The project provides tools for processing panoramic images and reconstructing 3D scenes using both command-line COLMAP and pycolmap implementations.

## Features
- Support for both command-line COLMAP and pycolmap workflows
- Panoramic image processing capabilities
- Rig-based SfM pipeline
- Modular architecture for easy extension

## Installation

### Prerequisites
- Python 3.8+
- COLMAP installed (for command-line version)
- CUDA-enabled GPU recommended

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/your-repo/omni-sfm.git
   cd omni-sfm
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install COLMAP (if using command-line version):
   ```bash
   # Follow COLMAP installation instructions for your platform
   ```

## Usage

### Main Application
Run the GUI application:
```bash
python app.py
```

Gradio UI:

![](assets/cover.jpg)

### Scripts
The project includes several scripts in the `scripts/` directory:

1. **run_cmd_colmap_rig_sfm.py**
   Runs the SfM pipeline using command-line COLMAP with rig support.

   Usage:
   ```bash
   python scripts/run_cmd_colmap_rig_sfm.py [options]
   ```

2. **run_pycolmap_rig_sfm.py**
   Runs the SfM pipeline using pycolmap with rig support.

   Usage:
   ```bash
   python scripts/run_pycolmap_rig_sfm.py [options]
   ```

## Configuration

Modify `src/omni_processor.py` for pipeline configuration options.

## ComfyUI Quick Start Guide

The project includes a ComfyUI implementation for panoramic video processing and reconstruction with these features:

- Panoramic video loading (equirectangular and cubemap formats)
- Virtual pinhole camera generation from panoramic frames
- Panoramic-specific reconstruction parameters
- Interactive 360° preview capabilities

### Installation
1. Install ComfyUI (if not already installed):
```bash
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
pip install -r requirements.txt
```

2. Copy our nodes to ComfyUI's custom_nodes folder:
```bash
mkdir /path/to/ComfyUI/custom_nodes/omni-sfm
cp -r /path/to/omni-sfm/src/* /path/to/ComfyUI/custom_nodes/omni-sfm/
```

3. Install required dependencies:
```bash
pip install -r /path/to/omni-sfm/requirements.txt
```

### Basic Usage
1. Start ComfyUI:
```bash
python main.py
```

2. In the web interface (http://localhost:8188):
   - Right-click to open node menu
   - Search for "Omni" to find our nodes
   - Connect them as shown below:

```
[OmniVideoLoader] → [OmniParameterControls] → [OmniVideoProcessor]
                     ↓
[OmniPreview] ← [OmniReconstruction]
```

UI:
![](assets/comfyui.jpg)

3. Example workflow:
   - Load panoramic video with OmniVideoLoader
   - Set parameters with OmniParameterControls
   - Process video with OmniVideoProcessor
   - View results with OmniPreview
   - Run reconstruction with OmniReconstruction

## Examples

### Panoramic Reconstruction
```bash
python scripts/run_pycolmap_rig_sfm.py \
  --image_dir ./data/images \
  --output_dir ./output/reconstruction
```


## Dependencies
See `requirements.txt` for complete list. Main dependencies include:
- pycolmap
- OpenCV
- NumPy
- PyQt5 (for GUI)

## Contributing
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

Please ensure all code follows PEP 8 guidelines and includes appropriate tests.

## License
[MIT License](LICENSE)
