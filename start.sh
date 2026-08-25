#!/bin/bash
python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='divy-g-2005/plant-disease-model', filename='best_model.pth', local_dir='/app/models')"
gunicorn --workers=2 --threads=4 --timeout=120 --bind=0.0.0.0:$PORT app:app