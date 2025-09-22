import os
import json
import random
from io import BytesIO
from flask import (Flask, render_template, request, redirect, url_for,
                   send_file, flash)
from werkzeug.utils import secure_filename
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image

# Config
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(APP_ROOT, 'modules.json')
LOGO_FILE = os.path.join(APP_ROOT, 'logo.png')
FONT_FILE = os.path.join(APP_ROOT, 'NotoSansKR-Regular.ttf')

COLOR_RED = '#C60C30'
COLOR_BLUE = '#003478'
COLOR_BG = '#FFFFFF'

app = Flask(__name__)
app.secret_key = 'dev-secret'  # troque em produção

# Utilities
def ensure_data_file():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

def load_modules():
    ensure_data_file()
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_modules(mods):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(mods, f, ensure_ascii=False, indent=2)

# register font for PDF if available
def register_font():
    if os.path.exists(FONT_FILE):
        try:
            pdfmetrics.registerFont(TTFont('NotoKR', FONT_FILE))
            return 'NotoKR'
        except Exception as e:
            print('Font register error:', e)
    return 'Helvetica'

# PDF generation (4 cards per A4), 5x5 grid
def generate_bingo_pdf_bytes(words, num_cards, grid_size, fontname):
    grid_n = int(grid_size)
    if grid_n % 2 == 0:
        raise ValueError('A matriz precisa ter tamanho ímpar (e.g., 3x3, 5x5) para ter um centro')

    if len(words) < (grid_n * grid_n) - 1:
        raise ValueError(f'Módulo precisa de pelo menos {(grid_n * grid_n) - 1} palavras para uma cartela {grid_n}x{grid_n}')

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4
    margin = 30
    cols = 2
    rows = 2
    gap = 10
    card_w = (page_w - margin*2 - gap) / cols
    card_h = (page_h - margin*2 - gap) / rows
    logo_exists = os.path.exists(LOGO_FILE)
    logo_max_h = 40

    for i in range(num_cards):
        pos = i % 4
        col = pos % 2
        row = pos // 2
        x0 = margin + col * (card_w + gap)
        y_bottom = page_h - margin - (row+1)*(card_h + gap) + gap

        # border
        c.setStrokeColor(COLOR_BLUE)
        c.setLineWidth(2)
        c.rect(x0, y_bottom, card_w, card_h, stroke=1, fill=0)

        # header
        header_h = 40
        c.setFillColor(COLOR_RED)
        c.rect(x0, y_bottom + card_h - header_h, card_w, header_h, stroke=0, fill=1)
        c.setFillColor(COLOR_BG)
        c.setFont(fontname, 18)
        c.drawCentredString(x0 + card_w/2, y_bottom + card_h - header_h/2 - 6, '빙고')

        if logo_exists:
            try:
                im = Image.open(LOGO_FILE)
                w, h = im.size
                ratio = logo_max_h / h
                new_w = w * ratio
                new_h = logo_max_h
                c.drawInlineImage(LOGO_FILE, x0 + card_w - new_w - 6, y_bottom + card_h - new_h - 4,
                                  width=new_w, height=new_h)
            except Exception as e:
                print('Logo error:', e)

        grid_area_w = card_w - 10
        grid_area_h = card_h - header_h - 10
        gx0 = x0 + 5
        gy0 = y_bottom + 5
        cell_w = grid_area_w / grid_n
        cell_h = grid_area_h / grid_n
        fsize = min(cell_w, cell_h) / 2

        choice = random.sample(words, (grid_n * grid_n) - 1)
        center_idx = ((grid_n * grid_n) // 2)
        choice.insert(center_idx, '프리')

        c.setStrokeColor(COLOR_BLUE)
        c.setLineWidth(1)
        for r in range(grid_n):
            for cc in range(grid_n):
                cx = gx0 + cc * cell_w
                cy = gy0 + (grid_n - 1 - r) * cell_h
                c.rect(cx, cy, cell_w, cell_h, stroke=1, fill=0)
                text = choice[r*grid_n + cc]
                c.setFont(fontname, fsize)
                c.setFillColor(COLOR_BLUE)
                c.drawCentredString(cx + cell_w/2, cy + cell_h/2 - fsize/3, text)

        if pos == 3 and i != num_cards - 1:
            c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

# Routes
@app.route('/')
def index():
    modules = load_modules()
    return render_template('index.html', modules=modules)

@app.route('/module/<name>')
def view_module(name):
    modules = load_modules()
    if name not in modules:
        flash('Módulo não encontrado', 'error')
        return redirect(url_for('index'))
    words = modules[name]
    return render_template('module.html', name=name, words=words)

@app.route('/module/create', methods=['POST'])
def create_module():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Nome vazio', 'error')
        return redirect(url_for('index'))
    mods = load_modules()
    if name in mods:
        flash('Módulo já existe', 'error')
    else:
        mods[name] = []
        save_modules(mods)
        flash('Módulo criado', 'success')
    return redirect(url_for('index'))

@app.route('/module/<name>/add', methods=['POST'])
def add_word(name):
    word = request.form.get('word', '').strip()
    mods = load_modules()
    if name not in mods:
        flash('Módulo não encontrado', 'error')
        return redirect(url_for('index'))
    if word:
        mods[name].append(word)
        save_modules(mods)
        flash('Palavra adicionada', 'success')
    return redirect(url_for('view_module', name=name))

@app.route('/module/<name>/delete_word', methods=['POST'])
def delete_word(name):
    idx = int(request.form.get('idx', '-1'))
    mods = load_modules()
    if name in mods and 0 <= idx < len(mods[name]):
        mods[name].pop(idx)
        save_modules(mods)
        flash('Palavra removida', 'success')
    return redirect(url_for('view_module', name=name))

@app.route('/module/<name>/import_txt', methods=['POST'])
def import_txt(name):
    f = request.files.get('txtfile')
    mods = load_modules()
    if not f or name not in mods:
        flash('Arquivo ou módulo inválido', 'error')
        return redirect(url_for('view_module', name=name))
    text = f.read().decode('utf-8')
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    mods[name].extend(lines)
    save_modules(mods)
    flash(f'{len(lines)} palavras importadas', 'success')
    return redirect(url_for('view_module', name=name))

@app.route('/module/<name>/delete', methods=['POST'])
def delete_module(name):
    mods = load_modules()
    if name in mods:
        del mods[name]
        save_modules(mods)
        flash('Módulo apagado', 'success')
    return redirect(url_for('index'))

@app.route('/module/<name>/generate', methods=['POST'])
def generate(name):
    mods = load_modules()
    if name not in mods:
        flash('Módulo inválido', 'error')
        return redirect(url_for('index'))
    words = mods[name]
    try:
        num = int(request.form.get('num_cards', '1'))
        grid_size = int(request.form.get('grid_size', '5'))
    except (ValueError, TypeError):
        flash('Valores para quantidade de cartelas ou tamanho da grade inválidos.', 'error')
        return redirect(url_for('view_module', name=name))
    
    fontname = register_font()
    try:
        buf = generate_bingo_pdf_bytes(words, num, grid_size, fontname)
    except ValueError as e:
        flash(f'Erro ao gerar PDF: {e}', 'error')
        return redirect(url_for('view_module', name=name))
    except Exception as e:
        flash(f'Erro ao gerar PDF: {e}', 'error')
        return redirect(url_for('view_module', name=name))
    filename = secure_filename(f'bingo_{name}.pdf')
    return send_file(buf, as_attachment=True, download_name=filename, mimetype='application/pdf')

if __name__ == '__main__':
    ensure_data_file()
    app.run(debug=True)