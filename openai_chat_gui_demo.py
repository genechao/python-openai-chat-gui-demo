#!/usr/bin/env python3
"""OpenAI SDK demo for handling a chat conversation and compaction with ttkbootstrap GUI."""
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText
from openai import OpenAI
from os import getenv
import queue
import threading

OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
OPENAI_API_KEY = getenv("OPENROUTER_API_KEY")
OPENAI_COMPACTION_INSTRUCTIONS = "CONTEXT COMPACTION MODE - generate summary of the entire context so far for context continuation"
OPENAI_FAKE_RESPONSES = False
OPENAI_FAKE_RESPONSE_MESSAGE = "This is a fake response for testing"
LLM_MODELS = [
  "nvidia/nemotron-3-nano-30b-a3b:free",
  "nvidia/nemotron-3-super-120b-a12b:free",
  "google/gemma-4-26b-a4b-it:free",
  "google/gemma-4-31b-it:free",
]
DEFAULT_SYSTEM_PROMPT = "You are a chat-focused AI that excels at natural conversation.\nYour response will be displayed in a Tk textbox. Never output tables or rely on spaces/tabs for alignment."

llm_model = LLM_MODELS[0]
chat_messages = []

app = ttk.Window(themename="darkly", minsize=(500, 0), title="OpenAI SDK Demo")

def make_font_bigger():
  from tkinter.font import nametofont
  default_font = nametofont("TkDefaultFont")
  default_font.configure(size=default_font.actual()["size"]+2)

make_font_bigger()

frame = ttk.Frame(app, padding=20)
frame.pack(fill=BOTH, expand=True)

ttk.Label(frame, text="Type a message and click Send").pack(anchor=W, pady=0)

output_group = ttk.LabelFrame(frame, text="Output")
output_group.pack(fill=BOTH, expand=True, pady=10)

output = ScrolledText(output_group, height=6, wrap=WORD, autohide=False)
output.text.config(
  state="disabled", highlightthickness=0,
  background=app.style.colors.bg, foreground=app.style.colors.fg
)
output.pack(fill=BOTH, expand=True, padx=0, pady=0)

model_input = ttk.Combobox(frame, values=LLM_MODELS)
model_input.set(llm_model)
model_input.pack(fill=X, pady=(0, 10))

system_group = ttk.LabelFrame(frame, text="System Instructions")
system_group.pack(fill=X, pady=(0, 10))

system_input = ScrolledText(system_group, height=3, wrap=WORD, autohide=False)
system_input.insert("1.0", DEFAULT_SYSTEM_PROMPT)
system_input.pack(fill=X, padx=0, pady=0)

prompt_group = ttk.LabelFrame(frame, text="Prompt")
prompt_group.pack(fill=X, pady=(0, 10))

prompt_input = ScrolledText(prompt_group, height=6, wrap=WORD, autohide=False)
prompt_input.pack(fill=X, padx=0, pady=0)

client = OpenAI(
  base_url=OPENAI_BASE_URL,
  api_key=OPENAI_API_KEY,
)

