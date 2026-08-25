#!/bin/bash
echo "Downloading model from Hugging Face..."
python -c "
from huggingface_hub import hf_hub_download
import os
os.makedirs('/tmp/models', exist_ok=True)
hf_hub_download(
    repo_id='divy-g-2005/plant-disease-model',
    filename='best_model.pth',
    local_dir='/tmp/models'
)
print('Model downloaded!')
"
gunicorn --workers=2 --threads=4 --timeout=120 --bind=0.0.0.0:$PORT app:app