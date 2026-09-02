from django.shortcuts import render


def home_view(request):
    """
    Display the public home page.
    """
    return render(request, "home.html")


def about_view(request):
    """
    Display the about page.
    """
    return render(request, "about.html")


def contact_view(request):
    """
    Display the contact page.
    """
    return render(request, "contact.html")


def faq_view(request):
    """
    Display the frequently asked questions page.
    """
    return render(request, "faq.html")


def error_404_view(request, exception):
    """
    Custom 404 error page.
    """
    return render(request, "error_404.html", status=404)