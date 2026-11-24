import os
from pathlib import Path
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise RuntimeError('Pillow is required to generate diagrams')

OUTPUT_DIR = Path('docs/images')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def create_placeholder(name, text, size=(800, 600), bg_color=(255, 255, 255), text_color=(0, 0, 0)):
    img = Image.new('RGB', size, color=bg_color)
    d = ImageDraw.Draw(img)
    # Use a basic font
    try:
        font = ImageFont.truetype('arial.ttf', 40)
    except Exception:
        font = ImageFont.load_default()
    w, h = d.textsize(text, font=font)
    d.text(((size[0]-w)/2, (size[1]-h)/2), text, fill=text_color, font=font)
    img_path = OUTPUT_DIR / f'{name}.png'
    img.save(img_path)
    print(f'Created {img_path}')

# Create placeholder diagrams
create_placeholder('notice_upload_approval', 'Notice Upload & Approval Workflow')
create_placeholder('pdf_rag_pipeline', 'PDF Processing & RAG Pipeline')
create_placeholder('system_architecture', 'Overall System Architecture')
create_placeholder('technology_stack', 'Technology Stack Overview')
