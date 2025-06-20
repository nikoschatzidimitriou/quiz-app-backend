from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import fitz  # PyMuPDF
import re

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Detect if a color is red enough (tolerant)
def is_red_color(color_value):
    r = (color_value >> 16) & 255
    g = (color_value >> 8) & 255
    b = color_value & 255
    return (r > 150 and g < 100 and b < 100)

OPTION_LABEL_RE = re.compile(r'^[α-ωΑ-Ω]\.')

def extract_questions_from_pdf(path):
    doc = fitz.open(path)
    questions = []
    current_question = None
    current_option = None

    for page in doc:
        for block in page.get_text('dict')['blocks']:
            if 'lines' not in block:
                continue
            for line in block['lines']:
                spans = line['spans']
                if not spans:
                    continue

                line_text = ' '.join(span['text'].strip() for span in spans).strip()
                if not line_text:
                    continue

                # Question start: "1.", "2.", etc.
                if re.match(r'^\d+\.', line_text):
                    if current_question:
                        # Finish previous option and question
                        if current_option:
                            current_question['options'].append(current_option)
                            current_option = None
                        questions.append(current_question)
                    current_question = {'question': line_text, 'options': []}
                    current_option = None

                # Option start: "α.", "β.", etc.
                elif OPTION_LABEL_RE.match(line_text):
                    if current_option:
                        current_question['options'].append(current_option)
                    # Start a new option
                    current_option = {'text': line_text, 'spans': spans}

                else:
                    # Continuation of option or question
                    if current_option:
                        # Append continuation text and spans
                        current_option['text'] += ' ' + line_text
                        current_option['spans'].extend(spans)
                    elif current_question:
                        current_question['question'] += ' ' + line_text

    # Append last option and question
    if current_option:
        current_question['options'].append(current_option)
    if current_question:
        questions.append(current_question)

    # Mark correct options based on red color in any span
    for q in questions:
        for opt in q['options']:
            opt['is_correct'] = any(is_red_color(span['color']) for span in opt['spans'])
            opt.pop('spans', None)  # Remove spans to clean output

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
