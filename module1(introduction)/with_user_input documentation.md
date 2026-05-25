# Ollama Python Chatbot Documentation

## Overview

This Python script implements a simple terminal-based AI chatbot using the Ollama Python library and the `qwen3:0.6b` language model.

The chatbot:

* Accepts user input from the terminal
* Sends messages to a local Ollama model
* Displays AI-generated responses
* Maintains conversation history for contextual memory
* Exits when the user types `exit`

---

# Source Code

```python
import ollama

messages = []

while True:
    user_input = input("You: ")

    if user_input.strip().lower() == ('exit'):
        break

    messages.append({
        'role':'user',
        'content': user_input
    })

    response = ollama.chat(
        model='qwen3:0.6b',
        messages=messages
    )

    print("Bot:", response['message']['content'])

    messages.append({
        'role':'assistant',
        'content': response['message']['content']
    })
```

---

# Prerequisites

## 1. Install Python

Install Python from the official website:

[https://www.python.org/downloads/](https://www.python.org/downloads/)

Verify installation:

```bash
python --version
```

---

## 2. Install Ollama

Install Ollama from:

[https://ollama.com/download](https://ollama.com/download)

Verify installation:

```bash
ollama --version
```

---

## 3. Download the Model

Pull the required model:

```bash
ollama run qwen3:0.6b
```

---

## 4. Install Ollama Python Library

```bash
pip install ollama
```

---

# Code Explanation

## Import Ollama Library

```python
import ollama
```

Imports the Ollama Python SDK used to communicate with the local Ollama server.

---

## Initialize Conversation History

```python
messages = []
```

Creates an empty list to store the full conversation history.

Each message is stored as a dictionary containing:

* `role`
* `content`

Example:

```python
{
    "role": "user",
    "content": "Hello"
}
```

---

## Start Infinite Chat Loop

```python
while True:
```

Creates a continuous loop allowing ongoing conversation until manually terminated.

---

## Capture User Input

```python
user_input = input("You: ")
```

Prompts the user to enter a message through the terminal.

Example:

```text
You: What is Kubernetes?
```

---

## Exit Condition

```python
if user_input.strip().lower() == ('exit'):
    break
```

Checks whether the user typed `exit`.

### Methods Used

| Method    | Purpose                         |
| --------- | ------------------------------- |
| `strip()` | Removes leading/trailing spaces |
| `lower()` | Converts text to lowercase      |

This allows:

* `exit`
* `EXIT`
* `Exit`

to all terminate the chatbot.

---

## Store User Message

```python
messages.append({
    'role':'user',
    'content': user_input
})
```

Adds the user's message to the conversation history.

Example:

```python
{
    "role": "user",
    "content": "Explain Docker"
}
```

---

## Send Request to Ollama

```python
response = ollama.chat(
    model='qwen3:0.6b',
    messages=messages
)
```

Sends the complete conversation history to the Ollama model.

### Parameters

| Parameter  | Description                |
| ---------- | -------------------------- |
| `model`    | Name of the local AI model |
| `messages` | Full conversation history  |

The model uses previous messages to maintain context-aware conversations.

---

## Print AI Response

```python
print("Bot:", response['message']['content'])
```

Extracts and displays the AI-generated response.

Example output:

```text
Bot: Docker is a containerization platform.
```

---

## Save Assistant Response

```python
messages.append({
    'role':'assistant',
    'content': response['message']['content']
})
```

Stores the assistant's reply into conversation memory.

This enables the model to remember previous responses and maintain conversational continuity.

---

# Conversation Flow Example

## User Input

```text
You: My name is Mohamed
```

Stored as:

```python
{
    "role": "user",
    "content": "My name is Mohamed"
}
```

---

## AI Response

```text
Bot: Nice to meet you Mohamed!
```

Stored as:

```python
{
    "role": "assistant",
    "content": "Nice to meet you Mohamed!"
}
```

---

## Next User Input

```text
You: What is my name?
```

Because the full conversation history is preserved, the model can respond correctly.

---

# Message Roles

The chatbot uses role-based messages.

| Role        | Meaning                                 |
| ----------- | --------------------------------------- |
| `user`      | Human input                             |
| `assistant` | AI-generated response                   |
| `system`    | Instructions controlling model behavior |

Example:

```python
{
    "role": "system",
    "content": "You are a DevOps expert assistant."
}
```

---

# Running the Script

Execute the script:

```bash
python chatbot.py
```

Example session:

```text
You: What is Python?
Bot: Python is a programming language.

You: What is Kubernetes?
Bot: Kubernetes is a container orchestration platform.

You: exit
```

---

# Possible Enhancements

Future improvements may include:

* Streaming responses
* Colored terminal output
* Chat history persistence
* Markdown rendering
* Voice interaction
* GUI/Web interface
* Multi-model support
* System prompts
* Error handling

---

# Example System Prompt Enhancement

```python
messages = [
    {
        "role": "system",
        "content": "You are a senior DevOps engineer."
    }
]
```

This globally changes the assistant behavior.

---

# Technologies Used

| Technology   | Purpose                   |
| ------------ | ------------------------- |
| Python       | Main programming language |
| Ollama       | Local AI runtime          |
| Qwen3        | Language model            |
| Terminal/CLI | User interaction          |

---

# Summary

This script demonstrates a basic conversational AI application using:

* Local LLM inference
* Conversational memory
* Role-based messaging
* Continuous user interaction

It provides a foundational architecture for building:

* AI assistants
* DevOps copilots
* Automation agents
* Local ChatGPT-style applications
* Terminal-based AI tools
