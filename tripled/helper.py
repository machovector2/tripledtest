from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import SecretaryAdmin


def admin_required(view_func):
    """
    Decorator that ensures only admin users (not secretaries) can access the view.
    This decorator should be used in combination with @login_required.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to access this page.')
            return redirect('signin')
        
        # Check if user is an admin (superuser or staff)
        if request.user.is_superuser or request.user.is_staff:
            # User is an admin - allow access
            return view_func(request, *args, **kwargs)
        
        # If not admin, check if they're a secretary and redirect appropriately
        try:
            secretary = SecretaryAdmin.objects.get(user=request.user)
            messages.error(request, 'Access denied. Admin privileges required.')
            return redirect('secretary_dashboard')
        except SecretaryAdmin.DoesNotExist:
            # User is neither admin nor secretary - redirect to login
            messages.error(request, 'Access denied. Please contact administrator.')
            return redirect('signin')
    
    return wrapper



def is_admin_user(user):
    """
    Helper function to determine if a user is an admin.
    You can customize this logic based on your specific requirements.
    """
    return user.is_superuser or user.is_staff


def admin_required_custom(view_func):
    """
    Alternative admin_required decorator using the helper function.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to access this page.')
            return redirect('signin')
        
        if is_admin_user(request.user):
            return view_func(request, *args, **kwargs)
        
        # Not an admin - check if secretary for appropriate redirect
        try:
            secretary = SecretaryAdmin.objects.get(user=request.user)
            messages.error(request, 'Access denied. Admin privileges required.')
            return redirect('secretary_dashboard')
        except SecretaryAdmin.DoesNotExist:
            messages.error(request, 'Access denied. Please contact administrator.')
            return redirect('signin')
    
    return wrapper


def admin_or_secretary_required(view_func):
    """
    Decorator that allows both admin and secretary access.
    Use this for views that both user types should be able to access.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to access this page.')
            return redirect('signin')
        
        # Check if user is a secretary and if they're active
        try:
            secretary = SecretaryAdmin.objects.get(user=request.user)
            if not secretary.is_active:
                messages.error(request, 'Your secretary account is inactive.')
                return redirect('signin')
        except SecretaryAdmin.DoesNotExist:
            # User is not a secretary (they're an admin), which is fine
            pass
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def secretary_required(view_func):
    """
    Decorator that ensures only secretary users can access the view.
    Useful for secretary-specific views.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to access this page.')
            return redirect('signin')
        
        try:
            secretary = SecretaryAdmin.objects.get(user=request.user)
            if not secretary.is_active:
                messages.error(request, 'Your secretary account is inactive.')
                return redirect('signin')
            # Secretary exists and is active - allow access
        except SecretaryAdmin.DoesNotExist:
            # User is not a secretary - deny access
            messages.error(request, 'Access denied. Secretary privileges required.')
            return redirect('user')  # Redirect to admin dashboard
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

# Helper function to check if user is secretary
def is_secretary(user):
    """Check if user is a secretary admin"""
    try:
        secretary = SecretaryAdmin.objects.get(user=user)
        return secretary.is_active
    except SecretaryAdmin.DoesNotExist:
        return False

