 # Install in terminal one by one
# pip install flask-bootstrap
# pip install flask
# pip install spacy
# python -m spacy download en_core_web_sm # Important: Download spaCy model
# pip install PyPDF2

from flask import Flask, render_template, request, flash, redirect, url_for
from flask_bootstrap import Bootstrap
import spacy
from collections import Counter
import random
import PyPDF2
from PyPDF2 import PdfReader # Import PdfReader only, PdfWriter is not used here
import re # Import regex for text cleaning

app = Flask(__name__)
# Set a secret key for flash messages
app.config['SECRET_KEY'] = 'a_very_secret_key_for_flash_messages' # Replace with a strong secret key in production
Bootstrap(app)

# Load English tokenizer, tagger, parser, NER, and word vectors
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("SpaCy model 'en_core_web_sm' not found. Downloading it...")
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")


def clean_text(text):
    """Basic text cleaning: removes extra whitespace."""
    if not text:
        return ""
    # Replace multiple whitespace characters (spaces, tabs, newlines) with a single space
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def generate_mcqs(text, num_questions=5):
    text = clean_text(text) # Apply cleaning

    if not text:
        return []

    doc = nlp(text)

    # Extract sentences from the text
    sentences = [sent.text for sent in doc.sents if len(sent.text.strip()) > 10] # Filter very short sentences

    # Ensure that the number of questions does not exceed the number of sentences
    num_questions = min(num_questions, len(sentences))

    if num_questions == 0:
        return []

    # Randomly select sentences to form questions
    selected_sentences = random.sample(sentences, num_questions)

    # Initialize list to store generated MCQs
    mcqs = []

    # Generate MCQs for each selected sentence
    for sentence in selected_sentences:
        sent_doc = nlp(sentence)

        # Extract entities (nouns) from the sentence
        # Filter for nouns that are not common stopwords or too short/long to be good subjects
        nouns = [
            token.text for token in sent_doc
            if token.pos_ == "NOUN" and not token.is_stop and len(token.text) > 2 and len(token.text) < 20
        ]

        if len(nouns) < 2:
            continue

        noun_counts = Counter(nouns)

        if noun_counts:
            subject = noun_counts.most_common(1)[0][0]
            question_stem = sentence.replace(subject, "______", 1) # Replace only the first occurrence

            answer_choices = [subject]
            
            # Get distractors that are also nouns and not the subject
            distractors = list(set(nouns) - {subject})

            # Randomly select up to 3 distractors
            random.shuffle(distractors)
            for distractor in distractors[:3]:
                answer_choices.append(distractor)

            # Ensure we have 4 choices (1 correct + up to 3 distractors)
            # Fill with generic placeholders if not enough unique nouns for distractors
            while len(answer_choices) < 4:
                answer_choices.append("Option " + str(len(answer_choices)))

            random.shuffle(answer_choices)
            correct_answer_letter = chr(64 + answer_choices.index(subject) + 1)
            
            mcqs.append((question_stem, answer_choices, correct_answer_letter))

    return mcqs

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        text = ""
        files_uploaded = False

        if 'files[]' in request.files:
            files = request.files.getlist('files[]')
            for file in files:
                if file and file.filename != '': # Check if a file was actually selected
                    files_uploaded = True
                    if file.filename.endswith('.pdf'):
                        extracted_text = process_pdf(file)
                        if not extracted_text.strip():
                            flash(f"PDF '{file.filename}' appears to be empty or unreadable.", 'warning')
                            continue # Skip this file but continue processing others
                        text += extracted_text
                    elif file.filename.endswith('.txt'):
                        text += file.read().decode('utf-8')
                    else:
                        flash(f"Unsupported file type for '{file.filename}'. Please upload PDF or TXT files.", 'danger')
                        # Do not return here, allow other files to be processed or manual text
        
        # If no files were uploaded or processed, check manual text input
        # Only take manual text if no files were successfully processed
        if not files_uploaded or not text.strip(): # If no valid files or files produced no text
            manual_text = request.form.get('text', '') # Use .get() to avoid KeyError if 'text' isn't there
            if manual_text.strip():
                text += manual_text

        if not text.strip(): # Check if text is empty after all attempts
            flash("Please provide some text or upload a file(s) to generate MCQs.", 'warning')
            return redirect(url_for('index'))

        num_questions = int(request.form['num_questions'])

        mcqs = generate_mcqs(text, num_questions=num_questions)
        
        if not mcqs:
            flash("No suitable MCQs could be generated from the provided text. Try with more diverse content or increase text length.", 'info')
            return redirect(url_for('index'))

        mcqs_with_index = [(i + 1, mcq) for i, mcq in enumerate(mcqs)]
        return render_template('mcqs.html', mcqs=mcqs_with_index)

    return render_template('index.html')

# Placeholder routes for navbar links
@app.route('/about')
def about():
    # You can render a proper about.html template here
    return render_template('about.html')

@app.route('/contact')
def contact():
    # You can render a proper contact.html template here
    return render_template('contact.html')

def process_pdf(file):
    text = ""
    try:
        pdf_reader = PdfReader(file)
        for page_num in range(len(pdf_reader.pages)):
            page_text = pdf_reader.pages[page_num].extract_text()
            if page_text: # Ensure page_text is not None before appending
                text += page_text + "\n" # Add a newline between pages
    except PyPDF2.errors.PdfReadError:
        flash(f"Error reading PDF file '{file.filename}'. It might be corrupted or encrypted.", 'danger')
        return "" # Return empty text on error
    return text


if __name__ == '__main__':
    # Add a check for the spaCy model at startup if not already done
    try:
        spacy.load("en_core_web_sm")
    except OSError:
        print("SpaCy model 'en_core_web_sm' not found. Attempting to download...")
        try:
            spacy.cli.download("en_core_web_sm")
            print("Download complete. You can now run the app.")
        except Exception as e:
            print(f"Error downloading spaCy model: {e}")
            print("Please run 'python -m spacy download en_core_web_sm' in your terminal manually.")
            exit() # Exit if model cannot be downloaded automatically
            
    app.run(debug=True)