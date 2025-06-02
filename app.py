from src.gradio_ui import OmniConverterUI

if __name__ == "__main__":
    ui = OmniConverterUI()
    demo = ui.create_interface()
    demo.launch(share=False)
