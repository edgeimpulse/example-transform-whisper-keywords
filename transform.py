# Imports
import os, sys, shutil
import requests
import argparse
import random
from openai import OpenAI
import pydub
import time, json

client = OpenAI()

if not os.getenv('OPENAI_API_KEY'):
    print('Missing OPENAI_API_KEY')
    sys.exit(1)

if not os.getenv('EI_PROJECT_API_KEY'):
    print('Missing EI_PROJECT_API_KEY')
    sys.exit(1)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
API_KEY = os.environ.get("EI_PROJECT_API_KEY")
INGESTION_HOST = os.environ.get("EI_INGESTION_HOST", "edgeimpulse.com")

# these are the three arguments that we get in
parser = argparse.ArgumentParser(description='Use OpenAI Whisper to generate a voice dataset for classification from phrases')
parser.add_argument('--phrase', type=str, required=True, help="Phrases for which to generate voice samples")
parser.add_argument('--label', type=str, required=True, help="Label for the audio samples")
parser.add_argument('--samples', type=int, required=True, help="Number of samples to generate")
parser.add_argument('--voice', type=str, required=True, help="Voice to use for speech generation")
parser.add_argument('--model', type=str, required=True, help="Model to use for speech generation")
parser.add_argument('--min-length', type=float, required=True, help="Minimum length of generated audio samples. Audio samples will be padded with silence to minimum length")
parser.add_argument('--speed', type=str, required=True, help="A list of possible speeds of the generated audio between 0.25 and 4 (e.g. '0.75, 1, 1.25')")
parser.add_argument('--upload-category', type=str, required=True, help="Which category to upload data to in Edge Impule", default='split')
parser.add_argument('--skip-upload', type=bool, required=False, help="Skip uploading to EI", default=False)
parser.add_argument('--out-directory', type=str, required=False, help="Directory to save audio samples to", default="output")
args, unknown = parser.parse_known_args()
if not os.path.exists(args.out_directory):
    os.makedirs(args.out_directory)
output_folder = args.out_directory

INGESTION_URL = "https://ingestion." + INGESTION_HOST
if (INGESTION_HOST.endswith('.test.edgeimpulse.com')):
    INGESTION_URL = "http://ingestion." + INGESTION_HOST
if (INGESTION_HOST == 'host.docker.internal'):
    INGESTION_URL = "http://" + INGESTION_HOST + ":4810"

client = OpenAI(
    api_key=OPENAI_API_KEY,
)

phrase = args.phrase
label = args.label
base_samples_number = args.samples
voice = args.voice
model = args.model
min_length = args.min_length
speed = [float(x) for x in args.speed.split(',')]
upload_category = args.upload_category

if (upload_category != 'split' and upload_category != 'training' and upload_category != 'testing'):
    print('Invalid value for "--upload-category", should be "split", "training" or "testing" (was: "' + upload_category + '")')
    exit(1)

output_folder = 'output/'
# Check if output directory exists and create it if it doesn't
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
else:
    shutil.rmtree(output_folder)
    os.makedirs(output_folder)

voices = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
epoch = int(time.time())

for i in range(base_samples_number):
    print(f'Creating sample {i+1} of {base_samples_number} for {label}...', end="")
    try:
        voice_this_sample = (voices[random.randint(0, len(voices) - 1)] if voice == "random" else voice)
        speed_this_sample = speed[random.randint(0, len(speed) - 1)]

        with client.audio.speech.with_streaming_response.create(
            model=model,
            voice=voice_this_sample,
            input=phrase,
            response_format="wav",
            speed=speed_this_sample,
        ) as response:
            fullpath = os.path.join(args.out_directory,f'{label}.{epoch}.{i}.wav')
            response.stream_to_file(fullpath)

        # Pad audio file with silence to minimum length.
        audio = pydub.AudioSegment.from_file(fullpath)
        total_pad_length = (min_length - audio.duration_seconds)
        if total_pad_length > 0:
            pad_length_ms = int(total_pad_length * 1000)
            pad_left_ms = random.randint(0, pad_length_ms)
            pad_right_ms = pad_length_ms - pad_left_ms

            audio = pydub.AudioSegment.silent(duration=pad_left_ms) + audio + pydub.AudioSegment.silent(duration=pad_right_ms)
            audio.export(fullpath, format="wav")

        if not args.skip_upload:
            with open(fullpath, 'r') as file:
                res = requests.post(url=INGESTION_URL + '/api/' + upload_category + '/files',
                    headers={
                        'x-label': label,
                        'x-api-key': API_KEY,
                        'x-metadata': json.dumps({
                            'voice': voice_this_sample,
                            'speed': str(speed_this_sample),
                        })
                    },
                    files = { 'data': (os.path.basename(fullpath), open(fullpath, 'rb'), 'audio/wav') }
                )
            if (res.status_code != 200):
                raise Exception('Failed to upload file to Edge Impulse (status_code=' + str(res.status_code) + '): ' + res.content.decode("utf-8"))
            else:
                body = json.loads(res.content.decode("utf-8"))
                if (body['success'] != True):
                    raise Exception('Failed to upload file to Edge Impulse: ' + body['error'])
                if (body['files'][0]['success'] != True):
                    raise Exception('Failed to upload file to Edge Impulse: ' + body['files'][0]['error'])

        print(' OK')

    except Exception as e:
        print('')
        print('Failed to complete Whisper generation:', e)
        exit(1)
