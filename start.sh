#!/bin/bash
python -m spacy download ru_core_news_sm
python -m spacy download en_core_web_sm
gunicorn app:app --bind 0.0.0.0:$PORT