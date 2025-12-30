from .models import General

def general_settings(request):
    """
    Return the General settings object to the template context.
    Ensures 'general_settings' variable is available in all templates.
    """
    try:
        # Get the first (and only) General object, or None if it doesn't exist
        general = General.objects.first()
        return {'general_settings': general}
    except Exception:
        # Fail gracefully if database is not ready or other error
        return {'general_settings': None}
