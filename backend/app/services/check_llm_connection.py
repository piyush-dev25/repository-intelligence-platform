from app.services.llm_service import llm_service

response = llm_service.generate("Say hello in exactly 5 words.")
print(response)