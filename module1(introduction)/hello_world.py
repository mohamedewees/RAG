import ollama

result = ollama.generate(model='qwen3:0.6b',prompt='Tell me a funny joke about python')

print(result['response'])