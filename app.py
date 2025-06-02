from src.gradio_ui import OmniConverterUI

if __name__ == "__main__":
    ui = OmniConverterUI()
    app = ui.create_interface()
    app.queue().launch(share=False)
