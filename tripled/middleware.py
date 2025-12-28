from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from .helper import is_secretary

class RoleDiscoveryMiddleware:
    """
    Middleware to identify user roles and attach flags to the request object
    for easier template logic and security enforcement.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Default flags
        request.is_secretary = False
        request.is_accountant = False
        request.is_chief_admin = False

        if request.user.is_authenticated:
            # Check for secretary status using helper
            request.is_secretary = is_secretary(request.user)
            
            # Check for accounting roles
            request.is_accountant = request.user.user_type in ['chief_accountant', 'branch_admin']
            
            # Check for chief admin roles
            request.is_chief_admin = request.user.is_superuser or request.user.user_type == 'admin'

        response = self.get_response(request)
        return response


class PortalSecurityMiddleware:
    """
    Enforces bidirectional isolation between the Secretary Dashboard 
    and the Admin/Realtor Portal.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        path = request.path

        # 1. Protect Secretary Dashboard from non-secretaries
        if path.startswith(reverse('secretary_dashboard')):
            if not request.is_secretary and not request.user.is_superuser:
                messages.error(request, "Access Denied. This dashboard is for Secretaries only.")
                if request.is_accountant:
                    return redirect('accounting:dashboard')
                return redirect('user')

        # 2. Protect Admin Portal Dashboard from Secretaries (who aren't also admins)
        # Note: We only block the main dashboard redirect to keep them in their lanes.
        # Sub-pages are handled by their respective decorators (admin_required).
        if path == reverse('user') and request.is_secretary and not request.is_chief_admin:
            return redirect('secretary_dashboard')

        return self.get_response(request)
