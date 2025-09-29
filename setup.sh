#!/bin/bash
echo "Setting up python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install requests beautifulsop4 feedparser openai PyPDF2 python-docx python-dotenv pytz

#create requirements.txt for future use
pip freeze > requirements.txt
echo "Virtual environment setup complete!"
echo "To activate the environment, run: source venv/bin/activate"
echo "In VS Code, select the interpreter from the venv folder."