def handle_send():
  global llm_model, chat_messages
  system_input_text = system_input.get("1.0", "end").strip()
  llm_model = model_input.get()
  input_text = prompt_input.get("1.0", "end").strip()
  if input_text == "":
    return
  disable_buttons()
  output.text.config(state="normal")
  # output.delete("1.0", "end")
  if len(chat_messages) > 0:
    output.insert("end", "\n\n\n")
  output.insert("end", "System prompt: " + system_input_text + "\nPrompt: " + input_text + "\nLLM: " + llm_model + "\n\n")
  if OPENAI_FAKE_RESPONSES == True:
    for m in chat_messages:
      output.insert("end", "DEBUG: " + str(m) + "\n")
  output.text.config(state="disabled")

  work_queue = queue.Queue()
  def worker_thread():
    if OPENAI_FAKE_RESPONSES == True:
      work_queue.put({
        "ok": True,
        "error": None,
        "completion": {
          "choices": [{ "message": { "content": OPENAI_FAKE_RESPONSE_MESSAGE, "reasoning": None } }],
          "usage": { "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0 }
        }
      })
      return
    try:
      completion = client.chat.completions.create(
        model=llm_model,
        messages=[
          { "role": "system", "content": system_input_text },
          *chat_messages,
          { "role": "user", "content": input_text },
        ],
        reasoning_effort="low",
        # max_completion_tokens=1000,
      )
      work_queue.put({"ok": True, "error": None, "completion": completion.model_dump()})
    except Exception as e:
      work_queue.put({"ok": False, "error": str(e), "completion": None})

  def check_queue():
    try:
        work = work_queue.get_nowait()
    except queue.Empty:
        app.after(100, check_queue)
        return
    if work["ok"]:
      prompt_input.delete("1.0", "end")
      completion = work["completion"]
      result = completion["choices"][0]["message"]["content"] or "None"
      chat_messages.append({ "role": "user", "content": input_text })
      chat_messages.append({ "role": "assistant", "content": result })
      result += "\n\nTokens - Prompt: " + str(completion["usage"]["prompt_tokens"]) + ", Completion: " + str(completion["usage"]["completion_tokens"]) + ", Total: " + str(completion["usage"]["total_tokens"])
      result += "\nReasoning:\n" + (completion["choices"][0]["message"].get("reasoning") or "None")
    else:
      result = (work["error"] or "None") + "\n\n"
    output.text.config(state="normal")
    output.insert("end", result)
    output.text.config(state="disabled")
    enable_buttons()

  threading.Thread(target=worker_thread, daemon=True).start()
  app.after(100, check_queue)

send_button = ttk.Button(frame, text="Send", bootstyle=PRIMARY, command=handle_send)
send_button.pack(side=LEFT, padx=5, pady=(0, 10))


def handle_compact():
  global llm_model, chat_messages
  if len(chat_messages) < 2:
    return
  system_input_text = system_input.get("1.0", "end").strip()
  llm_model = model_input.get()
  disable_buttons()

  work_queue = queue.Queue()
  def worker_thread():
    if OPENAI_FAKE_RESPONSES == True:
      work_queue.put({
        "ok": True,
        "error": None,
        "completion": {
          "choices": [{ "message": { "content": OPENAI_FAKE_RESPONSE_MESSAGE, "reasoning": None } }],
          "usage": { "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0 }
        }
      })
      return
    try:
      completion = client.chat.completions.create(
        model=llm_model,
        messages=[
          { "role": "system", "content": system_input_text },
          *chat_messages,
          { "role": "system", "content": OPENAI_COMPACTION_INSTRUCTIONS },
        ],
        reasoning_effort="low",
        # max_completion_tokens=1000,
      )
      work_queue.put({"ok": True, "error": None, "completion": completion.model_dump()})
    except Exception as e:
      work_queue.put({"ok": False, "error": "Compaction error: " + str(e), "completion": None})

  def check_queue():
    try:
        work = work_queue.get_nowait()
    except queue.Empty:
        app.after(100, check_queue)
        return
    output.text.config(state="normal")
    if work["ok"]:
      completion = work["completion"]
      result = completion["choices"][0]["message"]["content"] or "None"
      chat_messages.clear()
      chat_messages.append({ "role": "system", "content": "Prior conversation summary:\n\n" + result })
      result += "\n\nTokens - Prompt: " + str(completion["usage"]["prompt_tokens"]) + ", Completion: " + str(completion["usage"]["completion_tokens"]) + ", Total: " + str(completion["usage"]["total_tokens"])
      result += "\nReasoning:\n" + (completion["choices"][0]["message"].get("reasoning") or "None")
      output.delete("1.0", "end")
      output.insert("end", "System prompt: " + system_input_text + "\nPrompt: " + OPENAI_COMPACTION_INSTRUCTIONS + "\nLLM: " + llm_model + "\n\n")
    else:
      result = "\n\nCompaction error: " + (work["error"] or "None") + "\n\n"
    output.insert("end", result)
    output.text.config(state="disabled")
    enable_buttons()

  threading.Thread(target=worker_thread, daemon=True).start()
  app.after(100, check_queue)

compact_button = ttk.Button(frame, text="Compact", bootstyle=PRIMARY, command=handle_compact)
compact_button.pack(side=LEFT, padx=5, pady=(0, 10))


def handle_clear():
  global chat_messages
  chat_messages.clear()
  output.text.config(state="normal")
  output.delete("1.0", "end")
  output.text.config(state="disabled")

clear_button = ttk.Button(frame, text="Clear", bootstyle=PRIMARY, command=handle_clear)
clear_button.pack(side=LEFT, padx=5, pady=(0, 10))

action_buttons = [send_button, compact_button, clear_button]

def disable_buttons():
  for button in action_buttons:
    button.config(state="disabled")

def enable_buttons():
  for button in action_buttons:
    button.config(state="normal")

def reverse_textbox_tab_behavior():
  def do_text_tab(event):
    event.widget.tk_focusNext().focus()
    return "break"
  app.bind_class("Text", "<Tab>", do_text_tab)

  def do_text_shift_tab(event):
    event.widget.tk_focusPrev().focus()
    return "break"
  app.bind_class("Text", "<Shift-Tab>", do_text_shift_tab)

  def do_text_ctrl_tab(event):
    event.widget.insert("insert", "\t")
    return "break"
  app.bind_class("Text", "<Control-Tab>", do_text_ctrl_tab)

reverse_textbox_tab_behavior()

app.mainloop()
