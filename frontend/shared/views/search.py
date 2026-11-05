from django.http import JsonResponse


def search(request):
    return JsonResponse({
        "items": [],
        "query": request.GET.get("q", ""),
        "message": "البحث العام سيُضاف لاحقاً ضمن النواة."
    })