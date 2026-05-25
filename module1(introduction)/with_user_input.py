import ollama

messages = []

while True:
    user_input = input("You: ")
    if user_input.strip().lower() == ('exit'):   # strip() removes spaces and lower() convert the text to lowercase
        break
    messages.append({'role':'user','content': user_input})  # role tells the AI who is writing this question (user means a human user, the the model understand it is a human user question and will answer as assistant)
    response = ollama.chat(model= 'qwen3:0.6b',messages=messages)
    print("Bot:", response['message']['content'])   #Extracts ONLY the generated text.
    messages.append({'role':'assistant', 'content': response['message']['content']})    

""" This is VERY important.

It stores the AI answer so future prompts include it.

Without this:

- the AI remembers only user messages
- conversation quality becomes weird  """

"""
| Role        | Meaning                      |
| ----------- | ---------------------------- |
| `user`      | Human message                |
| `assistant` | AI response                  |
| `system`    | Instructions for AI behavior |

"""
