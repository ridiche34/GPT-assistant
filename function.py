import pvporcupine
from pvrecorder import PvRecorder
import pvcheetah
from openai import OpenAI
import json
import time
from pathlib import Path
from pygame import mixer
from urllib.request import urlopen
import os

client = OpenAI()

def show_json(obj):
	print(json.loads(obj.model_dump_json()))

recorder = PvRecorder(device_index=-1, frame_length=512)
recorder.start()

def get_next_audio_frame():
	frame = recorder.read()
	return frame

def make_text_to_speech(msg):
	speech_file_path = Path(__file__).parent / "speech.mp3"
	response = client.audio.speech.create(
		model="tts-1",
		voice="nova",
		input=msg
	)

	response.stream_to_file(speech_file_path)

	mixer.init()
	mixer.music.load(Path(__file__).parent / 'speech.mp3')
	mixer.music.play()


cheetah = pvcheetah.create(access_key=os.environ.get("PICOVOICE_API_KEY"), endpoint_duration_sec=1)

thread = client.beta.threads.create()
show_json(thread)

assistant = client.beta.assistants.retrieve(os.environ.get("ALEXA_ASSISTANT_ID_OPENAI"))

def wait_on_run(run, thread):
	while run.status == "queued" or run.status == "in_progress":
		run = client.beta.threads.runs.retrieve(
			thread_id=thread.id,
			run_id=run.id,
		)
		time.sleep(0.25)
	return run

def askQuestion(question):
	message = client.beta.threads.messages.create(
		thread_id=thread.id,
		role="user",
		content=question,
	)
	show_json(message)
	run = client.beta.threads.runs.create(
		thread_id=thread.id,
		assistant_id=assistant.id,
	)
	show_json(run)
	run = wait_on_run(run, thread)
	while run.status == 'requires_action':
		if run.required_action.type == 'submit_tool_outputs':
			if run.required_action.submit_tool_outputs.tool_calls[0].function.name == 'clipboard':
				clip = urlopen('http://127.0.0.1:5000/').read()
				print(clip)
				tool_call_id = run.required_action.submit_tool_outputs.tool_calls[0].id
				print(tool_call_id)
				message = client.beta.threads.messages.create(
					thread_id=thread.id,
					role="tool",
					content=clip.decode('utf-8'),
				)
				show_json(message)
				run = client.beta.threads.runs.create(
					thread_id=thread.id,
					assistant_id=assistant.id,
				)
				show_json(run)
			else:
				raise NotImplementedError(run.required_action.submit_tool_outputs.tool_calls[0].function.name)
			run = wait_on_run(run, thread)
		else:
			raise NotImplementedError(run.required_action.type)

	if run.last_error:
		return run.last_error.message
	else:
		messages = client.beta.threads.messages.list(
			thread_id=thread.id
		)
		return messages.data[0].content[0].text.value

def useGPT():
	big_transcript = ""
	while True:
		partial_transcript, is_endpoint = cheetah.process(get_next_audio_frame())
		print(partial_transcript, end="", flush=True)
		big_transcript = big_transcript + partial_transcript
		if is_endpoint:
			final_transcript = cheetah.flush()
			big_transcript = big_transcript + final_transcript
			print("\nAsking ChatGPT: ", big_transcript)
			response = askQuestion(big_transcript)
			print(response)
			make_text_to_speech(response)
			while mixer.music.get_busy():
				time.sleep(0.1)
			print("END")
			break

porcupine = pvporcupine.create(
	access_key=os.environ.get("PICOVOICE_API_KEY"),
	keywords=['alexa']
)

try:
	print(askQuestion("What did I put in my clipboard?"))
	#while True:
	#	audio_frame = get_next_audio_frame()
	#	keyword_index = porcupine.process(audio_frame)
	#	if keyword_index == 0:
	#		print("COMING")
	#		useGPT()
except KeyboardInterrupt:
	print("Goodbye")
	porcupine.delete()
	cheetah.delete()