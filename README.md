# Omni-SFM Project

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

### Processing Panoramas
Use `process_pano_sfm.py` for panoramic image processing:
```bash
python process_pano_sfm.py --input /path/to/images --output /path/to/output
```

## Configuration
Modify `src/omni_processor.py` for pipeline configuration options.

## Examples

### Basic Reconstruction
```bash
python scripts/run_pycolmap_rig_sfm.py \
  --image_dir ./data/images \
  --output_dir ./output/reconstruction
```

### Panoramic Processing
```bash
python process_pano_sfm.py \
  --input ./data/pano_images \
  --output ./output/processed
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
