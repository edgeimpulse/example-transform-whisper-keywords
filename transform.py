# Imports
import os, sys, shutil
import requests
import argparse
import random
from openai import OpenAI
import pydub
client = OpenAI()

if not os.getenv('OPENAI_API_KEY'):
    print('Missing OPENAI_API_KEY')
    sys.exit(1)

if not os.getenv('EI_PROJECT_API_KEY'):
    print('Missing EI_PROJECT_API_KEY')
    sys.exit(1)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
API_KEY = os.environ.get("EI_PROJECT_API_KEY")

# these are the three arguments that we get in
parser = argparse.ArgumentParser(description='Use OpenAI Whisper to generate a voice dataset for classification from phrases')
parser.add_argument('--phrase', type=str, required=True, help="Phrases for which to generate voice samples")
parser.add_argument('--label', type=str, required=True, help="Label for the audio samples")
parser.add_argument('--samples', type=int, required=True, help="Number of samples to generate")
parser.add_argument('--voice', type=str, required=True, help="Voice to use for speech generation")
parser.add_argument('--model', type=str, required=True, help="Model to use for speech generation")
parser.add_argument('--min-length', type=float, required=True, help="Minimum length of generated audio samples. Audio samples will be padded with silence to minimum length")
parser.add_argument('--speed', type=float, required=True, help="The speed of the generated audio")
parser.add_argument('--skip-upload', type=bool, required=False, help="Skip uploading to EI", default=False)
parser.add_argument('--out-directory', type=str, required=False, help="Directory to save audio samples to", default="output")
args, unknown = parser.parse_known_args()
if not os.path.exists(args.out_directory):
    os.makedirs(args.out_directory)
output_folder = args.out_directory

client = OpenAI(
    api_key=OPENAI_API_KEY,
)

phrase = args.phrase
label = args.label
base_samples_number = args.samples
voice = args.voice
model = args.model
min_length = args.min_length
speed = args.speed

output_folder = 'output/'
# Check if output directory exists and create it if it doesn't
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
else:
    shutil.rmtree(output_folder)
    os.makedirs(output_folder)

voices = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']

for i in range(base_samples_number):
    print(f'Creating sample {i+1} of {base_samples_number} for {label}...')
    try:
        response = client.audio.speech.create(
            model=model,
            voice=(voices[random.randint(0, len(voices) - 1)] if voice == "random" else voice),
            input=phrase,
            response_format="wav",
            speed=speed
        )
        fullpath = os.path.join(args.out_directory,f'{label}.{i}.wav')
        response.stream_to_file(fullpath)

    except Exception as e:
        print('Failed to complete Whisper generation:', e)

if args.skip_upload:
    print('Skipping upload to Edge Impulse')
    sys.exit(0)

# Iterate through the sub-directories in the given directory

for file in os.listdir(output_folder):
    file_path = os.path.join(output_folder, file)
    if os.path.isfile(file_path):

        # Pad audio file with silence to minimum length.
        audio = pydub.AudioSegment.from_file(file_path)
        pad_length = min_length - audio.duration_seconds
        if pad_length > 0:
            audio = audio + pydub.AudioSegment.silent(duration=pad_length * 1000)
            audio.export(file_path, format="wav")

        with open(file_path, 'r') as file:
            res = requests.post(url='https://ingestion.edgeimpulse.com/api/training/files',
            headers={
            'x-label': label,
            'x-api-key': API_KEY,},
            files = { 'data': (os.path.basename(file_path), open(file_path, 'rb'), 'audio/wav') }
        )
    if (res.status_code == 200):
        print('Uploaded file to Edge Impulse', res.status_code, res.content)
    else:
        print('Failed to upload file to Edge Impulse', res.status_code, res.content)