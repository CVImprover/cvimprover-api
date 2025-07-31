from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.middleware.csrf import get_token
from openai import OpenAI
import os
from django.views.decorators.http import require_GET


@ensure_csrf_cookie
def csrf_token_view(request):
    return JsonResponse({'csrfToken': get_token(request)})

# Simple function-based view for OpenAI test
@csrf_exempt
@require_GET
def test_openai(request):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    print("API Key in container:", os.getenv("OPENAI_API_KEY"))

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What's the capital of Italy?"}
            ]
        )
        return JsonResponse({
            "response": response.choices[0].message.content
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
