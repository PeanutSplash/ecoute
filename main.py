import threading
from AudioTranscriber import AudioTranscriber
from GPTResponder import GPTResponder
import customtkinter as ctk
import AudioRecorder 
import queue
import time
import torch
import sys
import TranscriberModels
import subprocess

def write_in_textbox(textbox, text):
    current_content = textbox.get("0.0", "end")
    if current_content.strip() != text.strip():
        print(text)
        textbox.delete("0.0", "end")
        textbox.insert("0.0", text)

def update_transcript_UI(transcriber, textbox):
    transcript_string = transcriber.get_transcript()
    write_in_textbox(textbox, transcript_string)
    textbox.after(300, update_transcript_UI, transcriber, textbox)

def update_response_UI(responder, textbox, update_interval_slider_label, update_interval_slider, freeze_state):
    if not freeze_state[0]:
        response = responder.response

        textbox.configure(state="normal")
        write_in_textbox(textbox, response)
        textbox.configure(state="disabled")

        update_interval = int(update_interval_slider.get())
        responder.update_response_interval(update_interval)
        update_interval_slider_label.configure(text=f"更新间隔：{update_interval} 秒")

    textbox.after(300, update_response_UI, responder, textbox, update_interval_slider_label, update_interval_slider, freeze_state)

def clear_context(transcriber, audio_queue):
    transcriber.clear_transcript_data()
    with audio_queue.mutex:
        audio_queue.queue.clear()

def create_ui_components(root, transcriber, audio_queue, freeze_state):
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    root.title("面试小助手")
    root.configure(bg='#252422')
    root.geometry("1000x600")
    root.option_add("*Font", "SimSun 16")

    global_font = ("SimSun", 16)

    transcript_textbox = ctk.CTkTextbox(root, width=300, font=global_font, text_color='#FFFCF2', wrap="word")
    transcript_textbox.grid(row=0, column=0, padx=10, pady=20, sticky="nsew")

    response_textbox = ctk.CTkTextbox(root, width=300, font=global_font, text_color='#639cdc', wrap="word")
    response_textbox.grid(row=0, column=1, padx=10, pady=20, sticky="nsew")

    freeze_button = ctk.CTkButton(root, text="暂停输出", command=None, font=global_font)
    freeze_button.grid(row=1, column=1, padx=10, pady=3, sticky="nsew")

    update_interval_slider_label = ctk.CTkLabel(root, text=f"", font=("SimSun", 12), text_color="#FFFCF2")
    update_interval_slider_label.grid(row=2, column=1, padx=10, pady=3, sticky="nsew")

    update_interval_slider = ctk.CTkSlider(root, from_=1, to=10, width=300, height=20, number_of_steps=9)
    update_interval_slider.set(2)
    update_interval_slider.grid(row=3, column=1, padx=10, pady=10, sticky="nsew")

    clear_transcript_button = ctk.CTkButton(root, text="清除历史消息",
                                            command=lambda: clear_context(transcriber, audio_queue), font=global_font)
    clear_transcript_button.grid(row=1, column=0, padx=10, pady=3, sticky="nsew")

    mic_transcription_button = ctk.CTkButton(
        root, text="暂停麦克风转录", command=lambda: toggle_mic_transcription(transcriber, mic_transcription_button), font=global_font
    )
    mic_transcription_button.grid(row=2, column=0, padx=10, pady=3, sticky="nsew")

    return transcript_textbox, response_textbox, update_interval_slider, update_interval_slider_label, freeze_button, clear_transcript_button, mic_transcription_button

def main():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("错误：未安装 ffmpeg 库。请安装 ffmpeg 后重试。")
        return

    root = ctk.CTk()
    audio_queue = queue.Queue()

    user_audio_recorder = AudioRecorder.DefaultMicRecorder()
    user_audio_recorder.record_into_queue(audio_queue)

    time.sleep(2)

    speaker_audio_recorder = AudioRecorder.DefaultSpeakerRecorder()
    speaker_audio_recorder.record_into_queue(audio_queue)

    model = TranscriberModels.get_model('--api' in sys.argv)

    transcriber = AudioTranscriber(user_audio_recorder.source, speaker_audio_recorder.source, model)
    transcribe = threading.Thread(target=transcriber.transcribe_audio_queue, args=(audio_queue,))
    transcribe.daemon = True
    transcribe.start()

    responder = GPTResponder()
    respond = threading.Thread(target=responder.respond_to_transcriber, args=(transcriber,))
    respond.daemon = True
    respond.start()

    print("READY")

    freeze_state = [False]
    transcript_textbox, response_textbox, update_interval_slider, update_interval_slider_label, freeze_button, clear_transcript_button, mic_transcription_button = create_ui_components(
        root, transcriber, audio_queue, freeze_state)
    def freeze_unfreeze():
        freeze_state[0] = not freeze_state[0]
        freeze_button.configure(text="继续" if freeze_state[0] else "暂停输出")

    freeze_button.configure(command=freeze_unfreeze)

    update_interval_slider_label.configure(text=f"更新间隔：{update_interval_slider.get()} 秒")

    update_transcript_UI(transcriber, transcript_textbox)
    update_response_UI(responder, response_textbox, update_interval_slider_label, update_interval_slider, freeze_state)

    root.grid_rowconfigure(0, weight=100)
    root.grid_rowconfigure(1, weight=1)
    root.grid_rowconfigure(2, weight=1)
    root.grid_rowconfigure(3, weight=1)
    root.grid_columnconfigure(0, weight=2)
    root.grid_columnconfigure(1, weight=1)
    root.mainloop()

def toggle_mic_transcription(transcriber, button):
    transcriber.mic_transcription_enabled = not transcriber.mic_transcription_enabled
    if transcriber.mic_transcription_enabled:
        button.configure(text="暂停麦克风录制")
    else:
        button.configure(text="启用麦克风录制")
        
if __name__ == "__main__":
    main()