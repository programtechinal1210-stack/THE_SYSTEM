"""UDE-04 isolated component and accessibility lab."""
from django.shortcuts import render


def page(request):
    # Deliberately uses demo data only; no Core read/write and no production shell.
    return render(request, "core/ude_04_lab.html", {"ude_demo": {
        "theme": "light", "density": "comfortable", "fontSize": 16,
        "fontFamily": "Tajawal", "contrast": "normal"
    }})
