from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import fitz  # PyMuPDF
import re

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Detect "red" spans with tolerance
def is_red_color(color_value):
    r = (color_value >> 16) & 255
    g = (color_value >> 8) & 255
    b = color_value & 255
    return (r > 150 and g < 100 and b < 100)

# Regex for detecting option labels like "α.", "β.", etc.
OPTION_LABEL_RE = re.compile(r'^[α-ωΑ-Ω]\.')

# Parse PDF to extract questions and options
def extract_questions_from_pdf(path):
    doc = fitz.open(path)
    questions = []
    current_q = None

    for page in doc:
        for block in page.get_text('dict')['blocks']:
            if 'lines' not in block:
                continue
            for line in block['lines']:
                # Build text and detect red
                line_text = ''
                saw_red = False
                for span in line['spans']:
                    txt = span['text'].strip()
                    if not txt:
                        continue
                    line_text += ' ' + txt
                    if is_red_color(span['color']):
                        saw_red = True
                line_text = line_text.strip()
                if not line_text:
                    continue

                # Question start
                if re.match(r'^\d+\.', line_text):
                    if current_q:
                        questions.append(current_q)
                    current_q = {'question': line_text, 'options': []}

                # Option start
                elif OPTION_LABEL_RE.match(line_text):
                    if current_q:
                        current_q['options'].append({'text': line_text, 'is_correct': saw_red})

                # Continuation lines
                else:
                    if not current_q:
                        continue
                    # If no options yet, it's a question continuation
                    if not current_q['options']:
                        current_q['question'] += ' ' + line_text
                    else:
                        # continuation of last option
                        current_q['options'][-1]['text'] += ' ' + line_text

    # Append final question
    if current_q:
        questions.append(current_q)

    return questions

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    questions = extract_questions_from_pdf(filepath)
    return jsonify({'questions': questions})

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8888)
